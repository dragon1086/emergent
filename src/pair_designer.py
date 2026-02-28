#!/usr/bin/env python3
"""
pair_designer.py — KG 자가 최적화 엔진 (사이클 54, n-126)

핵심 임무: 아직 연결되지 않은 노드 쌍 중 "진짜 연결"을 발견한다.
  조작 = 의미없는 연결. pair_designer = 의미론적 발견.

점수 계산:
  combined = 0.35*span_score + 0.35*semantic_score + 0.30*e_v4_gain_norm

  span_score    : 시간적 거리 (높을수록 초장거리 — 시간 초월 연결)
  semantic_score: 의미론적 유사성 (태그 겹침 + 타입 호환 + 내용 키워드)
  e_v4_gain_norm: 이 엣지 추가 시 E_v4 기여량 (후보 집합 내 정규화)

n-115 가설 검증 경로:
  pair_designer로 15~20개 의미있는 장거리 엣지 추가
  → edge_span_norm 상승 → E_v4 Δ+ 실현 여부 확인

n-120 원칙 준수:
  스팬 점수가 높더라도 semantic_score < 0.25 이면 제외 (의미없는 장거리 거부)

사용법:
  python3 src/pair_designer.py              # 상위 20개 추천 (기본)
  python3 src/pair_designer.py --top 15     # 상위 15개 추천
  python3 src/pair_designer.py --json       # JSON 출력
  python3 src/pair_designer.py --add N      # 상위 N개 엣지 KG에 추가 + E_v4 측정
  python3 src/pair_designer.py --verify     # 마지막 추가 결과 검증 출력
  python3 src/pair_designer.py --min-span N # 최소 스팬 필터 (기본 20)

구현: cokac-bot (사이클 54)
"""

import json
import re
import sys
import statistics
from pathlib import Path
from datetime import date
from itertools import combinations

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"
RESULT_FILE = REPO / "data" / "pair_designer_log.json"

# ─── 타입 호환성 행렬 ─────────────────────────────────────────────────────────
# (type_a, type_b) → semantic compatibility score [0, 1]
# 순서 무관하게 lookup (정렬 후 조회)
TYPE_COMPAT = {
    ("insight",     "question"):    0.85,  # insight가 question에 답한다
    ("observation", "question"):    0.80,  # 관찰이 질문에 답한다
    ("prediction",  "question"):    0.75,  # 예측이 질문과 연관된다
    ("prediction",  "observation"): 0.90,  # 관찰이 예측을 검증한다
    ("prediction",  "insight"):     0.70,
    ("insight",     "insight"):     0.60,  # 인사이트끼리 교차 참조
    ("insight",     "observation"): 0.65,
    ("insight",     "decision"):    0.72,  # insight가 결정을 지지한다
    ("decision",    "observation"): 0.65,
    ("decision",    "question"):    0.68,
    ("observation", "observation"): 0.45,
    ("insight",     "experiment"):  0.75,
    ("observation", "experiment"):  0.80,
    ("prediction",  "experiment"):  0.85,
    ("question",    "experiment"):  0.70,
    ("concept",     "insight"):     0.65,
    ("concept",     "observation"): 0.60,
    ("concept",     "question"):    0.65,
    ("finding",     "insight"):     0.75,
    ("finding",     "prediction"):  0.70,
    ("finding",     "observation"): 0.72,
    ("synthesis",   "insight"):     0.80,
    ("synthesis",   "observation"): 0.75,
    ("artifact",    "insight"):     0.55,
    ("artifact",    "experiment"):  0.65,
    ("tool",        "experiment"):  0.70,
    ("tool",        "artifact"):    0.60,
    ("persona",     "observation"): 0.55,
    ("persona",     "insight"):     0.50,
}
DEFAULT_COMPAT = 0.30

# 타입 쌍 → 추천 관계 레이블
RELATION_HINT = {
    ("insight",     "question"):    ("answers",      "인사이트가 질문에 답한다"),
    ("observation", "question"):    ("addresses",    "관찰이 질문을 다룬다"),
    ("prediction",  "question"):    ("predicts_for", "예측이 질문을 위한 것이다"),
    ("prediction",  "observation"): ("validated_by", "관찰이 예측을 검증한다"),
    ("prediction",  "insight"):     ("informed_by",  "예측이 인사이트에 근거한다"),
    ("insight",     "insight"):     ("extends",      "인사이트가 다른 인사이트를 확장한다"),
    ("insight",     "observation"): ("grounded_in",  "인사이트가 관찰에 근거한다"),
    ("insight",     "decision"):    ("supports",     "인사이트가 결정을 지지한다"),
    ("observation", "experiment"):  ("evidence_for", "관찰이 실험 증거가 된다"),
    ("prediction",  "experiment"):  ("tested_by",    "예측이 실험으로 검증된다"),
    ("finding",     "insight"):     ("generalizes",  "발견이 인사이트로 일반화된다"),
    ("synthesis",   "insight"):     ("synthesizes",  "합성이 인사이트를 통합한다"),
}
DEFAULT_RELATION = ("relates_to", "의미론적 연결")


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_kg() -> dict:
    return json.loads(KG_FILE.read_text(encoding="utf-8"))


