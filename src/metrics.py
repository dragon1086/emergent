#!/usr/bin/env python3
"""
metrics.py — emergent 창발 메트릭 통합 모듈
구현자: cokac-bot (사이클 50)

사이클 50 신규 지표:
  - edge_span: 엣지가 연결하는 두 노드의 시간적 거리 평균
    = mean(|node_num(u) - node_num(v)|) for all edges
    → 높을수록 오래된 노드와 새 노드가 연결됨 = 시간 초월 창발
  - node_age_diversity: 노드 나이 분포의 표준편차 / 최대값
    = std(node_ids) / max_node_id
    → 높을수록 KG가 다양한 나이대 노드를 고르게 보유

v4 창발 공식 (n-102 제안, 록이):
  E_new = 0.35*CSER + 0.25*DCI + 0.25*edge_span_norm + 0.15*node_age_diversity

  vs 이전 v3:
  E_v3  = 0.4*CSER + 0.3*DCI + 0.3*tag_convergence

  변경점:
  - tag_convergence 제거 (포화 상태 — n-101 관찰)
  - edge_span 도입: 시간적 경계 횡단 측정
  - node_age_diversity 도입: 나이대 다양성 포착
  - CSER 가중치 0.4→0.35 (소폭 감소)

사용법:
  python3 metrics.py              # 전체 메트릭 출력
  python3 metrics.py --json       # JSON 출력
  python3 metrics.py --v3         # v3 vs v4 비교 출력

수입:
  from src.metrics import compute_all_metrics
"""

import json
import os
import sys
import statistics
from pathlib import Path
from collections import Counter

REPO = Path(__file__).parent.parent
_kg_env = os.environ.get("EMERGENT_KG_PATH")
KG_FILE = Path(_kg_env) if _kg_env else REPO / "data" / "knowledge-graph.json"


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_kg():
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


# ─── 개별 지표 함수 ───────────────────────────────────────────────────────────

def compute_cser(kg: dict) -> float:
    """
    Cross-Source Edge Ratio (교차 출처 엣지 비율)
    = 출처 경계를 횡단하는 엣지 수 / 전체 엣지 수

    임계값: > 0.5 → 에코 챔버 탈출 (Layer 1-A)
    """
    def _norm(s: str) -> str:
        if s in ("cokac-bot", "cokac"):
            return "cokac"
        if s in ("록이", "상록"):
            return "록이"
        return s
    node_src = {n["id"]: _norm(n.get("source", "")) for n in kg["nodes"]}
    n_edges = len(kg["edges"])
    if n_edges == 0:
        return 0.0
    cross = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
    )
    return round(cross / n_edges, 4)


def compute_dxi(kg: dict) -> float:
    """
    Domain Crossing Index (도메인 횡단 지수)
    = 도메인이 다른 노드 간 엣지 / ontology가 있는 노드 간 전체 엣지

    CSER의 의미론적 확장 (source 경계 → domain 경계)
    임계값: > 0.4 → 도메인 간 창발 활성화

    ontology 필드가 없는 노드 간 엣지는 제외하고 계산.
    backfill_ontology.py 실행 후 의미 있는 값이 나옴.
    """
    n_edges = len(kg["edges"])
    if n_edges == 0:
        return 0.0

    node_domain: dict[str, str] = {}
    for n in kg["nodes"]:
        onto = n.get("ontology")
        if onto and isinstance(onto, dict):
            node_domain[n["id"]] = onto.get("domain", "")

    cross = 0
    counted = 0
    for e in kg["edges"]:
        d_from = node_domain.get(e["from"], "")
        d_to = node_domain.get(e["to"], "")
        if d_from and d_to:
            counted += 1
            if d_from != d_to:
                cross += 1

    if counted == 0:
        return 0.0
    return round(cross / counted, 4)


def compute_edge_span(kg: dict) -> dict:
    """
    Edge Span (엣지 시간 스팬)
    = mean(|node_num(u) - node_num(v)|) for all edges

    해석:
    - raw: 평균 노드 ID 간격 (시간 프록시)
    - normalized: raw / (총 노드 수 - 1)  → [0, 1]
    - distribution: max, min, median

    높을수록 = 시간적으로 먼 노드를 연결 = 창발 연결 가능성 높음
    n-001 ↔ n-100 같은 closes_loop 엣지가 최대 스팬 기여
    """
    spans = []
    for e in kg["edges"]:
        a = _node_num(e["from"])
        b = _node_num(e["to"])
        spans.append(abs(a - b))

    if not spans:
        return {"raw": 0.0, "normalized": 0.0, "max": 0, "min": 0, "median": 0.0}

    n_nodes = max(len(kg["nodes"]) - 1, 1)
    raw = statistics.mean(spans)
    return {
        "raw": round(raw, 3),
        "normalized": round(raw / n_nodes, 4),
        "max": max(spans),
        "min": min(spans),
        "median": round(statistics.median(spans), 1),
        "stdev": round(statistics.stdev(spans) if len(spans) > 1 else 0.0, 3),
    }


