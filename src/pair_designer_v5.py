#!/usr/bin/env python3
"""
pair_designer_v5.py — KG 자가 최적화 엔진 v5 (age_contrib 독립 계산 + cross-ratio 강제)

v4 버그 (D-115, D-116):
  age_contrib = edge_span_norm (동일 값 재사용 → 역할 혼재)
  실질적으로 0.80 * edge_span_norm + 0.20 * cross_flag로 작동.
  node_age_diversity가 독립 변수로 기능하지 않음.

v5 수정 (3항목):
  1. age_contrib 독립 계산: 두 노드의 cycle 기반 나이 평균 / max_cycle
  2. --min-span N: MIN_SPAN 상수를 CLI 옵션으로 대체
  3. --cross-ratio R: top-N 선택 시 최소 R 비율을 cross-source로 강제

combined_v5 = 0.50×edge_span_norm + 0.30×age_contrib + 0.20×cross_bonus

사용법:
  python3 src/pair_designer_v5.py                          # 상위 20개 추천
  python3 src/pair_designer_v5.py --top 15                 # 상위 15개
  python3 src/pair_designer_v5.py --json                   # JSON 출력
  python3 src/pair_designer_v5.py --json --cross-ratio 0.5 # cross_source_ratio 포함
  python3 src/pair_designer_v5.py --add N --cross-ratio 0.5 --min-span 60
  python3 src/pair_designer_v5.py --verify                 # 마지막 추가 결과 출력
  python3 src/pair_designer_v5.py --compare                # v4 vs v5 선택 비교

구현: cokac-bot — D-116
"""

import argparse
import json
import re
import sys
import statistics
from pathlib import Path
from datetime import date
from itertools import combinations

REPO = Path(__file__).parent.parent
KG_FILE     = REPO / "data" / "knowledge-graph.json"
RESULT_FILE = REPO / "data" / "pair_designer_v5_log.json"

VERSION = "v5"

# --- v5 핵심 상수 ---

W_EDGE_SPAN  = 0.50   # edge_span_norm 기여 (E_v4 γ=0.25 직접 최적화)
W_NODE_AGE   = 0.30   # age_contrib 기여 (E_v4 δ=0.15 직접 최적화) — v5: 독립 계산
W_CROSS      = 0.20   # 교차출처 보너스 (D-033 원칙)

# DCI feeding 관계 필터
DCI_FEEDING_RELATIONS = {"answers", "addresses"}

# 출처 분류
LOKI_SOURCES  = {"록이", "상록"}
COKAC_SOURCES = {"cokac", "cokac-bot"}

# --- 타입 호환성 행렬 (v4 동일) ---
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


# --- I/O ---

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
            "description": "pair_designer v5 이력 (age_contrib 독립 계산 + cross-ratio 강제)",
            "version": VERSION,
        },
        "sessions": [],
    }


def save_log(data: dict) -> None:
    RESULT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# --- 유틸 ---

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
        return ("resonates_with", f"{t1}<>{t2} 공명")
    return rel, lbl


def classify_source(src: str) -> str:
    if src in LOKI_SOURCES:  return "록이"
    if src in COKAC_SOURCES: return "cokac"
    return "기타"


def is_cross_source(n1: dict, n2: dict) -> bool:
    t1 = classify_source(n1.get("source", ""))
    t2 = classify_source(n2.get("source", ""))
    return t1 != t2 and "기타" not in (t1, t2)


# --- v5 핵심: age_contrib 독립 계산 ---

def score_pair_v5(n1: dict, n2: dict, max_node_id: int, max_cycle: int) -> dict:
    """
    v5 점수 계산.
    combined_v5 = W_EDGE_SPAN * edge_span_norm + W_NODE_AGE * age_contrib + W_CROSS * cross_flag

    v4 버그 수정: age_contrib를 edge_span_norm에서 분리.
    age_contrib = (node_a.cycle + node_b.cycle) / 2 / max_cycle
    """
    id1  = node_num(n1["id"])
    id2  = node_num(n2["id"])
    span = abs(id1 - id2)

    edge_span_norm = span / max_node_id if max_node_id > 0 else 0.0

    # v5 수정: age_contrib 독립 계산 (v4 버그 수정)
    # 두 노드의 cycle 기반 나이 평균 / max_cycle
    cycle_a = n1.get("cycle", id1)  # cycle 필드 없으면 node_id를 프록시로
    cycle_b = n2.get("cycle", id2)
    age_contrib = ((cycle_a + cycle_b) / 2 / max_cycle) if max_cycle > 0 else 0.0

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

    # 의미론적 점수 (필터용)
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
        "suggested_label":    f"{n1.get('label','')[:25]}<>{n2.get('label','')[:25]}",
    }


