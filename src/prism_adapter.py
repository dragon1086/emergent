#!/usr/bin/env python3
"""
prism_adapter.py — trigger_batch.py → emergent_selector.py 연결 어댑터 (사이클 68)

trigger_batch.py (prism-insight) 출력 구조:
  morning_results = {
    "volume_surge":       DataFrame (ticker, score, sector, ...),
    "gap_up_momentum":    DataFrame (ticker, score, sector, ...),
    "value_to_cap_ratio": DataFrame (ticker, score, sector, ...),
  }
  macro_context = {
    "usd_krw":      float,
    "us_futures":   "bullish" | "bearish",
    "hot_sectors":  list[str],    # e.g. ["반도체", "바이오"]
    "cold_sectors": list[str],    # e.g. ["건설", "유통"]
  }

변환 규칙 (D-061 기반):
  - volume_surge → TechnicalSignal(signal_type="거래량")
  - gap_up_momentum → TechnicalSignal(signal_type="OHLCV")
  - value_to_cap_ratio → TechnicalSignal(signal_type="이평선")  ← 저평가 모멘텀
  - hot_sectors → MacroSignal bullish (strength=0.8)
  - cold_sectors → MacroSignal bearish (strength=0.7)
  - usd_krw > 1400 → 수출 섹터 MacroSignal bullish (strength=0.75)
  - us_futures == "bullish" → 전체 MacroSignal 가중치 +10%

수출 섹터 기준 (D-061): 반도체, 자동차, 화학, 조선, 기계, 철강
  → 달러 강세(usd_krw > 1400)는 수출 기업 실적에 직접 긍정 작용

구현: cokac-bot (사이클 68)
"""

import math
import sys
from datetime import datetime
from typing import Optional

# emergent_selector는 src/ 안에 있으므로 같은 디렉토리에서 직접 임포트
try:
    from emergent_selector import MacroSignal, TechnicalSignal, select_emergent_stocks, ConvictionResult
except ImportError:
    # 외부에서 호출할 때 경로 보정
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from emergent_selector import MacroSignal, TechnicalSignal, select_emergent_stocks, ConvictionResult


# ─── 수출 섹터 정의 (D-061 기준) ─────────────────────────────────────────────

EXPORT_SECTORS = {"반도체", "자동차", "화학", "조선", "기계", "철강", "IT하드웨어"}

# USD/KRW 수출 우호 임계값
USD_KRW_EXPORT_THRESHOLD = 1400.0


# ─── 스코어 정규화 ─────────────────────────────────────────────────────────────

def normalize_scores(series) -> "Series":
    """
    DataFrame 컬럼 스코어를 [0.1, 1.0]으로 min-max 정규화.
    min_floor=0.1 → 최하위 종목도 최소 신호 유지 (D-062 MIN_FLOOR 일관성).
    """
    try:
        import pandas as pd
        s = pd.to_numeric(series, errors="coerce").fillna(0.0)
        s_min, s_max = s.min(), s.max()
        if s_max == s_min:
            return s.map(lambda _: 0.5)
        normalized = (s - s_min) / (s_max - s_min)
        # [0.1, 1.0] 범위로 스케일
        return 0.1 + normalized * 0.9
    except Exception:
        return series


def _get_ticker_col(df) -> str:
    """DataFrame에서 ticker 컬럼명을 추론한다."""
    for candidate in ["ticker", "종목코드", "code", "symbol", "Ticker"]:
        if candidate in df.columns:
            return candidate
    # index가 ticker인 경우
    return None


def _get_score_col(df) -> str:
    """DataFrame에서 score 컬럼명을 추론한다."""
    for candidate in ["score", "값", "value", "signal_score", "strength", "Score"]:
        if candidate in df.columns:
            return candidate
    # 수치형 컬럼 중 첫 번째
    try:
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        return numeric_cols[0] if numeric_cols else None
    except Exception:
        return None


def _get_sector_col(df) -> Optional[str]:
    """DataFrame에서 sector 컬럼명을 추론한다 (없으면 None)."""
    for candidate in ["sector", "섹터", "industry", "업종"]:
        if candidate in df.columns:
            return candidate
    return None


# ─── 핵심 변환 함수 ────────────────────────────────────────────────────────────

