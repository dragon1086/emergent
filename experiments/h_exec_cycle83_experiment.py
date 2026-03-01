"""
H_exec 사이클 83 — CSER-품질 스펙트럼의 복잡도 의존성 검증
=============================================================
핵심 가설 (H_complexity):
  "CSER 스펙트럼 효과는 문제 복잡도 O(n log n) 이상에서 나타난다"

사이클 82 발견:
  P2(GCD, O(log n)): A(CSER=1.0)=5/5, B_partial(CSER=0.444)=5/5 → 동등품질
  → 단순 문제에서는 에코챔버도 충분

사이클 83 신규 실험:
  P3(QuickSort, O(n log n)): A vs B_partial vs C
  → 복잡도가 올라가면 CSER 스펙트럼 효과가 발현되는가?

CSER 계산:
  Condition A  (CSER=1.0):   macro × tech 태그 완전 비대칭
  Condition B_partial (0.444): "sorting" 겹침 → 부분 에코챔버
  Condition C  (CSER=0.0):   완전 동종 태그 → 게이트 차단 예상
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
# 문제 정의 (P3: QuickSort — O(n log n))
# ---------------------------------------------------------------------------

PROBLEM_QUICKSORT = Problem(
    description=(
        "정수 리스트를 받아 오름차순으로 정렬한 새 리스트를 반환하는 함수 quicksort(arr)를 작성하라. "
        "QuickSort 알고리즘을 사용해야 하며, 원본 리스트를 변경하지 않는다."
    ),
    constraints=[
        "순수 함수 (원본 배열 불변)",
        "QuickSort 알고리즘 사용",
        "타입 힌트 포함",
        "빈 배열 및 단일 원소 처리",
        "중복값 처리",
        "역정렬 배열 처리",
    ],
    examples=[
        {"input": "quicksort([3,1,4,1,5])", "output": "[1,1,3,4,5]"},
        {"input": "quicksort([])", "output": "[]"},
        {"input": "quicksort([1])", "output": "[1]"},
        {"input": "quicksort([5,4,3,2,1])", "output": "[1,2,3,4,5]"},
        {"input": "quicksort([2,2,2,2])", "output": "[2,2,2,2]"},
    ],
    cycle=83,
)

# ---------------------------------------------------------------------------
# Condition A: 완전 비대칭 (CSER=1.0)
# macro: 알고리즘 설계/이론 관점 | tech: 구현/파티셔닝 관점
# 겹침: 없음 → cross_count = 3×3 = 9, total = 9 → CSER = 1.0
# ---------------------------------------------------------------------------

MACRO_A = MacroSpec(
    intent=(
        "QuickSort는 분할-정복 원리의 순수한 표현 — "
        "피벗 선택이 평균 O(n log n)을 보장하는 확률적 계약"
    ),
    architecture=(
        "재귀적 분해: 피벗 기준으로 less/equal/greater 세 부분으로 분할, "
        "각 부분을 독립적으로 재귀 처리, 결합"
    ),
    emergence_hooks=[
        "분할-정복이 왜 O(n log n)을 만드는가 — 재귀 깊이 × 분할 비용",
        "피벗 선택의 확률적 보장 — 임의성이 최악 케이스를 제거",
        "순수 함수 보장: 원본 불변이 검증 가능성의 전제",
    ],
    tags=["divide_conquer", "correctness_proof", "algorithm_theory"],
    source="openclaw_asymmetric",
)

TECH_A = TechSpec(
    implementation_strategy=(
        "list comprehension 방식: less=[x for x in arr[1:] if x<=pivot], "
        "greater=[x for x in arr[1:] if x>pivot]. "
        "피벗 = arr[0]. 재귀: quicksort(less) + [pivot] + quicksort(greater)"
    ),
    edge_cases=[
        "[] → []",
        "[x] → [x]",
        "[a,a,...] (중복) → 원소 보존",
        "역정렬 [n,...,1] → 최악케이스 O(n²) 주의",
    ],
    test_criteria=[
        "quicksort([3,1,4,1,5])==[1,1,3,4,5]",
        "quicksort([])==[]",
        "quicksort([1])==[1]",
        "quicksort([5,4,3,2,1])==[1,2,3,4,5]",
        "quicksort([2,2,2,2])==[2,2,2,2]",
    ],
    complexity_target="O(n log n) average",
    tags=["partition_logic", "pivot_selection", "recursive_implementation"],
    source="cokac_asymmetric",
)

# ---------------------------------------------------------------------------
# Condition B_partial: 부분 대칭 (CSER≈0.444)
# "sorting" 겹침 → 같은 도메인에서 출발
# macro_unique={algorithm_design, recursion}, tech_unique={implementation, testing}
# cross_count = 2×2 = 4, total = 3×3 = 9 → CSER = 4/9 ≈ 0.444
# ---------------------------------------------------------------------------

MACRO_B_PARTIAL = MacroSpec(
    intent=(
        "QuickSort는 sorting 알고리즘의 표준 — "
        "분할 정복 재귀 설계로 평균 O(n log n) 달성"
    ),
    architecture=(
        "피벗 기준 분할-재귀 구조. sorting의 핵심 알고리즘적 패턴을 구현"
    ),
    emergence_hooks=[
        "sorting의 알고리즘적 최적성: QuickSort vs MergeSort 트레이드오프",
        "재귀와 sorting 완전성 — 기저 케이스가 sorting을 보장",
    ],
    tags=["sorting", "algorithm_design", "recursion"],
    source="openclaw_partial_symmetric",
)

TECH_B_PARTIAL = TechSpec(
    implementation_strategy=(
        "sorting 함수 quicksort(arr): 피벗 arr[0], "
        "less/greater 분리, 재귀 결합. sorting 구현의 표준 패턴."
    ),
    edge_cases=["[] → []", "[x] → [x]", "중복값", "역정렬"],
    test_criteria=[
        "quicksort([3,1,4,1,5])==[1,1,3,4,5]",
        "quicksort([])==[]",
        "quicksort([1])==[1]",
        "quicksort([5,4,3,2,1])==[1,2,3,4,5]",
        "quicksort([2,2,2,2])==[2,2,2,2]",
    ],
    complexity_target="O(n log n) average",
    tags=["sorting", "implementation", "testing"],  # "sorting" 겹침
    source="cokac_partial_symmetric",
)

# ---------------------------------------------------------------------------
# Condition C: 완전 동종 (CSER=0.0) — 게이트 차단 예상
# macro_tags == tech_tags → macro_unique={}, tech_unique={}
# cross_count = 0, total = 9 → CSER = 0.0
# ---------------------------------------------------------------------------

MACRO_C = MacroSpec(
    intent="sorting 함수 quicksort(arr) 구현",
    architecture="sorting 알고리즘으로 리스트를 정렬",
    emergence_hooks=["sorting 구현"],
    tags=["sorting", "quicksort", "algorithm"],
    source="single_agent_macro",
)

TECH_C = TechSpec(
    implementation_strategy="sorting 알고리즘 quicksort 구현",
    edge_cases=["빈 리스트", "단일 원소"],
    test_criteria=["quicksort([3,1,4,1,5])==[1,1,3,4,5]"],
    complexity_target="O(n log n)",
    tags=["sorting", "quicksort", "algorithm"],  # 완전 동일 — CSER=0
    source="single_agent_tech",
)


# ---------------------------------------------------------------------------
# QuickSort 검증기 — exec() 기반 실제 실행
# ---------------------------------------------------------------------------

def quicksort_validator_fn(generated: GeneratedCode, tech: TechSpec) -> ValidationResult:
    """
    생성된 코드를 실제 Python exec()로 실행, QuickSort 테스트 케이스 검증.
    5개 엣지케이스 커버.
    """
    test_cases = [
        ([3, 1, 4, 1, 5], [1, 1, 3, 4, 5]),
        ([], []),
        ([1], [1]),
        ([5, 4, 3, 2, 1], [1, 2, 3, 4, 5]),
        ([2, 2, 2, 2], [2, 2, 2, 2]),
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

    # 함수명 탐색: quicksort, sort, solution 순
    qs_fn = (
        namespace.get("quicksort")
        or namespace.get("quick_sort")
        or namespace.get("sort")
        or namespace.get("solution")
    )
    if qs_fn is None:
        return ValidationResult(
            passed=False,
            test_results=[{"name": "func_lookup", "passed": False,
                           "message": "quicksort() 함수 없음"}],
            quality_score=0.0,
            complexity_actual="O(?)",
            issues=["quicksort function not defined in generated code"],
        )

    results = []
    for inp, expected in test_cases:
        try:
            got = qs_fn(list(inp))  # 원본 보호용 복사
            ok = got == expected
            results.append({
                "name": f"qs({inp})=={expected}",
                "passed": ok,
                "message": f"got {got}",
            })
        except Exception as e:
            results.append({
                "name": f"qs({inp})=={expected}",
                "passed": False,
                "message": str(e),
            })

    pass_rate = sum(1 for r in results if r["passed"]) / len(results)
    return ValidationResult(
        passed=pass_rate >= 0.8,
        test_results=results,
        quality_score=pass_rate,
        complexity_actual="O(n log n)",
        issues=[r["message"] for r in results if not r["passed"]],
    )


# ---------------------------------------------------------------------------
# CSER 사전 검증
# ---------------------------------------------------------------------------

def verify_all_cser() -> dict[str, float]:
    """세 조건의 CSER 수치 사전 계산."""
    results = {}
    for label, macro, tech in [
        ("A", MACRO_A, TECH_A),
        ("B_partial", MACRO_B_PARTIAL, TECH_B_PARTIAL),
        ("C", MACRO_C, TECH_C),
    ]:
        crossover = CSERCrossover(macro=macro, tech=tech)
        cser = crossover.compute_cser()
        macro_tags = set(macro.tags)
        tech_tags = set(tech.tags)
        shared = macro_tags & tech_tags
        macro_unique = macro_tags - tech_tags
        tech_unique = tech_tags - macro_tags
        results[label] = cser

        print(f"[Condition {label}]")
        print(f"  macro_tags:   {sorted(macro_tags)}")
        print(f"  tech_tags:    {sorted(tech_tags)}")
        print(f"  공유:         {sorted(shared)} ({len(shared)}개)")
        print(f"  cross_count:  {len(macro_unique) * len(tech_unique)}")
        print(f"  total:        {len(macro_tags) * len(tech_tags)}")
        print(f"  CSER:         {cser:.4f}")
        print(f"  게이트(0.30): {'✓ 통과' if cser >= 0.30 else '✗ 차단'}")
        print()
    return results


# ---------------------------------------------------------------------------
# 실험 러너
# ---------------------------------------------------------------------------

def run_condition(
    label: str,
    macro: MacroSpec,
    tech: TechSpec,
    n_trials: int,
    use_llm: bool,
    cycle_base: int,
) -> dict:
    """단일 조건 n_trials 실행."""
    loop = ExecutionLoop()

    # CSER 게이트 사전 확인
    crossover = CSERCrossover(macro=macro, tech=tech)
    cser = crossover.compute_cser()
    gate_ok = cser >= ExecutionLoop.CSER_THRESHOLD

    if not gate_ok:
        print(f"  ✗ 게이트 차단 (CSER={cser:.4f} < {ExecutionLoop.CSER_THRESHOLD})")
        return {
            "condition": label,
            "n_trials": n_trials,
            "cser_predicted": cser,
            "cser_actual": cser,
            "passed": 0,
            "pass_rate": 0.0,
            "avg_quality": 0.0,
            "quality_scores": [],
            "gate_passed": False,
            "blocked_by_gate": True,
            "individual_results": [],
        }

    code_fn = llm_code_generator_fn if use_llm else None
    valid_fn = quicksort_validator_fn if use_llm else None

    results = []
    for i in range(n_trials):
        problem = Problem(
            description=PROBLEM_QUICKSORT.description,
            constraints=PROBLEM_QUICKSORT.constraints,
            examples=PROBLEM_QUICKSORT.examples,
            cycle=cycle_base + i,
        )
        print(f"  [실행 {i+1}/{n_trials}]")
        r = loop.run(
            problem,
            macro,
            tech,
            code_generator_fn=code_fn,
            validator_fn=valid_fn,
        )
        results.append(r)

    passed_count = sum(1 for r in results if r.get("passed", False))
    quality_scores = [r.get("quality_score", 0.0) for r in results]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    cser_actual = results[0]["cser_score"] if results else cser

    return {
        "condition": label,
        "n_trials": n_trials,
        "cser_predicted": cser,
        "cser_actual": cser_actual,
        "passed": passed_count,
        "pass_rate": passed_count / n_trials,
        "avg_quality": avg_quality,
        "quality_scores": quality_scores,
        "gate_passed": True,
        "blocked_by_gate": False,
        "individual_results": results,
    }


def run_experiment(n_trials: int = 5, use_llm: bool = True) -> dict:
    """사이클 83 전체 실험."""
    print("=" * 65)
    print("사이클 83 — QuickSort CSER-복잡도 의존성 실험")
    print("=" * 65)
    print()

    cser_map = verify_all_cser()

    summaries = {}

    print(f"=== Condition A (CSER=1.0) — {n_trials}회 ===")
    summaries["A"] = run_condition("A", MACRO_A, TECH_A, n_trials, use_llm, 8300)

    print(f"\n=== Condition B_partial (CSER≈0.444) — {n_trials}회 ===")
    summaries["B_partial"] = run_condition(
        "B_partial", MACRO_B_PARTIAL, TECH_B_PARTIAL, n_trials, use_llm, 8310
    )

    print(f"\n=== Condition C (CSER=0.0) — 게이트 테스트 ===")
    summaries["C"] = run_condition("C", MACRO_C, TECH_C, 1, use_llm, 8320)

    return {
        "problem": "QuickSort (O(n log n))",
        "cycle": 83,
        "n_trials": n_trials,
        "summaries": summaries,
        "cser_map": cser_map,
    }


def print_results_table(experiment: dict) -> None:
    """A vs B_partial vs C 비교 테이블 (논문용)."""
    s = experiment["summaries"]
    print()
    print("=" * 75)
    print("사이클 83 결과 테이블 — QuickSort (O(n log n))")
    print("=" * 75)
    header = f"{'조건':<22} {'CSER':>8} {'게이트':>8} {'패스율':>10} {'평균품질':>10}"
    print(header)
    print("-" * 75)

    for label, cond in s.items():
        gate = "차단" if not cond["gate_passed"] else "통과"
        if cond["blocked_by_gate"]:
            pass_str = "—"
            qual_str = "—"
        else:
            n = cond["n_trials"]
            p = cond["passed"]
            pass_str = f"{p}/{n}={p/n:.0%}"
            qual_str = f"{cond['avg_quality']:.3f}"
        print(f"{label:<22} {cond['cser_actual']:>8.3f} {gate:>8} {pass_str:>10} {qual_str:>10}")

    print("-" * 75)

    # 비교 사이클 82 GCD 결과 (기록값)
    print()
    print("참고 — 사이클 82 GCD (O(log n)):")
    print("  A(CSER=1.0): 5/5=100%, 품질=1.000")
    print("  B_partial(CSER=0.444): 5/5=100%, 품질=1.000")
    print("  결론: GCD 수준에서는 CSER 스펙트럼 효과 없음")
    print()

    # H_complexity 판정
    sa = s.get("A", {})
    sb = s.get("B_partial", {})
    if not sa.get("gate_passed") or not sb.get("gate_passed"):
        print("가설 판정: 데이터 불충분")
        return

    qa = sa.get("avg_quality", 0)
    qb = sb.get("avg_quality", 0)
    pa = sa.get("pass_rate", 0)
    pb = sb.get("pass_rate", 0)
    delta_q = qa - qb
    delta_p = pa - pb

    print("H_complexity 판정:")
    if delta_q > 0.05 or delta_p > 0.1:
        print(f"  ✓ H_complexity 지지: QuickSort에서 A({qa:.3f}) > B_partial({qb:.3f})")
        print(f"    품질 Δ={delta_q:.3f}, 패스율 Δ={delta_p:.0%}")
        print(f"    → CSER 스펙트럼 효과는 O(n log n) 이상에서 발현")
        print(f"    → 논문: '이진 게이트' 아닌 '연속 스펙트럼' 모델 지지")
    else:
        print(f"  ✗ H_complexity 기각: A({qa:.3f}) ≈ B_partial({qb:.3f})")
        print(f"    품질 Δ={delta_q:.3f} (< 임계값 0.05)")
        print(f"    → QuickSort도 단순 문제와 마찬가지로 스펙트럼 효과 없음")
        print(f"    → 논문: 게이트 이진 모델 확정 (CSER > 0.30이면 품질 포화)")

    # C 조건 게이트 확인
    sc = s.get("C", {})
    if sc.get("blocked_by_gate"):
        print()
        print(f"  Condition C (CSER={sc['cser_actual']:.3f}): 게이트 차단 ✓")
        print(f"    → single_agent_only: 게이트 메커니즘 실증")


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="H_exec 사이클 83 — QuickSort CSER 복잡도 의존성 실험"
    )
    parser.add_argument("--mock", action="store_true", help="LLM 호출 없이 mock 실행")
    parser.add_argument("--trials", type=int, default=5, help="각 조건 실행 횟수 (기본: 5)")
    args = parser.parse_args()

    use_llm = not args.mock
    print(f"실험 모드: {'실제 LLM (claude CLI)' if use_llm else 'MOCK'}")
    print()

    start = time.time()
    experiment = run_experiment(n_trials=args.trials, use_llm=use_llm)
    elapsed = time.time() - start

    print_results_table(experiment)
    print(f"\n소요 시간: {elapsed:.1f}초")

    # 결과 저장
    out_path = Path(__file__).parent / "h_exec_cycle83_results.json"
    with open(out_path, "w") as f:
        json.dump(experiment, f, indent=2, ensure_ascii=False)
    print(f"결과 저장: {out_path}")