def rank_candidates(kg: dict, min_span: int) -> list:
    """
    v5 후보 랭킹.
    CSER 제약 없음. DCI feeding 관계만 필터. min_span은 CLI 옵션.
    """
    nodes      = [n for n in kg["nodes"] if n["id"].startswith("n-")]
    max_nid    = max(node_num(n["id"]) for n in nodes)

    # max_cycle 계산 (age_contrib 독립 계산용)
    cycles = [n.get("cycle", node_num(n["id"])) for n in nodes]
    max_cycle = max(cycles) if cycles else 1

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
        if span < min_span:
            continue

        scored = score_pair_v5(n1, n2, max_nid, max_cycle)

        # DCI feeding 필터
        if scored["suggested_relation"] in DCI_FEEDING_RELATIONS:
            stats["filtered_dci"] += 1
            continue

        if scored["cross_source"]:
            stats["cross"] += 1
        else:
            stats["same"] += 1

        candidates.append(scored)

    print(f"  후보 풀 -- 교차출처: {stats['cross']}개 / 동일출처: {stats['same']}개"
          f"  (DCI 필터: {stats['filtered_dci']}개 제외)")

    candidates.sort(key=lambda x: -x["combined"])
    return candidates


# --- cross-ratio 강제 선택 ---

def select_with_cross_ratio(candidates: list, add_n: int, cross_ratio: float) -> list:
    """
    v5 신규: --cross-ratio R 적용.
    상위 add_n개 중 최소 cross_ratio 비율을 cross-source 쌍으로 강제.
    """
    candidates_cross = [p for p in candidates if p["cross_source"]]
    candidates_same  = [p for p in candidates if not p["cross_source"]]

    n_cross = int(add_n * cross_ratio)
    n_same  = add_n - n_cross

    # 부족한 경우 가용한 만큼 채우기
    actual_cross = candidates_cross[:n_cross]
    actual_same  = candidates_same[:n_same]

    # cross가 부족하면 same으로 보충, 반대도 동일
    remaining = add_n - len(actual_cross) - len(actual_same)
    if remaining > 0:
        if len(actual_cross) < n_cross:
            actual_same = candidates_same[:n_same + remaining]
        else:
            actual_cross = candidates_cross[:n_cross + remaining]

    selected = actual_cross + actual_same
    # combined 점수 기준 재정렬
    selected.sort(key=lambda x: -x["combined"])
    return selected[:add_n]


# --- E_v4 / E_v3 delta 측정 ---

def compute_delta(kg: dict, additions: list) -> dict:
    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics

    before = compute_all_metrics(kg)
    test_kg = {"nodes": kg["nodes"], "edges": kg["edges"] + additions}
    after  = compute_all_metrics(test_kg)

    return {
        "E_v4_before":  before["E_v4"],
        "E_v4_after":   after["E_v4"],
        "E_v4_delta":   round(after["E_v4"] - before["E_v4"], 4),
        "E_v3_before":  before["E_v3"],
        "E_v3_after":   after["E_v3"],
        "E_v3_delta":   round(after["E_v3"] - before["E_v3"], 4),
        "E_v5_before":  before["E_v5"],
        "E_v5_after":   after["E_v5"],
        "E_v5_delta":   round(after["E_v5"] - before["E_v5"], 4),
        "gap_before":   round(before["E_v4"] - before["E_v3"], 4),
        "gap_after":    round(after["E_v4"]  - after["E_v3"],  4),
        "gap_delta":    round((after["E_v4"] - after["E_v3"]) - (before["E_v4"] - before["E_v3"]), 4),
        "CSER_before":  before["CSER"],
        "CSER_after":   after["CSER"],
        "DCI_before":   before["DCI"],
        "DCI_after":    after["DCI"],
        "edge_span_before": before["edge_span"]["raw"],
        "edge_span_after":  after["edge_span"]["raw"],
        "n_added":      len(additions),
        "v4_success":   (after["E_v4"] - after["E_v3"]) > 0,
    }


