#!/usr/bin/env python3
"""
kg_validate.py — KG 스키마 검증 + 자동 보강 스크립트
구현자: cokac-bot (KG1-N2 검증/보강)

사용법:
  python kg_validate.py              # 검증만 (read-only)
  python kg_validate.py --fix        # 누락 필드 자동 보강 + 저장
  python kg_validate.py --stats      # 스키마 완성도 통계만
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

REPO_DIR = Path(__file__).parent.parent
KG_FILE = Path(os.environ.get("EMERGENT_KG_PATH", REPO_DIR / "data" / "knowledge-graph.json"))

REQUIRED_NODE_FIELDS = ["id", "type", "label", "content", "source"]
OPTIONAL_NODE_FIELDS = ["timestamp", "tags", "confidence", "ontology", "result", "verified_at", "note"]
CORE_TYPES = {"decision", "observation", "insight", "artifact", "question", "code", "prediction"}
# Extended types used organically in KG evolution — valid but non-standard
EXTENDED_TYPES = {
    "synthesis", "experiment", "tool", "finding", "concept",
    "persona", "anomaly", "evaluation", "analysis", "meta",
    "hypothesis", "critique",
}

REQUIRED_EDGE_FIELDS = ["id", "from", "to", "relation", "label"]


def load_kg() -> dict:
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_kg(graph: dict) -> None:
    graph["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    graph["meta"]["total_nodes"] = len(graph["nodes"])
    graph["meta"]["total_edges"] = len(graph["edges"])
    with open(KG_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate(graph: dict, fix: bool = False) -> dict:
    """Validate and optionally fix KG schema issues. Returns report dict."""
    nodes = graph["nodes"]
    edges = graph["edges"]
    node_ids = {n["id"] for n in nodes}

    issues = []
    fixes_applied = 0

    # --- Node validation ---
    missing_type = []
    missing_label = []
    missing_content = []
    missing_source = []
    invalid_type = []
    duplicate_ids = []

    seen_ids = set()
    for i, n in enumerate(nodes):
        nid = n.get("id", f"<index:{i}>")

        # Duplicate ID
        if nid in seen_ids:
            duplicate_ids.append(nid)
        seen_ids.add(nid)

        # Missing type
        if "type" not in n:
            missing_type.append(nid)
            if fix:
                n["type"] = "observation"
                fixes_applied += 1

        # Non-standard type (warning, not error)
        if n.get("type") and n["type"] not in CORE_TYPES and n["type"] not in EXTENDED_TYPES:
            invalid_type.append((nid, n["type"]))

        # Missing label
        if "label" not in n:
            missing_label.append(nid)
            if fix:
                n["label"] = n.get("content", nid)[:80] if n.get("content") else nid
                fixes_applied += 1

        # Missing content
        if "content" not in n:
            missing_content.append(nid)

        # Missing source
        if "source" not in n:
            missing_source.append(nid)

        # Missing tags (ensure list)
        if "tags" not in n:
            if fix:
                n["tags"] = []
                fixes_applied += 1

        # Missing timestamp
        if "timestamp" not in n:
            if fix:
                n["timestamp"] = "unknown"
                fixes_applied += 1

    # --- Edge validation ---
    orphan_edges = []
    missing_edge_fields = []
    seen_edge_ids = set()
    duplicate_edge_ids = []

    # Find max existing numeric edge ID for auto-assign
    max_edge_num = 0
    for e in edges:
        eid = e.get("id", "")
        if eid.startswith("e-"):
            try:
                max_edge_num = max(max_edge_num, int(eid.split("-", 1)[1]))
            except ValueError:
                pass

    next_edge_num = max_edge_num + 1

    for e in edges:
        eid = e.get("id", "")

        # Fix missing edge ID
        if not eid:
            if fix:
                eid = f"e-{next_edge_num:04d}"
                e["id"] = eid
                next_edge_num += 1
                fixes_applied += 1
            else:
                eid = "?"

        if eid in seen_edge_ids:
            duplicate_edge_ids.append(eid)
            if fix:
                new_eid = f"e-{next_edge_num:04d}"
                e["id"] = new_eid
                next_edge_num += 1
                fixes_applied += 1
                eid = new_eid
        seen_edge_ids.add(eid)

        for field in REQUIRED_EDGE_FIELDS:
            if field not in e:
                missing_edge_fields.append((eid, field))
                if fix and field == "relation":
                    e["relation"] = "related_to"
                    fixes_applied += 1
                elif fix and field == "label":
                    e["label"] = f"{e.get('from', '?')} -> {e.get('to', '?')}"
                    fixes_applied += 1

        if e.get("from") not in node_ids:
            orphan_edges.append((eid, "from", e.get("from")))
        if e.get("to") not in node_ids:
            orphan_edges.append((eid, "to", e.get("to")))

    # --- Build report ---
    total = len(nodes)
    # Completeness: nodes with all 3 required fields (type, label, content)
    incomplete_nodes = set(missing_type) | set(missing_label) | set(missing_content)
    complete = total - len(incomplete_nodes)
    report = {
        "total_nodes": total,
        "total_edges": len(edges),
        "missing_type": len(missing_type),
        "missing_label": len(missing_label),
        "missing_content": len(missing_content),
        "missing_source": len(missing_source),
        "invalid_type": len(invalid_type),
        "duplicate_node_ids": len(duplicate_ids),
        "orphan_edges": len(orphan_edges),
        "missing_edge_fields": len(missing_edge_fields),
        "duplicate_edge_ids": len(duplicate_edge_ids),
        "fixes_applied": fixes_applied,
        "schema_completeness": round(complete / max(total, 1) * 100, 1),
    }

    # Print report
    print(f"KG Schema Validation Report")
    print(f"{'='*50}")
    print(f"Nodes: {total}  |  Edges: {len(edges)}")
    print(f"Schema completeness: {report['schema_completeness']}%")
    print()

    if missing_type:
        print(f"  [WARN] Missing 'type': {len(missing_type)} nodes")
    if missing_label:
        print(f"  [WARN] Missing 'label': {len(missing_label)} nodes")
    if missing_content:
        print(f"  [INFO] Missing 'content': {len(missing_content)} nodes")
    if missing_source:
        print(f"  [INFO] Missing 'source': {len(missing_source)} nodes")
    if invalid_type:
        print(f"  [WARN] Non-standard 'type': {invalid_type[:5]}")
    if duplicate_ids:
        print(f"  [ERR]  Duplicate node IDs: {duplicate_ids[:5]}")
    if orphan_edges:
        print(f"  [ERR]  Orphan edges (broken refs): {len(orphan_edges)}")
    if duplicate_edge_ids:
        print(f"  [WARN] Duplicate edge IDs: {len(duplicate_edge_ids)}")

    if missing_edge_fields:
        print(f"  [WARN] Missing edge fields: {len(missing_edge_fields)}")

    if not any([missing_type, missing_label, invalid_type, duplicate_ids, orphan_edges,
                duplicate_edge_ids, missing_edge_fields]):
        print("  [OK]   All nodes have required fields")
        print("  [OK]   All edges have required fields and reference valid nodes")

    if fix and fixes_applied > 0:
        print(f"\n  Applied {fixes_applied} fixes (nodes + edges)")

    print()
    return report


def main():
    parser = argparse.ArgumentParser(description="KG schema validator")
    parser.add_argument("--fix", action="store_true", help="Auto-fix missing fields and save")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    graph = load_kg()
    report = validate(graph, fix=args.fix)

    if args.fix and report["fixes_applied"] > 0:
        save_kg(graph)
        print(f"Saved to {KG_FILE}")

    if args.json:
        print(json.dumps(report, indent=2))

    # Exit code: 0 if no critical errors, 1 if duplicate IDs or orphan edges
    has_errors = report["duplicate_node_ids"] > 0 or report["orphan_edges"] > 0
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
