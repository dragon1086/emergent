#!/usr/bin/env python3
"""
emergent_selector.py — prism-insight 창발 종목 선정 엔진 (사이클 66)

D-060 기반 구현:
  source_A = 매크로 관점 (환율/글로벌/섹터)
  source_B = 기술 관점 (OHLCV/볼린저/거래량)
  cross_source_edge = 두 관점이 같은 종목을 다른 이유로 지목
  CSER_stock = cross_source_signals / total_signals
  conviction = CSER_component × macro_strength × technical_strength

설계 원칙 (D-033 이식):
  - 한 관점만 지목한 종목은 에코 챔버. 두 관점이 독립적으로 지목해야 창발.
  - CSER_component가 0이면 conviction = 0 (단일 관점 신호는 자동 탈락)
  - 신호 볼륨 보정: log1p 스케일링으로 소수 신호 과대평가 방지

D-060 conviction 공식 약점 (cokac 분석):
  원래: conviction = CSER_component × macro_strength × technical_strength
  약점:
    1. 순수 곱셈 → 한 요소 근제로 시 전체 붕괴 (임계 보정 필요)
    2. CSER_component 볼륨 무시 (1+1=100%, 50+50=100% 동일 취급)
    3. 신호 신선도(recency) 미반영
    4. 섹터 군집 보정 없음 → 동일 섹터 종목들이 의사 독립적으로 묶임
  수정:
    - CSER_component에 signal_volume 보정 (log1p)
    - 각 요소에 min_floor=0.1 추가 (완전 붕괴 방지)
    - recency_weight: 최신 신호 우대
    - 최종: conviction_v2 출력 (원래 공식 + 보정값 병기)

사용법:
  python3 src/emergent_selector.py                           # 기본 demo 실행
  python3 src/emergent_selector.py --demo                    # demo 신호 생성 + 선정
  python3 src/emergent_selector.py --json                    # JSON 출력
  python3 src/emergent_selector.py --top 10                  # 상위 10개
  python3 src/emergent_selector.py --min-conviction 0.1      # 최소 conviction 필터

구현: cokac-bot (사이클 66)
"""

import json
import math
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime


# ─── 데이터 구조 ──────────────────────────────────────────────────────────────

@dataclass
class MacroSignal:
    """매크로 관점 신호 (source_A)"""
    ticker: str
    signal_type: str          # "환율", "글로벌", "섹터", "금리", "원자재"
    direction: str            # "bullish", "bearish", "neutral"
    strength: float           # 0.0~1.0
    reason: str               # 신호 근거 (텍스트)
    timestamp: Optional[str] = None
    weight: float = 1.0       # 신호 가중치 (선택)


@dataclass
class TechnicalSignal:
    """기술 관점 신호 (source_B)"""
    ticker: str
    signal_type: str          # "OHLCV", "볼린저", "거래량", "RSI", "MACD", "이평선"
    direction: str            # "bullish", "bearish", "neutral"
    strength: float           # 0.0~1.0
    reason: str               # 신호 근거
    timestamp: Optional[str] = None
    weight: float = 1.0


@dataclass
class ConvictionResult:
    """종목별 conviction 계산 결과"""
    ticker: str
    macro_count: int
    technical_count: int
    total_signals: int
    cross_source_count: int        # 교차출처 신호 쌍 수
    cser_raw: float                # cross_source_count / total_signals (원래)
    cser_volume_adjusted: float    # log1p 볼륨 보정 CSER
    macro_strength: float          # 매크로 신호 강도 평균
    technical_strength: float      # 기술 신호 강도 평균
    conviction_v1: float           # 원래 D-060 공식
    conviction_v2: float           # 보정 공식 (권장)
    direction: str                 # 전체 방향 (bullish/bearish/mixed)
    top_macro_reason: str          # 가장 강한 매크로 근거
    top_technical_reason: str      # 가장 강한 기술 근거
    signal_freshness: float        # 신호 신선도 (0~1, 최근일수록 높음)
    sector_cluster_penalty: float  # 섹터 군집 페널티 (0~1)
    final_score: float             # 최종 선정 점수