# --- KG에 추가 ---

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
                "source":        "pair_designer_v5",
                "version":       VERSION,
                "date":          str(date.today()),
                "combined_v5":   c["combined"],
                "span":          c["span"],
                "edge_span_norm": c["edge_span_norm"],
                "age_contrib":   c["age_contrib"],
                "cross_source":  c["cross_source"],
                "dci_neutral":   True,
            },
        })

    updated_kg = {"nodes": kg["nodes"], "edges": kg["edges"] + new_edges}
    delta      = compute_delta(kg, new_edges)
    return updated_kg, new_edges, delta


# --- 출력 ---

def print_recommendations(candidates: list, top_n: int) -> None:
    n = min(top_n, len(candidates))
    cross_n = sum(1 for c in candidates[:n] if c["cross_source"])
    print("=== pair_designer v5 -- age_contrib 독립 + cross-ratio 강제 (D-116) ===")
    print(f"후보: {len(candidates)}쌍  |  상위 {n}개")
    print(f"combined_v5 = {W_EDGE_SPAN}*edge_span_norm + {W_NODE_AGE}*age_contrib(독립) + {W_CROSS}*cross_flag")
    print(f"CSER 제약: 없음 (v3 역설 탈출)")
    print(f"상위 {n}개 중 교차출처: {cross_n}개")
    print()

    for i, c in enumerate(candidates[:n], 1):
        cross_tag = " [교차]" if c["cross_source"] else ""
        print(f"  [{i:>2}] {c['from']}<>{c['to']}  combined={c['combined']:.4f}{cross_tag}")
        print(f"       {c['from_type']:<12} <> {c['to_type']:<12}  span={c['span']}")
        print(f"       edge_span_norm={c['edge_span_norm']:.4f}  age_contrib={c['age_contrib']:.4f}  semantic={c['semantic_score']:.4f}")
        print(f"       \"{c['from_label']}\"")
        print(f"       -> [{c['suggested_relation']}]")
        print(f"       \"{c['to_label']}\"")
        print()

    if not candidates:
        print("  추천 없음")


def print_delta_report(delta: dict) -> None:
    print(f"\n-- v5 실측 결과 --")
    print(f"  추가 엣지: {delta['n_added']}개")
    print()
    print(f"  E_v4: {delta['E_v4_before']:.4f} -> {delta['E_v4_after']:.4f}  ({delta['E_v4_delta']:+.4f})")
    print(f"  E_v3: {delta['E_v3_before']:.4f} -> {delta['E_v3_after']:.4f}  ({delta['E_v3_delta']:+.4f})")
    print(f"  E_v5: {delta['E_v5_before']:.4f} -> {delta['E_v5_after']:.4f}  ({delta['E_v5_delta']:+.4f})")
    print()
    print(f"  gap(E_v4 - E_v3) before: {delta['gap_before']:+.4f}")
    print(f"  gap(E_v4 - E_v3) after:  {delta['gap_after']:+.4f}")
    print(f"  gap 변화:                 {delta['gap_delta']:+.4f}")
    print()
    if delta["v4_success"]:
        print(f"  [OK] E_v4 > E_v3 (gap={delta['gap_after']:+.4f})")
    else:
        print(f"  [FAIL] E_v4 <= E_v3 (gap={delta['gap_after']:+.4f})")
    print()
    print(f"  CSER: {delta['CSER_before']:.4f} -> {delta['CSER_after']:.4f}")
    print(f"  DCI:  {delta['DCI_before']:.4f} -> {delta['DCI_after']:.4f}")
    print(f"  edge_span: {delta['edge_span_before']:.3f} -> {delta['edge_span_after']:.3f}")


# --- CLI ---

def parse_args():
    parser = argparse.ArgumentParser(description="pair_designer v5 -- age_contrib 독립 + cross-ratio 강제")
    parser.add_argument("--top", type=int, default=20, help="상위 N개 추천")
    parser.add_argument("--add", type=int, default=0, help="KG에 N개 추가")
    parser.add_argument("--min-span", type=int, default=20, help="최소 span (엣지 길이 하한)")
    parser.add_argument("--cross-ratio", type=float, default=0.5, help="최소 cross-source 비율 (0.0~1.0)")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    parser.add_argument("--verify", action="store_true", help="마지막 추가 결과 출력")
    parser.add_argument("--compare", action="store_true", help="v4 vs v5 선택 비교")
    return parser.parse_args()


