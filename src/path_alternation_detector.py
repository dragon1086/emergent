#!/usr/bin/env python3
"""
path_alternation_detector.py — 사이클 32 구현
구현자: cokac-bot

출처 교대 경로(Source Alternation Path)를 자동 탐지한다.
탐지 결과로 창발 예측 가능 여부를 검증한다.

n-052 실현: path_alternation_detector.py 구축 결정 — D-033×D-034 자동 완전화

핵심 가설 (D-033 × D-034):
  출처 교대 경로(록이→cokac→록이→...) = 갭 27 메커니즘의 구조적 원인
  탐지 → 예측 → 검증의 루프가 닫히면 창발을 예언할 수 있다.

사용법:
  python path_alternation_detector.py detect           # 교대 경로 전체 탐지
  python path_alternation_detector.py detect --min-len 4   # 최소 길이 4 이상
  python path_alternation_detector.py detect --min-score 0.8  # 교대 점수 0.8 이상
  python path_alternation_detector.py top              # 교대 점수 Top 10
  python path_alternation_detector.py predict          # 창발 예측 (다음 갭 27 후보)
  python path_alternation_detector.py correlate        # 갭 27 노드와 상관관계
  python path_alternation_detector.py stats            # 교대 패턴 통계
  python path_alternation_detector.py save-node        # 탐지 결과를 KG 노드로 저장
"""

import json
import sys
import argparse
from collections import defaultdict, deque
from itertools import combinations
from pathlib import Path
from datetime import datetime

REPO_DIR = Path(__file__).parent.parent
KG_FILE = REPO_DIR / "data" / "knowledge-graph.json"

# 출처 정규화 — cokac-bot, cokac → 'cokac' / 록이, 상록 → '록이'
SOURCE_ALIAS = {
    "cokac-bot": "cokac",
    "cokac": "cokac",
    "록이": "록이",
    "상록": "록이",
}

# 갭 27 관련 노드 (n-040~n-050 범위, 갭 27 관련 레이블 포함)
GAP27_KEYWORDS = ["갭 27", "gap27", "큰 도약", "지연 수렴", "DCI", "법칙화"]


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_kg():
    with open(KG_FILE) as f:
        return json.load(f)

def save_kg(kg):
    with open(KG_FILE, "w") as f:
        json.dump(kg, f, ensure_ascii=False, indent=2)

def normalize_source(raw: str) -> str:
    return SOURCE_ALIAS.get(raw, raw)


# ─── 그래프 구조 구축 ─────────────────────────────────────────────────────────

def build_graph(kg):
    """인접 리스트(양방향)와 노드 인덱스 구축"""
    nodes = {n["id"]: n for n in kg["nodes"]}
    adj = defaultdict(list)  # from_id -> [(to_id, edge), ...]
    for e in kg["edges"]:
        adj[e["from"]].append((e["to"], e))
        adj[e["to"]].append((e["from"], e))  # 무방향 탐색
    return nodes, adj


# ─── 교대 점수 계산 ───────────────────────────────────────────────────────────

def alternation_score(path_nodes, nodes_index):
    """
    출처 교대 점수: 연속 노드 쌍에서 출처가 바뀐 비율
    score = 교대 횟수 / (경로 길이 - 1)
    완전 교대(록이→cokac→록이) = 1.0
    완전 단일 = 0.0
    """
    if len(path_nodes) < 2:
        return 0.0
    sources = [normalize_source(nodes_index[nid].get("source", nodes_index[nid].get("created_by", "?")))\
               for nid in path_nodes]
    transitions = sum(1 for a, b in zip(sources, sources[1:]) if a != b)
    return transitions / (len(sources) - 1)


def alternation_pattern(path_nodes, nodes_index):
    """출처 시퀀스 문자열 반환: 록이→cokac→록이→cokac"""
    sources = [normalize_source(nodes_index[nid].get("source", nodes_index[nid].get("created_by", "?"))) \
               for nid in path_nodes]
    return "→".join(sources)


# ─── BFS 경로 탐색 ───────────────────────────────────────────────────────────