# ─── 핵심 계산 ────────────────────────────────────────────────────────────────

MIN_FLOOR = 0.10          # conviction 붕괴 방지 하한
SECTOR_PENALTY_THRESHOLD = 3  # 동일 섹터 내 이 수 이상이면 페널티


def compute_cser_volume_adjusted(macro_count: int, technical_count: int) -> float:
    """
    볼륨 보정 CSER:
    - 1매크로+1기술 = 2신호 → raw CSER = 100%
    - 5매크로+5기술 = 10신호 → raw CSER = 100%
    - 두 경우를 동일 취급하는 것이 D-060 약점 #2

    보정: min(macro, technical) / (log1p(total) + 1)
    신호 수가 많을수록 보정값도 높아지지만, 단순 비율만큼 빠르지 않음.
    """
    if macro_count == 0 or technical_count == 0:
        return 0.0
    # 교차 신호: min(두 관점의 신호 수) = 실제 "검증된" 쌍
    effective_cross = min(macro_count, technical_count)
    # 볼륨 보정 계수: 신호가 많을수록 신뢰도 증가 (log scale)
    volume_factor = math.log1p(effective_cross) / math.log1p(10)  # 10개 기준 정규화
    # raw CSER (교차 여부 자체) × 볼륨 보정
    raw_cser = 1.0 if (macro_count > 0 and technical_count > 0) else 0.0
    return round(min(1.0, raw_cser * (0.5 + 0.5 * volume_factor)), 4)


def compute_direction(signals: list) -> str:
    """신호 방향 집계 (bullish/bearish/mixed)"""
    if not signals:
        return "neutral"
    bulls = sum(1 for s in signals if s.direction == "bullish")
    bears = sum(1 for s in signals if s.direction == "bearish")
    if bulls > bears * 1.5:
        return "bullish"
    elif bears > bulls * 1.5:
        return "bearish"
    return "mixed"


def compute_strength(signals: list) -> float:
    """가중 평균 신호 강도"""
    if not signals:
        return 0.0
    total_w = sum(s.weight for s in signals)
    if total_w == 0:
        return 0.0
    weighted = sum(s.strength * s.weight for s in signals)
    return round(weighted / total_w, 4)


def compute_signal_freshness(signals: list) -> float:
    """
    신호 신선도 계산.
    timestamp 없으면 기본값 0.7 반환 (중립).
    있으면 가장 최근 신호 기준으로 0~1 반환.
    """
    ts_signals = [s for s in signals if s.timestamp]
    if not ts_signals:
        return 0.7  # 타임스탬프 없으면 중립
    try:
        now = datetime.now()
        ages = []
        for s in ts_signals:
            dt = datetime.fromisoformat(s.timestamp)
            age_hours = (now - dt).total_seconds() / 3600
            ages.append(age_hours)
        min_age = min(ages)
        # 6시간 이내 = 1.0, 24시간 = 0.7, 72시간 = 0.3
        freshness = math.exp(-min_age / 48)
        return round(min(1.0, max(0.0, freshness)), 4)
    except Exception:
        return 0.7


# ─── 핵심 공식 ────────────────────────────────────────────────────────────────

def compute_conviction_v1(cser_raw: float, macro_strength: float,
                           technical_strength: float) -> float:
    """D-060 원래 공식 (약점 포함, 비교용)"""
    return round(cser_raw * macro_strength * technical_strength, 4)


def compute_conviction_v2(cser_vol: float, macro_strength: float,
                           technical_strength: float,
                           freshness: float = 0.7,
                           cluster_penalty: float = 0.0) -> float:
    """
    D-060 보정 공식 (사이클 66):
    conviction_v2 = CSER_vol × max(macro, floor) × max(tech, floor) × freshness × (1 - penalty)

    약점 수정:
    - min_floor 적용으로 붕괴 방지
    - 볼륨 보정 CSER 사용
    - 신선도 반영
    - 섹터 군집 페널티
    """
    m = max(macro_strength, MIN_FLOOR)
    t = max(technical_strength, MIN_FLOOR)
    raw = cser_vol * m * t * freshness
    final = raw * (1.0 - cluster_penalty)
    return round(max(0.0, final), 4)