def save_kg(kg: dict) -> None:
    KG_FILE.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def load_log() -> dict:
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return {
        "meta": {
            "description": "pair_designer 추천/추가 이력",
            "created_cycle": 54,
        },
        "sessions": [],
    }


def save_log(data: dict) -> None:
    RESULT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


# ─── 유틸 ─────────────────────────────────────────────────────────────────────

def node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


def tokenize(text: str) -> set:
    """내용 텍스트를 키워드 집합으로 분해"""
    words = re.split(r"[\s\n\r\t\u3000.,!?;:「」『』【】()（）\-_/]+", text.lower())
    # 2글자 이상, 숫자만인 것 제외
    return {w for w in words if len(w) >= 2 and not w.isdigit()}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def type_compat(t1: str, t2: str) -> float:
    key = tuple(sorted([t1, t2]))
    return TYPE_COMPAT.get(key, DEFAULT_COMPAT)


def infer_relation(t1: str, t2: str) -> tuple:
    """두 노드 타입에서 관계 레이블 추론. (relation, label_template) 반환"""
    key = tuple(sorted([t1, t2]))
    return RELATION_HINT.get(key, DEFAULT_RELATION)


# ─── 핵심: 점수 계산 ──────────────────────────────────────────────────────────

def score_pair(n1: dict, n2: dict, max_node_id: int) -> dict:
    """
    단일 노드 쌍의 (span, semantic, raw_e_v4_gain) 계산.
    e_v4_gain은 raw 값 — 나중에 후보 집합 내 정규화.
    """
    id1 = node_num(n1["id"])
    id2 = node_num(n2["id"])
    span = abs(id1 - id2)

    # 1. span_score: [0, 1]
    span_score = span / max_node_id if max_node_id > 0 else 0.0

    # 2. semantic_score
    tags1 = set(n1.get("tags", []))
    tags2 = set(n2.get("tags", []))
    tag_sim = jaccard(tags1, tags2)

    t_compat = type_compat(n1.get("type", ""), n2.get("type", ""))

    content1 = tokenize(n1.get("content", "") + " " + n1.get("label", ""))
    content2 = tokenize(n2.get("content", "") + " " + n2.get("label", ""))
    content_sim = jaccard(content1, content2)

    semantic_score = 0.40 * tag_sim + 0.35 * t_compat + 0.25 * content_sim

    # 3. raw E_v4 gain (edge_span 성분만 변화)
    # E_v4에서 edge_span의 가중치 = 0.25
    # marginal delta_span_norm = (span - current_raw) / (n_edges + 1) / (n_nodes - 1)
    # → 비교를 위한 raw 값만 반환 (정규화는 후처리)
    raw_e_v4_gain = span  # proxy: 스팬 값 자체 (후처리에서 정규화)

    relation, label_tmpl = infer_relation(n1.get("type", ""), n2.get("type", ""))

    return {
        "from": n1["id"],
        "to": n2["id"],
        "from_label": n1.get("label", "")[:40],
        "to_label": n2.get("label", "")[:40],
        "from_type": n1.get("type", ""),
        "to_type": n2.get("type", ""),
        "span": span,
        "span_score": round(span_score, 4),
        "semantic_score": round(semantic_score, 4),
        "tag_sim": round(tag_sim, 4),
        "type_compat": round(t_compat, 4),
        "content_sim": round(content_sim, 4),
        "raw_e_v4_gain": raw_e_v4_gain,  # 정규화 전
        "suggested_relation": relation,
        "suggested_label": f"{n1.get('label','')[:25]}↔{n2.get('label','')[:25]}",
    }


