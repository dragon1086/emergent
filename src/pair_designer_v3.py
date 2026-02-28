#!/usr/bin/env python3
"""
pair_designer_v3.py — KG 자가 최적화 엔진 v3 (CSER 제약 + 교차출처 보너스)

사이클 59, n-150 설계결함 분석 → v3 구현.

v2 → v3 핵심 변경:
  1. cross_source_bonus = +0.30
     - 록이↔cokac 교차 쌍에 0.30 가산점
     - semantic_score 동일출처 우위 역전 (D-033: 경계 횡단 = 창발)

  2. CSER >= 0.65 제약 (신규)
     - 엣지 추가 후 CSER 유지 보장
     - 동일출처 엣지가 CSER 잠식하면 선택에서 제외

  3. 4차원 목표함수:
       max(E_v4) subject to:
         CSER >= 0.65          ← 신규 제약
         0.15 < distance < 0.30   (distance = span_score = span / max_node_id)
         1.20 < asymmetry < 2.50  (asymmetry = span_score / semantic_score)

  4. min_semantic 하향: 0.25 → 0.05
     - 교차출처 쌍은 의미론적 유사도가 낮음. cross_bonus로 보완.

v2 설계결함 (n-150):
  semantic_score가 동일출처 쌍(록이→록이)을 선호.
  cross_source_bonus 없이는 D-033(경계 횡단=창발) 위반.

4D 제약 설계 원리:
  - distance = span_score: 시간적 거리. 너무 가까우면 local, 너무 멀면 forced.
  - asymmetry = span_score / semantic_score: 시간 거리 대비 의미 차이 비율.
    높을수록 "의미론적으로 다른데 시간적으로 가까운" 연결.
    1.20~2.50이 "교차출처 자연 연결" 구간.
    동일출처 쌍은 semantic_score가 높아 asymmetry가 낮아짐 → 자연 필터.

사용법:
  python3 src/pair_designer_v3.py              # 상위 20개 추천
  python3 src/pair_designer_v3.py --top 15     # 상위 15개
  python3 src/pair_designer_v3.py --json       # JSON 출력
  python3 src/pair_designer_v3.py --add N      # KG에 추가 + E_v4 측정
  python3 src/pair_designer_v3.py --soft       # 4D 소프트 모드 (제약 위반 허용, 페널티만)
  python3 src/pair_designer_v3.py --verify     # 마지막 추가 결과 출력
  python3 src/pair_designer_v3.py --source-stats  # 교차출처 통계

구현: cokac-bot (사이클 60)
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
RESULT_FILE = REPO / "data" / "pair_designer_v3_log.json"

VERSION = "v3"
CYCLE = 60

# ─── v3 핵심 상수 ──────────────────────────────────────────────────────────────

# 록이↔cokac 교차 쌍 가산점 (D-033: 경계 횡단 = 창발)
CROSS_SOURCE_BONUS = 0.30

# CSER 하한 제약 (신규)
CSER_MIN = 0.65

# 4차원 목표함수 제약 범위
DISTANCE_MIN = 0.15   # span_score 하한
DISTANCE_MAX = 0.30   # span_score 상한
ASYMMETRY_MIN = 1.20  # span_score / semantic_score 하한
ASYMMETRY_MAX = 2.50  # span_score / semantic_score 상한

# DCI feeding 관계 — v2 정책 유지
DCI_FEEDING_RELATIONS = {"answers", "addresses"}
MAX_DCI_DELTA_PER_EDGE = 0.0001

# 교차출처 팀 분류
LOKI_SOURCES = {"록이", "상록"}
COKAC_SOURCES = {"cokac", "cokac-bot"}

# ─── 타입 호환성 행렬 (v2 동일) ───────────────────────────────────────────────
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

# ─── DCI 중립 관계 힌트 (v2 동일) ────────────────────────────────────────────
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
    if "meta" not in kg:
        existing_nums = [int(n["id"].split("-")[1]) for n in kg["nodes"] if n["id"].startswith("n-")]
        next_num = (max(existing_nums) + 1) if existing_nums else 1
        kg["meta"] = {
            "next_node_id": f"n-{next_num:03d}",
            "last_updated": str(date.today()),
            "total_nodes": len(kg["nodes"]),
            "total_edges": len(kg["edges"]),
        }
    else:
        kg["meta"]["total_nodes"] = len(kg["nodes"])
        kg["meta"]["total_edges"] = len(kg["edges"])
        kg["meta"]["last_updated"] = str(date.today())
    KG_FILE.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def load_log() -> dict:
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return {
        "meta": {
            "description": "pair_designer v3 이력 (CSER 제약 + 교차출처 보너스)",
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


def type_compat_score(t1: str, t2: str) -> float:
    key = tuple(sorted([t1, t2]))
    return TYPE_COMPAT.get(key, DEFAULT_COMPAT)


def infer_relation(t1: str, t2: str) -> tuple:
    key = tuple(sorted([t1, t2]))
    rel, label = RELATION_HINT.get(key, DEFAULT_RELATION)
    if rel in DCI_FEEDING_RELATIONS:
        return ("resonates_with", f"{t1}↔{t2} 공명")
    return rel, label


def classify_source(source: str) -> str:
    """출처를 팀으로 분류."""
    if source in LOKI_SOURCES:
        return "록이"
    if source in COKAC_SOURCES:
        return "cokac"
    return "기타"


def is_cross_source(n1: dict, n2: dict) -> bool:
    """두 노드가 록이↔cokac 교차 출처인지 판별."""
    t1 = classify_source(n1.get("source", ""))
    t2 = classify_source(n2.get("source", ""))
    return t1 != t2 and "기타" not in (t1, t2)


# ─── CSER 시뮬레이션 ──────────────────────────────────────────────────────────

def compute_cser_raw(kg: dict) -> tuple:
    """(cross_count, total_count) 반환."""
    node_src = {n["id"]: n.get("source", "") for n in kg["nodes"]}
    cross = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
    )
    return cross, len(kg["edges"])


def simulate_cser(kg: dict, new_pairs: list) -> float:
    """
    new_pairs: [(from_id, to_id, is_cross_source), ...] 추가 후 CSER 예측.
    """
    node_src = {n["id"]: n.get("source", "") for n in kg["nodes"]}
    cross_now, total_now = compute_cser_raw(kg)

    add_cross = sum(
        1 for (fid, tid, _) in new_pairs
        if node_src.get(fid, "") != node_src.get(tid, "")
    )
    total_new = total_now + len(new_pairs)
    if total_new == 0:
        return 0.0
    return round((cross_now + add_cross) / total_new, 4)


# ─── 4차원 제약 검사 ──────────────────────────────────────────────────────────

def check_4d(span_score: float, semantic_score: float) -> tuple:
    """
    4D 제약 검사.
    반환: (passes: bool, distance: float, asymmetry: float, reason: str)

    distance  = span_score
    asymmetry = span_score / (semantic_score + eps)
    """
    distance = span_score
    eps = 0.001
    asymmetry = span_score / (semantic_score + eps)

    if not (DISTANCE_MIN < distance < DISTANCE_MAX):
        return False, distance, asymmetry, f"distance {distance:.3f} ∉ ({DISTANCE_MIN},{DISTANCE_MAX})"
    if not (ASYMMETRY_MIN < asymmetry < ASYMMETRY_MAX):
        return False, distance, asymmetry, f"asymmetry {asymmetry:.3f} ∉ ({ASYMMETRY_MIN},{ASYMMETRY_MAX})"
    return True, distance, asymmetry, "OK"


# ─── 핵심: 점수 계산 ──────────────────────────────────────────────────────────

def score_pair(n1: dict, n2: dict, max_node_id: int) -> dict:
    id1 = node_num(n1["id"])
    id2 = node_num(n2["id"])
    span = abs(id1 - id2)
    span_score = span / max_node_id if max_node_id > 0 else 0.0

    tags1 = set(n1.get("tags", []))
    tags2 = set(n2.get("tags", []))
    tag_sim = jaccard(tags1, tags2)

    t_compat = type_compat_score(n1.get("type", ""), n2.get("type", ""))

    content1 = tokenize(n1.get("content", "") + " " + n1.get("label", ""))
    content2 = tokenize(n2.get("content", "") + " " + n2.get("label", ""))
    content_sim = jaccard(content1, content2)

    semantic_score = 0.40 * tag_sim + 0.35 * t_compat + 0.25 * content_sim

    cross = is_cross_source(n1, n2)
    passes_4d, distance, asymmetry, reason = check_4d(span_score, semantic_score)

    relation, _ = infer_relation(n1.get("type", ""), n2.get("type", ""))

    return {
        "from": n1["id"],
        "to": n2["id"],
        "from_label": n1.get("label", "")[:40],
        "to_label": n2.get("label", "")[:40],
        "from_type": n1.get("type", ""),
        "to_type": n2.get("type", ""),
        "from_source": n1.get("source", ""),
        "to_source": n2.get("source", ""),
        "span": span,
        "span_score": round(span_score, 4),
        "semantic_score": round(semantic_score, 4),
        "tag_sim": round(tag_sim, 4),
        "type_compat": round(t_compat, 4),
        "content_sim": round(content_sim, 4),
        "cross_source": cross,
        "distance": round(distance, 4),
        "asymmetry": round(asymmetry, 4),
        "passes_4d": passes_4d,
        "constraint_reason": reason,
        "raw_e_v4_gain": span,
        "suggested_relation": relation,
        "suggested_label": f"{n1.get('label','')[:25]}↔{n2.get('label','')[:25]}",
        "dci_delta": 0.0,
    }


def rank_candidates(kg: dict, min_span: int = 20, min_semantic: float = 0.05,
                    strict_4d: bool = True) -> list:
    """
    v3 후보 랭킹.
    - strict_4d=True: 4D 제약 위반 시 제외 (기본)
    - strict_4d=False: 소프트 모드 — 위반 시 combined에서 0.10 패널티

    combined_v3 = base_combined + CROSS_SOURCE_BONUS (교차출처 시)
    base_combined = 0.35*span_score + 0.35*semantic_score + 0.30*e_v4_gain_norm
    """
    nodes = [n for n in kg["nodes"] if n["id"].startswith("n-")]
    max_node_id = max(node_num(n["id"]) for n in nodes)

    existing = set()
    for e in kg["edges"]:
        existing.add((e["from"], e["to"]))
        existing.add((e["to"], e["from"]))

    candidates = []
    stats = {"filtered_4d": 0, "filtered_sem": 0, "cross": 0, "same": 0}

    for n1, n2 in combinations(nodes, 2):
        if (n1["id"], n2["id"]) in existing:
            continue
        span = abs(node_num(n1["id"]) - node_num(n2["id"]))
        if span < min_span:
            continue

        scored = score_pair(n1, n2, max_node_id)

        if scored["semantic_score"] < min_semantic:
            stats["filtered_sem"] += 1
            continue

        # DCI feeding 관계 필터 (v2 정책 유지)
        if scored["suggested_relation"] in DCI_FEEDING_RELATIONS:
            continue

        # 4D 제약
        if strict_4d and not scored["passes_4d"]:
            stats["filtered_4d"] += 1
            continue

        if scored["cross_source"]:
            stats["cross"] += 1
        else:
            stats["same"] += 1

        candidates.append(scored)

    # 통계 출력
    total_filtered = stats["filtered_4d"] + stats["filtered_sem"]
    if total_filtered > 0:
        print(f"  🔢 4D 필터: {stats['filtered_4d']}개 제외 (distance/asymmetry 범위 외)")
    print(f"  📊 후보 풀 — 교차출처: {stats['cross']}개 / 동일출처: {stats['same']}개")

    if not candidates:
        return candidates

    # E_v4 gain 정규화
    gains = [c["raw_e_v4_gain"] for c in candidates]
    gain_min, gain_max = min(gains), max(gains)
    gain_range = gain_max - gain_min if gain_max != gain_min else 1.0

    for c in candidates:
        e_v4_norm = (c["raw_e_v4_gain"] - gain_min) / gain_range
        c["e_v4_gain_norm"] = round(e_v4_norm, 4)

        # v3 combined: base + cross_source_bonus (교차출처이면 +0.30 직접 합산)
        base = (
            0.35 * c["span_score"]
            + 0.35 * c["semantic_score"]
            + 0.30 * c["e_v4_gain_norm"]
        )
        cross_add = CROSS_SOURCE_BONUS if c["cross_source"] else 0.0

        # 소프트 모드: 4D 제약 위반 시 패널티
        penalty = -0.10 if (not strict_4d and not c["passes_4d"]) else 0.0

        c["combined"] = round(base + cross_add + penalty, 4)

    candidates.sort(key=lambda x: -x["combined"])
    return candidates


# ─── CSER 제약 기반 선택 ──────────────────────────────────────────────────────

def select_with_cser_constraint(kg: dict, candidates: list, n: int) -> list:
    """
    CSER >= CSER_MIN 제약을 유지하면서 상위 n개 선택.

    규칙:
    - 교차출처 엣지: 항상 허용 (CSER 상승에 기여)
    - 동일출처 엣지: 추가 후 CSER >= CSER_MIN 유지될 때만 허용
    이미 CSER < CSER_MIN인 경우: 동일출처 엣지 전면 차단
    (교차출처만 쌓아서 임계값 회복)
    """
    node_src = {nd["id"]: nd.get("source", "") for nd in kg["nodes"]}
    cross_now, total_now = compute_cser_raw(kg)
    current_cser = cross_now / total_now if total_now > 0 else 0.0

    selected = []
    skipped_cser = 0

    for c in candidates:
        if len(selected) >= n:
            break

        is_cross = node_src.get(c["from"], "") != node_src.get(c["to"], "")

        if is_cross:
            # 교차출처: 무조건 허용 (CSER 개선)
            selected.append(c)
        else:
            # 동일출처: 현재 CSER < 임계값이면 차단
            if current_cser < CSER_MIN:
                skipped_cser += 1
                continue
            # 현재 OK → 추가 후에도 OK인지 시뮬레이션
            sel_cross = sum(1 for s in selected
                            if node_src.get(s["from"], "") != node_src.get(s["to"], ""))
            projected_cross = cross_now + sel_cross
            projected_total = total_now + len(selected) + 1
            projected_cser = projected_cross / projected_total if projected_total > 0 else 0.0
            if projected_cser < CSER_MIN:
                skipped_cser += 1
                continue
            selected.append(c)

    if skipped_cser > 0:
        print(f"  🛡️  CSER 제약: {skipped_cser}개 동일출처 엣지 제외 (현재 CSER {current_cser:.4f} < {CSER_MIN})")

    return selected


# ─── E_v4 측정 ────────────────────────────────────────────────────────────────

def compute_e_v4_delta(kg: dict, additions: list) -> dict:
    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics

    before = compute_all_metrics(kg)
    test_kg = {"nodes": kg["nodes"], "edges": kg["edges"] + additions}
    after = compute_all_metrics(test_kg)

    e_v4_delta = round(after["E_v4"] - before["E_v4"], 4)
    dci_delta = round(after["DCI"] - before["DCI"], 4)
    cser_delta = round(after["CSER"] - before["CSER"], 4)
    e_v4_gain_excl_dci = round(e_v4_delta - 0.25 * dci_delta, 4)

    return {
        "e_v4_before": before["E_v4"],
        "e_v4_after": after["E_v4"],
        "delta": e_v4_delta,
        "e_v4_gain_excl_dci": e_v4_gain_excl_dci,
        "dci_before": before["DCI"],
        "dci_after": after["DCI"],
        "dci_delta": dci_delta,
        "cser_before": before["CSER"],
        "cser_after": after["CSER"],
        "cser_delta": cser_delta,
        "cser_ok": after["CSER"] >= CSER_MIN,
        "edge_span_before": before["edge_span"]["raw"],
        "edge_span_after": after["edge_span"]["raw"],
        "n_added": len(additions),
    }


# ─── KG에 추가 ────────────────────────────────────────────────────────────────

def add_edges_to_kg(kg: dict, selected: list) -> tuple:
    current_max_edge = max(
        (int(e["id"].replace("e-", "")) for e in kg["edges"] if e["id"].startswith("e-")),
        default=0
    )
    new_edges = []
    for i, c in enumerate(selected, start=1):
        eid = f"e-{current_max_edge + i}"
        edge = {
            "id": eid,
            "from": c["from"],
            "to": c["to"],
            "relation": c["suggested_relation"],
            "label": c["suggested_label"],
            "meta": {
                "source": "pair_designer_v3",
                "version": VERSION,
                "cycle": CYCLE,
                "date": str(date.today()),
                "combined_score": c["combined"],
                "span": c["span"],
                "semantic_score": c["semantic_score"],
                "cross_source": c["cross_source"],
                "cross_source_bonus": CROSS_SOURCE_BONUS if c["cross_source"] else 0.0,
                "distance": c["distance"],
                "asymmetry": c["asymmetry"],
                "passes_4d": c["passes_4d"],
                "dci_neutral": True,
            },
        }
        new_edges.append(edge)

    updated_kg = {"nodes": kg["nodes"], "edges": kg["edges"] + new_edges}
    delta = compute_e_v4_delta(kg, new_edges)
    return updated_kg, new_edges, delta


# ─── 교차출처 통계 ────────────────────────────────────────────────────────────

def cmd_source_stats(kg: dict) -> None:
    node_src = {n["id"]: n.get("source", "") for n in kg["nodes"]}
    team = {n["id"]: classify_source(n.get("source", "")) for n in kg["nodes"]}

    loki_nodes = sum(1 for t in team.values() if t == "록이")
    cokac_nodes = sum(1 for t in team.values() if t == "cokac")
    other_nodes = sum(1 for t in team.values() if t == "기타")

    cross_edges = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
    )
    v3_edges = [e for e in kg["edges"] if e.get("meta", {}).get("source") == "pair_designer_v3"]
    v3_cross = sum(1 for e in v3_edges if e.get("meta", {}).get("cross_source", False))

    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics
    m = compute_all_metrics(kg)

    print("═══ 교차출처 통계 (pair_designer v3) ═══")
    print(f"노드 — 록이: {loki_nodes}  cokac: {cokac_nodes}  기타: {other_nodes}")
    print(f"전체 교차출처 엣지: {cross_edges}/{len(kg['edges'])}  = CSER {m['CSER']:.4f}")
    print(f"v3 추가 엣지: {len(v3_edges)}개  (교차출처: {v3_cross}개)")
    print(f"CSER >= {CSER_MIN}: {'✅' if m['CSER'] >= CSER_MIN else '❌'} (현재 {m['CSER']:.4f})")


# ─── 출력 ─────────────────────────────────────────────────────────────────────

def print_recommendations(candidates: list, top_n: int = 20) -> None:
    cross_in_top = sum(1 for c in candidates[:top_n] if c["cross_source"])
    print("═══ pair_designer v3 — CSER 제약 + 교차출처 보너스 (사이클 60) ═══")
    print(f"후보 풀: {len(candidates)}쌍  |  상위 {min(top_n, len(candidates))}개 표시")
    print(f"가중치: span=0.35  semantic=0.35  E_v4=0.30  + cross_bonus={CROSS_SOURCE_BONUS} (교차출처)")
    print(f"4D 제약: distance∈({DISTANCE_MIN},{DISTANCE_MAX})  asymmetry∈({ASYMMETRY_MIN},{ASYMMETRY_MAX})")
    print(f"CSER 제약: >= {CSER_MIN}")
    print(f"상위 {min(top_n, len(candidates))}개 중 교차출처: {cross_in_top}개")
    print()

    for i, c in enumerate(candidates[:top_n], 1):
        cross_tag = " [교차✓]" if c["cross_source"] else ""
        bonus_tag = f" +{CROSS_SOURCE_BONUS}" if c["cross_source"] else ""
        print(f"  [{i:>2}] {c['from']}↔{c['to']}  combined={c['combined']:.4f}{bonus_tag}{cross_tag}")
        print(f"       {c['from_type']:<12} ↔ {c['to_type']:<12}  span={c['span']}")
        print(f"       dist={c['distance']:.3f}  asym={c['asymmetry']:.2f}"
              f"  sem={c['semantic_score']:.3f}  ({c['from_source']}↔{c['to_source']})")
        print(f"       \"{c['from_label']}\"")
        print(f"       → [{c['suggested_relation']}]")
        print(f"       \"{c['to_label']}\"")
        print()

    if len(candidates) == 0:
        print("  추천 없음 — --soft 플래그로 소프트 모드 시도")


def print_delta_report(delta: dict) -> None:
    arrow = "↑" if delta["delta"] >= 0 else "↓"
    sign = "+" if delta["delta"] >= 0 else ""

    print(f"\n── E_v4 실측 결과 (v3 CSER 제약) ────────────────────")
    print(f"  추가된 엣지        : {delta['n_added']}개")
    print(f"  E_v4               : {delta['e_v4_before']:.4f} → {delta['e_v4_after']:.4f}  ({sign}{delta['delta']:.4f} {arrow})")
    print(f"  e_v4_gain_excl_dci : {'+' if delta['e_v4_gain_excl_dci'] >= 0 else ''}{delta['e_v4_gain_excl_dci']:.4f}")
    print(f"  DCI 변화           : {delta['dci_before']:.4f} → {delta['dci_after']:.4f}  (Δ{delta['dci_delta']:+.4f})")
    print(f"  CSER               : {delta['cser_before']:.4f} → {delta['cser_after']:.4f}  (Δ{delta['cser_delta']:+.4f})")
    cser_status = "✅ 제약 준수" if delta["cser_ok"] else f"❌ 제약 위반 ({CSER_MIN} 미달)"
    print(f"  CSER >= {CSER_MIN}        : {cser_status}")
    print(f"  edge_span_raw      : {delta['edge_span_before']:.3f} → {delta['edge_span_after']:.3f}")

    if delta["dci_delta"] > 0.005:
        print(f"\n  ⚠️  DCI 증가 감지: Δ{delta['dci_delta']:+.4f}")
    else:
        print(f"\n  ✅ DCI 중립: Δ{delta['dci_delta']:+.4f}")

    if delta["cser_delta"] >= 0:
        print(f"  ✅ CSER 유지/상승: Δ{delta['cser_delta']:+.4f}")
    else:
        print(f"  ⚠️  CSER 소폭 하락: Δ{delta['cser_delta']:+.4f} — CSER {'OK' if delta['cser_ok'] else '제약 위반'}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    kg = load_kg()

    top_n = 20
    min_span = 20
    add_n = 0
    strict_4d = "--soft" not in args

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

    if "--source-stats" in args:
        cmd_source_stats(kg)
        return

    if "--verify" in args:
        log = load_log()
        if not log["sessions"]:
            print("기록 없음")
            return
        last = log["sessions"][-1]
        print(json.dumps(last, ensure_ascii=False, indent=2))
        return

    mode_label = "소프트(4D 페널티)" if not strict_4d else "엄격(4D 하드필터)"
    print(f"  🔧 모드: {mode_label}")

    candidates = rank_candidates(kg, min_span=min_span, min_semantic=0.05, strict_4d=strict_4d)

    if "--json" in args:
        output = {
            "version": VERSION,
            "candidates": candidates[:top_n],
            "total_pool": len(candidates),
            "params": {
                "top_n": top_n,
                "min_span": min_span,
                "strict_4d": strict_4d,
                "cross_source_bonus": CROSS_SOURCE_BONUS,
                "cser_min": CSER_MIN,
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if add_n > 0:
        n = min(add_n, len(candidates))
        if n == 0:
            print("추천 후보 없음 — --soft 모드 또는 파라미터 조정 필요")
            return

        print(f"═══ pair_designer v3 --add {n} (CSER 제약 + 교차출처) ═══\n")

        # CSER 제약 기반 선택
        selected = select_with_cser_constraint(kg, candidates, n)
        actual_n = len(selected)

        if actual_n == 0:
            print("CSER 제약으로 선택 가능한 엣지 없음")
            return

        cross_selected = sum(1 for s in selected if s["cross_source"])
        print(f"\n  선택된 엣지 {actual_n}개 — 교차출처: {cross_selected}개 / 동일출처: {actual_n - cross_selected}개")

        updated_kg, added, delta = add_edges_to_kg(kg, selected)
        save_kg(updated_kg)
        print_delta_report(delta)

        log = load_log()
        session = {
            "date": str(date.today()),
            "version": VERSION,
            "cycle": CYCLE,
            "n_added": actual_n,
            "cross_source_count": cross_selected,
            "delta": delta,
            "added_edges": [
                {
                    "id": e["id"],
                    "from": e["from"],
                    "to": e["to"],
                    "relation": e["relation"],
                    "span": e["meta"]["span"],
                    "combined_score": e["meta"]["combined_score"],
                    "cross_source": e["meta"]["cross_source"],
                    "distance": e["meta"]["distance"],
                    "asymmetry": e["meta"]["asymmetry"],
                }
                for e in added
            ],
        }
        log["sessions"].append(session)
        save_log(log)
        print(f"\n  ✅ {actual_n}개 엣지 추가 완료 → data/knowledge-graph.json")
        print(f"  로그 → data/pair_designer_v3_log.json")
        return

    print_recommendations(candidates, top_n)


if __name__ == "__main__":
    main()
