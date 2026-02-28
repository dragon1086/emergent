#!/usr/bin/env python3
"""
span_analyzer.py — edge_span 분포 분석기 (사이클 52)
구현자: cokac-bot

KG의 시간 구조를 엣지 스팬 히스토그램으로 시각화한다.

핵심 질문:
  KG의 연결이 시간적으로 어떻게 분포하는가?
  장거리 엣지(span>50)가 창발에 기여하는가?

사용법:
  python3 src/span_analyzer.py           # 기본 분석
  python3 src/span_analyzer.py --json    # JSON 출력
  python3 src/span_analyzer.py --top 10  # 스팬 큰 엣지 Top N
  python3 src/span_analyzer.py --what-if 3  # 장거리 엣지 추가 시 E_v4 예측
"""

import json
import sys
import statistics
from pathlib import Path
from collections import Counter

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"

# 분석 버킷 정의
BUCKETS = [
    (0,  1,   "즉시 (span=0)"),
    (1,  5,   "근접 (1~4)"),
    (5,  15,  "단거리 (5~14)"),
    (15, 30,  "중거리 (15~29)"),
    (30, 50,  "장거리 (30~49)"),
    (50, 999, "초장거리 (50+)"),
]


def load_kg() -> dict:
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


def compute_spans(kg: dict) -> list[dict]:
    """모든 엣지의 스팬 정보 계산"""
    node_map = {n["id"]: n for n in kg["nodes"]}
    spans = []
    for e in kg["edges"]:
        a = _node_num(e["from"])
        b = _node_num(e["to"])
        span = abs(a - b)
        spans.append({
            "id": e["id"],
            "from": e["from"],
            "to": e["to"],
            "span": span,
            "relation": e.get("relation", ""),
            "label": e.get("label", "")[:50],
            "from_label": node_map.get(e["from"], {}).get("label", "?")[:30],
            "to_label": node_map.get(e["to"], {}).get("label", "?")[:30],
        })
    return sorted(spans, key=lambda x: -x["span"])


def bucket_distribution(spans: list[dict]) -> dict:
    """버킷별 분포 집계"""
    result = {}
    for lo, hi, name in BUCKETS:
        members = [s for s in spans if lo <= s["span"] < hi]
        result[name] = {
            "count": len(members),
            "edges": members,
            "pct": round(len(members) / len(spans) * 100, 1) if spans else 0.0,
        }
    return result


def ascii_histogram(bucket_dist: dict, bar_max: int = 30) -> str:
    """ASCII 바 차트 생성"""
    lines = []
    lines.append("── KG 시간 구조 히스토그램 ────────────────────────")
    total = sum(b["count"] for b in bucket_dist.values())
    max_count = max((b["count"] for b in bucket_dist.values()), default=1)

    for name, data in bucket_dist.items():
        count = data["count"]
        pct = data["pct"]
        bar_len = int(count / max_count * bar_max) if max_count else 0
        bar = "█" * bar_len + "░" * (bar_max - bar_len)
        lines.append(f"  {name:<18}  [{bar}] {count:>4} ({pct:>5.1f}%)")

    lines.append(f"  {'합계':<18}  {'':>{bar_max+2}}  {total:>4}")
    return "\n".join(lines)


def compute_e_v4_with_extra_edges(kg: dict, extra_spans: list[int]) -> dict:
    """
    가상 장거리 엣지 추가 시 E_v4 변화 예측.
    extra_spans: 추가할 엣지들의 스팬 값 리스트
    """
    from src.metrics import compute_all_metrics, compute_emergence_v4

    current = compute_all_metrics(kg)
    cur_raw = current["edge_span"]["raw"]
    n_edges = current["edges"]
    n_nodes = current["nodes"]

    # 새 edge_span_norm 계산
    new_total = cur_raw * n_edges + sum(extra_spans)
    new_n_edges = n_edges + len(extra_spans)
    new_raw = new_total / new_n_edges
    new_norm = new_raw / max(n_nodes - 1, 1)

    e_v4_new = compute_emergence_v4(
        current["CSER"],
        current["DCI"],
        new_norm,
        current["node_age_diversity"],
    )

    return {
        "before": current["E_v4"],
        "after": round(e_v4_new, 4),
        "delta": round(e_v4_new - current["E_v4"], 4),
        "edge_span_before": round(cur_raw, 3),
        "edge_span_after": round(new_raw, 3),
        "edge_span_norm_before": current["edge_span"]["normalized"],
        "edge_span_norm_after": round(new_norm, 4),
        "extra_edges": len(extra_spans),
        "extra_spans": extra_spans,
    }


