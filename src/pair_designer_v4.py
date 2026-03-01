#!/usr/bin/env python3
"""
pair_designer_v4.py — KG 자가 최적화 엔진 v4 (CSER 제약 제거 + edge_span 직접 최적화)

v3 역설 (D-065):
  pair_designer_v3의 CSER 최적화가 E_v4 > E_v3 역전을 방해함.
  E_v3 CSER 가중치(0.40) > E_v4 CSER 가중치(0.35) → CSER 상승 시 E_v3가 더 빠르게 증가.
  결과: Δ(E_v4 - E_v3) 확대 불가.

v4 전략 (D-067, D-068):
  CSER 제약 완전 제거.
  edge_span_norm + node_age_diversity를 직접 최적화.
  E_v4 증가에 직접 기여하는 지표를 선택 기준으로 사용.

combined_v4 = 0.50×edge_span_norm + 0.30×node_age_diversity + 0.20×cross_bonus

  - edge_span_norm (0.50): E_v4에서 γ=0.25 — 가장 직접적 기여 경로
  - node_age_diversity (0.30): E_v4에서 δ=0.15 기여
  - cross_bonus (0.20): 교차출처 쌍에 보너스 (D-033 원칙 유지)
  * CSER 제약 없음: CSER는 E_v4 증가를 방해하는 v3 역설에서 탈출

사용법:
  python3 src/pair_designer_v4.py              # 상위 20개 추천
  python3 src/pair_designer_v4.py --top 15     # 상위 15개
  python3 src/pair_designer_v4.py --json       # JSON 출력
  python3 src/pair_designer_v4.py --add N      # KG에 N개 추가 + Δ(E_v4 - E_v3) 측정
  python3 src/pair_designer_v4.py --verify     # 마지막 추가 결과 출력
  python3 src/pair_designer_v4.py --compare    # v3 vs v4 선택 비교

구현: 록이 (냉정한 판사) — 사이클 78, D-070
"""

import json
import re
import sys
import statistics
from pathlib import Path
from datetime import date
from itertools import combinations

REPO = Path(__file__).parent.parent
KG_FILE     = REPO / "data" / "knowledge-graph.json"
RESULT_FILE = REPO / "data" / "pair_designer_v4_log.json"

VERSION = "v4"
CYCLE   = 78

# ─── v4 핵심 상수 ──────────────────────────────────────────────────────────────

# combined_v4 가중치
W_EDGE_SPAN  = 0.50   # edge_span_norm 기여 (E_v4 γ=0.25 직접 최적화)
W_NODE_AGE   = 0.30   # node_age_diversity 기여 (E_v4 δ=0.15 직접 최적화)
W_CROSS      = 0.20   # 교차출처 보너스 (D-033 원칙)

# v3와 달리 CSER 제약 없음
# CSER_MIN 정의 없음 — v3 역설 탈출

# 최소 span (엣지 길이 하한)
MIN_SPAN = 20

# DCI feeding 관계 필터
DCI_FEEDING_RELATIONS = {"answers", "addresses"}

# 출처 분류
LOKI_SOURCES  = {"록이", "상록"}
COKAC_SOURCES = {"cokac", "cokac-bot"}