# ─── 선정 엔진 ────────────────────────────────────────────────────────────────

def select_emergent_stocks(
    macro_signals: list,
    technical_signals: list,
    top_n: int = 10,
    min_conviction: float = 0.05,
    direction_filter: Optional[str] = None,  # "bullish" | "bearish" | None
) -> list:
    """
    창발 종목 선정 메인 함수.

    Args:
        macro_signals:     MacroSignal 객체 리스트
        technical_signals: TechnicalSignal 객체 리스트
        top_n:             상위 N개 반환
        min_conviction:    최소 conviction_v2 필터
        direction_filter:  방향 필터 (None이면 전체)

    Returns:
        ConvictionResult 리스트 (conviction_v2 기준 내림차순)

    D-033 적용: CSER_vol = 0인 종목(단일 관점만)은 자동 탈락.
    """
    # 종목별 신호 그룹화
    macro_by_ticker: dict[str, list] = {}
    technical_by_ticker: dict[str, list] = {}

    for sig in macro_signals:
        macro_by_ticker.setdefault(sig.ticker, []).append(sig)
    for sig in technical_signals:
        technical_by_ticker.setdefault(sig.ticker, []).append(sig)

    # 양쪽 관점 모두 있는 종목만 후보
    all_tickers = set(macro_by_ticker) | set(technical_by_ticker)

    # 섹터 군집 분석 (페널티 계산용)
    sector_counts: dict[str, int] = {}
    for sig in macro_signals:
        sector = sig.signal_type
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    results = []
    for ticker in all_tickers:
        m_sigs = macro_by_ticker.get(ticker, [])
        t_sigs = technical_by_ticker.get(ticker, [])

        macro_count = len(m_sigs)
        technical_count = len(t_sigs)
        total_signals = macro_count + technical_count

        # D-033: 한 관점만 있으면 cross_source = 0 → conviction = 0 → 탈락
        cser_raw = 1.0 if (macro_count > 0 and technical_count > 0) else 0.0
        cser_vol = compute_cser_volume_adjusted(macro_count, technical_count)

        # 강도 계산
        macro_str = compute_strength(m_sigs)
        tech_str = compute_strength(t_sigs)

        # 방향
        all_sigs = m_sigs + t_sigs
        direction = compute_direction(all_sigs)

        # 신선도
        freshness = compute_signal_freshness(all_sigs)

        # 섹터 페널티: 동일 섹터 유형 신호가 많을수록 페널티
        top_sector = max(sector_counts, key=sector_counts.get) if sector_counts else ""
        ticker_sectors = {s.signal_type for s in m_sigs}
        if top_sector in ticker_sectors and sector_counts.get(top_sector, 0) >= SECTOR_PENALTY_THRESHOLD:
            cluster_penalty = min(0.3, 0.1 * sector_counts[top_sector])
        else:
            cluster_penalty = 0.0

        # conviction 계산
        v1 = compute_conviction_v1(cser_raw, macro_str, tech_str)
        v2 = compute_conviction_v2(cser_vol, macro_str, tech_str, freshness, cluster_penalty)

        # 최종 점수 = conviction_v2 (방향 가중 없음, 투명하게)
        final_score = v2

        # 방향 필터
        if direction_filter and direction != direction_filter:
            continue

        # 최소 conviction 필터
        if final_score < min_conviction:
            continue

        # 근거 요약
        top_m = max(m_sigs, key=lambda s: s.strength, default=None)
        top_t = max(t_sigs, key=lambda s: s.strength, default=None)

        results.append(ConvictionResult(
            ticker=ticker,
            macro_count=macro_count,
            technical_count=technical_count,
            total_signals=total_signals,
            cross_source_count=min(macro_count, technical_count),
            cser_raw=round(cser_raw, 4),
            cser_volume_adjusted=cser_vol,
            macro_strength=macro_str,
            technical_strength=tech_str,
            conviction_v1=v1,
            conviction_v2=v2,
            direction=direction,
            top_macro_reason=top_m.reason if top_m else "",
            top_technical_reason=top_t.reason if top_t else "",
            signal_freshness=freshness,
            sector_cluster_penalty=round(cluster_penalty, 4),
            final_score=final_score,
        ))

    # 내림차순 정렬
    results.sort(key=lambda r: -r.final_score)
    return results[:top_n]