def _df_to_technical_signals(
    df,
    signal_type: str,
    reason_template: str,
    direction: str = "bullish",
    timestamp: Optional[str] = None,
) -> list:
    """
    trigger_batch DataFrame 한 종류를 TechnicalSignal 리스트로 변환.

    Args:
        df:              trigger_batch 출력 DataFrame
        signal_type:     "거래량" | "OHLCV" | "이평선" 등
        reason_template: 신호 근거 텍스트 템플릿 (ticker placeholder 없음)
        direction:       신호 방향 (기본값: "bullish" — trigger_batch는 매수 신호 위주)
        timestamp:       ISO 타임스탬프 (없으면 현재 시각)
    """
    if df is None or len(df) == 0:
        return []

    ts = timestamp or datetime.now().isoformat()
    signals = []

    ticker_col = _get_ticker_col(df)
    score_col = _get_score_col(df)

    if score_col is None:
        return []

    # 스코어 정규화
    df = df.copy()
    df["_norm_strength"] = normalize_scores(df[score_col])

    for _, row in df.iterrows():
        # ticker 추출
        if ticker_col:
            ticker = str(row[ticker_col])
        else:
            ticker = str(row.name)  # index를 ticker로 사용

        strength = float(row["_norm_strength"])

        signals.append(TechnicalSignal(
            ticker=ticker,
            signal_type=signal_type,
            direction=direction,
            strength=round(strength, 4),
            reason=reason_template,
            timestamp=ts,
            weight=1.0,
        ))

    return signals


def _make_sector_macro_signals(
    df_tickers: set,
    sector_col_data: dict,  # {ticker: sector}
    hot_sectors: list,
    cold_sectors: list,
    timestamp: str,
    us_futures_boost: float = 1.0,
) -> list:
    """
    섹터 정보를 바탕으로 MacroSignal 생성.
    hot/cold 섹터 소속 여부로 방향과 강도를 결정.
    """
    signals = []

    for ticker in df_tickers:
        sector = sector_col_data.get(ticker, "")

        # hot 섹터 소속
        if sector and any(h.lower() in sector.lower() or sector.lower() in h.lower()
                          for h in hot_sectors):
            signals.append(MacroSignal(
                ticker=ticker,
                signal_type="섹터",
                direction="bullish",
                strength=round(min(1.0, 0.8 * us_futures_boost), 4),
                reason=f"hot 섹터({sector}) 포함 — 매크로 순풍",
                timestamp=timestamp,
                weight=1.2,  # 섹터 신호는 가중치 높임
            ))

        # cold 섹터 소속
        elif sector and any(c.lower() in sector.lower() or sector.lower() in c.lower()
                            for c in cold_sectors):
            signals.append(MacroSignal(
                ticker=ticker,
                signal_type="섹터",
                direction="bearish",
                strength=round(min(1.0, 0.7 * us_futures_boost), 4),
                reason=f"cold 섹터({sector}) 포함 — 매크로 역풍",
                timestamp=timestamp,
                weight=0.9,
            ))

    return signals


def _make_export_macro_signals(
    df_tickers: set,
    sector_col_data: dict,  # {ticker: sector}
    usd_krw: float,
    timestamp: str,
) -> list:
    """
    usd_krw > 1400 시: 수출 섹터 종목에 MacroSignal bullish 추가.

    D-061: 달러 강세는 반도체·자동차·화학·조선·기계·철강 섹터에 직접적 환차익 효과.
    """
    if usd_krw <= USD_KRW_EXPORT_THRESHOLD:
        return []

    signals = []
    excess_ratio = (usd_krw - USD_KRW_EXPORT_THRESHOLD) / USD_KRW_EXPORT_THRESHOLD
    # 1400원 초과분에 비례하여 strength 보정 (최대 0.95)
    base_strength = min(0.95, 0.75 + excess_ratio * 2)

    for ticker in df_tickers:
        sector = sector_col_data.get(ticker, "")
        is_export = any(exp.lower() in sector.lower() or sector.lower() in exp.lower()
                        for exp in EXPORT_SECTORS) if sector else False

        if is_export:
            signals.append(MacroSignal(
                ticker=ticker,
                signal_type="환율",
                direction="bullish",
                strength=round(base_strength, 4),
                reason=f"USD/KRW={usd_krw:.0f} (>{USD_KRW_EXPORT_THRESHOLD:.0f}) → {sector} 수출 환차익",
                timestamp=timestamp,
                weight=1.1,
            ))

    return signals


def _make_global_macro_signals(
    df_tickers: set,
    us_futures: str,
    timestamp: str,
) -> list:
    """
    us_futures 방향으로 전체 종목에 글로벌 매크로 신호 추가.
    단독으로는 약하게 (strength 0.5~0.6), 다른 신호와 결합 시 창발 효과.
    """
    if us_futures not in ("bullish", "bearish"):
        return []

    direction = us_futures
    strength = 0.55 if direction == "bullish" else 0.50
    reason = (
        "미 선물 강세 → 위험선호 심리 유입" if direction == "bullish"
        else "미 선물 약세 → 위험회피 심리 → 외국인 매도 우려"
    )

    return [
        MacroSignal(
            ticker=ticker,
            signal_type="글로벌",
            direction=direction,
            strength=strength,
            reason=reason,
            timestamp=timestamp,
            weight=0.8,  # 글로벌 신호는 가중치 낮게 — 개별 섹터·환율 신호가 우선
        )
        for ticker in df_tickers
    ]


