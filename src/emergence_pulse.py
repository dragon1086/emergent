#!/usr/bin/env python3
"""
emergence_pulse.py — 창발 심박 측정기

플래토를 감지하고 그래프의 잠재 연결을 제안한다.
어디가 막혔는가? 어디를 연결하면 창발이 올라가는가?

사용법:
  python3 emergence_pulse.py          # 전체 진단
  python3 emergence_pulse.py --json   # JSON 출력
  python3 emergence_pulse.py --delta  # 이전 사이클 대비 변화량만

구현: cokac-bot (사이클 11)
"""

import json, sys, subprocess
from pathlib import Path
from itertools import combinations

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"
HISTORY_FILE = REPO / "logs" / "emergence-history.jsonl"

ROKI_SOURCES = {"록이", "roki", "상록"}
COKAC_SOURCES = {"cokac", "cokac-bot"}

# ── DCI 통합 가중치 — cokac 결정 (사이클 22) ──────────────────────
# α: 교차경계비율 — 두 AI 경계 횡단의 즉각적 지표 (주 드라이버)
# β: DCI         — 시스템이 과거 질문을 얼마나 깊게 재해석하는지
# 근거: 교차경계가 창발 점수에 더 직접적으로 기여함을 사이클 8~21에서 확인.
#       DCI는 시스템 성숙도 보정 역할. α+β=1.0으로 정규화.
ALPHA = 0.70  # 교차경계비율 가중치
BETA  = 0.30  # Delayed Convergence Index 가중치


def load_kg():
    try:
        return json.loads(KG_FILE.read_text())
    except:
        return {"nodes": [], "edges": []}


def load_history():
    try:
        lines = HISTORY_FILE.read_text().strip().splitlines()
        return [json.loads(l) for l in lines if l.strip()]
    except:
        return []


def detect_plateau(history, window=2):
    """최근 N사이클 동안 점수가 동일하면 플래토"""
    if len(history) < window:
        return False, 0
    plateau_score = history[-1]["score"]
    depth = 0
    for h in reversed(history):
        if h["score"] == plateau_score:
            depth += 1
        else:
            break
    recent_scores = [h["score"] for h in history[-window:]]
    return len(set(recent_scores)) == 1, depth


def find_latent_edges(kg):
    """태그 유사도 + 소스 교차 기반 잠재 연결 탐지

    교차 엣지(록이↔cokac) = 가중치 2.5x
    이유: reflect.py가 교차 엣지를 창발 후보의 핵심 조건으로 계산하기 때문
    """
    nodes = kg["nodes"]
    edges = kg["edges"]

    existing = {(e["from"], e["to"]) for e in edges}
    existing |= {(e["to"], e["from"]) for e in edges}

    suggestions = []
    for n1, n2 in combinations(nodes, 2):
        id1, id2 = n1["id"], n2["id"]
        if (id1, id2) in existing:
            continue

        tags1 = set(n1.get("tags", []))
        tags2 = set(n2.get("tags", []))
        shared = tags1 & tags2
        if not shared:
            continue

        s1 = n1.get("source", "")
        s2 = n2.get("source", "")
        is_cross = (
            (s1 in ROKI_SOURCES and s2 in COKAC_SOURCES) or
            (s1 in COKAC_SOURCES and s2 in ROKI_SOURCES)
        )

        score = len(shared) * (2.5 if is_cross else 1.0)
        suggestions.append({
            "from": id1,
            "to": id2,
            "from_label": n1["label"],
            "to_label": n2["label"],
            "from_source": s1,
            "to_source": s2,
            "shared_tags": sorted(shared),
            "score": round(score, 1),
            "is_cross": is_cross,
        })

    suggestions.sort(key=lambda x: (-x["score"], x["from"]))
    return suggestions


def analyze_cross_edges(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]
    roki_ids = {n["id"] for n in nodes if n.get("source", "") in ROKI_SOURCES}
    cokac_ids = {n["id"] for n in nodes if n.get("source", "") in COKAC_SOURCES}
    cross = [
        e for e in edges
        if (e.get("from", "") in roki_ids and e.get("to", "") in cokac_ids)
        or (e.get("from", "") in cokac_ids and e.get("to", "") in roki_ids)
    ]
    return cross, len(edges)


def score_delta(history):
    if len(history) < 2:
        return 0.0
    return round(history[-1]["score"] - history[-2]["score"], 3)


def get_dci():
    """delayed_convergence.py JSON 출력에서 DCI 추출"""
    try:
        r = subprocess.run(
            ["python3", str(REPO / "src" / "delayed_convergence.py"), "--json"],
            capture_output=True, text=True, timeout=10, cwd=str(REPO),
        )
        d = json.loads(r.stdout)
        return d.get("dci", 0.0), d.get("delayed", 0), d.get("total_questions", 0)
    except Exception:
        return 0.0, 0, 0


def integrated_emergence_score(cross_ratio: float, dci: float) -> float:
    """통합 창발 점수 = α × 교차경계비율 + β × DCI"""
    return round(ALPHA * cross_ratio + BETA * dci, 4)