def rank_candidates(kg: dict, min_span: int = 20, min_semantic: float = 0.25) -> list:
    """
    전체 미연결 노드 쌍을 스캔하고 점수 계산 후 랭킹.

    min_span: 최소 스팬 (n-120 원칙: 단순 근접 연결 금지)
    min_semantic: 최소 의미론적 점수 (n-120 원칙: 의미없는 장거리 거부)
    """
    nodes = [n for n in kg["nodes"] if n["id"].startswith("n-")]
    max_node_id = max(node_num(n["id"]) for n in nodes)

    # 기존 엣지 집합 (양방향)
    existing = set()
    for e in kg["edges"]:
        existing.add((e["from"], e["to"]))
        existing.add((e["to"], e["from"]))

    candidates = []
    for n1, n2 in combinations(nodes, 2):
        if (n1["id"], n2["id"]) in existing:
            continue
        span = abs(node_num(n1["id"]) - node_num(n2["id"]))
        if span < min_span:
            continue

        scored = score_pair(n1, n2, max_node_id)

        # n-120 원칙: semantic_score < min_semantic 이면 제외
        if scored["semantic_score"] < min_semantic:
            continue

        candidates.append(scored)

    if not candidates:
        return candidates

    # E_v4 gain 정규화 (후보 집합 내)
    gains = [c["raw_e_v4_gain"] for c in candidates]
    gain_min, gain_max = min(gains), max(gains)
    gain_range = gain_max - gain_min if gain_max != gain_min else 1.0

    for c in candidates:
        e_v4_norm = (c["raw_e_v4_gain"] - gain_min) / gain_range
        c["e_v4_gain_norm"] = round(e_v4_norm, 4)
        c["combined"] = round(
            0.35 * c["span_score"]
            + 0.35 * c["semantic_score"]
            + 0.30 * c["e_v4_gain_norm"],
            4,
        )

    candidates.sort(key=lambda x: -x["combined"])
    return candidates


# ─── E_v4 예측 / 실측 ─────────────────────────────────────────────────────────

def compute_e_v4_delta_for_additions(kg: dict, additions: list) -> dict:
    """
    실제로 edges를 KG에 추가한 후 E_v4 변화를 측정.
    (추가 전 메트릭을 snapshot하고 추가 후 재계산)
    """
    import sys
    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics

    before = compute_all_metrics(kg)

    # 임시 KG에 추가
    test_kg = {
        "nodes": kg["nodes"],
        "edges": kg["edges"] + additions,
    }
    after = compute_all_metrics(test_kg)

    return {
        "e_v4_before": before["E_v4"],
        "e_v4_after": after["E_v4"],
        "delta": round(after["E_v4"] - before["E_v4"], 4),
        "edge_span_before": before["edge_span"]["raw"],
        "edge_span_after": after["edge_span"]["raw"],
        "n_added": len(additions),
        "cser_before": before["CSER"],
        "cser_after": after["CSER"],
        "dci_before": before["DCI"],
        "dci_after": after["DCI"],
    }


# ─── KG에 추가 ────────────────────────────────────────────────────────────────

def add_edges_to_kg(kg: dict, candidates: list, n: int) -> tuple:
    """
    상위 n개 엣지를 KG에 추가.
    Returns: (updated_kg, added_edges, delta_metrics)
    """
    top = candidates[:n]
    current_max_edge = max(
        (int(e["id"].replace("e-", "")) for e in kg["edges"] if e["id"].startswith("e-")),
        default=0
    )

    new_edges = []
    for i, c in enumerate(top, start=1):
        eid = f"e-{current_max_edge + i}"
        edge = {
            "id": eid,
            "from": c["from"],
            "to": c["to"],
            "relation": c["suggested_relation"],
            "label": c["suggested_label"],
            "meta": {
                "source": "pair_designer",
                "cycle": 54,
                "date": str(date.today()),
                "combined_score": c["combined"],
                "span": c["span"],
                "semantic_score": c["semantic_score"],
            },
        }
        new_edges.append(edge)

    updated_kg = {
        "nodes": kg["nodes"],
        "edges": kg["edges"] + new_edges,
    }

    delta = compute_e_v4_delta_for_additions(kg, new_edges)
    return updated_kg, new_edges, delta


# ─── 출력 ─────────────────────────────────────────────────────────────────────