# ─── 메인 어댑터 ──────────────────────────────────────────────────────────────

def adapt_trigger_batch(
    morning_results: dict,
    macro_context: dict,
    top_n: int = 10,
    min_conviction: float = 0.05,
    direction_filter: Optional[str] = None,
) -> list:
    """
    trigger_batch.py 결과 → emergent_selector 입력 변환 → ConvictionResult 리스트 반환.

    Args:
        morning_results: {
            "volume_surge":       DataFrame,
            "gap_up_momentum":    DataFrame,
            "value_to_cap_ratio": DataFrame,
        }
        macro_context: {
            "usd_krw":      float,
            "us_futures":   "bullish" | "bearish",
            "hot_sectors":  list[str],
            "cold_sectors": list[str],
        }
        top_n:             상위 N개 반환 (기본 10)
        min_conviction:    최소 conviction_v2 필터 (기본 0.05)
        direction_filter:  방향 필터 ("bullish" | "bearish" | None)

    Returns:
        ConvictionResult 리스트 (conviction_v2 기준 내림차순)

    D-033 적용: 매크로+기술 양쪽 신호 없으면 자동 탈락 (단일 관점 종목 제외).
    D-062 적용: conviction_v2 공식 (min_floor + 볼륨보정 + freshness).
    """
    ts = datetime.now().isoformat()

    # ── 1. macro_context 파싱 ─────────────────────────────────────────────────
    usd_krw = float(macro_context.get("usd_krw", 1300.0))
    us_futures = macro_context.get("us_futures", "neutral")
    hot_sectors = macro_context.get("hot_sectors", [])
    cold_sectors = macro_context.get("cold_sectors", [])

    # us_futures bullish → 전체 매크로 신호 강도 10% 부스트
    us_futures_boost = 1.10 if us_futures == "bullish" else (0.95 if us_futures == "bearish" else 1.0)

    # ── 2. TechnicalSignal 변환 ───────────────────────────────────────────────
    technical_signals = []

    df_volume = morning_results.get("volume_surge")
    if df_volume is not None and len(df_volume) > 0:
        technical_signals.extend(_df_to_technical_signals(
            df_volume,
            signal_type="거래량",
            reason_template="trigger_batch: volume_surge — 거래량 급증 모멘텀",
            timestamp=ts,
        ))

    df_gap = morning_results.get("gap_up_momentum")
    if df_gap is not None and len(df_gap) > 0:
        technical_signals.extend(_df_to_technical_signals(
            df_gap,
            signal_type="OHLCV",
            reason_template="trigger_batch: gap_up — 갭상승 + 상승 모멘텀 지속",
            timestamp=ts,
        ))

    df_value = morning_results.get("value_to_cap_ratio")
    if df_value is not None and len(df_value) > 0:
        technical_signals.extend(_df_to_technical_signals(
            df_value,
            signal_type="이평선",
            reason_template="trigger_batch: value_to_cap — 저평가 대비 시가총액 모멘텀",
            timestamp=ts,
        ))

    # ── 3. 전체 ticker + sector 수집 ─────────────────────────────────────────
    all_tickers = {sig.ticker for sig in technical_signals}
    sector_map: dict[str, str] = {}  # {ticker: sector}

    for df_key in ["volume_surge", "gap_up_momentum", "value_to_cap_ratio"]:
        df = morning_results.get(df_key)
        if df is None or len(df) == 0:
            continue
        sector_col = _get_sector_col(df)
        ticker_col = _get_ticker_col(df)
        if sector_col is None:
            continue
        for _, row in df.iterrows():
            ticker = str(row[ticker_col]) if ticker_col else str(row.name)
            if ticker not in sector_map and not _is_nan(row[sector_col]):
                sector_map[ticker] = str(row[sector_col])

    # ── 4. MacroSignal 생성 ───────────────────────────────────────────────────
    macro_signals = []

    # 4-A: 섹터 기반 신호 (hot/cold)
    macro_signals.extend(_make_sector_macro_signals(
        all_tickers, sector_map, hot_sectors, cold_sectors, ts, us_futures_boost,
    ))

    # 4-B: 환율 기반 수출주 신호
    macro_signals.extend(_make_export_macro_signals(
        all_tickers, sector_map, usd_krw, ts,
    ))

    # 4-C: 글로벌 매크로 (us_futures) — 보조 신호
    macro_signals.extend(_make_global_macro_signals(all_tickers, us_futures, ts))

    # ── 5. emergent_selector 호출 ─────────────────────────────────────────────
    results = select_emergent_stocks(
        macro_signals=macro_signals,
        technical_signals=technical_signals,
        top_n=top_n,
        min_conviction=min_conviction,
        direction_filter=direction_filter,
    )

    return results


