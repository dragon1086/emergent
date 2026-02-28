#!/usr/bin/env python3
"""
persona_fingerprint.py — 사이클 36 구현
구현자: cokac-bot

D-036 이후 다음 질문: 페르소나 지문이 시간에 따라 진화하는가?

핵심 질문 (n-065):
  비대칭은 불변이다 (D-036).
  하지만 비대칭의 '질'이 변하는가?
  초기 사이클 vs 최근 사이클의 패턴 지문이 달라지는가?

측정 지표:
  1. 노드 타입 분포 (question / observation / decision / insight 비율)
  2. 관계 타입 분포 (어떤 엣지를 만드는가)
  3. 연결 밀도 (노드당 평균 엣지 수)
  4. 교차 소스 비율 (자신→자신 vs 자신→상대방 관계)
  5. 코사인 유사도 (초기 지문 vs 최근 지문)

사용법:
  python persona_fingerprint.py print        # 현재 지문 출력
  python persona_fingerprint.py compare      # 초기 vs 최근 비교
  python persona_fingerprint.py timeline     # 사이클별 지문 변화
  python persona_fingerprint.py divergence   # 두 페르소나 간 거리
"""

import json
import sys
import math
from pathlib import Path
from collections import defaultdict, Counter

REPO_DIR = Path(__file__).parent.parent
KG_FILE = REPO_DIR / "data" / "knowledge-graph.json"

SOURCE_ALIAS = {
    "cokac-bot": "cokac",
    "cokac": "cokac",
    "록이": "록이",
    "상록": "록이",
}


def load_kg():
    with open(KG_FILE) as f:
        return json.load(f)


def normalize(s):
    return SOURCE_ALIAS.get(s, s)


def compute_fingerprint(nodes, edges, source_filter=None):
    """에이전트 페르소나 지문 계산"""
    if source_filter:
        target_nodes = [n for n in nodes if normalize(n.get("source", "")) == source_filter]
    else:
        target_nodes = nodes

    if not target_nodes:
        return None

    target_ids = {n["id"] for n in target_nodes}

    # 1. 노드 타입 분포
    type_dist = Counter(n.get("type", "unknown") for n in target_nodes)
    total_nodes = len(target_nodes)
    type_vec = {t: c / total_nodes for t, c in type_dist.items()}

    # 2. 관계 타입 분포 (아웃바운드 엣지)
    out_edges = [e for e in edges if e.get("from", "") in target_ids]
    rel_dist = Counter(e.get("relation", "unknown") for e in out_edges)
    total_rels = len(out_edges) if out_edges else 1
    rel_vec = {r: c / total_rels for r, c in rel_dist.items()}

    # 3. 연결 밀도
    in_edges = [e for e in edges if e.get("to", "") in target_ids]
    avg_out_degree = len(out_edges) / total_nodes
    avg_in_degree = len(in_edges) / total_nodes

    # 4. 교차 소스 비율
    all_node_src = {n["id"]: normalize(n.get("source", "unknown")) for n in nodes}
    cross_edges = [
        e for e in out_edges
        if e.get("to", "") in all_node_src
        and all_node_src.get(e.get("to", ""), "") != source_filter
    ]
    cross_ratio = len(cross_edges) / len(out_edges) if out_edges else 0

    # 5. 태그 다양성
    all_tags = []
    for n in target_nodes:
        all_tags.extend(n.get("tags", []))
    tag_entropy = _entropy(Counter(all_tags))

    return {
        "source": source_filter,
        "node_count": total_nodes,
        "type_distribution": dict(type_dist),
        "type_vector": type_vec,
        "relation_distribution": dict(rel_dist),
        "relation_vector": rel_vec,
        "avg_out_degree": round(avg_out_degree, 3),
        "avg_in_degree": round(avg_in_degree, 3),
        "cross_source_ratio": round(cross_ratio, 3),
        "tag_entropy": round(tag_entropy, 3),
        "dominant_type": type_dist.most_common(1)[0][0] if type_dist else "none",
        "dominant_relation": rel_dist.most_common(1)[0][0] if rel_dist else "none",
    }


def _entropy(counter):
    """Shannon entropy"""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counter.values() if c > 0)


def cosine_similarity(vec_a, vec_b):
    """두 벡터의 코사인 유사도"""
    keys = set(vec_a.keys()) | set(vec_b.keys())
    a = [vec_a.get(k, 0) for k in keys]
    b = [vec_b.get(k, 0) for k in keys]

    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / (mag_a * mag_b), 4)


def split_by_era(nodes, early_cutoff=15, late_start=45):
    """초기 / 중기 / 최근 노드 분리"""
    early, mid, late = [], [], []
    for n in nodes:
        nid = int(n["id"].replace("n-", ""))
        if nid <= early_cutoff:
            early.append(n)
        elif nid >= late_start:
            late.append(n)
        else:
            mid.append(n)
    return early, mid, late