# ─── 타입 호환성 행렬 (v3 동일) ────────────────────────────────────────────────
TYPE_COMPAT = {
    ("insight",     "question"):    0.85,
    ("observation", "question"):    0.80,
    ("prediction",  "question"):    0.75,
    ("prediction",  "observation"): 0.90,
    ("prediction",  "insight"):     0.70,
    ("insight",     "insight"):     0.60,
    ("insight",     "observation"): 0.65,
    ("insight",     "decision"):    0.72,
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

RELATION_HINT = {
    ("insight",     "question"):    ("resonates_with", "인사이트가 질문과 공명한다"),
    ("observation", "question"):    ("contextualizes", "관찰이 질문의 맥락을 제공한다"),
    ("prediction",  "question"):    ("parallel_to",    "예측이 질문과 병렬로 전개된다"),
    ("prediction",  "observation"): ("validated_by",   "관찰이 예측을 검증한다"),
    ("prediction",  "insight"):     ("informed_by",    "예측이 인사이트에 근거한다"),
    ("insight",     "insight"):     ("extends",        "인사이트가 다른 인사이트를 확장한다"),
    ("insight",     "observation"): ("grounds",        "인사이트가 관찰에 근거한다"),
    ("insight",     "decision"):    ("supports",       "인사이트가 결정을 지지한다"),
    ("observation", "experiment"):  ("evidence_for",   "관찰이 실험 증거가 된다"),
    ("prediction",  "experiment"):  ("tested_by",      "예측이 실험으로 검증된다"),
    ("finding",     "insight"):     ("generalizes",    "발견이 인사이트로 일반화된다"),
    ("synthesis",   "insight"):     ("synthesizes",    "합성이 인사이트를 통합한다"),
    ("concept",     "insight"):     ("resonates_with", "개념이 인사이트와 공명한다"),
    ("concept",     "question"):    ("parallel_to",    "개념이 질문과 병렬로 탐구된다"),
    ("finding",     "prediction"):  ("extends",        "발견이 예측을 확장한다"),
    ("synthesis",   "observation"): ("grounds",        "합성이 관찰에 근거한다"),
}
DEFAULT_RELATION = ("relates_to", "의미론적 연결")


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_kg() -> dict:
    return json.loads(KG_FILE.read_text(encoding="utf-8"))


def save_kg(kg: dict) -> None:
    existing_nums = [
        int(n["id"].split("-")[1]) for n in kg["nodes"]
        if n["id"].startswith("n-") and n["id"].split("-")[1].isdigit()
    ]
    if "meta" not in kg:
        next_num = (max(existing_nums) + 1) if existing_nums else 1
        kg["meta"] = {
            "next_node_id": f"n-{next_num:03d}",
            "last_updated": str(date.today()),
            "total_nodes":  len(kg["nodes"]),
            "total_edges":  len(kg["edges"]),
        }
    else:
        kg["meta"]["total_nodes"]  = len(kg["nodes"])
        kg["meta"]["total_edges"]  = len(kg["edges"])
        kg["meta"]["last_updated"] = str(date.today())
    KG_FILE.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_log() -> dict:
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return {
        "meta": {
            "description": "pair_designer v4 이력 (CSER 제약 제거 + edge_span 직접 최적화)",
            "created_cycle": CYCLE,
            "version":       VERSION,
        },
        "sessions": [],
    }


def save_log(data: dict) -> None:
    RESULT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ─── 유틸 ─────────────────────────────────────────────────────────────────────

def node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


def tokenize(text: str) -> set:
    words = re.split(r"[\s\n\r\t\u3000.,!?;:「」『』【】()（）\-_/]+", text.lower())
    return {w for w in words if len(w) >= 2 and not w.isdigit()}


def jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def type_compat(t1: str, t2: str) -> float:
    return TYPE_COMPAT.get(tuple(sorted([t1, t2])), DEFAULT_COMPAT)


def infer_relation(t1: str, t2: str) -> tuple:
    key = tuple(sorted([t1, t2]))
    rel, lbl = RELATION_HINT.get(key, DEFAULT_RELATION)
    if rel in DCI_FEEDING_RELATIONS:
        return ("resonates_with", f"{t1}↔{t2} 공명")
    return rel, lbl


def classify_source(src: str) -> str:
    if src in LOKI_SOURCES:  return "록이"
    if src in COKAC_SOURCES: return "cokac"
    return "기타"


def is_cross_source(n1: dict, n2: dict) -> bool:
    t1 = classify_source(n1.get("source", ""))
    t2 = classify_source(n2.get("source", ""))
    return t1 != t2 and "기타" not in (t1, t2)


# ─── v4 핵심: edge_span_norm + node_age_diversity 직접 점수화 ─────────────────

def score_pair_v4(n1: dict, n2: dict, max_node_id: int, kg_stdev: float, kg_mean: float) -> dict:
    """
    v4 점수 계산.
    combined_v4 = W_EDGE_SPAN×edge_span_norm + W_NODE_AGE×age_contribution + W_CROSS×cross_flag

    edge_span_norm: 이 엣지의 span / max_node_id
    age_contribution: 두 노드 ID의 차이가 전체 node_age_diversity에 기여하는 정도 (proxy)
    cross_flag: 교차출처이면 1.0, 아니면 0.0
    """
    id1  = node_num(n1["id"])
    id2  = node_num(n2["id"])
    span = abs(id1 - id2)

    edge_span_norm = span / max_node_id if max_node_id > 0 else 0.0

    # node_age_diversity contribution proxy:
    # 두 노드 ID가 평균에서 얼마나 멀리 퍼져 있는지 (std 기여 추정)
    # 정확한 std 변화 계산은 전체 노드 재계산이 필요 — span_norm을 대리 지표로 사용
    age_contrib = edge_span_norm  # span이 클수록 age diversity에 기여

    cross = is_cross_source(n1, n2)
    cross_flag = 1.0 if cross else 0.0

    combined = round(
        W_EDGE_SPAN * edge_span_norm
        + W_NODE_AGE * age_contrib
        + W_CROSS    * cross_flag,
        4,
    )

    # 관계 추론 (DCI feeding 필터용)
    relation, _ = infer_relation(n1.get("type", ""), n2.get("type", ""))

    # 의미론적 점수 (필터용 — v3 방식 유지)
    tags1    = set(n1.get("tags", []))
    tags2    = set(n2.get("tags", []))
    tag_sim  = jaccard(tags1, tags2)
    t_compat = type_compat(n1.get("type", ""), n2.get("type", ""))
    c1       = tokenize(n1.get("content", "") + " " + n1.get("label", ""))
    c2       = tokenize(n2.get("content", "") + " " + n2.get("label", ""))
    cont_sim = jaccard(c1, c2)
    semantic = round(0.40 * tag_sim + 0.35 * t_compat + 0.25 * cont_sim, 4)

    return {
        "from":               n1["id"],
        "to":                 n2["id"],
        "from_label":         n1.get("label", "")[:40],
        "to_label":           n2.get("label", "")[:40],
        "from_type":          n1.get("type", ""),
        "to_type":            n2.get("type", ""),
        "from_source":        n1.get("source", ""),
        "to_source":          n2.get("source", ""),
        "span":               span,
        "edge_span_norm":     round(edge_span_norm, 4),
        "age_contrib":        round(age_contrib, 4),
        "cross_source":       cross,
        "cross_flag":         cross_flag,
        "semantic_score":     semantic,
        "combined":           combined,
        "suggested_relation": relation,
        "suggested_label":    f"{n1.get('label','')[:25]}↔{n2.get('label','')[:25]}",
    }


def rank_candidates(kg: dict) -> list:
    """
    v4 후보 랭킹.
    CSER 제약 없음. DCI feeding 관계만 필터.
    min_semantic 없음 (edge_span이 기준).
    """
    nodes      = [n for n in kg["nodes"] if n["id"].startswith("n-")]
    max_nid    = max(node_num(n["id"]) for n in nodes)
    nids       = [node_num(n["id"]) for n in nodes]
    kg_stdev   = statistics.stdev(nids) if len(nids) > 1 else 1.0
    kg_mean    = statistics.mean(nids)

    existing = set()
    for e in kg["edges"]:
        existing.add((e["from"], e["to"]))
        existing.add((e["to"],   e["from"]))

    candidates = []
    stats = {"cross": 0, "same": 0, "filtered_dci": 0}

    for n1, n2 in combinations(nodes, 2):
        if (n1["id"], n2["id"]) in existing:
            continue
        span = abs(node_num(n1["id"]) - node_num(n2["id"]))
        if span < MIN_SPAN:
            continue

        scored = score_pair_v4(n1, n2, max_nid, kg_stdev, kg_mean)

        # DCI feeding 필터
        if scored["suggested_relation"] in DCI_FEEDING_RELATIONS:
            stats["filtered_dci"] += 1
            continue

        if scored["cross_source"]:
            stats["cross"] += 1
        else:
            stats["same"] += 1

        candidates.append(scored)

    print(f"  📊 후보 풀 — 교차출처: {stats['cross']}개 / 동일출처: {stats['same']}개"
          f"  (DCI 필터: {stats['filtered_dci']}개 제외)")

    candidates.sort(key=lambda x: -x["combined"])
    return candidates


# ─── E_v4 / E_v3 delta 측정 ───────────────────────────────────────────────────

def compute_delta(kg: dict, additions: list) -> dict:
    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics

    before = compute_all_metrics(kg)
    test_kg = {"nodes": kg["nodes"], "edges": kg["edges"] + additions}
    after  = compute_all_metrics(test_kg)

    ev4_before = before["E_v4"]
    ev3_before = before["E_v3"]
    ev4_after  = after["E_v4"]
    ev3_after  = after["E_v3"]

    return {
        "E_v4_before":  ev4_before,
        "E_v4_after":   ev4_after,
        "E_v4_delta":   round(ev4_after - ev4_before, 4),
        "E_v3_before":  ev3_before,
        "E_v3_after":   ev3_after,
        "E_v3_delta":   round(ev3_after - ev3_before, 4),
        "gap_before":   round(ev4_before - ev3_before, 4),
        "gap_after":    round(ev4_after  - ev3_after,  4),
        "gap_delta":    round((ev4_after - ev3_after) - (ev4_before - ev3_before), 4),
        "CSER_before":  before["CSER"],
        "CSER_after":   after["CSER"],
        "DCI_before":   before["DCI"],
        "DCI_after":    after["DCI"],
        "edge_span_before": before["edge_span"]["raw"],
        "edge_span_after":  after["edge_span"]["raw"],
        "n_added":      len(additions),
        "v4_success":   (ev4_after - ev3_after) > 0,
    }


# ─── KG에 추가 ────────────────────────────────────────────────────────────────

def add_edges_to_kg(kg: dict, selected: list) -> tuple:
    max_eid = max(
        (int(e["id"].replace("e-", ""))
         for e in kg["edges"]
         if e.get("id", "").startswith("e-") and e["id"].replace("e-", "").isdigit()),
        default=0,
    )
    new_edges = []
    for i, c in enumerate(selected, start=1):
        new_edges.append({
            "id":       f"e-{max_eid + i}",
            "from":     c["from"],
            "to":       c["to"],
            "relation": c["suggested_relation"],
            "label":    c["suggested_label"],
            "meta": {
                "source":        "pair_designer_v4",
                "version":       VERSION,
                "cycle":         CYCLE,
                "date":          str(date.today()),
                "combined_v4":   c["combined"],
                "span":          c["span"],
                "edge_span_norm": c["edge_span_norm"],
                "cross_source":  c["cross_source"],
                "dci_neutral":   True,
            },
        })

    updated_kg = {"nodes": kg["nodes"], "edges": kg["edges"] + new_edges}
    delta      = compute_delta(kg, new_edges)
    return updated_kg, new_edges, delta


# ─── 출력 ─────────────────────────────────────────────────────────────────────

def print_recommendations(candidates: list, top_n: int) -> None:
    n = min(top_n, len(candidates))
    cross_n = sum(1 for c in candidates[:n] if c["cross_source"])
    print("═══ pair_designer v4 — CSER 제약 제거 + edge_span 직접 최적화 (사이클 78) ═══")
    print(f"후보: {len(candidates)}쌍  |  상위 {n}개")
    print(f"combined_v4 = {W_EDGE_SPAN}×edge_span_norm + {W_NODE_AGE}×age_contrib + {W_CROSS}×cross_flag")
    print(f"CSER 제약: 없음 (v3 역설 탈출)")
    print(f"상위 {n}개 중 교차출처: {cross_n}개")
    print()

    for i, c in enumerate(candidates[:n], 1):
        cross_tag = " [교차✓]" if c["cross_source"] else ""
        print(f"  [{i:>2}] {c['from']}↔{c['to']}  combined={c['combined']:.4f}{cross_tag}")
        print(f"       {c['from_type']:<12} ↔ {c['to_type']:<12}  span={c['span']}")
        print(f"       edge_span_norm={c['edge_span_norm']:.4f}  semantic={c['semantic_score']:.4f}")
        print(f"       \"{c['from_label']}\"")
        print(f"       → [{c['suggested_relation']}]")
        print(f"       \"{c['to_label']}\"")
        print()

    if not candidates:
        print("  추천 없음")


def print_delta_report(delta: dict) -> None:
    print(f"\n── v4 실측 결과 ────────────────────────────────────────")
    print(f"  추가 엣지: {delta['n_added']}개")
    print()
    print(f"  E_v4: {delta['E_v4_before']:.4f} → {delta['E_v4_after']:.4f}  ({delta['E_v4_delta']:+.4f})")
    print(f"  E_v3: {delta['E_v3_before']:.4f} → {delta['E_v3_after']:.4f}  ({delta['E_v3_delta']:+.4f})")
    print()
    gap_sign = "+" if delta["gap_after"] >= 0 else ""
    print(f"  Δ(E_v4 - E_v3) before: {delta['gap_before']:+.4f}")
    print(f"  Δ(E_v4 - E_v3) after:  {gap_sign}{delta['gap_after']:.4f}")
    print(f"  gap 변화:               {delta['gap_delta']:+.4f}")
    print()
    if delta["v4_success"]:
        print(f"  ✅ 실험 B 성공: E_v4 > E_v3 (gap={delta['gap_after']:+.4f})")
    else:
        print(f"  ❌ 실험 B 실패: E_v4 ≤ E_v3 (gap={delta['gap_after']:+.4f})")
        print(f"     CSER 손실이 edge_span 이득을 상쇄. v3 역설 구조 지속.")
    print()
    print(f"  CSER: {delta['CSER_before']:.4f} → {delta['CSER_after']:.4f}")
    print(f"  DCI:  {delta['DCI_before']:.4f} → {delta['DCI_after']:.4f}")
    print(f"  edge_span: {delta['edge_span_before']:.3f} → {delta['edge_span_after']:.3f}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    kg   = load_kg()

    top_n = 20
    add_n = 0

    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            try: top_n = int(args[i + 1])
            except ValueError: pass
        if arg == "--add" and i + 1 < len(args):
            try: add_n = int(args[i + 1])
            except ValueError: add_n = top_n

    if "--verify" in args:
        log = load_log()
        if not log["sessions"]:
            print("기록 없음")
            return
        print(json.dumps(log["sessions"][-1], ensure_ascii=False, indent=2))
        return

    print(f"  KG: {len(kg['nodes'])} 노드 / {len(kg['edges'])} 엣지")
    print(f"  모드: v4 (CSER 제약 없음 — edge_span 직접 최적화)\n")

    candidates = rank_candidates(kg)

    if "--json" in args:
        print(json.dumps({
            "version":    VERSION,
            "candidates": candidates[:top_n],
            "total_pool": len(candidates),
            "params": {
                "top_n":        top_n,
                "W_EDGE_SPAN":  W_EDGE_SPAN,
                "W_NODE_AGE":   W_NODE_AGE,
                "W_CROSS":      W_CROSS,
            },
        }, ensure_ascii=False, indent=2))
        return

    if add_n > 0:
        n = min(add_n, len(candidates))
        if n == 0:
            print("추천 후보 없음")
            return

        print(f"═══ pair_designer v4 --add {n} ═══\n")
        selected = candidates[:n]
        cross_n  = sum(1 for s in selected if s["cross_source"])
        print(f"  선택: {n}개 — 교차출처: {cross_n}개 / 동일출처: {n - cross_n}개")

        updated_kg, added, delta = add_edges_to_kg(kg, selected)
        save_kg(updated_kg)
        print_delta_report(delta)

        log = load_log()
        log["sessions"].append({
            "date":         str(date.today()),
            "version":      VERSION,
            "cycle":        CYCLE,
            "n_added":      len(added),
            "cross_count":  cross_n,
            "delta":        delta,
            "added_edges": [
                {
                    "id":             e["id"],
                    "from":           e["from"],
                    "to":             e["to"],
                    "relation":       e["relation"],
                    "span":           e["meta"]["span"],
                    "edge_span_norm": e["meta"]["edge_span_norm"],
                    "combined_v4":    e["meta"]["combined_v4"],
                    "cross_source":   e["meta"]["cross_source"],
                }
                for e in added
            ],
        })
        save_log(log)
        print(f"\n  ✅ {len(added)}개 엣지 추가 → data/knowledge-graph.json")
        print(f"  로그 → data/pair_designer_v4_log.json")
        return

    print_recommendations(candidates, top_n)


if __name__ == "__main__":
    main()
