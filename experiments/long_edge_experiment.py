#!/usr/bin/env python3
"""
long_edge_experiment.py — 장거리 엣지 의도적 생성 실험 (사이클 52)
구현자: cokac-bot

가설 (n-115): span > 50 비율 증가 → E_v4 상승
검증 방법: 3개의 장거리 엣지를 의도적으로 추가하고 E_v4 변화 측정

실험 설계:
  1. 현재 E_v4 / edge_span_norm 기록
  2. span > 50인 노드 쌍 후보 탐색 (아직 연결 안 된 것)
  3. 의미 있는 관계 3개 선정
  4. 엣지 추가
  5. E_v4 재계산 → Δ 측정
  6. 결과를 KG 노드로 기록

사용법:
  python3 experiments/long_edge_experiment.py --dry-run  # 후보 탐색만
  python3 experiments/long_edge_experiment.py             # 실제 추가 + 측정
  python3 experiments/long_edge_experiment.py --undo      # 추가한 엣지 롤백 (ID 기반)
"""

import json
import sys
import statistics
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"

# 실험에서 추가한 엣지 ID 추적용
EXPERIMENT_LOG = REPO / "experiments" / "long_edge_experiment_log.json"


def load_kg() -> dict:
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_kg(kg: dict) -> None:
    kg["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    kg["meta"]["total_nodes"] = len(kg["nodes"])
    kg["meta"]["total_edges"] = len(kg["edges"])
    with open(KG_FILE, "w", encoding="utf-8") as f:
        json.dump(kg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


def compute_edge_span_norm(kg: dict) -> tuple[float, float]:
    """(raw, normalized) 반환"""
    spans = [abs(_node_num(e["from"]) - _node_num(e["to"])) for e in kg["edges"]]
    if not spans:
        return 0.0, 0.0
    raw = statistics.mean(spans)
    n_nodes = max(len(kg["nodes"]) - 1, 1)
    return raw, raw / n_nodes


def compute_e_v4(kg: dict) -> float:
    """E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span_norm + 0.15*node_age_diversity"""
    sys.path.insert(0, str(REPO / "src"))
    from metrics import compute_all_metrics
    m = compute_all_metrics(kg)
    return m["E_v4"], m


def find_long_span_candidates(kg: dict, min_span: int = 50, top_n: int = 20) -> list[dict]:
    """
    span > min_span 이면서 아직 연결되지 않은 노드 쌍 탐색.
    의미적으로 흥미로운 쌍 우선 (타입 다양성 고려).
    """
    nodes = kg["nodes"]
    existing = set()
    for e in kg["edges"]:
        existing.add((e["from"], e["to"]))
        existing.add((e["to"], e["from"]))

    node_map = {n["id"]: n for n in nodes}
    candidates = []

    for i, na in enumerate(nodes):
        for nb in nodes[i + 1:]:
            span = abs(_node_num(na["id"]) - _node_num(nb["id"]))
            if span < min_span:
                continue
            if (na["id"], nb["id"]) in existing:
                continue

            # 의미적 점수: 타입 다양성 + 출처 다양성
            type_score = 1.0 if na["type"] != nb["type"] else 0.5
            src_score = 1.0 if na.get("source") != nb.get("source") else 0.5
            interest_score = (span / 115) * 0.5 + type_score * 0.3 + src_score * 0.2

            candidates.append({
                "from": na["id"],
                "to": nb["id"],
                "span": span,
                "from_type": na["type"],
                "to_type": nb["type"],
                "from_source": na.get("source", "?"),
                "to_source": nb.get("source", "?"),
                "from_label": na["label"][:50],
                "to_label": nb["label"][:50],
                "interest_score": round(interest_score, 3),
            })

    # 관심도 기준 정렬
    candidates.sort(key=lambda x: -x["interest_score"])
    return candidates[:top_n]


# ─── 실험용 엣지 3개 사전 정의 ─────────────────────────────────────────────
# cokac-bot이 KG 의미를 분석해 선정한 "시간 초월" 연결
PREDEFINED_LONG_EDGES = [
    {
        "from": "n-001",
        "to": "n-092",
        "relation": "closes_loop",
        "label": "프로젝트 탄생(n-001)이 창발 측정 시작(n-092)을 완성 — 기원과 측정의 닫힌 고리",
        "span_reason": "첫 번째 결정이 측정 인프라로 이어짐. span=91.",
    },
    {
        "from": "n-005",
        "to": "n-099",
        "relation": "grounds",
        "label": "기억 레이어 설계(n-005)가 수렴 조건 논의(n-099)의 토대 — 기억 없이 수렴 없다",
        "span_reason": "초기 기억 메커니즘이 사이클 48 수렴 이론의 기반. span=94.",
    },
    {
        "from": "n-010",
        "to": "n-087",
        "relation": "foreshadows",
        "label": "사이클 7 첫 모순 감지(n-010)가 Layer2A 인과 논쟁(n-087)을 예고 — 모순이 창발로",
        "span_reason": "초기 모순 관찰이 훗날 인과 판결 구조를 예견. span=77.",
    },
]


def add_long_edges(kg: dict, edges: list[dict]) -> list[str]:
    """엣지 추가 후 추가된 edge ID 리스트 반환"""
    added_ids = []
    for e_spec in edges:
        # 이미 연결됐는지 확인
        existing = {(e["from"], e["to"]) for e in kg["edges"]}
        existing |= {(e["to"], e["from"]) for e in kg["edges"]}
        if (e_spec["from"], e_spec["to"]) in existing:
            print(f"  ⏭  이미 연결됨: {e_spec['from']} ↔ {e_spec['to']}")
            continue

        # 노드 존재 확인
        node_ids = {n["id"] for n in kg["nodes"]}
        if e_spec["from"] not in node_ids or e_spec["to"] not in node_ids:
            print(f"  ❌ 노드 없음: {e_spec['from']} 또는 {e_spec['to']}")
            continue

        # edge ID 계산
        existing_enums = [int(e["id"].split("-")[1]) for e in kg["edges"] if e["id"].startswith("e-")]
        next_enum = (max(existing_enums) + 1) if existing_enums else 1
        edge_id = f"e-{next_enum:03d}"

        span = abs(_node_num(e_spec["from"]) - _node_num(e_spec["to"]))
        edge = {
            "id": edge_id,
            "from": e_spec["from"],
            "to": e_spec["to"],
            "relation": e_spec["relation"],
            "label": e_spec["label"],
            "experiment": "cycle52-long-edge",
            "span": span,
        }
        kg["edges"].append(edge)
        added_ids.append(edge_id)
        print(f"  ✅ 엣지 추가: {edge_id}  {e_spec['from']}↔{e_spec['to']}  span={span}  [{e_spec['relation']}]")

    return added_ids


def main():
    kg = load_kg()

    # Dry-run: 후보만 탐색
    if "--dry-run" in sys.argv:
        print("═══ 장거리 엣지 후보 탐색 (span≥50) ═══\n")
        candidates = find_long_span_candidates(kg, min_span=50, top_n=15)
        print(f"총 {len(candidates)}개 후보 (관심도 기준 정렬)\n")
        print(f"  {'순위':<4} {'쌍':<16} {'span':>4}  {'관심도':>6}  {'관계 제안'}")
        print(f"  {'─'*4} {'─'*16} {'─'*4}  {'─'*6}  {'─'*20}")
        for i, c in enumerate(candidates[:10], 1):
            print(f"  {i:<4} {c['from']}↔{c['to']:<8}  {c['span']:>4}  {c['interest_score']:>6.3f}")
            print(f"       [{c['from']}] {c['from_label']}")
            print(f"       [{c['to']}]   {c['to_label']}")
        return

    # Undo: 실험 엣지 롤백
    if "--undo" in sys.argv:
        if not EXPERIMENT_LOG.exists():
            print("❌ 실험 로그 없음 — 롤백 불가")
            return
        log = json.loads(EXPERIMENT_LOG.read_text())
        undo_ids = set(log.get("added_edge_ids", []))
        before = len(kg["edges"])
        kg["edges"] = [e for e in kg["edges"] if e["id"] not in undo_ids]
        removed = before - len(kg["edges"])
        save_kg(kg)
        print(f"✅ 롤백 완료: {removed}개 엣지 제거")
        return

    # 실험 실행
    print("═══ 장거리 엣지 실험 — 사이클 52 ═══\n")
    print("── Before ──────────────────────────────────────")
    e_v4_before, m_before = compute_e_v4(kg)
    span_raw_before, span_norm_before = compute_edge_span_norm(kg)
    n_edges_before = len(kg["edges"])
    long_before = sum(1 for e in kg["edges"] if abs(_node_num(e["from"]) - _node_num(e["to"])) >= 50)
    print(f"  E_v4             : {e_v4_before:.4f}")
    print(f"  edge_span (raw)  : {span_raw_before:.3f}")
    print(f"  edge_span (norm) : {span_norm_before:.4f}")
    print(f"  총 엣지          : {n_edges_before}")
    print(f"  span≥50 엣지     : {long_before}개  ({long_before/n_edges_before*100:.1f}%)")
    print()

    print("── 장거리 엣지 추가 ────────────────────────────")
    for spec in PREDEFINED_LONG_EDGES:
        span = abs(_node_num(spec["from"]) - _node_num(spec["to"]))
        print(f"  계획: {spec['from']}↔{spec['to']}  span={span}  [{spec['relation']}]")
        print(f"  이유: {spec['span_reason']}")
    print()

    added_ids = add_long_edges(kg, PREDEFINED_LONG_EDGES)
    kg["meta"]["last_updater"] = "cokac"
    save_kg(kg)
    print()

    print("── After ───────────────────────────────────────")
    e_v4_after, m_after = compute_e_v4(kg)
    span_raw_after, span_norm_after = compute_edge_span_norm(kg)
    n_edges_after = len(kg["edges"])
    long_after = sum(1 for e in kg["edges"] if abs(_node_num(e["from"]) - _node_num(e["to"])) >= 50)
    print(f"  E_v4             : {e_v4_after:.4f}  (Δ{e_v4_after - e_v4_before:+.4f})")
    print(f"  edge_span (raw)  : {span_raw_after:.3f}  (Δ{span_raw_after - span_raw_before:+.3f})")
    print(f"  edge_span (norm) : {span_norm_after:.4f}  (Δ{span_norm_after - span_norm_before:+.4f})")
    print(f"  총 엣지          : {n_edges_after}  (+{n_edges_after - n_edges_before})")
    print(f"  span≥50 엣지     : {long_after}개  ({long_after/n_edges_after*100:.1f}%)  (+{long_after - long_before})")
    print()

    # 결과 해석
    print("── 해석 ────────────────────────────────────────")
    delta = e_v4_after - e_v4_before
    if delta > 0:
        print(f"  ✅ n-115 가설 지지: 장거리 엣지 추가 → E_v4 +{delta:.4f}")
    else:
        print(f"  ⚠️  n-115 가설 미지지: 장거리 엣지 3개만으로는 E_v4 변화 미미 (Δ{delta:+.4f})")
        print(f"     → edge_span_norm 0.105 → 0.28 달성엔 더 많은 장거리 엣지 필요")
        needed = round((0.28 * (n_edges_after - 1) - span_raw_after * n_edges_after) / (80 - span_raw_after), 0)
        print(f"     → 추정: span=80짜리 엣지 약 {int(max(needed, 5))}개 더 필요")

    e_v4_norm_needed = 0.28  # 역전 조건
    pct_to_reversal = (e_v4_norm_needed - span_norm_after) / e_v4_norm_needed * 100
    print(f"  현재 edge_span_norm: {span_norm_after:.4f}  (역전 목표: 0.28, {pct_to_reversal:.1f}% 남음)")
    print()

    # 로그 저장
    log = {
        "cycle": 52,
        "timestamp": datetime.now().isoformat(),
        "added_edge_ids": added_ids,
        "before": {
            "E_v4": e_v4_before,
            "edge_span_raw": span_raw_before,
            "edge_span_norm": span_norm_before,
            "n_edges": n_edges_before,
            "long_edges": long_before,
        },
        "after": {
            "E_v4": e_v4_after,
            "edge_span_raw": span_raw_after,
            "edge_span_norm": span_norm_after,
            "n_edges": n_edges_after,
            "long_edges": long_after,
        },
        "delta_E_v4": round(delta, 4),
        "verdict": "지지" if delta > 0 else "미지지",
    }
    EXPERIMENT_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    print(f"✅ 실험 로그 저장: {EXPERIMENT_LOG.name}")
    print()

    return log


if __name__ == "__main__":
    main()
