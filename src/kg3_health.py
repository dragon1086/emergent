#!/usr/bin/env python3
"""kg3_health.py — KG-3 instance health diagnostic.

Checks:
  1. Model/source consistency (gpt-4o + gemini-2.5-flash expected)
  2. CSER (cross-source edge ratio)
  3. DCI status and question node availability
  4. Duplicate labels
  5. Missing domain fields
  6. Orphan edges

Usage:
  EMERGENT_KG_PATH=kg3/data/knowledge-graph.json python3 src/kg3_health.py
  python3 src/kg3_health.py --kg kg3/data/knowledge-graph.json
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).parent.parent
DEFAULT_KG = REPO / "kg3" / "data" / "knowledge-graph.json"


def load_kg(path: str = None) -> dict:
    p = Path(path) if path else Path(os.environ.get("EMERGENT_KG_PATH", str(DEFAULT_KG)))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _node_num(nid: str) -> int:
    m = re.search(r'\d+', nid)
    return int(m.group()) if m else 0


EXPECTED_SOURCES = {"gpt-4o", "gemini-2.5-flash", "openclaw"}


def check_source_consistency(kg: dict) -> list[str]:
    """Check that node sources match expected models for KG-3."""
    issues = []
    src_counts = Counter(n.get("source", "?") for n in kg["nodes"])
    unexpected = {s: c for s, c in src_counts.items() if s not in EXPECTED_SOURCES}
    if unexpected:
        issues.append(f"[WARN] Unexpected sources: {unexpected}")
        issues.append(f"       Expected: {EXPECTED_SOURCES}")
    return issues


def check_cser(kg: dict) -> tuple[float, list[str]]:
    """Compute real CSER by matching node sources across edges."""
    node_src = {n["id"]: n.get("source", "") for n in kg["nodes"]}
    edges = kg["edges"]
    if not edges:
        return 0.0, ["[WARN] No edges"]
    cross = sum(1 for e in edges
                if node_src.get(e["from"], "") != node_src.get(e["to"], ""))
    cser = cross / len(edges)
    issues = []
    if cser < 0.3:
        issues.append(f"[WARN] CSER={cser:.4f} — echo chamber risk (< 0.3)")
    return cser, issues


def check_dci(kg: dict) -> tuple[float, list[str]]:
    """Compute actual DCI from question nodes + answers edges."""
    issues = []
    questions = [n for n in kg["nodes"] if n.get("type") == "question"]
    if not questions:
        issues.append("[INFO] DCI=0.0 — no 'question' type nodes exist")
        issues.append("       Add question nodes + 'answers' edges to enable DCI")
        return 0.0, issues

    q_ids = {n["id"] for n in questions}
    answers_edges = [e for e in kg["edges"]
                     if e.get("relation") == "answers" and e.get("to") in q_ids]

    if not answers_edges:
        issues.append(f"[WARN] {len(questions)} question nodes but 0 'answers' edges — DCI=0.0")
        return 0.0, issues

    # DCI = (questions with at least one answer) / total questions
    answered_qs = {e["to"] for e in answers_edges}
    dci = len(answered_qs) / len(questions)

    if dci < 0.5:
        issues.append(f"[WARN] DCI={dci:.4f} — many questions unanswered ({len(answered_qs)}/{len(questions)})")
    else:
        issues.append(f"[INFO] DCI={dci:.4f} ({len(answered_qs)}/{len(questions)} questions answered, {len(answers_edges)} answers edges)")

    return dci, issues


def check_duplicates(kg: dict) -> list[str]:
    """Find duplicate node labels."""
    labels = [n.get("label", "") for n in kg["nodes"]]
    dups = {l: c for l, c in Counter(labels).items() if c > 1}
    issues = []
    if dups:
        issues.append(f"[WARN] {len(dups)} duplicate labels (top 5):")
        for label, count in sorted(dups.items(), key=lambda x: -x[1])[:5]:
            issues.append(f"       '{label[:60]}' x{count}")
    return issues


def check_missing_fields(kg: dict) -> list[str]:
    """Check for nodes missing key optional fields."""
    issues = []
    no_domain = [n["id"] for n in kg["nodes"] if not n.get("domain")]
    if no_domain:
        issues.append(f"[INFO] {len(no_domain)} nodes missing 'domain' field")
    return issues


def check_orphan_edges(kg: dict) -> list[str]:
    """Check for edges referencing non-existent nodes."""
    node_ids = {n["id"] for n in kg["nodes"]}
    issues = []
    orphans = [(e["id"], e.get("from"), e.get("to")) for e in kg["edges"]
               if e.get("from") not in node_ids or e.get("to") not in node_ids]
    if orphans:
        issues.append(f"[ERR] {len(orphans)} orphan edges:")
        for eid, ef, et in orphans[:5]:
            issues.append(f"       {eid}: {ef} -> {et}")
    return issues


def check_source_balance(kg: dict) -> list[str]:
    """Check vendor balance for cross-vendor experiment validity."""
    src_counts = Counter(n.get("source", "?") for n in kg["nodes"])
    # Only check the two main experiment sources
    main_sources = {s: c for s, c in src_counts.items() if s in {"gpt-4o", "gemini-2.5-flash"}}
    if len(main_sources) == 2:
        vals = sorted(main_sources.values())
        ratio = vals[1] / max(vals[0], 1)
        if ratio > 1.8:
            bigger = max(main_sources, key=main_sources.get)
            smaller = min(main_sources, key=main_sources.get)
            issues = [f"[WARN] Source imbalance: {bigger}={main_sources[bigger]} vs {smaller}={main_sources[smaller]} (ratio {ratio:.1f}x)",
                      f"       Cross-vendor experiment validity may be affected"]
            # Estimate Agent B failure rate
            expected_b = main_sources.get("gemini-2.5-flash", 0)
            expected_a = main_sources.get("gpt-4o", 0)
            if expected_a > expected_b:
                fail_rate = 100 * (expected_a - expected_b) / max(expected_a, 1)
                issues.append(f"       Estimated Agent B failure rate: {fail_rate:.0f}%")
            return issues
    return []


def check_answers_ratio(kg: dict) -> list[str]:
    """Check answers-per-question ratio for semantic validity."""
    issues = []
    q_ids = {n["id"] for n in kg["nodes"] if n.get("type") == "question"}
    if not q_ids:
        return []
    answers_edges = [e for e in kg["edges"] if e.get("relation") == "answers"]
    answers_to_q = [e for e in answers_edges if e.get("to") in q_ids]
    answers_to_non_q = [e for e in answers_edges if e.get("to") not in q_ids]
    if answers_to_non_q:
        issues.append(f"[WARN] {len(answers_to_non_q)} 'answers' edges point to non-question nodes (semantic mismatch)")
    if q_ids and answers_to_q:
        ratio = len(answers_to_q) / len(q_ids)
        if ratio > 20:
            issues.append(f"[WARN] answers-per-question ratio={ratio:.1f} (target <20) — DCI metric may be inflated")
    return issues


def check_edge_span(kg: dict) -> list[str]:
    """Check edge span distribution for DCI health."""
    spans = []
    for e in kg["edges"]:
        a = _node_num(e["from"])
        b = _node_num(e["to"])
        if a and b:
            spans.append(abs(a - b))
    if not spans:
        return ["[WARN] No valid edge spans"]
    avg = sum(spans) / len(spans)
    long_range = sum(1 for s in spans if s > 50)
    pct = 100 * long_range / len(spans)
    issues = []
    if pct < 10:
        issues.append(f"[WARN] Only {pct:.1f}% long-range edges (>50 span) — DCI recovery needed")
    return issues


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KG-3 health diagnostic")
    parser.add_argument("--kg", help="Path to KG JSON file")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    kg = load_kg(args.kg)

    print("=" * 55)
    print(f"  KG-3 Health Diagnostic")
    print(f"  Nodes: {len(kg['nodes'])}  |  Edges: {len(kg['edges'])}")
    print("=" * 55)

    all_issues = []
    checks = {
        "source_consistency": check_source_consistency(kg),
        "duplicates": check_duplicates(kg),
        "missing_fields": check_missing_fields(kg),
        "orphan_edges": check_orphan_edges(kg),
        "edge_span": check_edge_span(kg),
        "source_balance": check_source_balance(kg),
        "answers_ratio": check_answers_ratio(kg),
    }

    cser, cser_issues = check_cser(kg)
    checks["cser"] = cser_issues
    print(f"\n  CSER: {cser:.4f}  {'OK' if cser >= 0.3 else 'LOW'}")

    dci, dci_issues = check_dci(kg)
    checks["dci"] = dci_issues
    q_count = sum(1 for n in kg["nodes"] if n.get("type") == "question")
    dci_note = "(no question nodes)" if q_count == 0 else f"({q_count} question nodes)"
    dci_status = "OK" if dci >= 0.5 else "LOW"
    print(f"  DCI:  {dci:.4f}  {dci_status}  {dci_note}")

    # Source distribution
    src_counts = Counter(n.get("source", "?") for n in kg["nodes"])
    print(f"\n  Sources: {dict(src_counts)}")

    print()
    has_issues = False
    for name, issues in checks.items():
        if issues:
            has_issues = True
            for line in issues:
                print(f"  {line}")
            all_issues.extend(issues)

    if not has_issues:
        print("  All checks passed.")

    print()

    if args.json:
        result = {
            "nodes": len(kg["nodes"]),
            "edges": len(kg["edges"]),
            "cser": cser,
            "dci": dci,
            "sources": dict(src_counts),
            "issues": all_issues,
            "healthy": not has_issues,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(1 if any("[ERR]" in i for i in all_issues) else 0)


if __name__ == "__main__":
    main()