def compute_node_age_diversity(kg: dict) -> float:
    """
    Node Age Diversity (노드 나이 다양성)
    = std(node_ids) / max_node_id

    해석:
    - 낮음 (~0.2): 최신 노드 밀집 (단계적 성장)
    - 높음 (~0.3+): 넓은 나이대 고르게 분포
    - 이론적 최대 = std([1,2,...,n]) / n ≈ 0.289 (균등 분포)
    """
    nums = [_node_num(n["id"]) for n in kg["nodes"] if n["id"].startswith("n-")]
    if len(nums) < 2:
        return 0.0
    return round(statistics.stdev(nums) / max(nums), 4)


def compute_tag_convergence(kg: dict) -> float:
    """
    Tag Convergence (태그 수렴 비율)
    = 3개 이상 노드에서 공유된 태그 수 / 전체 고유 태그 수

    n-101 관찰: 사이클 49에서 포화 상태(1.0 근접)
    별도 지표 convergence_health = 1.0 - tag_convergence 권장
    """
    all_tags = []
    for n in kg["nodes"]:
        all_tags.extend(n.get("tags", []))
    tag_counts = Counter(all_tags)
    if not tag_counts:
        return 0.0
    convergence = sum(1 for v in tag_counts.values() if v >= 3)
    return round(convergence / len(tag_counts), 4)


def compute_dci(kg: dict) -> float:
    """
    Delayed Convergence Index (지연 수렴 지수)
    = sum(max_gap for answered questions) / (total_questions * total_nodes)

    delayed_convergence.py 동일 공식을 여기서도 직접 계산 가능하게 중복 구현.
    (import 순환 방지)
    """
    nodes = kg["nodes"]
    edges = kg["edges"]
    questions = {n["id"] for n in nodes if n.get("type") == "question"}
    total_questions = len(questions)
    total_nodes = len(nodes)

    if total_questions == 0 or total_nodes == 0:
        return 0.0

    # answers 엣지 수집
    answers_from = {}  # qid → max gap
    for e in edges:
        if e.get("relation") != "answers":
            continue
        src, tgt = e["from"], e["to"]
        if src in questions:
            gap = abs(_node_num(tgt) - _node_num(src))
            answers_from[src] = max(answers_from.get(src, 0), gap)
        if tgt in questions:
            gap = abs(_node_num(src) - _node_num(tgt))
            answers_from[tgt] = max(answers_from.get(tgt, 0), gap)

    gap_sum = sum(answers_from.values())
    raw = gap_sum / (total_questions * total_nodes)
    return round(min(1.0, raw), 4)


# ─── 통합 공식 ────────────────────────────────────────────────────────────────

def compute_emergence_v3(cser: float, dci: float, tag_conv: float) -> float:
    """
    창발 공식 v3 (기존)
    E_v3 = 0.4*CSER + 0.3*DCI + 0.3*tag_convergence
    """
    return round(0.4 * cser + 0.3 * dci + 0.3 * tag_conv, 4)


def compute_emergence_v4(cser: float, dci: float,
                         edge_span_norm: float, node_age_div: float) -> float:
    """
    창발 공식 v4 (n-102 제안, 록이)
    E_new = 0.35*CSER + 0.25*DCI + 0.25*edge_span_norm + 0.15*node_age_diversity

    개선점:
    - tag_convergence 제거 (포화 — n-101)
    - edge_span 추가: 시간 초월 연결 측정
    - node_age_diversity 추가: 나이대 균형 측정
    """
    return round(0.35 * cser + 0.25 * dci + 0.25 * edge_span_norm + 0.15 * node_age_div, 4)


def compute_emergence_v5(cser: float, dci: float,
                         edge_span_norm: float, node_age_div: float, dxi: float) -> float:
    """
    창발 공식 v5 (온톨로지 기반 도메인 횡단 지수 추가)
    E_v5 = 0.30*CSER + 0.22*DCI + 0.22*edge_span_norm + 0.13*node_age_div + 0.13*DXI

    변경점 (v4 → v5):
    - DXI (Domain Crossing Index) 추가: source 경계에서 domain 경계로 확장
    - CSER 가중치 0.35→0.30, DCI 0.25→0.22, edge_span 0.25→0.22
    - node_age_div 0.15→0.13, DXI 신규 0.13
    - 총합 = 0.30+0.22+0.22+0.13+0.13 = 1.00

    DXI 임계값: > 0.4 → 도메인 간 창발 활성화
    """
    return round(0.30 * cser + 0.22 * dci + 0.22 * edge_span_norm + 0.13 * node_age_div + 0.13 * dxi, 4)


# ─── 전체 계산 ────────────────────────────────────────────────────────────────

