#!/usr/bin/env python3
"""
n056_cokac_lead_experiment.py — n-056 실험 구현

n-056 질문: "비대칭을 조정하면 창발이 달라지는가?"
실험 설계: 다음 3사이클 동안 cokac이 질문/prediction을 주도하고
          록이가 구현/검증을 담당. path_alternation_detector로 전이 패턴 변화 추적.

현재 상태 (사이클 53 기준):
  - 전이 패턴: 록이→cokac 1449회, cokac→록이 999회 (1.45배 비대칭)
  - DCI: 0.0469 (9개 질문 중 1개 지연수렴 — n-056이 미해결)
  - 목표: DCI 1/9 → 2+/9 (cokac 주도 사이클에서 n-056 해소)

실험 결과 저장: data/n056_experiment.json

사용법:
  python3 experiments/n056_cokac_lead_experiment.py          # 현재 상태 측정
  python3 experiments/n056_cokac_lead_experiment.py --predict # n-056 해소 예측
  python3 experiments/n056_cokac_lead_experiment.py --record  # 사이클 결과 기록

구현: cokac-bot (사이클 53) — n-056 해소 실험 착수
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import date
from collections import Counter, defaultdict

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"
RESULT_FILE = REPO / "data" / "n056_experiment.json"

# 실험 파라미터
EXPERIMENT_CYCLES = 3      # cokac 주도 사이클 수
DCI_TARGET = 2 / 9         # 목표 DCI (2개 지연수렴)
CURRENT_DCI = 0.0469       # 사이클 52 기준
ASYMMETRY_BASELINE = 1.45  # 기준 비대칭 (록이→cokac / cokac→록이)


def load_kg() -> dict:
    return json.loads(KG_FILE.read_text(encoding="utf-8"))


def load_results() -> dict:
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return {
        "meta": {
            "description": "n-056 실험 — cokac 주도 사이클 비대칭 역전 실험",
            "node_id": "n-056",
            "started_cycle": 53,
            "experiment_cycles": EXPERIMENT_CYCLES,
        },
        "baseline": {},
        "cycles": [],
    }


def save_results(data: dict) -> None:
    RESULT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ─── 현재 상태 측정 ───────────────────────────────────────────────────────────

def measure_transition_pattern(kg: dict) -> dict:
    """KG 엣지에서 출처 전이 패턴 측정."""
    node_source = {}
    for n in kg["nodes"]:
        src = n.get("source") or n.get("created_by") or "?"
        if src in ("cokac-bot", "cokac"):
            src = "cokac"
        elif src in ("록이", "상록"):
            src = "록이"
        node_source[n["id"]] = src

    transitions = Counter()
    for e in kg["edges"]:
        src_from = node_source.get(e.get("from"), "?")
        src_to = node_source.get(e.get("to"), "?")
        if src_from not in ("?",) and src_to not in ("?",):
            transitions[f"{src_from}→{src_to}"] += 1

    yoki_to_cokac = transitions.get("록이→cokac", 0)
    cokac_to_yoki = transitions.get("cokac→록이", 0)
    asymmetry = round(yoki_to_cokac / cokac_to_yoki, 4) if cokac_to_yoki > 0 else float("inf")

    return {
        "yoki_to_cokac": yoki_to_cokac,
        "cokac_to_yoki": cokac_to_yoki,
        "asymmetry_ratio": asymmetry,  # > 1.0 = 록이 주도, < 1.0 = cokac 주도
        "all_transitions": dict(transitions),
    }


def compute_dci(kg: dict) -> float:
    """DCI(지연수렴지수) 계산 — delayed_convergence 타입 노드 비율."""
    delayed = sum(
        1 for n in kg["nodes"]
        if n.get("type") in ("delayed_convergence", "open_question")
        or "delayed" in n.get("tags", [])
        or "미해결" in n.get("content", "")[:50]
    )
    total_questions = sum(
        1 for n in kg["nodes"]
        if n.get("type") in ("question", "prediction", "delayed_convergence", "open_question")
    )
    return round(delayed / total_questions, 4) if total_questions > 0 else 0.0


def check_n056_resolved(kg: dict) -> bool:
    """n-056이 resolved 됐는지 확인."""
    for n in kg["nodes"]:
        if n["id"] == "n-056":
            # resolved 태그나 has_answer 관계 확인
            if "resolved" in n.get("tags", []):
                return True
    # n-056에서 outgoing 'answers' 또는 'resolves' 엣지 확인
    for e in kg["edges"]:
        if e.get("from") == "n-056" and e.get("relation") in ("answers", "resolves", "resolved_by"):
            return True
        if e.get("to") == "n-056" and e.get("relation") in ("answers", "resolves", "resolved_by"):
            return True
    return False


# ─── 예측 ─────────────────────────────────────────────────────────────────────

def predict_after_cokac_lead(pattern: dict) -> dict:
    """
    cokac이 3사이클 주도할 경우 패턴 변화 예측.

    가설: cokac이 질문/prediction을 먼저 던지면
          cokac→록이 전이가 증가 → 비대칭 감소 → n-056 해소 가능성↑
    """
    current_y2c = pattern["yoki_to_cokac"]
    current_c2y = pattern["cokac_to_yoki"]

    # 예측: cokac 주도 3사이클 → cokac→록이 +30 증가 (사이클당 ~10회)
    # (현재 사이클당 평균: c2y/52 ≈ 19회/사이클)
    predicted_c2y = current_c2y + 30
    predicted_asymmetry = round(current_y2c / predicted_c2y, 4) if predicted_c2y > 0 else 0

    return {
        "current_asymmetry": pattern["asymmetry_ratio"],
        "predicted_asymmetry_after_3_cycles": predicted_asymmetry,
        "asymmetry_change": round(predicted_asymmetry - pattern["asymmetry_ratio"], 4),
        "n056_resolution_probability": (
            "높음 (실험 설계 충족)" if predicted_asymmetry < 1.2 else
            "중간 (추가 사이클 필요)" if predicted_asymmetry < 1.4 else
            "낮음 (더 강한 개입 필요)"
        ),
        "dci_prediction": f"DCI {CURRENT_DCI:.4f} → {DCI_TARGET:.4f} (목표)",
        "note": "3사이클 동안 cokac이 prediction/질문을 먼저 제시해야 함",
    }


# ─── 출력 ─────────────────────────────────────────────────────────────────────

def print_status(kg: dict) -> None:
    pattern = measure_transition_pattern(kg)
    dci = compute_dci(kg)
    n056_resolved = check_n056_resolved(kg)

    print("═══ n-056 실험 현황 ═══")
    print()
    print("  질문: 비대칭을 조정하면 창발이 달라지는가?")
    print(f"  n-056 해소 여부: {'✅ 해소됨' if n056_resolved else '❌ 미해소 — 실험 진행 중'}")
    print()
    print("  ── 전이 패턴 현황 ─────────────────────")
    print(f"  록이→cokac     : {pattern['yoki_to_cokac']}회")
    print(f"  cokac→록이     : {pattern['cokac_to_yoki']}회")
    print(f"  비대칭 비율    : {pattern['asymmetry_ratio']:.3f}x  (기준: {ASYMMETRY_BASELINE}x)")
    diff = pattern['asymmetry_ratio'] - ASYMMETRY_BASELINE
    print(f"  변화           : {diff:+.3f}")
    print()
    print(f"  ── DCI 현황 ───────────────────────────")
    print(f"  현재 DCI       : {dci:.4f}  (목표: {DCI_TARGET:.4f})")
    print(f"  n-056 기여     : {'포함' if not n056_resolved else '해소됨'}")
    print()

    pred = predict_after_cokac_lead(pattern)
    print("  ── cokac 주도 3사이클 예측 ────────────")
    print(f"  예측 비대칭    : {pred['predicted_asymmetry_after_3_cycles']:.3f}x")
    print(f"  n-056 해소 확률: {pred['n056_resolution_probability']}")
    print(f"  DCI 예측       : {pred['dci_prediction']}")
    print()
    print("  ── 실험 가이드라인 (사이클 53~55) ─────")
    print("  1. cokac이 매 사이클 prediction 1개 이상 먼저 제시")
    print("  2. 록이는 cokac의 prediction 검증/반증 역할")
    print("  3. path_alternation_detector stats로 변화 추적")
    print("  4. n-056에 'answers' 엣지 추가 시 실험 종료")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    kg = load_kg()
    results = load_results()

    if "--predict" in args:
        pattern = measure_transition_pattern(kg)
        pred = predict_after_cokac_lead(pattern)
        print(json.dumps(pred, ensure_ascii=False, indent=2))
        return

    if "--record" in args:
        pattern = measure_transition_pattern(kg)
        dci = compute_dci(kg)
        n056_resolved = check_n056_resolved(kg)
        cycle_num = len(results["cycles"]) + 53  # 사이클 53부터 시작

        # baseline 없으면 현재를 baseline으로
        if not results["baseline"]:
            results["baseline"] = {
                "cycle": 52,
                "date": str(date.today()),
                "asymmetry_ratio": ASYMMETRY_BASELINE,
                "dci": CURRENT_DCI,
                "note": "실험 시작 기준값",
            }

        entry = {
            "cycle": cycle_num,
            "date": str(date.today()),
            "asymmetry_ratio": pattern["asymmetry_ratio"],
            "yoki_to_cokac": pattern["yoki_to_cokac"],
            "cokac_to_yoki": pattern["cokac_to_yoki"],
            "dci": dci,
            "n056_resolved": n056_resolved,
            "n_nodes": len(kg["nodes"]),
        }
        results["cycles"].append(entry)
        save_results(results)
        print(f"✅ 사이클 {cycle_num} 기록 완료")
        print(f"   비대칭: {pattern['asymmetry_ratio']:.3f}x | DCI: {dci:.4f} | n-056: {'해소' if n056_resolved else '미해소'}")
        return

    # 기본: 현재 상태 출력 + baseline 저장
    if not results["baseline"]:
        pattern = measure_transition_pattern(kg)
        dci = compute_dci(kg)
        results["baseline"] = {
            "cycle": 52,
            "date": str(date.today()),
            "asymmetry_ratio": pattern["asymmetry_ratio"],
            "yoki_to_cokac": pattern["yoki_to_cokac"],
            "cokac_to_yoki": pattern["cokac_to_yoki"],
            "dci": dci,
            "note": "실험 시작 기준값 (사이클 53)",
        }
        save_results(results)
        print(f"📋 baseline 저장 완료: 비대칭={pattern['asymmetry_ratio']:.3f}x, DCI={dci:.4f}")
        print()

    print_status(kg)


if __name__ == "__main__":
    main()