# ─── D-060 약점 분석 리포트 ──────────────────────────────────────────────────

def analyze_conviction_formula(results: list) -> dict:
    """
    D-060 conviction 공식 v1 vs v2 비교 분석.
    약점이 실제로 얼마나 영향을 주는지 정량화.
    """
    if not results:
        return {}

    v1_scores = [r.conviction_v1 for r in results]
    v2_scores = [r.conviction_v2 for r in results]
    deltas = [v2 - v1 for v1, v2 in zip(v1_scores, v2_scores)]

    # CSER 볼륨 왜곡 감지: v1과 v2 순위 역전 케이스
    v1_ranked = sorted(results, key=lambda r: -r.conviction_v1)
    v2_ranked = sorted(results, key=lambda r: -r.conviction_v2)
    rank_inversions = sum(
        1 for i, (r1, r2) in enumerate(zip(v1_ranked, v2_ranked))
        if r1.ticker != r2.ticker
    )

    return {
        "total_candidates": len(results),
        "v1_mean": round(sum(v1_scores) / len(v1_scores), 4),
        "v2_mean": round(sum(v2_scores) / len(v2_scores), 4),
        "delta_mean": round(sum(deltas) / len(deltas), 4),
        "rank_inversions": rank_inversions,
        "formula_divergence_pct": round(abs(sum(deltas) / len(deltas)) * 100, 1),
        "weakness_summary": {
            "volume_bias": "cser_raw가 신호 수 무관 100% 고정 — 볼륨 보정 필수",
            "collapse_risk": f"min_floor={MIN_FLOOR} 적용으로 0 붕괴 방지",
            "freshness": "타임스탬프 있으면 신선도 가중 적용",
            "sector_cluster": f"동일섹터 신호 {SECTOR_PENALTY_THRESHOLD}개+ 시 페널티",
        }
    }


# ─── CLI / 데모 ───────────────────────────────────────────────────────────────

def generate_demo_signals():
    """
    데모 신호 생성 (실제 prism-insight 데이터 대신 시뮬레이션).
    D-060 기반 매크로 + 기술 신호 구조.
    """
    ts_now = datetime.now().isoformat()

    macro = [
        MacroSignal("005930", "글로벌", "bullish", 0.85, "미-중 반도체 수출 규제 완화 기대", ts_now),
        MacroSignal("005930", "환율", "bullish", 0.70, "원화 강세 전환 → 반도체 수출 가격 경쟁력", ts_now),
        MacroSignal("000660", "섹터", "bullish", 0.78, "AI 인프라 투자 사이클 상단 → HBM 수요 급증", ts_now),
        MacroSignal("035420", "글로벌", "bearish", 0.60, "글로벌 디지털 광고 시장 위축 신호", ts_now),
        MacroSignal("068270", "섹터", "bullish", 0.90, "바이오시밀러 FDA 승인 사이클 진입", ts_now),
        MacroSignal("068270", "글로벌", "bullish", 0.75, "미 약가인하 법안 우려 완화"),
        MacroSignal("051910", "환율", "bearish", 0.65, "달러 강세 지속 시 소재 수입 원가 상승"),
        MacroSignal("051910", "섹터", "neutral", 0.40, "배터리 소재 섹터 보합"),
        MacroSignal("247540", "섹터", "bullish", 0.80, "2차전지 섹터 반등 기대"),
    ]

    technical = [
        TechnicalSignal("005930", "볼린저", "bullish", 0.88, "BB 하단 이탈 후 V자 반등, 밴드폭 확대", ts_now),
        TechnicalSignal("005930", "거래량", "bullish", 0.80, "거래량 이평 대비 3배 급증 (기관 매수)", ts_now),
        TechnicalSignal("000660", "MACD", "bullish", 0.72, "MACD 골든크로스 + 히스토그램 양전환", ts_now),
        TechnicalSignal("000660", "OHLCV", "bullish", 0.65, "4일 연속 양봉, 종가 52주 고점 근접"),
        TechnicalSignal("035420", "RSI", "bearish", 0.70, "RSI 28 과매도 진입 — 단기 반등 가능성"),
        TechnicalSignal("068270", "볼린저", "bullish", 0.92, "BB 상단 돌파 + 급등 캔들 (강한 모멘텀)"),
        TechnicalSignal("051910", "이평선", "bearish", 0.58, "5일선 아래 주가 + 20일선 데드크로스"),
        TechnicalSignal("247540", "거래량", "bullish", 0.85, "거래량 폭발 + 상한가 근접"),
        TechnicalSignal("247540", "볼린저", "bullish", 0.78, "BB 상단 연속 돌파"),
        # 매크로만 있는 종목 (탈락 테스트용)
        TechnicalSignal("999999", "OHLCV", "bullish", 0.90, "강한 기술 신호 — 그러나 매크로 없음"),
    ]

    return macro, technical