def compute_all_metrics(kg: dict = None) -> dict:
    """
    전체 메트릭 계산 및 반환.
    """
    if kg is None:
        kg = load_kg()

    cser = compute_cser(kg)
    dci = compute_dci(kg)
    edge_span = compute_edge_span(kg)
    node_age_div = compute_node_age_diversity(kg)
    tag_conv = compute_tag_convergence(kg)

    dxi = compute_dxi(kg)

    e_v3 = compute_emergence_v3(cser, dci, tag_conv)
    e_v4 = compute_emergence_v4(cser, dci, edge_span["normalized"], node_age_div)
    e_v5 = compute_emergence_v5(cser, dci, edge_span["normalized"], node_age_div, dxi)

    convergence_health = round(1.0 - tag_conv, 4)

    return {
        "nodes": len(kg["nodes"]),
        "edges": len(kg["edges"]),
        "CSER": cser,
        "DCI": dci,
        "DXI": dxi,
        "edge_span": edge_span,
        "node_age_diversity": node_age_div,
        "tag_convergence": tag_conv,
        "convergence_health": convergence_health,
        "E_v3": e_v3,
        "E_v4": e_v4,
        "E_v5": e_v5,
        "E_delta_v4_v3": round(e_v4 - e_v3, 4),
        "E_delta_v5_v4": round(e_v5 - e_v4, 4),
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    kg = load_kg()
    m = compute_all_metrics(kg)

    show_all = "--all" in sys.argv

    if "--json" in sys.argv:
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return

    print("═══ emergent 창발 메트릭 v5 ═══")
    print(f"KG: {m['nodes']} 노드 / {m['edges']} 엣지\n")

    print("── Layer 1: 창발 조건 지표 ──────────────────")
    print(f"  CSER (교차출처비율)   : {m['CSER']:.4f}  {'✅ 에코챔버 탈출' if m['CSER'] > 0.5 else '⚠️  에코챔버 위험'}")
    print(f"  DCI  (지연수렴지수)   : {m['DCI']:.4f}")
    dxi_flag = "✅ 도메인 간 창발 활성화" if m["DXI"] > 0.4 else ("⚠️  온톨로지 backfill 필요" if m["DXI"] == 0.0 else "")
    print(f"  DXI  (도메인횡단지수) : {m['DXI']:.4f}  {dxi_flag}")
    print()

    print("── Layer 2: 구조 지표 ───────────────────────")
    es = m["edge_span"]
    print(f"  edge_span (raw)      : {es['raw']:.3f}  (mean |Δnode_id| per edge)")
    print(f"  edge_span (normalized): {es['normalized']:.4f}")
    print(f"  edge_span 분포       : max={es['max']}, min={es['min']}, median={es['median']}")
    print(f"  node_age_diversity   : {m['node_age_diversity']:.4f}  (std/max 나이 분산)")
    print()
    print(f"  tag_convergence      : {m['tag_convergence']:.4f}  {'⚠️  포화 상태' if m['tag_convergence'] > 0.9 else ''}")
    print(f"  convergence_health   : {m['convergence_health']:.4f}  (1 - tag_conv, n-101 제안)")
    print()

    print("── 창발 공식 비교 ──────────────────────────")
    if show_all:
        print(f"  E_v3 = 0.4*CSER + 0.3*DCI + 0.3*tag_conv")
        print(f"       = {m['E_v3']:.4f}")
        print()
        d43_sign = "+" if m["E_delta_v4_v3"] >= 0 else ""
        print(f"  E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span + 0.15*node_age_div  (n-102)")
        print(f"       = {m['E_v4']:.4f}  (Δ v4-v3 = {d43_sign}{m['E_delta_v4_v3']:.4f})")
        print()
    else:
        print(f"  E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span + 0.15*node_age_div")
        print(f"       = {m['E_v4']:.4f}")
        print()

    d54_sign = "+" if m["E_delta_v5_v4"] >= 0 else ""
    print(f"  E_v5 = 0.30*CSER + 0.22*DCI + 0.22*edge_span + 0.13*node_age_div + 0.13*DXI")
    print(f"       = {m['E_v5']:.4f}  (Δ v5-v4 = {d54_sign}{m['E_delta_v5_v4']:.4f})")
    print()

    if "--v3" not in sys.argv:
        print("── 해석 ────────────────────────────────────")
        print(f"  edge_span={es['raw']:.1f}노드 평균 간격 → 시간 초월 연결 활발")
        print(f"  max_span={es['max']} → n-001↔n-100 closes_loop 엣지가 최대 기여")
        if m["node_age_diversity"] > 0.28:
            print(f"  node_age_diversity={m['node_age_diversity']:.4f} → 균등 분포 이론치(0.289) 근접")
        if m["CSER"] > 0.7:
            print(f"  CSER={m['CSER']:.4f} → 강한 에코챔버 탈출 (임계값 0.5 초과)")
        if m["DXI"] == 0.0:
            print(f"  DXI=0.0 → backfill_ontology.py 실행 후 재측정 권장")
        elif m["DXI"] > 0.4:
            print(f"  DXI={m['DXI']:.4f} → 도메인 경계 횡단 창발 활성화 (임계값 0.4 초과)")
    print()


if __name__ == "__main__":
    main()