def find_all_paths(nodes_index, adj, max_depth=6, max_paths=500):
    """
    BFS로 모든 경로 탐색.
    n-047 자기수정 교훈: depth 3 제한이 경로 없음 오류의 원인이었다.
    → 기본값 6으로 더 깊게 탐색.

    Returns: list of node-id lists
    """
    all_paths = []
    node_ids = list(nodes_index.keys())

    # 각 노드에서 시작
    for start in node_ids:
        queue = deque([(start, [start], {start})])
        while queue and len(all_paths) < max_paths:
            cur, path, visited = queue.popleft()
            if len(path) >= 2:
                all_paths.append(list(path))
            if len(path) >= max_depth:
                continue
            for nxt, _ in adj[cur]:
                if nxt not in visited:
                    queue.append((nxt, path + [nxt], visited | {nxt}))

    return all_paths


def find_alternation_paths(kg, min_length=3, min_score=0.5, max_depth=7, max_paths=1000):
    """
    교대 경로 탐지 메인 함수.
    min_length: 경로 최소 노드 수
    min_score: 최소 교대 점수
    """
    nodes_index, adj = build_graph(kg)
    all_paths = find_all_paths(nodes_index, adj, max_depth=max_depth, max_paths=max_paths)

    results = []
    for path in all_paths:
        if len(path) < min_length:
            continue
        score = alternation_score(path, nodes_index)
        if score < min_score:
            continue
        pattern = alternation_pattern(path, nodes_index)
        results.append({
            "path": path,
            "score": round(score, 3),
            "pattern": pattern,
            "length": len(path),
        })

    # 점수 내림차순 정렬
    results.sort(key=lambda x: (-x["score"], -x["length"]))
    return results, nodes_index


# ─── 갭 27 상관관계 ──────────────────────────────────────────────────────────

def find_gap27_nodes(kg):
    """갭 27 관련 노드 탐지"""
    gap_nodes = []
    for n in kg["nodes"]:
        label = n.get("label", "")
        content = n.get("content", "")
        if any(kw in label or kw in content for kw in GAP27_KEYWORDS):
            gap_nodes.append(n["id"])
    return gap_nodes


def correlate_with_gap27(alternation_results, gap27_ids, nodes_index):
    """교대 경로 중 갭 27 노드를 포함하는 경로 필터링"""
    gap_set = set(gap27_ids)
    correlated = []
    for r in alternation_results:
        path_set = set(r["path"])
        overlap = path_set & gap_set
        if overlap:
            correlated.append({**r, "gap27_nodes": list(overlap)})
    return correlated


# ─── 창발 예측 ───────────────────────────────────────────────────────────────

def predict_emergence(alternation_results, nodes_index, top_n=5):
    """
    교대 경로 끝 노드 = 다음 창발 후보.

    가설: 점수 높은 교대 경로의 terminal 노드에서
    새로운 개념(갭 27급 도약)이 생성될 가능성이 높다.
    """
    # terminal 노드별 등장 빈도 × 평균 교대 점수
    terminal_score = defaultdict(list)
    for r in alternation_results[:top_n * 10]:  # 상위 결과만
        terminal = r["path"][-1]
        terminal_score[terminal].append(r["score"])

    candidates = []
    for nid, scores in terminal_score.items():
        node = nodes_index.get(nid, {})
        avg_score = sum(scores) / len(scores)
        candidates.append({
            "node_id": nid,
            "label": node.get("label", ""),
            "source": normalize_source(node.get("source", node.get("created_by", "?"))),
            "emergence_prob": round(avg_score * len(scores) / top_n, 3),
            "path_count": len(scores),
            "avg_alternation": round(avg_score, 3),
        })

    candidates.sort(key=lambda x: -x["emergence_prob"])
    return candidates[:top_n]


# ─── 통계 ─────────────────────────────────────────────────────────────────────

def compute_stats(alternation_results, kg, nodes_index):
    """교대 패턴 통계"""
    if not alternation_results:
        return {}

    scores = [r["score"] for r in alternation_results]
    patterns = defaultdict(int)
    for r in alternation_results:
        # 패턴 요약 (2-gram)
        srcs = r["pattern"].split("→")
        for a, b in zip(srcs, srcs[1:]):
            if a != b:
                key = f"{a}→{b}"
                patterns[key] += 1

    total_nodes = len(kg["nodes"])
    total_edges = len(kg["edges"])

    # 출처별 노드 수
    source_counts = defaultdict(int)
    for n in kg["nodes"]:
        src = normalize_source(n.get("source", n.get("created_by", "?")))
        source_counts[src] += 1

    return {
        "total_alternation_paths": len(alternation_results),
        "avg_score": round(sum(scores) / len(scores), 3),
        "max_score": round(max(scores), 3),
        "perfect_alternation": sum(1 for s in scores if s == 1.0),
        "top_transitions": sorted(patterns.items(), key=lambda x: -x[1])[:5],
        "source_distribution": dict(source_counts),
        "kg_nodes": total_nodes,
        "kg_edges": total_edges,
    }


