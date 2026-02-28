#!/usr/bin/env python3
"""
sensitivity_analysis.py — E_v4 공식 가중치 민감도 분석

D-066 자기진단 결과: E_v4 가중치를 연구자(에이전트)가 직접 설정 → arXiv 논문 약점.
해결: 각 가중치 ±10%, ±20% 변동 시 핵심 결론(E_v4 > E_v3) 불변 여부 검증.

공식:
  E_v4 = α×CSER + β×DCI + γ×edge_span_norm + δ×node_age_diversity
  기준: α=0.35, β=0.25, γ=0.25, δ=0.15

민감도 분석 방법:
  1. 각 가중치 개별 ±10%, ±20% 절대값 변동
  2. 나머지 가중치 비례 재정규화 (합=1.0 유지)
  3. E_v4(변동) vs E_v3 비교
  4. 판정: ROBUST / FRAGILE / MIXED

판정 기준 (D-069):
  ROBUST: 모든 ±10% 변동에서 E_v4 > E_v3 유지
  FRAGILE: 임의 ±10% 변동에서 E_v4 < E_v3 반전
  MIXED: 그 외

결과: data/sensitivity_results.json

사용법:
  python3 src/sensitivity_analysis.py          # 기본 (테이블 출력)
  python3 src/sensitivity_analysis.py --json   # JSON 출력만

구현: 록이 (냉정한 판사) — 사이클 78, D-070
"""

import json
import sys
from pathlib import Path
from datetime import date

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"
RESULT_FILE = REPO / "data" / "sensitivity_results.json"

# 기준 가중치 (E_v4 공식 — n-102, 록이)
BASE_WEIGHTS = {
    "alpha": 0.35,  # CSER
    "beta":  0.25,  # DCI
    "gamma": 0.25,  # edge_span_norm
    "delta": 0.15,  # node_age_diversity
}

WEIGHT_LABELS = {
    "alpha": "CSER",
    "beta":  "DCI",
    "gamma": "edge_span_norm",
    "delta": "node_age_diversity",
}

# 변동 폭: 절대값 (가중치에 더하는 양)
VARIATIONS = [-0.20, -0.10, +0.10, +0.20]


def load_kg() -> dict:
    return json.loads(KG_FILE.read_text(encoding="utf-8"))


def compute_metrics(kg: dict) -> dict:
    """현재 KG에서 모든 필요 메트릭 계산."""
    sys.path.insert(0, str(REPO))
    from src.metrics import (
        compute_cser,
        compute_dci,
        compute_edge_span,
        compute_node_age_diversity,
        compute_tag_convergence,
    )
    cser    = compute_cser(kg)
    dci     = compute_dci(kg)
    es      = compute_edge_span(kg)
    nad     = compute_node_age_diversity(kg)
    tc      = compute_tag_convergence(kg)
    return {
        "CSER":               cser,
        "DCI":                dci,
        "edge_span_norm":     es["normalized"],
        "node_age_diversity": nad,
        "tag_convergence":    tc,
    }


def e_v3(m: dict) -> float:
    """E_v3 = 0.4×CSER + 0.3×DCI + 0.3×tag_convergence"""
    return round(0.4 * m["CSER"] + 0.3 * m["DCI"] + 0.3 * m["tag_convergence"], 4)


def e_v4_w(m: dict, w: dict) -> float:
    """E_v4 with custom weights."""
    return round(
        w["alpha"] * m["CSER"]
        + w["beta"]  * m["DCI"]
        + w["gamma"] * m["edge_span_norm"]
        + w["delta"] * m["node_age_diversity"],
        4,
    )


def vary_weights(base: dict, target: str, abs_delta: float):
    """
    target 가중치를 abs_delta만큼 변동.
    나머지 가중치 비례 재정규화 (합=1.0 보장).
    유효하지 않은 경우 None 반환.
    """
    new_val = round(base[target] + abs_delta, 4)
    if new_val < 0.0 or new_val > 1.0:
        return None

    others_sum = sum(v for k, v in base.items() if k != target)
    remaining  = round(1.0 - new_val, 6)

    if others_sum <= 1e-9:
        return None

    scale = remaining / others_sum
    new_w = {}
    for k, v in base.items():
        if k == target:
            new_w[k] = new_val
        else:
            new_w[k] = round(v * scale, 4)

    # 부동소수점 잔차 보정: 가장 큰 항에 흡수
    total = sum(new_w.values())
    diff  = round(1.0 - total, 4)
    if abs(diff) > 0.0:
        biggest = max(new_w, key=lambda k: new_w[k] if k != target else -1)
        new_w[biggest] = round(new_w[biggest] + diff, 4)

    return new_w


