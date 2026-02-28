#!/usr/bin/env python3
"""
pair_designer_v2.py — KG 자가 최적화 엔진 v2 (DCI 중립 모드)

사이클 58, n-144 self-wiring 승인 구현.

v1 → v2 핵심 변경:
  1. DCI 중립 관계 집합: answers/addresses 완전 제거
     → resonates_with, extends, parallel_to, grounds, contextualizes
  2. 사전 DCI 시뮬레이션 필터: 엣지 추가 전 DCI 변화량 계산, 초과 시 제외
  3. e_v4_gain_excl_dci 지표: DCI 기여 제외 순수 edge_span 기여 격리
     → e_v4_gain_excl_dci = E_v4_delta - 0.25 * DCI_delta

설계 원칙 (n-143 결론):
  - DCI 왜곡 = pair_designer가 (insight, question) 쌍에 answers 붙인 부작용
  - 해결: DCI에 영향을 주는 관계 타입을 아예 사용하지 않는다
  - MAX_DCI_DELTA_PER_EDGE = 0.0001: DCI 변화가 이보다 크면 후보 제외

사용법:
  python3 src/pair_designer_v2.py              # 상위 20개 추천
  python3 src/pair_designer_v2.py --top 15     # 상위 15개
  python3 src/pair_designer_v2.py --json       # JSON 출력
  python3 src/pair_designer_v2.py --add N      # KG에 추가 + E_v4 측정
  python3 src/pair_designer_v2.py --add N --min-span 30  # min_span 30 이상만
  python3 src/pair_designer_v2.py --verify     # 마지막 추가 결과 출력
  python3 src/pair_designer_v2.py --dci-check  # 현재 DCI 기여 엣지 진단

구현: cokac-bot (사이클 58)
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
RESULT_FILE = REPO / "data" / "pair_designer_v2_log.json"

VERSION = "v2"
CYCLE = 58

# DCI 왜곡을 유발하는 관계 — 이 목록에 있는 관계는 절대 사용하지 않는다
DCI_FEEDING_RELATIONS = {"answers", "addresses"}

# DCI 변화 허용 상한 (per edge)
# = 0.0001: 사실상 0 — DCI 순증을 완전 차단
MAX_DCI_DELTA_PER_EDGE = 0.0001

# ─── 타입 호환성 행렬 ─────────────────────────────────────────────────────────
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

# ─── DCI 중립 관계 힌트 (v2 핵심) ────────────────────────────────────────────
# answers / addresses 완전 제거 → resonates_with / contextualizes / parallel_to 대체
RELATION_HINT_V2 = {
    # v1에서 'answers'였던 것 → resonates_with (DCI 중립)
    ("insight",     "question"):    ("resonates_with", "인사이트가 질문과 공명한다"),
    # v1에서 'addresses'였던 것 → contextualizes (DCI 중립)
    ("observation", "question"):    ("contextualizes", "관찰이 질문의 맥락을 제공한다"),
    # v1에서 'predicts_for'였던 것 → parallel_to (DCI 중립)
    ("prediction",  "question"):    ("parallel_to",    "예측이 질문과 병렬로 전개된다"),
    # 아래는 DCI에 영향 없는 관계 — v1과 동일하게 유지
    ("prediction",  "observation"): ("validated_by",   "관찰이 예측을 검증한다"),
    ("prediction",  "insight"):     ("informed_by",    "예측이 인사이트에 근거한다"),
    ("insight",     "insight"):     ("extends",        "인사이트가 다른 인사이트를 확장한다"),
    ("insight",     "observation"): ("grounds",        "인사이트가 관찰에 근거한다"),
    ("insight",     "decision"):    ("supports",       "인사이트가 결정을 지지한다"),
    ("observation", "experiment"):  ("evidence_for",   "관찰이 실험 증거가 된다"),
    ("prediction",  "experiment"):  ("tested_by",      "예측이 실험으로 검증된다"),
    ("finding",     "insight"):     ("generalizes",    "발견이 인사이트로 일반화된다"),
    ("synthesis",   "insight"):     ("synthesizes",    "합성이 인사이트를 통합한다"),
    # 새 DCI-중립 관계 (v2 추가)
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
    # meta 키 보존 (kg.py와 호환성 유지)
    if "meta" not in kg:
        existing_nums = [int(n["id"].split("-")[1]) for n in kg["nodes"] if n["id"].startswith("n-")]
        next_num = (max(existing_nums) + 1) if existing_nums else 1
        kg["meta"] = {
            "next_node_id": f"n-{next_num:03d}",
            "last_updated": "2026-02-28",
            "total_nodes": len(kg["nodes"]),
            "total_edges": len(kg["edges"]),
        }
    else:
        kg["meta"]["total_nodes"] = len(kg["nodes"])
        kg["meta"]["total_edges"] = len(kg["edges"])
    KG_FILE.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def load_log() -> dict:
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return {
        "meta": {
            "description": "pair_designer v2 추천/추가 이력 (DCI 중립 모드)",
            "created_cycle": CYCLE,
            "version": VERSION,
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
    words = re.split(r"[\s\n\r\t\u3000.,!?;:「」『』【】()（）\-_/]+", text.lower())
    return {w for w in words if len(w) >= 2 and not w.isdigit()}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def type_compat(t1: str, t2: str) -> float:
    key = tuple(sorted([t1, t2]))
    return TYPE_COMPAT.get(key, DEFAULT_COMPAT)


def infer_relation_v2(t1: str, t2: str) -> tuple:
    """
    DCI 중립 관계 레이블 추론.
    answers / addresses 는 절대 반환하지 않는다.
    """
    key = tuple(sorted([t1, t2]))
    rel, label = RELATION_HINT_V2.get(key, DEFAULT_RELATION)
    # 안전망: DCI feeding 관계가 들어오면 resonates_with로 교체
    if rel in DCI_FEEDING_RELATIONS:
        return ("resonates_with", f"{t1}↔{t2} 공명")
    return rel, label


# ─── DCI 시뮬레이션 ───────────────────────────────────────────────────────────

def _compute_dci_raw(kg: dict) -> tuple:
    """
    (gap_sum, total_questions, total_nodes, answers_map) 반환.
    DCI = min(1.0, gap_sum / (total_questions * total_nodes))
    """
    nodes = kg["nodes"]
    edges = kg["edges"]
    questions = {n["id"] for n in nodes if n.get("type") == "question"}
    total_questions = len(questions)
    total_nodes = len(nodes)

    answers_map = {}  # qid → max_gap
    for e in edges:
        if e.get("relation") not in ("answers",):
            continue
        src, tgt = e["from"], e["to"]
        if src in questions:
            gap = abs(node_num(tgt) - node_num(src))
            answers_map[src] = max(answers_map.get(src, 0), gap)
        if tgt in questions:
            gap = abs(node_num(src) - node_num(tgt))
            answers_map[tgt] = max(answers_map.get(tgt, 0), gap)

    gap_sum = sum(answers_map.values())
    return gap_sum, total_questions, total_nodes, answers_map


def simulate_dci_delta(kg: dict, candidate: dict) -> float:
    """
    이 후보 엣지를 추가했을 때 DCI 변화량 사전 계산.
    DCI는 오직 'answers' 관계만 영향. v2는 answers를 쓰지 않으므로 항상 0.0이어야 함.
    그러나 혹시 오염된 관계가 들어올 경우를 대비한 안전 검사.
    """
    rel = candidate["suggested_relation"]
    if rel not in DCI_FEEDING_RELATIONS:
        return 0.0  # DCI 중립 관계 → 변화 없음

    # DCI feeding 관계가 들어온 경우 (이론상 v2에서 발생하지 않아야 함)
    gap_sum_before, total_q, total_n, answers_map = _compute_dci_raw(kg)
    if total_q == 0 or total_n == 0:
        return 0.0

    dci_before = min(1.0, gap_sum_before / (total_q * total_n))

    questions = {n["id"] for n in kg["nodes"] if n.get("type") == "question"}
    from_id, to_id = candidate["from"], candidate["to"]
    new_map = dict(answers_map)

    if rel == "answers":
        if from_id in questions:
            gap = abs(node_num(to_id) - node_num(from_id))
            new_map[from_id] = max(new_map.get(from_id, 0), gap)
        if to_id in questions:
            gap = abs(node_num(from_id) - node_num(to_id))
            new_map[to_id] = max(new_map.get(to_id, 0), gap)

    dci_after = min(1.0, sum(new_map.values()) / (total_q * total_n))
    return round(dci_after - dci_before, 6)


# ─── 핵심: 점수 계산 ──────────────────────────────────────────────────────────

def score_pair(n1: dict, n2: dict, max_node_id: int) -> dict:
    """
    단일 노드 쌍 점수 계산 + DCI 시뮬레이션 포함.
    """
    id1 = node_num(n1["id"])
    id2 = node_num(n2["id"])
    span = abs(id1 - id2)

    span_score = span / max_node_id if max_node_id > 0 else 0.0

    tags1 = set(n1.get("tags", []))
    tags2 = set(n2.get("tags", []))
    tag_sim = jaccard(tags1, tags2)

    t_compat = type_compat(n1.get("type", ""), n2.get("type", ""))

    content1 = tokenize(n1.get("content", "") + " " + n1.get("label", ""))
    content2 = tokenize(n2.get("content", "") + " " + n2.get("label", ""))
    content_sim = jaccard(content1, content2)

    semantic_score = 0.40 * tag_sim + 0.35 * t_compat + 0.25 * content_sim

    relation, label_tmpl = infer_relation_v2(n1.get("type", ""), n2.get("type", ""))

    raw_e_v4_gain = span  # 후처리 정규화용 proxy

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
        "raw_e_v4_gain": raw_e_v4_gain,
        "suggested_relation": relation,
        "suggested_label": f"{n1.get('label','')[:25]}↔{n2.get('label','')[:25]}",
        "dci_delta": 0.0,  # v2에서는 항상 0 (사후 확인용 필드)
    }


def rank_candidates(kg: dict, min_span: int = 20, min_semantic: float = 0.25) -> list:
    """
    전체 미연결 노드 쌍 스캔 + DCI 시뮬레이션 필터 적용.

    v2 변경:
    - DCI 변화 > MAX_DCI_DELTA_PER_EDGE 인 후보 제외
    - (v2 관계 집합에서 answers를 쓰지 않으므로 이론상 필터가 발동하지 않음)
    """
    nodes = [n for n in kg["nodes"] if n["id"].startswith("n-")]
    max_node_id = max(node_num(n["id"]) for n in nodes)

    existing = set()
    for e in kg["edges"]:
        existing.add((e["from"], e["to"]))
        existing.add((e["to"], e["from"]))

    candidates = []
    dci_filtered = 0

    for n1, n2 in combinations(nodes, 2):
        if (n1["id"], n2["id"]) in existing:
            continue
        span = abs(node_num(n1["id"]) - node_num(n2["id"]))
        if span < min_span:
            continue

        scored = score_pair(n1, n2, max_node_id)

        if scored["semantic_score"] < min_semantic:
            continue

        # DCI 시뮬레이션 필터 (v2 핵심)
        dci_delta = simulate_dci_delta(kg, scored)
        scored["dci_delta"] = round(dci_delta, 6)

        if dci_delta > MAX_DCI_DELTA_PER_EDGE:
            dci_filtered += 1
            continue

        candidates.append(scored)

    if dci_filtered > 0:
        print(f"  ⚠️  DCI 필터: {dci_filtered}개 후보 제외 (DCI delta > {MAX_DCI_DELTA_PER_EDGE})")

    if not candidates:
        return candidates

    # E_v4 gain 정규화
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


# ─── E_v4 측정 + excl_dci 지표 ───────────────────────────────────────────────

def compute_e_v4_delta_for_additions(kg: dict, additions: list) -> dict:
    """
    엣지 추가 후 E_v4 변화 측정.

    v2 추가:
    - e_v4_gain_excl_dci: DCI 기여 완전 제외 순수 edge_span 기여
      = E_v4_delta - 0.25 * DCI_delta
      → DCI가 변해도 이 값은 순수 edge_span 효과만 반영
    """
    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics

    before = compute_all_metrics(kg)

    test_kg = {
        "nodes": kg["nodes"],
        "edges": kg["edges"] + additions,
    }
    after = compute_all_metrics(test_kg)

    e_v4_delta = round(after["E_v4"] - before["E_v4"], 4)
    dci_delta = round(after["DCI"] - before["DCI"], 4)

    # e_v4_gain_excl_dci: DCI 변화분 제거
    # E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span + 0.15*node_age
    # → DCI 기여: 0.25 * DCI_delta
    e_v4_gain_excl_dci = round(e_v4_delta - 0.25 * dci_delta, 4)

    return {
        "e_v4_before": before["E_v4"],
        "e_v4_after": after["E_v4"],
        "delta": e_v4_delta,
        "e_v4_gain_excl_dci": e_v4_gain_excl_dci,  # ← v2 핵심 지표
        "dci_delta": dci_delta,
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
                "source": "pair_designer_v2",
                "version": VERSION,
                "cycle": CYCLE,
                "date": str(date.today()),
                "combined_score": c["combined"],
                "span": c["span"],
                "semantic_score": c["semantic_score"],
                "dci_delta": c.get("dci_delta", 0.0),
                "dci_neutral": True,
            },
        }
        new_edges.append(edge)

    updated_kg = {
        "nodes": kg["nodes"],
        "edges": kg["edges"] + new_edges,
    }

    delta = compute_e_v4_delta_for_additions(kg, new_edges)
    return updated_kg, new_edges, delta


# ─── DCI 진단 ─────────────────────────────────────────────────────────────────

def cmd_dci_check(kg: dict) -> None:
    """현재 KG에서 DCI를 유발하는 answers 엣지 진단."""
    answers_edges = [e for e in kg["edges"] if e.get("relation") == "answers"]
    questions = {n["id"]: n for n in kg["nodes"] if n.get("type") == "question"}

    print("═══ DCI 진단 (pair_designer v2) ═══")
    print(f"총 answers 엣지: {len(answers_edges)}개")
    print(f"question 노드: {len(questions)}개")
    print()

    pd_answers = [e for e in answers_edges if e.get("meta", {}).get("source") == "pair_designer"]
    other_answers = [e for e in answers_edges if e.get("meta", {}).get("source") != "pair_designer"]

    print(f"  pair_designer v1 유발 answers: {len(pd_answers)}개  ← DCI 왜곡 원인")
    print(f"  기타 answers (자연 생성): {other_answers and len(other_answers) or 0}개")
    print()

    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics, compute_dci
    m = compute_all_metrics(kg)
    print(f"현재 DCI: {m['DCI']:.4f}")

    # pair_designer 유발 answers 제거 시 DCI
    kg_without_pd = {
        "nodes": kg["nodes"],
        "edges": [e for e in kg["edges"] if e not in pd_answers],
    }
    dci_without_pd = compute_dci(kg_without_pd)
    print(f"v1 answers 제거 시 DCI: {dci_without_pd:.4f}  (순수 DCI)")
    print(f"DCI 왜곡량: +{m['DCI'] - dci_without_pd:.4f}  ← pair_designer v1 인위 기여")
    print()
    print("→ pair_designer v2는 DCI feeding 관계를 사용하지 않습니다.")
    print(f"  새 추가 엣지의 suggested_relation ∉ {DCI_FEEDING_RELATIONS}")


# ─── 출력 ─────────────────────────────────────────────────────────────────────

def print_recommendations(candidates: list, top_n: int = 20) -> None:
    print("═══ pair_designer v2 — DCI 중립 KG 최적화 추천 (사이클 58) ═══")
    print(f"후보 풀: {len(candidates)}쌍  |  상위 {min(top_n, len(candidates))}개 표시")
    print(f"가중치: span=0.35  semantic=0.35  E_v4_gain=0.30")
    print(f"필터: min_span≥20, min_semantic≥0.25, DCI_delta≤{MAX_DCI_DELTA_PER_EDGE}")
    print(f"관계: resonates_with / extends / parallel_to / grounds / contextualizes (answers 없음)")
    print()

    for i, c in enumerate(candidates[:top_n], 1):
        span_bar = "█" * min(int(c["span"] / 10), 12) + f" ({c['span']})"
        dci_tag = "" if c.get("dci_delta", 0) == 0 else f"  [DCI Δ{c['dci_delta']:+.4f}]"
        print(f"  [{i:>2}] {c['from']}↔{c['to']}  combined={c['combined']:.4f}{dci_tag}")
        print(f"       {c['from_type']:<12} ↔ {c['to_type']:<12}  span={span_bar}")
        print(f"       span={c['span_score']:.3f}  sem={c['semantic_score']:.3f}"
              f"  (tag={c['tag_sim']:.2f} tc={c['type_compat']:.2f} kw={c['content_sim']:.2f})"
              f"  ev4={c['e_v4_gain_norm']:.3f}")
        print(f"       \"{c['from_label']}\"")
        print(f"       → [{c['suggested_relation']}] →  (DCI 중립 ✓)")
        print(f"       \"{c['to_label']}\"")
        print()

    if len(candidates) == 0:
        print("  추천 없음 — min_span/min_semantic 조건을 낮춰보세요")

    top = candidates[:top_n]
    if top:
        avg_span = statistics.mean(c["span"] for c in top)
        avg_sem = statistics.mean(c["semantic_score"] for c in top)
        print(f"── 상위 {len(top)}개 통계 ─────────────────────────────")
        print(f"  평균 스팬     : {avg_span:.1f}")
        print(f"  평균 의미점수 : {avg_sem:.3f}")
        print(f"  장거리(≥50)  : {sum(1 for c in top if c['span'] >= 50)}개")
        print(f"  초장거리(≥80): {sum(1 for c in top if c['span'] >= 80)}개")
        print(f"  DCI 오염 없음: 모든 관계 ∉ {DCI_FEEDING_RELATIONS} ✅")
        print()
        print(f"  실행: python3 src/pair_designer_v2.py --add {top_n}")


def print_delta_report(delta: dict) -> None:
    arrow = "↑" if delta["delta"] >= 0 else "↓"
    sign = "+" if delta["delta"] >= 0 else ""
    excl_sign = "+" if delta["e_v4_gain_excl_dci"] >= 0 else ""

    print(f"\n── E_v4 실측 결과 (v2 DCI 중립) ───────────────────")
    print(f"  추가된 엣지        : {delta['n_added']}개")
    print(f"  E_v4               : {delta['e_v4_before']:.4f} → {delta['e_v4_after']:.4f}  ({sign}{delta['delta']:.4f} {arrow})")
    print(f"  e_v4_gain_excl_dci : {excl_sign}{delta['e_v4_gain_excl_dci']:.4f}  ← 순수 edge_span 기여 (DCI 제외)")
    print(f"  DCI 변화           : {delta['dci_before']:.4f} → {delta['dci_after']:.4f}  (Δ{delta['dci_delta']:+.4f})")
    print(f"  edge_span_raw      : {delta['edge_span_before']:.3f} → {delta['edge_span_after']:.3f}")
    print(f"  CSER               : {delta['cser_before']:.4f} → {delta['cser_after']:.4f}")

    if delta["dci_delta"] > 0.005:
        print(f"\n  ⚠️  DCI 증가 감지: {delta['dci_delta']:+.4f} — v2 버그 여부 확인 필요")
    else:
        print(f"\n  ✅ DCI 중립 확인: DCI 변화 {delta['dci_delta']:+.4f} (정상 범위)")

    if delta["e_v4_gain_excl_dci"] > 0.005:
        print(f"  ✅ n-115 재보정 지지: 순수 edge_span 기여 +{delta['e_v4_gain_excl_dci']:.4f}")
    elif delta["e_v4_gain_excl_dci"] > 0:
        print(f"  ⚠️  소폭 순수 상승: +{delta['e_v4_gain_excl_dci']:.4f} (더 많은 엣지 필요?)")
    else:
        print(f"  ❌ 순수 E_v4 하락: {delta['e_v4_gain_excl_dci']:.4f}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    kg = load_kg()

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

    if "--dci-check" in args:
        cmd_dci_check(kg)
        return

    if "--verify" in args:
        log = load_log()
        if not log["sessions"]:
            print("기록 없음")
            return
        last = log["sessions"][-1]
        print(json.dumps(last, ensure_ascii=False, indent=2))
        return

    candidates = rank_candidates(kg, min_span=min_span, min_semantic=0.25)

    if "--json" in args:
        output = {
            "version": VERSION,
            "candidates": candidates[:top_n],
            "total_pool": len(candidates),
            "params": {"top_n": top_n, "min_span": min_span},
            "dci_policy": {
                "feeding_relations": list(DCI_FEEDING_RELATIONS),
                "max_delta_per_edge": MAX_DCI_DELTA_PER_EDGE,
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if add_n > 0:
        n = min(add_n, len(candidates))
        if n == 0:
            print("추천 후보 없음 — 파라미터 조정 필요")
            return

        print(f"═══ pair_designer v2 --add {n} (DCI 중립) ═══")
        print(f"상위 {n}개 엣지를 KG에 추가합니다...\n")

        updated_kg, added, delta = add_edges_to_kg(kg, candidates, n)
        save_kg(updated_kg)

        print_delta_report(delta)

        log = load_log()
        session = {
            "date": str(date.today()),
            "version": VERSION,
            "cycle": CYCLE,
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
                    "dci_neutral": e["meta"]["dci_neutral"],
                }
                for e in added
            ],
        }
        log["sessions"].append(session)
        save_log(log)
        print(f"\n  ✅ {n}개 DCI-중립 엣지 추가 완료 → data/knowledge-graph.json")
        print(f"  로그 → data/pair_designer_v2_log.json")
        return

    print_recommendations(candidates, top_n)


if __name__ == "__main__":
    main()
