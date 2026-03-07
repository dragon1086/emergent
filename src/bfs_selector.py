#!/usr/bin/env python3
"""BFS-based old node selector for DCI recovery.

Replaces random.choice(old_ids) with BFS distance maximization.
Called from evolve-auto-kg{2,3,4}.sh HARD-FIX sections.

Usage:
  python3 src/bfs_selector.py <kg_path> <edge_to> [<old_ids_space_separated>]

Output:
  KEEP              — edge_to is already in old_ids
  OVERRIDE:<old>:<new> — edge_to was outside old_ids, replaced with BFS-max
"""
import json
import re
import sys
from collections import deque


def _node_num(nid: str) -> int:
    m = re.search(r'\d+', nid)
    return int(m.group()) if m else 0


def build_adjacency(kg: dict) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for e in kg.get("edges", []):
        src, tgt = e["from"], e["to"]
        adj.setdefault(src, []).append(tgt)
        adj.setdefault(tgt, []).append(src)
    return adj


def bfs_distances(adj: dict[str, list[str]], start: str) -> dict[str, int]:
    dist = {start: 0}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nb in adj.get(cur, []):
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                queue.append(nb)
    return dist


def select_bfs_max(kg_path: str, edge_to: str, old_ids: list[str]) -> str:
    """Select the old_id with maximum BFS distance from the newest node.

    Tie-break: prefer lower node_id (older node).
    Fallback: random.choice if graph can't be loaded.
    """
    if not old_ids:
        return f"KEEP"

    if edge_to in old_ids:
        return "KEEP"

    try:
        with open(kg_path, encoding="utf-8") as f:
            kg = json.load(f)
    except Exception:
        import random
        return f"OVERRIDE:{edge_to}:{random.choice(old_ids)}"

    nodes = kg.get("nodes", [])
    if not nodes:
        import random
        return f"OVERRIDE:{edge_to}:{random.choice(old_ids)}"

    # Find newest node (highest node_id number)
    newest = max(nodes, key=lambda n: _node_num(n["id"]))
    newest_id = newest["id"]

    adj = build_adjacency(kg)
    dists = bfs_distances(adj, newest_id)

    # Score old_ids by BFS distance (higher = better)
    # Tie-break: lower node_num (older) preferred
    scored = []
    for oid in old_ids:
        d = dists.get(oid, len(nodes))  # unreachable = max distance
        scored.append((-d, _node_num(oid), oid))  # neg distance for min sort

    scored.sort()
    best = scored[0][2]
    return f"OVERRIDE:{edge_to}:{best}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: bfs_selector.py <kg_path> <edge_to> [old_ids...]", file=sys.stderr)
        sys.exit(1)

    kg_path = sys.argv[1]
    edge_to = sys.argv[2]
    old_ids = sys.argv[3].split() if len(sys.argv) > 3 else []

    print(select_bfs_max(kg_path, edge_to, old_ids))
