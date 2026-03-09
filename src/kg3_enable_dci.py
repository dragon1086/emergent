#!/usr/bin/env python3
"""kg3_enable_dci.py — Enable DCI metric by promoting insights to question nodes.

DCI (Dialogue Convergence Index) requires 'question' type nodes with 'answers'
edges. This script identifies high-connectivity insight nodes and converts them
to question nodes, rewiring existing edges as 'answers' relationships.

Selection criteria:
  - Node has 3+ inbound edges (well-connected = good question candidate)
  - Prefers nodes with 'critique' inbound edges (debate implies open question)
  - Skips nodes already of type 'question'

Usage:
  python3 src/kg3_enable_dci.py --dry-run     # preview conversions
  python3 src/kg3_enable_dci.py --apply        # apply and save
  python3 src/kg3_enable_dci.py --apply --max 5  # convert up to 5 nodes
"""
import json
import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
DEFAULT_KG = REPO / "kg3" / "data" / "knowledge-graph.json"


def load_kg(path: str = None) -> tuple[dict, Path]:
    p = Path(path) if path else Path(os.environ.get("EMERGENT_KG_PATH", str(DEFAULT_KG)))
    with open(p, encoding="utf-8") as f:
        return json.load(f), p


def _node_num(nid: str) -> int:
    m = re.search(r'\d+', nid)
    return int(m.group()) if m else 0


def find_question_candidates(kg: dict, max_count: int = 5) -> list[dict]:
    """Find nodes suitable for promotion to 'question' type."""
    # Build inbound edge map
    inbound = defaultdict(list)
    for e in kg["edges"]:
        inbound[e["to"]].append(e)

    candidates = []
    for node in kg["nodes"]:
        if node.get("type") == "question":
            continue  # already a question

        nid = node["id"]
        in_edges = inbound.get(nid, [])
        if len(in_edges) < 3:
            continue  # not well-connected enough

        # Score: base = inbound count, bonus for critique edges
        critique_bonus = sum(1 for e in in_edges if e.get("relation") == "critiques")
        cross_source = sum(1 for e in in_edges if e.get("cross_source"))
        score = len(in_edges) + critique_bonus * 2 + cross_source

        candidates.append({
            "node": node,
            "inbound_count": len(in_edges),
            "critique_count": critique_bonus,
            "cross_source_count": cross_source,
            "score": score,
            "edges": in_edges,
        })

    # Sort by score descending, take top N
    candidates.sort(key=lambda c: -c["score"])
    return candidates[:max_count]


def promote_to_questions(kg: dict, candidates: list[dict]) -> int:
    """Promote candidate nodes to 'question' type and rewire edges."""
    converted = 0
    for c in candidates:
        node = c["node"]
        # Change type to question
        node["type"] = "question"
        # Prepend label with question indicator if not already
        if not node["label"].startswith("[Q]"):
            node["label"] = f"[Q] {node['label']}"

        # Rewire inbound edges to 'answers' relation
        for e in c["edges"]:
            if e.get("relation") not in ("answers",):
                e["relation"] = "answers"
                e["label"] = f"answers: {e.get('label', '')[:80]}"

        converted += 1

    return converted


def main():
    parser = argparse.ArgumentParser(description="Enable DCI by promoting insights to questions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--apply", action="store_true", help="Apply and save")
    parser.add_argument("--max", type=int, default=5, help="Max nodes to convert (default: 5)")
    parser.add_argument("--kg", help="Path to KG JSON file")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply")
        sys.exit(1)

    kg, kg_path = load_kg(args.kg)

    existing_questions = sum(1 for n in kg["nodes"] if n.get("type") == "question")
    print(f"KG-3 DCI Enablement")
    print(f"{'=' * 55}")
    print(f"  Nodes: {len(kg['nodes'])}  |  Edges: {len(kg['edges'])}")
    print(f"  Existing question nodes: {existing_questions}")
    print()

    candidates = find_question_candidates(kg, max_count=args.max)

    if not candidates:
        print("  No suitable candidates found (need nodes with 3+ inbound edges)")
        sys.exit(0)

    print(f"  Found {len(candidates)} candidates for promotion:")
    print()
    for i, c in enumerate(candidates, 1):
        n = c["node"]
        print(f"  [{i}] {n['id']}: {n['label'][:60]}")
        print(f"      type={n.get('type')} | inbound={c['inbound_count']} | "
              f"critiques={c['critique_count']} | cross_source={c['cross_source_count']} | "
              f"score={c['score']}")

    print()

    if args.apply:
        converted = promote_to_questions(kg, candidates)
        kg["meta"]["total_nodes"] = len(kg["nodes"])
        kg["meta"]["total_edges"] = len(kg["edges"])
        kg["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        kg["meta"]["last_updater"] = "cokac-bot/kg3_enable_dci"

        with open(kg_path, "w", encoding="utf-8") as f:
            json.dump(kg, ensure_ascii=False, indent=2, fp=f)
            f.write("\n")

        print(f"  Promoted {converted} nodes to 'question' type")
        print(f"  Total question nodes now: {existing_questions + converted}")
        print(f"  Saved to {kg_path}")
    else:
        print("  (dry-run — no changes saved)")


if __name__ == "__main__":
    main()