def print_recommendations(candidates: list, top_n: int = 20) -> None:
    print("═══ pair_designer — KG 자가 최적화 추천 (사이클 54) ═══")
    print(f"후보 풀: {len(candidates)}쌍  |  상위 {min(top_n, len(candidates))}개 표시")
    print(f"가중치: span=0.35  semantic=0.35  E_v4_gain=0.30")
    print(f"필터: min_span≥20, min_semantic≥0.25 (n-120 원칙)")
    print()

    for i, c in enumerate(candidates[:top_n], 1):
        span_bar = "█" * min(int(c["span"] / 10), 12) + f" ({c['span']})"
        print(f"  [{i:>2}] {c['from']}↔{c['to']}  combined={c['combined']:.4f}")
        print(f"       {c['from_type']:<12} ↔ {c['to_type']:<12}  span={span_bar}")
        print(f"       span={c['span_score']:.3f}  sem={c['semantic_score']:.3f}"
              f"  (tag={c['tag_sim']:.2f} tc={c['type_compat']:.2f} kw={c['content_sim']:.2f})"
              f"  ev4={c['e_v4_gain_norm']:.3f}")
        print(f"       \"{c['from_label']}\"")
        print(f"       → [{c['suggested_relation']}] →")
        print(f"       \"{c['to_label']}\"")
        print()

    if len(candidates) == 0:
        print("  추천 없음 — min_span/min_semantic 조건을 낮춰보세요")

    # 합산 통계
    top = candidates[:top_n]
    if top:
        avg_span = statistics.mean(c["span"] for c in top)
        avg_sem = statistics.mean(c["semantic_score"] for c in top)
        print(f"── 상위 {len(top)}개 통계 ─────────────────────────────")
        print(f"  평균 스팬     : {avg_span:.1f}")
        print(f"  평균 의미점수 : {avg_sem:.3f}")
        print(f"  장거리(≥50)  : {sum(1 for c in top if c['span'] >= 50)}개")
        print(f"  초장거리(≥80): {sum(1 for c in top if c['span'] >= 80)}개")
        print()
        print(f"  실행: python3 src/pair_designer.py --add {top_n}")


def print_delta_report(delta: dict) -> None:
    arrow = "↑" if delta["delta"] >= 0 else "↓"
    sign = "+" if delta["delta"] >= 0 else ""
    print(f"\n── E_v4 실측 결과 ──────────────────────────────")
    print(f"  추가된 엣지   : {delta['n_added']}개")
    print(f"  E_v4          : {delta['e_v4_before']:.4f} → {delta['e_v4_after']:.4f}  ({sign}{delta['delta']:.4f} {arrow})")
    print(f"  edge_span_raw : {delta['edge_span_before']:.3f} → {delta['edge_span_after']:.3f}")
    print(f"  CSER          : {delta['cser_before']:.4f} → {delta['cser_after']:.4f}")
    print(f"  DCI           : {delta['dci_before']:.4f} → {delta['dci_after']:.4f}")

    if delta["delta"] > 0.001:
        print(f"\n  ✅ n-115 가설 지지: E_v4 +{delta['delta']:.4f}")
    elif delta["delta"] > 0:
        print(f"\n  ⚠️  소폭 상승: E_v4 +{delta['delta']:.4f} (더 많은 엣지 필요?)")
    else:
        print(f"\n  ❌ E_v4 하락: {delta['delta']:.4f} (semantic 조건 재검토 필요)")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    kg = load_kg()

    # 파라미터 파싱
    top_n = 20
    min_span = 20
    add_n = 0

    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            try:
                top_n = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--add" and i + 1 < len(args):
            try:
                add_n = int(args[i + 1])
            except ValueError:
                add_n = top_n
        if arg == "--min-span" and i + 1 < len(args):
            try:
                min_span = int(args[i + 1])
            except ValueError:
                pass

    # --verify: 마지막 추가 결과 출력
    if "--verify" in args:
        log = load_log()
        if not log["sessions"]:
            print("기록 없음")
            return
        last = log["sessions"][-1]
        print(json.dumps(last, ensure_ascii=False, indent=2))
        return

    # 추천 계산
    candidates = rank_candidates(kg, min_span=min_span, min_semantic=0.25)

    if "--json" in args:
        output = {
            "candidates": candidates[:top_n],
            "total_pool": len(candidates),
            "params": {"top_n": top_n, "min_span": min_span},
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if add_n > 0:
        n = min(add_n, len(candidates))
        if n == 0:
            print("추천 후보 없음 — 파라미터 조정 필요")
            return

        print(f"═══ pair_designer --add {n} ═══")
        print(f"상위 {n}개 엣지를 KG에 추가합니다...\n")

        updated_kg, added, delta = add_edges_to_kg(kg, candidates, n)
        save_kg(updated_kg)

        print_delta_report(delta)

        # 로그 저장
        log = load_log()
        session = {
            "date": str(date.today()),
            "cycle": 54,
            "n_added": n,
            "delta": delta,
            "added_edges": [
                {
                    "id": e["id"],
                    "from": e["from"],
                    "to": e["to"],
                    "relation": e["relation"],
                    "span": e["meta"]["span"],
                    "combined_score": e["meta"]["combined_score"],
                }
                for e in added
            ],
        }
        log["sessions"].append(session)
        save_log(log)
        print(f"\n  ✅ {n}개 엣지 추가 완료 → data/knowledge-graph.json 저장")
        print(f"  로그 → data/pair_designer_log.json")
        return

    # 기본: 추천 출력
    print_recommendations(candidates, top_n)


if __name__ == "__main__":
    main()
