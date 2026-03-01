"""
H_exec 사이클 82 — Condition B 실제 실행: 중간 CSER (0.44) GCD 실험
=====================================================================
목표: "CSER가 낮으면 코드 품질이 나쁘다" 직접 증명

사이클 79 선행 결과 (Condition A):
  A 조건(CSER≈1.0): 5/5 통과, 품질=1.0 (GCD 문제)
  B 조건(CSER=0.25): 0/3 — CSER 게이트(0.30)에서 차단
  C 조건(CSER=0.0):  0/3 — CSER 게이트(0.30)에서 차단

사이클 82 신규 조건 B_partial:
  B_partial 조건: CSER=0.444 (게이트 통과, 그러나 부분적 에코챔버)
  예측: 게이트는 통과하지만 코드 품질이 A조건보다 낮음

CSER 계산 설계 (B_partial):
  macro_tags = ["algorithm", "math_foundation", "purity"]
  tech_tags  = ["algorithm", "implementation", "testing"]
  겹침: {"algorithm"} → macro_unique={math_foundation, purity}, tech_unique={implementation, testing}
  cross_count = 2×2 = 4, total = 3×3 = 9 → CSER = 4/9 ≈ 0.444

논문 기여:
  "CSER 0.44는 게이트를 통과하나, 동종 개념('algorithm')이 지배적
   → 코드 품질이 A조건(CSER≈1.0)보다 낮음 — H_exec의 연속 스펙트럼 검증"
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from execution_loop import (
    CSERCrossover,
    ExecutionLoop,
    GeneratedCode,
    MacroSpec,
    Problem,
    TechSpec,
    ValidationResult,
    llm_code_generator_fn,
)


# ---------------------------------------------------------------------------
# 문제 정의 (P2: GCD — 사이클 79와 동일 문제로 비교 가능)
# ---------------------------------------------------------------------------

PROBLEM_GCD = Problem(
    description=(
        "두 양의 정수 a, b를 입력받아 최대공약수(GCD)를 반환하는 함수 gcd(a, b)를 작성하라."
    ),
    constraints=["순수 함수", "타입 힌트 포함", "docstring 포함", "재귀 또는 반복 방식 모두 허용"],
    examples=[
        {"input": "gcd(12, 8)", "output": "4"},
        {"input": "gcd(100, 75)", "output": "25"},
        {"input": "gcd(7, 13)", "output": "1"},
        {"input": "gcd(0, 5)", "output": "5"},
        {"input": "gcd(15, 15)", "output": "15"},
    ],
    cycle=82,
)

# ---------------------------------------------------------------------------
# Condition B_partial: 부분 대칭 (CSER≈0.444)
# "algorithm"이 겹침 → 두 관점이 같은 개념 도메인에서 출발
# ---------------------------------------------------------------------------

MACRO_B_PARTIAL = MacroSpec(
    intent=(
        "GCD는 두 수의 공통 약수 구조를 압축하는 알고리즘 — 수학적 순수성과 구현의 접점"
    ),
    architecture=(
        "단일 함수, 입출력 계약 명시, 알고리즘 선택은 구현자에게 위임"
    ),
    emergence_hooks=[
        "알고리즘의 수학적 필연성: 왜 유클리드 알고리즘이 최선인가",
        "순수 함수: 부수효과 없음이 검증 가능성을 보장",
    ],
    tags=["algorithm", "math_foundation", "purity"],
    source="openclaw_symmetric",  # 의도적으로 같은 도메인
)

TECH_B_PARTIAL = TechSpec(
    implementation_strategy=(
        "알고리즘 선택: 유클리드 반복 방식. gcd(a,b) → while b≠0: a,b = b,a%b → return a"
    ),
    edge_cases=["b=0 → a 반환", "a=0 → b 반환", "서로소 (GCD=1)"],
    test_criteria=[
        "gcd(12,8)==4", "gcd(100,75)==25", "gcd(7,13)==1",
        "gcd(0,5)==5", "gcd(15,15)==15",
    ],
    complexity_target="O(log min(a,b))",
    tags=["algorithm", "implementation", "testing"],  # "algorithm" 겹침
    source="cokac_symmetric",
)


# ---------------------------------------------------------------------------
# 실제 GCD 코드 검증기 — exec() 기반
# ---------------------------------------------------------------------------

def gcd_validator_fn(generated: GeneratedCode, tech: TechSpec) -> ValidationResult:
    """
    생성된 코드를 실제 Python exec()로 실행, GCD 테스트 케이스 검증.
    mock 없음 — 실제 동작 측정.
    """
    test_cases = [
        (12, 8, 4),
        (100, 75, 25),
        (7, 13, 1),
        (0, 5, 5),
        (15, 15, 15),
    ]
    namespace: dict = {}
    try:
        exec(generated.code, namespace)  # noqa: S102 — 실험용 exec
    except Exception as e:
        return ValidationResult(
            passed=False,
            test_results=[{"name": "exec_load", "passed": False, "message": str(e)}],
            quality_score=0.0,
            complexity_actual="O(?)",
            issues=[f"SyntaxError or RuntimeError: {e}"],
        )

    # gcd 함수 탐색
    gcd_fn = namespace.get("gcd") or namespace.get("solution") or namespace.get("compute_gcd")
    if gcd_fn is None:
        return ValidationResult(
            passed=False,
            test_results=[{"name": "func_lookup", "passed": False, "message": "gcd() 함수 없음"}],
            quality_score=0.0,
            complexity_actual="O(?)",
            issues=["gcd function not defined in generated code"],
        )

    results = []
    for a, b, expected in test_cases:
        try:
            got = gcd_fn(a, b)
            ok = got == expected
            results.append({
                "name": f"gcd({a},{b})=={expected}",
                "passed": ok,
                "message": f"got {got}",
            })
        except Exception as e:
            results.append({
                "name": f"gcd({a},{b})=={expected}",
                "passed": False,
                "message": str(e),
            })

    pass_rate = sum(1 for r in results if r["passed"]) / len(results)
    return ValidationResult(
        passed=pass_rate >= 0.8,
        test_results=results,
        quality_score=pass_rate,
        complexity_actual="O(log n)",
        issues=[r["message"] for r in results if not r["passed"]],
    )


# ---------------------------------------------------------------------------
# CSER 사전 검증
# ---------------------------------------------------------------------------

def verify_cser() -> float:
    """B_partial 조건의 CSER 수치를 사전 계산해서 출력."""
    crossover = CSERCrossover(macro=MACRO_B_PARTIAL, tech=TECH_B_PARTIAL)
    cser = crossover.compute_cser()
    macro_tags = set(MACRO_B_PARTIAL.tags)
    tech_tags = set(TECH_B_PARTIAL.tags)
    shared = macro_tags & tech_tags
    macro_unique = macro_tags - tech_tags
    tech_unique = tech_tags - macro_tags

    print("=" * 60)
    print("CSER 사전 검증 (Condition B_partial)")
    print("=" * 60)
    print(f"  macro_tags:   {sorted(macro_tags)}")
    print(f"  tech_tags:    {sorted(tech_tags)}")
    print(f"  공유:         {sorted(shared)} ({len(shared)}개)")
    print(f"  macro_unique: {sorted(macro_unique)} ({len(macro_unique)}개)")
    print(f"  tech_unique:  {sorted(tech_unique)} ({len(tech_unique)}개)")
    print(f"  cross_count:  {len(macro_unique) * len(tech_unique)}")
    print(f"  total:        {len(macro_tags) * len(tech_tags)}")
    print(f"  CSER:         {cser:.4f}")
    print(f"  게이트(0.30): {'✓ 통과' if cser >= 0.30 else '✗ 차단'}")
    print()
    return cser


# ---------------------------------------------------------------------------
# 메인 실험 러너
# ---------------------------------------------------------------------------

def run_experiment(n_trials: int = 5, use_llm: bool = True) -> dict:
    """
    Condition B_partial 5회 실행.

    Args:
        n_trials: 실행 횟수 (논문: 5회)
        use_llm: True면 실제 claude CLI 호출, False면 mock

    Returns:
        실험 결과 딕셔너리
    """
    cser_predicted = verify_cser()

    loop = ExecutionLoop()
    results = []

    print(f"=== Condition B_partial 실험 시작 ({n_trials}회) ===")
    print(f"  use_llm = {use_llm}")
    print()

    code_fn = llm_code_generator_fn if use_llm else None
    valid_fn = gcd_validator_fn if use_llm else None

    for i in range(n_trials):
        problem = Problem(
            description=PROBLEM_GCD.description,
            constraints=PROBLEM_GCD.constraints,
            examples=PROBLEM_GCD.examples,
            cycle=82 * 100 + i,  # 사이클 ID 충돌 방지
        )
        print(f"[실행 {i+1}/{n_trials}]")
        result = loop.run(
            problem,
            MACRO_B_PARTIAL,
            TECH_B_PARTIAL,
            code_generator_fn=code_fn,
            validator_fn=valid_fn,
        )
        results.append(result)

    # 결과 집계
    passed_count = sum(1 for r in results if r.get("passed", False))
    quality_scores = [r.get("quality_score", 0.0) for r in results]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    cser_actual = results[0]["cser_score"] if results else 0.0

    summary = {
        "condition": "B_partial",
        "n_trials": n_trials,
        "cser_predicted": cser_predicted,
        "cser_actual": cser_actual,
        "passed": passed_count,
        "pass_rate": passed_count / n_trials,
        "avg_quality": avg_quality,
        "quality_scores": quality_scores,
        "gate_passed": cser_actual >= ExecutionLoop.CSER_THRESHOLD,
        "individual_results": results,
    }

    return summary


def print_comparison_table(summary_b: dict) -> None:
    """A vs B_partial 비교 테이블 출력 (논문용)."""
    # 사이클 79 A조건 결과 (기록된 값)
    A_CSER = 1.0
    A_PASS = 5
    A_TOTAL = 5
    A_QUALITY = 1.0

    b_cser = summary_b["cser_actual"]
    b_pass = summary_b["passed"]
    b_total = summary_b["n_trials"]
    b_quality = summary_b["avg_quality"]

    print()
    print("=" * 70)
    print("A vs B_partial 비교 테이블 (논문 Table — 사이클 82)")
    print("=" * 70)
    print(f"{'조건':<20} {'CSER':>8} {'게이트':>8} {'패스율':>10} {'평균품질':>10}")
    print("-" * 70)
    print(f"{'A (비대칭, 79)':<20} {A_CSER:>8.3f} {'통과':>8} {A_PASS}/{A_TOTAL}={A_PASS/A_TOTAL:.0%}  {A_QUALITY:>10.3f}")
    print(f"{'B_partial (부분대칭)':<20} {b_cser:>8.3f} {'통과' if summary_b['gate_passed'] else '차단':>8} {b_pass}/{b_total}={b_pass/b_total:.0%}  {b_quality:>10.3f}")
    print("-" * 70)
    print(f"{'Δ (A - B)':<20} {A_CSER-b_cser:>8.3f} {'':>8} {(A_PASS/A_TOTAL)-(b_pass/b_total):>10.0%}  {A_QUALITY-b_quality:>10.3f}")
    print("=" * 70)

    quality_delta = A_QUALITY - b_quality
    pass_delta = (A_PASS / A_TOTAL) - (b_pass / b_total)

    print()
    print("가설 평가:")
    if quality_delta > 0:
        print(f"  ✓ H_exec 지지: A조건 품질이 B_partial보다 {quality_delta:.3f} 높음")
        print(f"    CSER {A_CSER:.2f}(A) vs {b_cser:.3f}(B) → 품질 차이 {quality_delta:.3f}")
        print(f"    CSER 스펙트럼이 코드 품질에 연속적으로 영향")
    else:
        print(f"  ✗ H_exec 미지지: A조건 품질({A_QUALITY:.3f}) ≤ B_partial({b_quality:.3f})")
        print(f"    → 게이트(0.30) 이상에서는 품질 차이 없음 — 주장 범위 재검토 필요")


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H_exec 사이클 82 Condition B_partial 실험")
    parser.add_argument("--mock", action="store_true", help="LLM 호출 없이 mock 실행 (빠름)")
    parser.add_argument("--trials", type=int, default=5, help="실행 횟수 (기본: 5)")
    args = parser.parse_args()

    use_llm = not args.mock
    print(f"실험 모드: {'실제 LLM (claude CLI)' if use_llm else 'MOCK'}")
    print()

    start = time.time()
    summary = run_experiment(n_trials=args.trials, use_llm=use_llm)
    elapsed = time.time() - start

    print_comparison_table(summary)

    print(f"\n소요 시간: {elapsed:.1f}초")

    # 결과 저장
    out_path = Path(__file__).parent / "h_exec_cycle82_results.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
