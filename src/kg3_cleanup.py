#!/usr/bin/env python3
"""kg3_cleanup.py — KG-3 source migration + duplicate removal + domain fill.

Fixes:
  1. Source tag migration: gpt-5.2 -> gpt-4o, gemini-2.0-flash -> gemini-2.5-flash
  2. Duplicate label removal: keep oldest node, rewire edges to survivor
  3. Missing domain fill: set 'emergence_theory' default

Usage:
  python3 src/kg3_cleanup.py --dry-run   # preview changes
  python3 src/kg3_cleanup.py --apply     # apply and save
"""
import json
import os
import re
import sys
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

REPO = Path(__file__).parent.parent
KG3_PATH = Path(os.environ.get("EMERGENT_KG_PATH", str(REPO / "kg3" / "data" / "knowledge-graph.json")))

SOURCE_MAP = {
    "gpt-5.2": "gpt-4o",
    "gemini-2.0-flash": "gemini-2.5-flash",
}


def _node_num(nid: str) -> int:
    m = re.search(r'\d+', nid)
    return int(m.group()) if m else 9999


def migrate_sources(kg: dict) -> int:
    """Fix historical source tags to match KG-3 experiment design."""
    count = 0
    for n in kg["nodes"]:
        old = n.get("source", "")
        if old in SOURCE_MAP:
            n["source"] = SOURCE_MAP[old]
            count += 1
    for e in kg["edges"]:
        old = e.get("source", "")
        if old in SOURCE_MAP:
            e["source"] = SOURCE_MAP[old]
    return count


def remove_duplicates(kg: dict) -> int:
    """Remove duplicate-label nodes, keeping the oldest (lowest ID). Rewire edges."""
    label_groups = defaultdict(list)
    for n in kg["nodes"]:
        label = n.get("label", "").strip()
        if label:
            label_groups[label].append(n)

    to_remove = set()
    remap = {}  # removed_id -> survivor_id

    for label, nodes in label_groups.items():
        if len(nodes) <= 1:
            continue
        nodes.sort(key=lambda n: _node_num(n["id"]))
        survivor = nodes[0]
        for dup in nodes[1:]:
            to_remove.add(dup["id"])
            remap[dup["id"]] = survivor["id"]

    if not to_remove:
        return 0

    # Rewire edges
    for e in kg["edges"]:
        if e["from"] in remap:
            e["from"] = remap[e["from"]]
        if e["to"] in remap:
            e["to"] = remap[e["to"]]

    # Remove self-loops created by rewiring
    kg["edges"] = [e for e in kg["edges"] if e["from"] != e["to"]]

    # Remove duplicate edges (same from+to+relation)
    seen = set()
    unique_edges = []
    for e in kg["edges"]:
        key = (e["from"], e["to"], e.get("relation", ""))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)
    kg["edges"] = unique_edges

    # Remove nodes
    kg["nodes"] = [n for n in kg["nodes"] if n["id"] not in to_remove]

    return len(to_remove)


def fill_missing_domains(kg: dict) -> int:
    """Fill missing domain fields with default."""
    count = 0
    for n in kg["nodes"]:
        if not n.get("domain"):
            n["domain"] = "emergence_theory"
            count += 1
    return count


def update_meta(kg: dict):
    kg["meta"]["total_nodes"] = len(kg["nodes"])
    kg["meta"]["total_edges"] = len(kg["edges"])
    kg["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    kg["meta"]["last_updater"] = "cokac-bot/kg3_cleanup"


def main():
    parser = argparse.ArgumentParser(description="KG-3 cleanup: source migration + dedup + domain fill")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")
    parser.add_argument("--apply", action="store_true", help="Apply changes and save")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply")
        sys.exit(1)

    with open(KG3_PATH, encoding="utf-8") as f:
        kg = json.load(f)

    before_nodes = len(kg["nodes"])
    before_edges = len(kg["edges"])

    print(f"KG-3 Cleanup — Before: {before_nodes} nodes, {before_edges} edges")
    print("=" * 55)

    # 1. Source migration
    migrated = migrate_sources(kg)
    print(f"  [1] Source migration: {migrated} nodes fixed")

    # 2. Duplicate removal
    removed = remove_duplicates(kg)
    print(f"  [2] Duplicate removal: {removed} nodes removed")

    # 3. Domain fill
    filled = fill_missing_domains(kg)
    print(f"  [3] Domain fill: {filled} nodes updated")

    after_nodes = len(kg["nodes"])
    after_edges = len(kg["edges"])
    print(f"\n  After: {after_nodes} nodes, {after_edges} edges")
    print(f"  Delta: -{before_nodes - after_nodes} nodes, -{before_edges - after_edges} edges")

    if args.apply:
        update_meta(kg)
        with open(KG3_PATH, "w", encoding="utf-8") as f:
            json.dump(kg, ensure_ascii=False, indent=2, fp=f)
            f.write("\n")
        print(f"\n  Saved to {KG3_PATH}")
    else:
        print("\n  (dry-run — no changes saved)")


if __name__ == "__main__":
    main()