def cmd_print(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]

    print("=" * 55)
    print("🔬 페르소나 지문 (현재 전체)")
    print("=" * 55)
    for source in ["록이", "cokac"]:
        fp = compute_fingerprint(nodes, edges, source)
        if not fp:
            continue
        print(f"\n【{source}】 ({fp['node_count']} 노드)")
        print(f"  주요 노드 타입: {fp['dominant_type']} | 타입 분포: {fp['type_distribution']}")
        print(f"  주요 관계 타입: {fp['dominant_relation']}")
        print(f"  출력 연결도: {fp['avg_out_degree']} | 교차 소스 비율: {fp['cross_source_ratio']}")
        print(f"  태그 엔트로피: {fp['tag_entropy']}")


def cmd_compare(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]
    early_nodes, _, late_nodes = split_by_era(nodes)

    print("=" * 55)
    print("🧬 초기 vs 최근 — 페르소나 지문 비교")
    print(f"   초기: n-001~n-015 ({len(early_nodes)} 노드)")
    print(f"   최근: n-045~n-064 ({len(late_nodes)} 노드)")
    print("=" * 55)

    for source in ["록이", "cokac"]:
        fp_early = compute_fingerprint(early_nodes, edges, source)
        fp_late = compute_fingerprint(late_nodes, edges, source)

        if not fp_early or not fp_late:
            print(f"\n【{source}】 데이터 부족")
            continue

        sim_type = cosine_similarity(fp_early["type_vector"], fp_late["type_vector"])
        sim_rel = cosine_similarity(fp_early["relation_vector"], fp_late["relation_vector"])

        print(f"\n【{source}】")
        print(f"  초기 주요 타입: {fp_early['dominant_type']} → 최근: {fp_late['dominant_type']}")
        print(f"  타입 유사도 (코사인): {sim_type}  {'← 불변' if sim_type > 0.9 else '← 변화'}")
        print(f"  관계 유사도 (코사인): {sim_rel}  {'← 불변' if sim_rel > 0.9 else '← 변화'}")
        print(f"  교차 소스 비율: {fp_early['cross_source_ratio']} → {fp_late['cross_source_ratio']}")
        print(f"  태그 엔트로피: {fp_early['tag_entropy']} → {fp_late['tag_entropy']}")


def cmd_timeline(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]

    print("=" * 55)
    print("📈 사이클별 페르소나 지문 변화 (window=10)")
    print("=" * 55)

    window = 10
    all_ids = sorted(int(n["id"].replace("n-", "")) for n in nodes)
    max_id = all_ids[-1]

    for start in range(1, max_id, window):
        end = start + window - 1
        window_nodes = [n for n in nodes if start <= int(n["id"].replace("n-", "")) <= end]
        if len(window_nodes) < 3:
            continue

        r_fp = compute_fingerprint(window_nodes, edges, "록이")
        c_fp = compute_fingerprint(window_nodes, edges, "cokac")

        r_cross = r_fp["cross_source_ratio"] if r_fp else 0
        c_cross = c_fp["cross_source_ratio"] if c_fp else 0
        r_dom = r_fp["dominant_type"][:8] if r_fp else "-"
        c_dom = c_fp["dominant_type"][:8] if c_fp else "-"

        print(f"  n-{start:03d}~n-{end:03d}: 록이={r_dom}({r_cross:.2f}) | cokac={c_dom}({c_cross:.2f})")


def cmd_divergence(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]

    fp_r = compute_fingerprint(nodes, edges, "록이")
    fp_c = compute_fingerprint(nodes, edges, "cokac")

    if not fp_r or not fp_c:
        print("데이터 부족")
        return

    type_sim = cosine_similarity(fp_r["type_vector"], fp_c["type_vector"])
    rel_sim = cosine_similarity(fp_r["relation_vector"], fp_c["relation_vector"])
    divergence = round(1 - (type_sim + rel_sim) / 2, 4)

    print("=" * 55)
    print("↔️  두 페르소나 간 거리 (Divergence)")
    print("=" * 55)
    print(f"  타입 유사도: {type_sim}")
    print(f"  관계 유사도: {rel_sim}")
    print(f"  페르소나 거리: {divergence}  (0=동일, 1=완전 다름)")
    print()
    print(f"  록이 주요: {fp_r['dominant_type']} / {fp_r['dominant_relation']}")
    print(f"  cokac 주요: {fp_c['dominant_type']} / {fp_c['dominant_relation']}")
    print()
    if divergence > 0.3:
        print("  → 두 페르소나는 구조적으로 다르다")
    else:
        print("  → 두 페르소나는 수렴하고 있다")


def main():
    kg = load_kg()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "print"

    if cmd == "print":
        cmd_print(kg)
    elif cmd == "compare":
        cmd_compare(kg)
    elif cmd == "timeline":
        cmd_timeline(kg)
    elif cmd == "divergence":
        cmd_divergence(kg)
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python persona_fingerprint.py [print|compare|timeline|divergence]")


if __name__ == "__main__":
    main()
