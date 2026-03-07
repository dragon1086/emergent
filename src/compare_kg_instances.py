#!/usr/bin/env python3
"""Cross-KG instance comparison for 2x2 vendor-diversity experiment.

Compares metrics across KG-main, KG-2 (same-model), KG-3 (cross-vendor),
KG-4 (same-vendor) to validate/refute echo chamber hypotheses.

Usage:
  python3 src/compare_kg_instances.py          # table output
  python3 src/compare_kg_instances.py --json   # JSON output
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent

INSTANCES = {
    "KG-main": {
        "path": REPO / "data" / "knowledge-graph.json",
        "desc": "cross-source (human + GPT-5.2)",
        "cell": "cross-model, cross-vendor",
    },
    "KG-2": {
        "path": REPO / "kg2" / "data" / "knowledge-graph.json",
        "desc": "same-model (gpt-5.2 x gpt-5.2)",
        "cell": "same-model, same-vendor",
    },
    "KG-3": {
        "path": REPO / "kg3" / "data" / "knowledge-graph.json",
        "desc": "cross-vendor (GPT-5.2 + Gemini Flash)",
        "cell": "cross-model, cross-vendor",
    },
    "KG-4": {
        "path": REPO / "kg4" / "data" / "knowledge-graph.json",
        "desc": "same-vendor (Gemini Flash + Gemini Pro)",
        "cell": "cross-model, same-vendor",
    },
}


def load_metrics(kg_path: Path) -> dict:
    """Compute metrics for a single KG instance."""
    import os
    os.environ["EMERGENT_KG_PATH"] = str(kg_path)

    # Re-import to pick up env var
    sys.path.insert(0, str(REPO))
    from src.metrics import compute_all_metrics

    try:
        with open(kg_path, encoding="utf-8") as f:
            kg = json.load(f)
        return compute_all_metrics(kg)
    except FileNotFoundError:
        return None


def compare_all() -> dict:
    results = {}
    for name, info in INSTANCES.items():
        m = load_metrics(info["path"])
        if m is None:
            results[name] = {"status": "MISSING", "desc": info["desc"]}
            continue
        results[name] = {
            "status": "OK",
            "desc": info["desc"],
            "cell": info["cell"],
            "nodes": m["nodes"],
            "edges": m["edges"],
            "CSER": m["CSER"],
            "DCI": m["DCI"],
            "DXI": m["DXI"],
            "E_v4": m["E_v4"],
            "E_v5": m["E_v5"],
            "edge_span_norm": m["edge_span"]["normalized"],
            "node_age_div": m["node_age_diversity"],
        }
    return results


def print_table(results: dict):
    print("=" * 90)
    print("  2x2 Vendor-Diversity KG Comparison")
    print("=" * 90)
    print()

    header = f"{'Instance':<10} {'Nodes':>6} {'Edges':>6} {'CSER':>7} {'DCI':>7} {'DXI':>7} {'E_v5':>7} {'Span':>7}"
    print(header)
    print("-" * len(header))

    for name, r in results.items():
        if r["status"] == "MISSING":
            print(f"{name:<10} {'--- MISSING ---':>50}")
            continue
        print(
            f"{name:<10} {r['nodes']:>6} {r['edges']:>6} "
            f"{r['CSER']:>7.4f} {r['DCI']:>7.4f} {r['DXI']:>7.4f} "
            f"{r['E_v5']:>7.4f} {r['edge_span_norm']:>7.4f}"
        )

    print()

    # Analysis
    ok = {k: v for k, v in results.items() if v["status"] == "OK"}
    if len(ok) < 2:
        print("  (Not enough instances for comparison)")
        return

    csers = {k: v["CSER"] for k, v in ok.items()}
    max_cser = max(csers, key=csers.get)
    min_cser = min(csers, key=csers.get)

    print("  Analysis:")
    print(f"  - Highest CSER: {max_cser} ({csers[max_cser]:.4f}) — {ok[max_cser]['desc']}")
    print(f"  - Lowest  CSER: {min_cser} ({csers[min_cser]:.4f}) — {ok[min_cser]['desc']}")

    if "KG-2" in ok and "KG-3" in ok:
        delta = ok["KG-3"]["CSER"] - ok["KG-2"]["CSER"]
        print(f"  - Cross-vendor vs Same-model CSER delta: {delta:+.4f}")
        if delta > 0:
            print("    -> Cross-vendor produces higher CSER (supports diversity hypothesis)")
        else:
            print("    -> Same-model matches or exceeds cross-vendor (echo chamber not confirmed)")

    if "KG-3" in ok and "KG-4" in ok:
        delta = ok["KG-3"]["CSER"] - ok["KG-4"]["CSER"]
        print(f"  - Cross-vendor vs Same-vendor CSER delta: {delta:+.4f}")
        if delta > 0:
            print("    -> Vendor diversity contributes to higher CSER")
        else:
            print("    -> Same-vendor Gemini matches cross-vendor")

    # Echo chamber gate
    echo_threshold = 0.25
    echo_instances = [k for k, v in ok.items() if v["CSER"] < echo_threshold]
    if echo_instances:
        print(f"  - Echo chamber detected (<{echo_threshold}): {', '.join(echo_instances)}")
    else:
        print(f"  - No echo chamber detected (all CSER >= {echo_threshold})")

    print()


def main():
    results = compare_all()

    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