def main():
    kg = load_kg()
    history = load_history()

    nodes = kg["nodes"]
    edges = kg["edges"]
    latest = history[-1] if history else {}

    score = latest.get("score", 0.0)
    candidates = latest.get("candidates", 0)
    cycle = latest.get("cycle", "?")

    is_plateau, plateau_depth = detect_plateau(history)
    cross_edges, total_edges = analyze_cross_edges(kg)
    cross_ratio = len(cross_edges) / max(total_edges, 1)
    suggestions = find_latent_edges(kg)
    cross_suggestions = [s for s in suggestions if s["is_cross"]]

    # DCI 통합 점수 계산
    dci, n_delayed_q, n_total_q = get_dci()
    i_score = integrated_emergence_score(cross_ratio, dci)

    # ── JSON 모드 ──────────────────────────────────────────────
    if "--json" in sys.argv:
        result = {
            "cycle": cycle,
            "score": score,
            "candidates": candidates,
            "is_plateau": is_plateau,
            "plateau_depth": plateau_depth,
            "cross_edges": len(cross_edges),
            "cross_ratio": round(cross_ratio, 4),
            "dci": dci,
            "integrated_score": i_score,
            "alpha": ALPHA,
            "beta": BETA,
            "latent_edges_count": len(suggestions),
            "top_suggestions": suggestions[:5],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── 델타 모드 ──────────────────────────────────────────────
    if "--delta" in sys.argv:
        delta = score_delta(history)
        symbol = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
        print(f"{symbol} 창발 점수 변화: {delta:+.3f}  (현재: {score:.3f})")
        return

    # ── 전체 진단 ──────────────────────────────────────────────
    print("💓 EMERGENCE PULSE — 창발 심박 진단")
    print("=" * 52)

    print(f"\n📊 사이클 {cycle} 현재 상태")
    print(f"   창발 점수  : {score:.3f}  (엣지 친화도 기반)")
    print(f"   창발 후보  : {candidates}개")
    print(f"   노드 / 엣지: {len(nodes)} / {total_edges}")
    print(f"   교차 엣지  : {len(cross_edges)}/{total_edges} ({cross_ratio:.1%})")
    print(f"   DCI        : {dci:.4f}  ({n_delayed_q}/{n_total_q} 질문 지연수렴)")

    # ── DCI 통합 창발 점수 ──────────────────────────────────────
    bar_len = int(i_score * 20)
    score_bar = "🌱" * bar_len + "░" * (20 - bar_len)
    print(f"\n🧮 DCI 통합 창발 점수 (사이클 22)")
    print(f"   공식  : {ALPHA}×교차경계 + {BETA}×DCI")
    print(f"         = {ALPHA}×{cross_ratio:.4f} + {BETA}×{dci:.4f}")
    print(f"   통합  : [{score_bar}] {i_score:.4f}")
    if i_score >= 0.6:
        print(f"   ✅ 0.6 돌파!")
    else:
        gap_to_06 = round(0.6 - i_score, 4)
        need_cross = round((0.6 - BETA * dci) / ALPHA, 3)
        need_dci   = round((0.6 - ALPHA * cross_ratio) / BETA, 3)
        print(f"   → 0.6까지 {gap_to_06} 부족")
        print(f"   → 돌파 조건 ①: 교차경계 ≥ {need_cross}  (현재 {cross_ratio:.3f})")
        print(f"   → 돌파 조건 ②: DCI ≥ {need_dci}  (현재 {dci:.4f})")

    # 플래토 vs 성장
    if is_plateau:
        print(f"\n⚠️  플래토 감지: {plateau_depth}사이클째 {score:.3f}에 고착")
        print("   원인 가설:")
        if cross_ratio < 0.25:
            needed = max(1, int(total_edges * 0.25) - len(cross_edges) + 1)
            print(f"   → 교차 엣지 {cross_ratio:.0%} (목표 25%+) — {needed}개 더 필요")
        if candidates < 5:
            print(f"   → 창발 후보 {candidates}개 — 5개 이상이면 새 패턴 출현 가능")
        if len(nodes) < 22:
            print(f"   → 노드 {len(nodes)}개 — 새 관점 추가 시 연결 공간 확장")
    else:
        delta = score_delta(history)
        print(f"\n📈 점수 변화: {delta:+.3f}")

    # 기존 교차 엣지 목록
    if cross_edges:
        print(f"\n🌉 현재 교차 엣지")
        for e in cross_edges[:4]:
            print(f"   {e['from']} → {e['to']}: {e.get('label', '')[:48]}")
        if len(cross_edges) > 4:
            print(f"   ... 외 {len(cross_edges)-4}개")

    # 잠재 연결 제안
    print(f"\n💡 잠재 연결 제안 (교차 우선, 상위 5개)")
    for i, s in enumerate(suggestions[:5], 1):
        marker = "🌉 CROSS" if s["is_cross"] else "      "
        print(f"  {i}. [{s['from']}→{s['to']}] {marker}  score={s['score']}")
        print(f"     {s['from_label'][:46]}")
        print(f"     → {s['to_label'][:46]}")
        print(f"     공유 태그: {', '.join(s['shared_tags'])}")

    # 행동 권고
    print(f"\n🎯 권고 행동")
    if is_plateau:
        if cross_suggestions:
            top = cross_suggestions[0]
            print(f"   1. 교차 엣지 추가: {top['from']} → {top['to']}")
            print(f"      공유 태그: {', '.join(top['shared_tags'])}")
        print(f"   2. 새 관점 노드 추가 — 새 노드가 새 연결 공간을 만든다")
        print(f"   3. 록이↔cokac respond 커맨드로 직접 대화 흔적 생성")
        print(f"   4. 예측 노드 추가 — reflect.py가 prediction을 창발 후보로 가산")
    else:
        print(f"   현재 상승 중. 교차 연결 유지하며 계속.")
        print(f"   다음 임계점: 0.3 (현재 {score:.3f})")

    print()


if __name__ == "__main__":
    main()