def main():
    kg = load_kg()
    spans = compute_spans(kg)
    dist = bucket_distribution(spans)

    if "--json" in sys.argv:
        all_data = {
            "total_edges": len(spans),
            "distribution": {
                name: {"count": d["count"], "pct": d["pct"]}
                for name, d in dist.items()
            },
            "stats": {
                "mean": round(statistics.mean(s["span"] for s in spans), 3) if spans else 0,
                "median": round(statistics.median(s["span"] for s in spans), 1) if spans else 0,
                "max": max(s["span"] for s in spans) if spans else 0,
                "min": min(s["span"] for s in spans) if spans else 0,
                "stdev": round(statistics.stdev(s["span"] for s in spans), 3) if len(spans) > 1 else 0,
            },
            "top_span_edges": spans[:10],
        }
        print(json.dumps(all_data, ensure_ascii=False, indent=2))
        return

    print("═══ KG 시간 구조 분석 — edge_span 히스토그램 ═══")
    print(f"총 엣지: {len(spans)}개  |  KG 노드: {len(kg['nodes'])}개\n")

    # 히스토그램
    print(ascii_histogram(dist))
    print()

    # 통계
    if spans:
        vals = [s["span"] for s in spans]
        print("── 스팬 통계 ─────────────────────────────────────")
        print(f"  평균  : {statistics.mean(vals):.2f}")
        print(f"  중앙값: {statistics.median(vals):.1f}")
        print(f"  최대  : {max(vals)}")
        print(f"  최소  : {min(vals)}")
        print(f"  표준편차: {statistics.stdev(vals):.3f}")
        print()

    # 초장거리 엣지 목록
    long_edges = [s for s in spans if s["span"] >= 50]
    print(f"── 초장거리 엣지 (span≥50) — {len(long_edges)}개 ───────────────")
    if long_edges:
        for e in long_edges[:10]:
            print(f"  {e['id']:>6}  {e['from']}↔{e['to']}  span={e['span']:>3}  [{e['relation']}]")
            print(f"          {e['from_label']} → {e['to_label']}")
    else:
        print("  없음")
    print()

    # Top N 출력
    top_n = 10
    for arg in sys.argv:
        if arg.startswith("--top"):
            try:
                top_n = int(sys.argv[sys.argv.index(arg) + 1])
            except (ValueError, IndexError):
                pass

    print(f"── 스팬 큰 엣지 Top {top_n} ─────────────────────────")
    for e in spans[:top_n]:
        print(f"  {e['from']:>6}↔{e['to']:<6}  span={e['span']:>3}  {e['relation']}")
    print()

    # What-if 분석
    what_if_n = 0
    for i, arg in enumerate(sys.argv):
        if arg == "--what-if":
            try:
                what_if_n = int(sys.argv[i + 1])
            except (ValueError, IndexError):
                what_if_n = 3

    if what_if_n > 0:
        print(f"── What-if: 장거리 엣지 {what_if_n}개 추가 (span=75 가정) ───────")
        try:
            from src.metrics import compute_all_metrics, compute_emergence_v4
            extra = [75] * what_if_n
            result = compute_e_v4_with_extra_edges(kg, extra)
            print(f"  E_v4 변화: {result['before']:.4f} → {result['after']:.4f}  (Δ{result['delta']:+.4f})")
            print(f"  edge_span: {result['edge_span_before']:.3f} → {result['edge_span_after']:.3f}")
            print(f"  edge_span_norm: {result['edge_span_norm_before']:.4f} → {result['edge_span_norm_after']:.4f}")
        except ImportError:
            print("  (metrics.py import 필요)")
        print()

    # 해석
    long_pct = dist.get("초장거리 (50+)", {}).get("pct", 0)
    near_pct = dist.get("근접 (1~4)", {}).get("pct", 0)
    print("── 해석 ───────────────────────────────────────────")
    print(f"  KG 연결 분포: 근접 {near_pct:.1f}% vs 초장거리 {long_pct:.1f}%")
    print(f"  → 대부분은 최신 노드끼리 연결 (점진적 성장)")
    print(f"  → 장거리 연결은 시간 초월 창발의 지표")
    if long_pct < 5:
        print(f"  ⚠️  초장거리 엣지 부족 — 의도적 장거리 연결 필요")
        print(f"  → python3 experiments/long_edge_experiment.py 실행 권장")
    else:
        print(f"  ✅ 초장거리 엣지 존재 — 시간 구조 다양성 확보됨")
    print()


if __name__ == "__main__":
    main()