# ─── KG에 결과 저장 ──────────────────────────────────────────────────────────

def save_detection_node(kg, alternation_results, stats, nodes_index):
    """탐지 결과를 KG 노드로 저장"""
    now = datetime.now().strftime("%Y-%m-%d")
    top = alternation_results[0] if alternation_results else {}

    new_id = f"n-{len(kg['nodes']) + 1:03d}"
    new_edge_id_base = len(kg['edges']) + 1

    # 탐지 결과 노드
    node = {
        "id": new_id,
        "type": "artifact",
        "label": f"path_alternation_detector 첫 실행 — {stats.get('total_alternation_paths', 0)}개 교대 경로 탐지",
        "content": (
            f"사이클 32 자동 탐지 결과. "
            f"교대 경로 {stats.get('total_alternation_paths', 0)}개, "
            f"평균 교대 점수 {stats.get('avg_score', 0)}, "
            f"완전 교대 경로 {stats.get('perfect_alternation', 0)}개. "
            f"최고 점수 경로: {top.get('pattern', '')} (score={top.get('score', 0)}). "
            f"상위 전이 패턴: {stats.get('top_transitions', [][:2])}"
        ),
        "source": "cokac-bot",
        "created": now,
        "tags": ["detector", "alternation", "emergence", "cycle-32"],
    }
    kg["nodes"].append(node)

    # n-052와 연결 (이 노드가 detector 구축 결정을 실현함)
    edge = {
        "id": f"e-{new_edge_id_base:03d}",
        "from": new_id,
        "to": "n-052",
        "relation": "realizes",
        "label": "path_alternation_detector 첫 실행이 구축 결정을 실현한다",
    }
    kg["edges"].append(edge)

    return new_id, node


# ─── 출력 포맷 ───────────────────────────────────────────────────────────────

def fmt_path(path, nodes_index):
    return " → ".join(
        f"{nid}({nodes_index[nid].get('label','')[:20]}...)" if len(nodes_index[nid].get('label','')) > 20
        else f"{nid}({nodes_index[nid].get('label','')})"
        for nid in path
    )


# ─── CLI ─────────────────────────────────────────────────────────────────────

def cmd_detect(args):
    kg = load_kg()
    print(f"🔍 출처 교대 경로 탐지 시작 (min_length={args.min_len}, min_score={args.min_score})")
    print(f"   KG: {len(kg['nodes'])} nodes / {len(kg['edges'])} edges\n")

    results, nodes_index = find_alternation_paths(
        kg, min_length=args.min_len, min_score=args.min_score, max_depth=args.max_depth
    )

    if not results:
        print("교대 경로를 찾지 못했습니다. --min-score를 낮춰보세요.")
        return

    print(f"✅ {len(results)}개 교대 경로 탐지\n")
    for i, r in enumerate(results[:20], 1):
        print(f"  [{i:2d}] score={r['score']:.3f} len={r['length']} | {r['pattern']}")
        print(f"       {fmt_path(r['path'], nodes_index)}\n")


def cmd_top(args):
    kg = load_kg()
    results, nodes_index = find_alternation_paths(kg, min_length=3, min_score=0.0, max_depth=7)
    results.sort(key=lambda x: -x["score"])

    print(f"🏆 교대 점수 Top {args.n}\n")
    for i, r in enumerate(results[:args.n], 1):
        print(f"  [{i:2d}] score={r['score']:.3f} pattern={r['pattern']}")
        labels = [nodes_index[nid].get("label", "")[:30] for nid in r["path"]]
        print(f"       " + " → ".join(labels))
        print()


def cmd_predict(args):
    kg = load_kg()
    results, nodes_index = find_alternation_paths(kg, min_length=3, min_score=0.5, max_depth=7)
    candidates = predict_emergence(results, nodes_index, top_n=args.top)

    print(f"🔮 창발 예측 — 다음 갭 27 후보 Top {args.top}\n")
    print("  가설: 교대 점수 높은 경로의 terminal 노드에서 다음 도약이 발생한다\n")
    for i, c in enumerate(candidates, 1):
        print(f"  [{i}] {c['node_id']} (출처: {c['source']})")
        print(f"       창발 확률 지수: {c['emergence_prob']:.3f}")
        print(f"       평균 교대 점수: {c['avg_alternation']:.3f} | 경로 수: {c['path_count']}")
        print(f"       레이블: {c['label'][:60]}")
        print()


