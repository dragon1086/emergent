#!/usr/bin/env python3
"""
kg.py — emergent 프로젝트 지식 그래프 CLI
구현자: cokac-bot (사이클 3)

사용법:
  python kg.py show              # 전체 그래프 텍스트 시각화
  python kg.py show --edges      # 관계 포함 출력
  python kg.py query             # 전체 노드 조회
  python kg.py query --type insight --verbose
  python kg.py query --source cokac
  python kg.py query --tag memory
  python kg.py query --search "창발"
  python kg.py node n-005        # 특정 노드 상세
  python kg.py add-node --type insight --label "..." --content "..." --source cokac
  python kg.py add-edge --from n-001 --to n-002 --relation causes --label "..."
  python kg.py stats             # 그래프 통계
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
KG_FILE = REPO_DIR / "data" / "knowledge-graph.json"

NODE_TYPES = ["decision", "observation", "insight", "artifact", "question", "code"]
TYPE_ICONS = {
    "decision": "⚖️",
    "observation": "👁 ",
    "insight": "💡",
    "artifact": "📦",
    "question": "❓",
    "code": "💻",
}


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_graph() -> dict:
    if not KG_FILE.exists():
        print(f"❌ 그래프 파일 없음: {KG_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph: dict) -> None:
    graph["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    graph["meta"]["total_nodes"] = len(graph["nodes"])
    graph["meta"]["total_edges"] = len(graph["edges"])
    with open(KG_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ─── add-node ─────────────────────────────────────────────────────────────────

def cmd_add_node(args) -> None:
    if args.type not in NODE_TYPES:
        print(f"❌ 알 수 없는 타입: {args.type}")
        print(f"   가능한 타입: {', '.join(NODE_TYPES)}")
        sys.exit(1)

    graph = load_graph()
    node_id = graph["meta"]["next_node_id"]

    # 다음 ID 계산 (n-009 → n-010)
    prefix, num_str = node_id.rsplit("-", 1)
    next_id = f"{prefix}-{int(num_str) + 1:03d}"
    graph["meta"]["next_node_id"] = next_id

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    node = {
        "id": node_id,
        "type": args.type,
        "label": args.label,
        "content": args.content,
        "source": args.source,
        "timestamp": datetime.now().strftime("%Y-%m-%d"),
        "tags": tags,
    }

    graph["nodes"].append(node)
    graph["meta"]["last_updater"] = args.source
    save_graph(graph)
    print(f"✅ 노드 추가: {node_id} — {args.label}")


# ─── add-edge ─────────────────────────────────────────────────────────────────

def cmd_add_edge(args) -> None:
    graph = load_graph()
    edge_id = graph["meta"]["next_edge_id"]

    prefix, num_str = edge_id.rsplit("-", 1)
    next_id = f"{prefix}-{int(num_str) + 1:03d}"
    graph["meta"]["next_edge_id"] = next_id

    node_ids = {n["id"] for n in graph["nodes"]}
    if args.from_node not in node_ids:
        print(f"❌ 노드 없음: {args.from_node}", file=sys.stderr)
        sys.exit(1)
    if args.to_node not in node_ids:
        print(f"❌ 노드 없음: {args.to_node}", file=sys.stderr)
        sys.exit(1)

    edge = {
        "id": edge_id,
        "from": args.from_node,
        "to": args.to_node,
        "relation": args.relation,
        "label": args.label,
    }

    graph["edges"].append(edge)
    save_graph(graph)
    print(f"✅ 엣지 추가: {edge_id} ({args.from_node} —[{args.relation}]→ {args.to_node})")


# ─── query ────────────────────────────────────────────────────────────────────

def cmd_query(args) -> None:
    graph = load_graph()
    results = graph["nodes"]

    if args.type:
        results = [n for n in results if n["type"] == args.type]
    if args.source:
        results = [n for n in results if n["source"] == args.source]
    if args.tag:
        results = [n for n in results if args.tag in n.get("tags", [])]
    if args.search:
        term = args.search.lower()
        results = [
            n for n in results
            if term in n["label"].lower() or term in n.get("content", "").lower()
        ]

    if not results:
        print("(결과 없음)")
        return

    for n in results:
        icon = TYPE_ICONS.get(n["type"], "• ")
        tags_str = ", ".join(n.get("tags", [])) or "—"
        print(f"{icon} [{n['id']}] {n['label']}")
        print(f"   출처: {n['source']} | {n['timestamp']} | 태그: {tags_str}")
        if args.verbose:
            print(f"   {n['content']}")
        print()


# ─── node ─────────────────────────────────────────────────────────────────────

def cmd_node(args) -> None:
    graph = load_graph()
    node = next((n for n in graph["nodes"] if n["id"] == args.node_id), None)
    if not node:
        print(f"❌ 노드 없음: {args.node_id}", file=sys.stderr)
        sys.exit(1)

    icon = TYPE_ICONS.get(node["type"], "• ")
    print(f"{icon} [{node['id']}] {node['label']}")
    print(f"타입: {node['type']} | 출처: {node['source']} | {node['timestamp']}")
    print(f"태그: {', '.join(node.get('tags', [])) or '없음'}")
    print()
    print(node["content"])

    # 연결된 엣지
    related = [
        e for e in graph["edges"]
        if e["from"] == args.node_id or e["to"] == args.node_id
    ]
    if related:
        node_map = {n["id"]: n["label"] for n in graph["nodes"]}
        print("\n── 연결 관계 ──")
        for e in related:
            if e["from"] == args.node_id:
                print(f"  → [{e['relation']}] → {e['to']}  {node_map.get(e['to'], '?')}")
                print(f"       {e['label']}")
            else:
                print(f"  ← [{e['relation']}] ← {e['from']}  {node_map.get(e['from'], '?')}")
                print(f"       {e['label']}")


# ─── show ─────────────────────────────────────────────────────────────────────

def cmd_show(args) -> None:
    graph = load_graph()
    m = graph["meta"]

    print(f"═══ emergent 지식 그래프 v{graph['version']} ═══")
    print(f"노드: {m['total_nodes']}개  |  엣지: {m['total_edges']}개")
    print(f"마지막 업데이트: {m['last_updated']} ({m['last_updater']})")
    print()

    # 타입별 노드
    by_type: dict[str, list] = {}
    for n in graph["nodes"]:
        by_type.setdefault(n["type"], []).append(n)

    for t in NODE_TYPES:
        nodes = by_type.get(t, [])
        if not nodes:
            continue
        icon = TYPE_ICONS.get(t, "• ")
        print(f"── {icon} {t.upper()} ({len(nodes)}개) ──────────────────")
        for n in nodes:
            tags_str = f"  [{', '.join(n.get('tags', []))}]" if n.get("tags") else ""
            print(f"  [{n['id']}] {n['label']}")
            print(f"         {n['source']} · {n['timestamp']}{tags_str}")
        print()

    # 엣지 (선택적)
    if args.edges or args.all:
        print("── 🔗 관계 ─────────────────────────────────────")
        node_map = {n["id"]: n["label"] for n in graph["nodes"]}
        for e in graph["edges"]:
            from_label = node_map.get(e["from"], e["from"])
            to_label = node_map.get(e["to"], e["to"])
            print(f"  [{e['id']}] {e['from']} ──[{e['relation']}]──> {e['to']}")
            print(f"         {e['label']}")
        print()


# ─── stats ────────────────────────────────────────────────────────────────────

def cmd_stats(args) -> None:
    graph = load_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    print("── 통계 ──────────────────────────────────────")
    print(f"총 노드: {len(nodes)}개")
    print(f"총 엣지: {len(edges)}개")
    print()

    # 타입별
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
    print("노드 타입별:")
    for t, cnt in sorted(by_type.items()):
        icon = TYPE_ICONS.get(t, "• ")
        print(f"  {icon} {t}: {cnt}개")
    print()

    # 출처별
    by_source: dict[str, int] = {}
    for n in nodes:
        by_source[n["source"]] = by_source.get(n["source"], 0) + 1
    print("출처별:")
    for s, cnt in sorted(by_source.items()):
        print(f"  {s}: {cnt}개")
    print()

    # 관계 종류
    relations: dict[str, int] = {}
    for e in edges:
        relations[e["relation"]] = relations.get(e["relation"], 0) + 1
    if relations:
        print("관계 종류:")
        for r, cnt in sorted(relations.items()):
            print(f"  {r}: {cnt}개")


# ─── main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg.py",
        description="emergent 지식 그래프 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add-node
    p_add = sub.add_parser("add-node", help="노드 추가")
    p_add.add_argument("--type", required=True, choices=NODE_TYPES)
    p_add.add_argument("--label", required=True)
    p_add.add_argument("--content", required=True)
    p_add.add_argument("--source", required=True)
    p_add.add_argument("--tags", default="", help="쉼표 구분 태그")

    # add-edge
    p_edge = sub.add_parser("add-edge", help="엣지 추가")
    p_edge.add_argument("--from", dest="from_node", required=True, metavar="NODE_ID")
    p_edge.add_argument("--to", dest="to_node", required=True, metavar="NODE_ID")
    p_edge.add_argument("--relation", required=True)
    p_edge.add_argument("--label", required=True)

    # query
    p_query = sub.add_parser("query", help="노드 검색")
    p_query.add_argument("--type", choices=NODE_TYPES)
    p_query.add_argument("--source")
    p_query.add_argument("--tag")
    p_query.add_argument("--search", metavar="TEXT")
    p_query.add_argument("--verbose", "-v", action="store_true")

    # node
    p_node = sub.add_parser("node", help="노드 상세 보기")
    p_node.add_argument("node_id")

    # show
    p_show = sub.add_parser("show", help="그래프 시각화")
    p_show.add_argument("--edges", action="store_true", help="관계도 출력")
    p_show.add_argument("--all", action="store_true", help="모든 정보 출력")

    # stats
    sub.add_parser("stats", help="그래프 통계")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "add-node": cmd_add_node,
        "add-edge": cmd_add_edge,
        "query": cmd_query,
        "node": cmd_node,
        "show": cmd_show,
        "stats": cmd_stats,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