def print_results(results: list, show_formula_analysis: bool = True) -> None:
    analysis = analyze_conviction_formula(results)

    print("═══ emergent_selector — 창발 종목 선정 (D-060 구현, 사이클 66) ═══")
    print()
    print(f"conviction 공식:")
    print(f"  v1 (D-060 원래): CSER × macro_strength × technical_strength")
    print(f"  v2 (보정):       CSER_vol × max(macro,{MIN_FLOOR}) × max(tech,{MIN_FLOOR}) × freshness × (1-penalty)")
    print()

    if not results:
        print("  선정된 종목 없음 (min_conviction 조건 미달)")
        return

    print(f"══ 선정 결과: {len(results)}종목 ══")
    print()
    for i, r in enumerate(results, 1):
        dir_emoji = "📈" if r.direction == "bullish" else "📉" if r.direction == "bearish" else "↔️"
        print(f"  [{i:>2}] {r.ticker}  {dir_emoji}  conviction_v2={r.final_score:.4f}")
        print(f"       신호: 매크로 {r.macro_count}개 / 기술 {r.technical_count}개")
        print(f"       CSER_raw={r.cser_raw:.2f}  CSER_vol={r.cser_volume_adjusted:.4f}")
        print(f"       macro_str={r.macro_strength:.3f}  tech_str={r.technical_strength:.3f}")
        print(f"       freshness={r.signal_freshness:.3f}  cluster_penalty={r.sector_cluster_penalty:.3f}")
        print(f"       v1={r.conviction_v1:.4f}  v2={r.final_score:.4f}  (Δ{r.final_score-r.conviction_v1:+.4f})")
        print(f"       매크로: \"{r.top_macro_reason[:60]}\"")
        print(f"       기술:   \"{r.top_technical_reason[:60]}\"")
        print()

    if show_formula_analysis and analysis:
        print("══ D-060 공식 약점 분석 ══")
        print(f"  총 후보: {analysis['total_candidates']}개")
        print(f"  v1 평균: {analysis['v1_mean']:.4f}  v2 평균: {analysis['v2_mean']:.4f}")
        print(f"  수식 발산: {analysis['formula_divergence_pct']:.1f}%")
        print(f"  순위 역전: {analysis['rank_inversions']}건")
        print()
        for k, v in analysis['weakness_summary'].items():
            print(f"  [{k}] {v}")


def main():
    args = sys.argv[1:]
    top_n = 10
    min_conv = 0.05
    as_json = "--json" in args
    direction = None

    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            try:
                top_n = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--min-conviction" and i + 1 < len(args):
            try:
                min_conv = float(args[i + 1])
            except ValueError:
                pass
        if arg == "--direction" and i + 1 < len(args):
            direction = args[i + 1]

    macro, technical = generate_demo_signals()
    results = select_emergent_stocks(
        macro, technical,
        top_n=top_n,
        min_conviction=min_conv,
        direction_filter=direction,
    )

    if as_json:
        output = [asdict(r) for r in results]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    print_results(results)


if __name__ == "__main__":
    main()