def main():
    args = parse_args()
    kg   = load_kg()

    if args.verify:
        log = load_log()
        if not log["sessions"]:
            print("기록 없음")
            return
        print(json.dumps(log["sessions"][-1], ensure_ascii=False, indent=2))
        return

    print(f"  KG: {len(kg['nodes'])} 노드 / {len(kg['edges'])} 엣지")
    print(f"  모드: v5 (age_contrib 독립 계산 + cross-ratio={args.cross_ratio})")
    print(f"  min_span: {args.min_span}\n")

    candidates = rank_candidates(kg, args.min_span)

    if args.json and args.add == 0:
        # --json 단독: 추천만 출력 (cross_source_ratio 포함)
        top_candidates = candidates[:args.top]
        if args.cross_ratio > 0:
            top_candidates = select_with_cross_ratio(candidates, args.top, args.cross_ratio)

        n_cross_actual = sum(1 for c in top_candidates if c["cross_source"])
        cross_source_ratio = n_cross_actual / len(top_candidates) if top_candidates else 0.0

        print(json.dumps({
            "version":            VERSION,
            "candidates":         top_candidates,
            "total_pool":         len(candidates),
            "cross_source_ratio": round(cross_source_ratio, 4),
            "params": {
                "top_n":        args.top,
                "min_span":     args.min_span,
                "cross_ratio":  args.cross_ratio,
                "W_EDGE_SPAN":  W_EDGE_SPAN,
                "W_NODE_AGE":   W_NODE_AGE,
                "W_CROSS":      W_CROSS,
            },
        }, ensure_ascii=False, indent=2))
        return

    if args.add > 0:
        n = min(args.add, len(candidates))
        if n == 0:
            print("추천 후보 없음")
            return

        # cross-ratio 강제 선택
        selected = select_with_cross_ratio(candidates, n, args.cross_ratio)
        cross_n  = sum(1 for s in selected if s["cross_source"])
        cross_source_ratio = cross_n / len(selected) if selected else 0.0

        print(f"=== pair_designer v5 --add {n} --cross-ratio {args.cross_ratio} ===\n")
        print(f"  선택: {len(selected)}개 -- 교차출처: {cross_n}개 / 동일출처: {len(selected) - cross_n}개")
        print(f"  cross_source_ratio: {cross_source_ratio:.4f}")

        if cross_source_ratio < args.cross_ratio:
            print(f"  [WARN] cross_source_ratio {cross_source_ratio:.4f} < 목표 {args.cross_ratio}")
            print(f"         교차출처 후보 부족 ({sum(1 for c in candidates if c['cross_source'])}개)")

        updated_kg, added, delta = add_edges_to_kg(kg, selected)
        save_kg(updated_kg)
        print_delta_report(delta)

        log = load_log()
        log["sessions"].append({
            "date":               str(date.today()),
            "version":            VERSION,
            "n_added":            len(added),
            "cross_count":        cross_n,
            "cross_source_ratio": round(cross_source_ratio, 4),
            "cross_ratio_target": args.cross_ratio,
            "min_span":           args.min_span,
            "delta":              delta,
            "added_edges": [
                {
                    "id":             e["id"],
                    "from":           e["from"],
                    "to":             e["to"],
                    "relation":       e["relation"],
                    "span":           e["meta"]["span"],
                    "edge_span_norm": e["meta"]["edge_span_norm"],
                    "age_contrib":    e["meta"]["age_contrib"],
                    "combined_v5":    e["meta"]["combined_v5"],
                    "cross_source":   e["meta"]["cross_source"],
                }
                for e in added
            ],
        })
        save_log(log)
        print(f"\n  [OK] {len(added)}개 엣지 추가 -> data/knowledge-graph.json")
        print(f"  로그 -> data/pair_designer_v5_log.json")
        return

    if args.compare:
        # v4 vs v5 비교: 동일 후보에 대해 두 점수 비교
        sys.path.insert(0, str(REPO))
        from src.pair_designer_v4 import rank_candidates as rank_v4
        v4_candidates = rank_v4(kg)
        v5_candidates = candidates

        print("=== v4 vs v5 상위 10개 비교 ===\n")
        print(f"{'순위':>4} | {'v4 combined':>12} | {'v5 combined':>12} | {'v4 age_contrib':>14} | {'v5 age_contrib':>14} | pair")
        print("-" * 90)
        for i in range(min(10, len(v4_candidates), len(v5_candidates))):
            v4c = v4_candidates[i]
            v5c = v5_candidates[i]
            print(f"  {i+1:>2} | {v4c['combined']:>12.4f} | {v5c['combined']:>12.4f} | {v4c['age_contrib']:>14.4f} | {v5c['age_contrib']:>14.4f} | {v5c['from']}<>{v5c['to']}")
        return

    print_recommendations(candidates, args.top)


if __name__ == "__main__":
    main()