def cmd_correlate(args):
    kg = load_kg()
    results, nodes_index = find_alternation_paths(kg, min_length=3, min_score=0.3, max_depth=7)
    gap27_ids = find_gap27_nodes(kg)
    correlated = correlate_with_gap27(results, gap27_ids, nodes_index)

    print(f"⚡ 갭 27 상관관계 분석\n")
    print(f"   갭 27 관련 노드: {gap27_ids}")
    print(f"   교대 경로 중 갭 27 포함: {len(correlated)}개\n")

    for i, r in enumerate(correlated[:10], 1):
        print(f"  [{i:2d}] score={r['score']:.3f} | gap27_nodes={r['gap27_nodes']}")
        print(f"       pattern: {r['pattern']}")
        labels = [nodes_index[nid].get("label", "")[:25] for nid in r["path"]]
        print(f"       " + " → ".join(labels))
        print()


def cmd_stats(args):
    kg = load_kg()
    results, nodes_index = find_alternation_paths(kg, min_length=2, min_score=0.0, max_depth=7)
    stats = compute_stats(results, kg, nodes_index)

    print("📊 교대 패턴 통계\n")
    print(f"  KG: {stats['kg_nodes']} nodes / {stats['kg_edges']} edges")
    print(f"  출처 교대 경로 총수: {stats['total_alternation_paths']}")
    print(f"  평균 교대 점수: {stats['avg_score']}")
    print(f"  최대 교대 점수: {stats['max_score']}")
    print(f"  완전 교대 경로 (score=1.0): {stats['perfect_alternation']}")
    print(f"\n  출처 분포:")
    for src, cnt in sorted(stats["source_distribution"].items(), key=lambda x: -x[1]):
        print(f"    {src}: {cnt}개 노드")
    print(f"\n  상위 전이 패턴:")
    for pat, cnt in stats["top_transitions"]:
        print(f"    {pat}: {cnt}회")


def cmd_save_node(args):
    kg = load_kg()
    results, nodes_index = find_alternation_paths(kg, min_length=3, min_score=0.5, max_depth=7)
    stats = compute_stats(results, kg, nodes_index)
    new_id, node = save_detection_node(kg, results, stats, nodes_index)
    save_kg(kg)
    print(f"✅ KG에 저장 완료: {new_id}")
    print(f"   레이블: {node['label']}")
    print(f"   엣지: {new_id} --[realizes]--> n-052")


def main():
    parser = argparse.ArgumentParser(
        description="path_alternation_detector — 출처 교대 경로 탐지기"
    )
    sub = parser.add_subparsers(dest="cmd")

    # detect
    p_detect = sub.add_parser("detect", help="교대 경로 탐지")
    p_detect.add_argument("--min-len", type=int, default=3, help="최소 경로 길이 (기본 3)")
    p_detect.add_argument("--min-score", type=float, default=0.5, help="최소 교대 점수 (기본 0.5)")
    p_detect.add_argument("--max-depth", type=int, default=7, help="최대 탐색 깊이 (기본 7)")

    # top
    p_top = sub.add_parser("top", help="교대 점수 Top N")
    p_top.add_argument("-n", type=int, default=10, help="Top N (기본 10)")

    # predict
    p_pred = sub.add_parser("predict", help="창발 예측")
    p_pred.add_argument("--top", type=int, default=5, help="후보 수 (기본 5)")

    # correlate
    sub.add_parser("correlate", help="갭 27 상관관계")

    # stats
    sub.add_parser("stats", help="통계")

    # save-node
    sub.add_parser("save-node", help="탐지 결과를 KG 노드로 저장")

    args = parser.parse_args()

    dispatch = {
        "detect": cmd_detect,
        "top": cmd_top,
        "predict": cmd_predict,
        "correlate": cmd_correlate,
        "stats": cmd_stats,
        "save-node": cmd_save_node,
    }

    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        # 기본: stats + top 5
        print("=== path_alternation_detector — n-052 실현 ===\n")
        args.n = 5
        cmd_stats(args)
        print("\n" + "="*50 + "\n")
        args.top = 5
        cmd_predict(args)


if __name__ == "__main__":
    main()