def _is_nan(val) -> bool:
    """NaN/None 체크 유틸."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


# ─── 변환 요약 리포트 ──────────────────────────────────────────────────────────

def print_adaptation_summary(
    morning_results: dict,
    macro_context: dict,
    results: list,
) -> None:
    """어댑터 실행 결과 요약 출력."""
    total_tech = sum(
        len(df) for df in morning_results.values()
        if df is not None and len(df) > 0
    )
    usd_krw = macro_context.get("usd_krw", 0)
    us_futures = macro_context.get("us_futures", "neutral")

    print("═══ prism_adapter — trigger_batch → emergent_selector 변환 요약 ═══")
    print()
    print(f"입력 신호:")
    for name, df in morning_results.items():
        cnt = len(df) if df is not None else 0
        print(f"  [{name}] {cnt}종목")
    print()
    print(f"매크로 컨텍스트:")
    print(f"  USD/KRW: {usd_krw:.0f}  → 수출주 부스트: {'✓' if usd_krw > USD_KRW_EXPORT_THRESHOLD else '✗'}")
    print(f"  미 선물: {us_futures}")
    print(f"  hot 섹터: {macro_context.get('hot_sectors', [])}")
    print(f"  cold 섹터: {macro_context.get('cold_sectors', [])}")
    print()
    print(f"출력: {len(results)}종목 선정 (창발 기준 통과)")
    print()

    if not results:
        print("  선정 종목 없음 (양쪽 관점 신호 동시 보유 종목 없음 — D-033 탈락)")
        return

    for i, r in enumerate(results, 1):
        dir_emoji = "📈" if r.direction == "bullish" else "📉" if r.direction == "bearish" else "↔️"
        print(f"  [{i:>2}] {r.ticker}  {dir_emoji}  conviction_v2={r.final_score:.4f}")
        print(f"       매크로 {r.macro_count}개 / 기술 {r.technical_count}개 | CSER_vol={r.cser_volume_adjusted:.4f}")
        print(f"       \"{r.top_macro_reason[:55]}\"")
        print(f"       \"{r.top_technical_reason[:55]}\"")
        print()


# ─── 데모 / 테스트 ────────────────────────────────────────────────────────────

def _make_demo_dataframes():
    """
    prism-insight trigger_batch 출력 시뮬레이션.
    실제 데이터 없이 어댑터 동작을 검증한다.
    """
    try:
        import pandas as pd
    except ImportError:
        print("[WARN] pandas 미설치 — 데모 실행 불가")
        return None, None

    # volume_surge 시뮬레이션
    volume_surge = pd.DataFrame({
        "ticker": ["005930", "000660", "068270", "247540", "051910"],
        "score":  [0.92, 0.78, 0.85, 0.88, 0.61],
        "sector": ["반도체", "반도체", "바이오", "2차전지", "화학"],
        "reason": ["거래량 3배", "거래량 2.5배", "거래량 4배", "거래량 5배", "거래량 1.8배"],
    })

    # gap_up_momentum 시뮬레이션
    gap_up_momentum = pd.DataFrame({
        "ticker": ["005930", "068270", "035420", "003550"],
        "score":  [0.75, 0.90, 0.55, 0.68],
        "sector": ["반도체", "바이오", "IT서비스", "IT하드웨어"],
        "reason": ["갭상승 +3.2%", "갭상승 +5.1%", "갭상승 +1.8%", "갭상승 +2.4%"],
    })

    # value_to_cap_ratio 시뮬레이션
    value_to_cap_ratio = pd.DataFrame({
        "ticker": ["247540", "051910", "009540", "011170"],
        "score":  [0.80, 0.70, 0.95, 0.65],
        "sector": ["2차전지", "화학", "조선", "화학"],
        "reason": ["저평가 모멘텀", "저평가 모멘텀", "저평가 모멘텀", "저평가 모멘텀"],
    })

    morning_results = {
        "volume_surge": volume_surge,
        "gap_up_momentum": gap_up_momentum,
        "value_to_cap_ratio": value_to_cap_ratio,
    }

    macro_context = {
        "usd_krw": 1420.0,           # 1400 초과 → 수출주 부스트
        "us_futures": "bullish",     # 미 선물 강세 → 전체 부스트
        "hot_sectors": ["반도체", "바이오"],
        "cold_sectors": ["건설", "유통"],
    }

    return morning_results, macro_context


def main():
    print("prism_adapter 데모 실행 중...\n")

    morning_results, macro_context = _make_demo_dataframes()
    if morning_results is None:
        return

    results = adapt_trigger_batch(
        morning_results=morning_results,
        macro_context=macro_context,
        top_n=10,
        min_conviction=0.05,
    )

    print_adaptation_summary(morning_results, macro_context, results)

    # JSON 모드
    if "--json" in sys.argv:
        from dataclasses import asdict
        import json
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