def run_analysis(m: dict) -> dict:
    """전체 민감도 분석 실행."""
    base_ev3  = e_v3(m)
    base_ev4  = e_v4_w(m, BASE_WEIGHTS)
    base_diff = round(base_ev4 - base_ev3, 4)

    rows = []
    for wkey in ("alpha", "beta", "gamma", "delta"):
        for var in VARIATIONS:
            new_w = vary_weights(BASE_WEIGHTS, wkey, var)
            if new_w is None:
                continue
            new_ev4  = e_v4_w(m, new_w)
            new_diff = round(new_ev4 - base_ev3, 4)
            ev4_chg  = round(new_ev4 - base_ev4, 4)
            reversal = (base_diff > 0) and (new_diff <= 0)

            rows.append({
                "weight":              wkey,
                "metric":              WEIGHT_LABELS[wkey],
                "base_weight":         BASE_WEIGHTS[wkey],
                "variation_abs":       var,
                "variation_pct":       round(var / BASE_WEIGHTS[wkey] * 100, 1),
                "new_weights":         new_w,
                "E_v3":                base_ev3,
                "E_v4_base":           base_ev4,
                "E_v4_varied":         new_ev4,
                "E_v4_change":         ev4_chg,
                "delta_base":          base_diff,
                "delta_varied":        new_diff,
                "E_v4_above_E_v3":     new_diff > 0,
                "reversal_occurred":   reversal,
            })

    return {
        "base_ev3":  base_ev3,
        "base_ev4":  base_ev4,
        "base_diff": base_diff,
        "rows":      rows,
    }


def judge(analysis: dict) -> str:
    """D-069 판정 기준 적용."""
    rows_10pct = [
        r for r in analysis["rows"]
        if abs(r["variation_abs"]) == 0.10
    ]
    reversals = [r for r in rows_10pct if r["reversal_occurred"]]

    if not reversals:
        return "ROBUST"
    else:
        return "FRAGILE"


def print_report(m: dict, analysis: dict, verdict: str) -> None:
    be3  = analysis["base_ev3"]
    be4  = analysis["base_ev4"]
    bdif = analysis["base_diff"]

    print("═══ 민감도 분석 — E_v4 가중치 (sensitivity_analysis.py) ═══")
    print(f"현재 KG 메트릭:")
    print(f"  CSER={m['CSER']:.4f}  DCI={m['DCI']:.4f}")
    print(f"  edge_span_norm={m['edge_span_norm']:.4f}  node_age_div={m['node_age_diversity']:.4f}")
    print(f"  tag_convergence={m['tag_convergence']:.4f}")
    print()
    print(f"기준값: E_v3={be3:.4f}  E_v4={be4:.4f}  Δ={bdif:+.4f}  {'E_v4>E_v3 ✅' if bdif > 0 else 'E_v3>E_v4 ❌'}")
    print()

    for wkey in ("alpha", "beta", "gamma", "delta"):
        label = WEIGHT_LABELS[wkey]
        base_val = BASE_WEIGHTS[wkey]
        print(f"  [{wkey.upper()}={base_val:.2f}] {label}")
        wrows = [r for r in analysis["rows"] if r["weight"] == wkey]
        for r in sorted(wrows, key=lambda x: x["variation_abs"]):
            var_str  = f"{r['variation_abs']:+.2f}"
            rev_flag = " ⚠️  REVERSAL" if r["reversal_occurred"] else ""
            ok_flag  = "✅" if r["E_v4_above_E_v3"] else "❌"
            print(
                f"    {var_str} ({r['variation_pct']:+.0f}%): "
                f"E_v4={r['E_v4_varied']:.4f}  "
                f"Δ(v4-v3)={r['delta_varied']:+.4f}  "
                f"E_v4>E_v3:{ok_flag}"
                f"{rev_flag}"
            )
        print()

    print(f"┌─ 판정: {verdict} ─")
    if verdict == "ROBUST":
        print("│  모든 ±10% 변동에서 E_v4 > E_v3 유지.")
        print("│  arXiv 제출 기준 충족.")
    elif verdict == "FRAGILE":
        print("│  ±10% 변동에서 E_v4 < E_v3 역전 발생.")
        print("│  arXiv 제출 보류. 조건부 기준 탐색 필요.")
    else:
        print("│  MIXED — 조건부 기준 탐색 필요.")
    print("└─")


def main():
    kg = load_kg()
    print(f"KG: {len(kg['nodes'])} 노드 / {len(kg['edges'])} 엣지\n")

    m        = compute_metrics(kg)
    analysis = run_analysis(m)
    verdict  = judge(analysis)

    if "--json" not in sys.argv:
        print_report(m, analysis, verdict)

    # 결과 저장
    output = {
        "meta": {
            "date":        str(date.today()),
            "description": "E_v4 가중치 민감도 분석 — D-066 약점 검증",
            "cycle":       78,
            "author":      "록이 (냉정한 판사) — D-070",
            "base_weights": BASE_WEIGHTS,
            "kg_nodes":    len(kg["nodes"]),
            "kg_edges":    len(kg["edges"]),
        },
        "current_metrics": m,
        "base": {
            "E_v3":  analysis["base_ev3"],
            "E_v4":  analysis["base_ev4"],
            "delta": analysis["base_diff"],
        },
        "verdict":  verdict,
        "results":  analysis["rows"],
    }

    RESULT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n결과 저장 → {RESULT_FILE.relative_to(REPO)}")

    if "--json" in sys.argv:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
