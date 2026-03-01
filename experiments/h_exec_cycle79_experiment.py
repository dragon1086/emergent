"""
H_exec 사이클 79 — A 조건 단독 5회 LLM 실행 (GCD 문제)
========================================================
목표: 조건 A만 5회 실제 LLM 호출로 GCD 코드 생성 및 품질 검증

사이클 78 선행 결과:
  A 조건(CSER=1.0): 3/3회 통과, 품질=1.0 (덧셈 문제 add(a,b))
  B 조건(CSER=0.25): 0/3 — 에코챔버 게이트 차단
  C 조건(CSER=0.0):  0/3 — 에코챔버 게이트 차단

사이클 79 신규 문제 P2: GCD (두 정수의 최대공약수)
  - P1(덧셈, O(1))보다 복잡한 로직 — 유클리드 알고리즘 O(log n)
  - KG 피드백 노드 + CSER 교차 엣지 기록

핵심 가설 계속 검증:
  "에코챔버는 코드를 만들 수 없다 — A 조건만이 실행 루프에 진입"
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from execution_loop import (
    ExecutionLoop,
    GeneratedCode,
    MacroSpec,
    Problem,
    TechSpec,
    ValidationResult,
    llm_code_generator_fn,
)

# ---------------------------------------------------------------------------
# 문제 정의 (P2: GCD)
# ---------------------------------------------------------------------------

PROBLEM_P2 = Problem(
    description="두 양의 정수 a, b를 입력받아 최대공약수(GCD)를 반환하는 함수 gcd(a, b)를 작성하라.",
    constraints=["순수 함수", "타입 힌트 포함", "docstring 포함", "재귀 또는 반복 방식 모두 허용"],
    examples=[
        {"input": "gcd(12, 8)", "output": "4"},
        {"input": "gcd(100, 75)", "output": "25"},
        {"input": "gcd(7, 13)", "output": "1"},
        {"input": "gcd(0, 5)", "output": "5"},
    ],
    cycle=79,
)

# ---------------------------------------------------------------------------
# 조건 A: 완전 비대칭 (CSER = 1.0)
# macro_unique={emergence, algorithm_essence, irreducibility, mathematical_truth}(4)
# tech_unique={euclidean, modulo, recursion, termination}(4)
# 겹침: 없음 → CSER = (4×4)/(4×4) = 1.0
# ---------------------------------------------------------------------------

MACRO_A_GCD = MacroSpec(
    intent="최대공약수는 두 수 사이의 숨겨진 공약 구조를 드러내는 함수 — 단순성 속에 수학적 진리",
    architecture="알고리즘 자체가 수학적 불변 관계를 구현, 부수효과 없음, 입출력 계약 명시",
    emergence_hooks=[
        "GCD는 알고리즘과 수학 사이의 경계가 사라지는 지점",
        "유클리드 알고리즘: 인류 최초의 알고리즘 중 하나 — 단순함의 극치",
        "두 수의 GCD: 집합의 공약 구조 전체를 하나의 수로 압축",
    ],
    tags=["emergence", "algorithm_essence", "irreducibility", "mathematical_truth"],
    source="openclaw",
)

TECH_A_GCD = TechSpec(
    implementation_strategy="유클리드 알고리즘: gcd(a, b) = gcd(b, a%b), base case: gcd(a, 0) = a",
    edge_cases=["b=0 → a 반환", "a=0 → b 반환", "두 수 같음 → 자기 자신", "서로소 쌍 (GCD=1)"],
    test_criteria=[
        "gcd(12,8)==4", "gcd(100,75)==25", "gcd(7,13)==1",
        "gcd(0,5)==5", "gcd(15,15)==15",
    ],
    complexity_target="O(log min(a,b))",
    tags=["euclidean", "modulo", "recursion", "termination"],
    source="cokac",
)
# 예상 CSER = (4×4)/(4×4) = 16/16 = 1.0 → 게이트(0.30) 통과 확실


# ---------------------------------------------------------------------------
# GCD 전용 validator — exec() 실제 실행
# ---------------------------------------------------------------------------

def gcd_validator_fn(generated: GeneratedCode, tech: TechSpec) -> ValidationResult:
    """생성된 코드를 실제로 exec()하여 GCD 테스트 케이스 검증."""
    code = generated.code
    test_cases = [
        ("gcd(12, 8)",    4),
        ("gcd(100, 75)", 25),
        ("gcd(7, 13)",    1),
        ("gcd(0, 5)",     5),
        ("gcd(15, 15)",  15),
    ]

    namespace: dict = {}
    tests = []
    exec_error = None

    try:
        exec(code, namespace)  # noqa: S102
    except Exception as exc:
        exec_error = str(exc)

    if exec_error:
        for expr, _ in test_cases:
            tests.append({"name": expr, "passed": False, "message": f"exec 실패: {exec_error}"})
        return ValidationResult(
            passed=False,
            test_results=tests,
            quality_score=0.0,
            complexity_actual="unknown",
            issues=[f"코드 실행 오류: {exec_error}"],
        )

    if "gcd" not in namespace:
        for expr, _ in test_cases:
            tests.append({"name": expr, "passed": False, "message": "gcd 함수 정의 없음"})
        return ValidationResult(
            passed=False,
            test_results=tests,
            quality_score=0.0,
            complexity_actual="unknown",
            issues=["gcd 함수가 정의되지 않음"],
        )

    for expr, expected in test_cases:
        try:
            actual = eval(expr, namespace)  # noqa: S307
            ok = int(actual) == int(expected)
            tests.append({
                "name": expr,
                "passed": ok,
                "message": f"expected={expected}, actual={actual}",
            })
        except Exception as exc:
            tests.append({"name": expr, "passed": False, "message": str(exc)})

    passed_n = sum(1 for t in tests if t["passed"])
    quality = passed_n / len(tests)

    return ValidationResult(
        passed=quality >= ExecutionLoop.QUALITY_THRESHOLD,
        test_results=tests,
        quality_score=quality,
        complexity_actual="O(log min(a,b))",
        issues=[t["message"] for t in tests if not t["passed"]],
    )


# ---------------------------------------------------------------------------
# CSER 사전 계산 (확인용)
# ---------------------------------------------------------------------------

def _cser_preview(macro: MacroSpec, tech: TechSpec) -> float:
    mt = set(macro.tags)
    tt = set(tech.tags)
    mu = mt - tt
    tu = tt - mt
    cross = len(mu) * len(tu)
    total = len(mt) * len(tt) if mt and tt else 1
    return cross / max(total, 1)


# ---------------------------------------------------------------------------
# 실험 실행
# ---------------------------------------------------------------------------

def run_cycle79(n_trials: int = 5, use_llm: bool = True) -> dict:
    """
    사이클 79: 조건 A만 5회 실제 LLM 호출.

    수집:
      - 각 실행의 코드 품질 점수 (테스트 통과 여부)
      - 실제 CSER 교차 엣지 내용
      - KG에 추가된 피드백 노드 확인
    """
    code_gen_fn = llm_code_generator_fn if use_llm else None
    validator = gcd_validator_fn if use_llm else None

    preview_cser = _cser_preview(MACRO_A_GCD, TECH_A_GCD)

    print(f"{'='*60}")
    print("H_exec 사이클 79 — 조건 A 단독 실험 (GCD 문제)")
    print(f"  CSER 예상: {preview_cser:.4f}  (임계값 0.30 → {'통과' if preview_cser >= 0.30 else '차단'})")
    print(f"  문제: {PROBLEM_P2.description}")
    print(f"  모드: {'실제 LLM (claude CLI)' if use_llm else 'Mock 모드'}")
    print(f"  반복: {n_trials}회")
    print(f"{'='*60}")

    loop = ExecutionLoop()
    trial_results = []
    cross_edges_detail = []

    for trial in range(n_trials):
        p = Problem(
            description=PROBLEM_P2.description,
            constraints=PROBLEM_P2.constraints,
            examples=PROBLEM_P2.examples,
            cycle=79 + trial,
        )
        print(f"\n  [Trial {trial+1}/{n_trials}]")
        r = loop.run(
            p, MACRO_A_GCD, TECH_A_GCD,
            code_generator_fn=code_gen_fn,
            validator_fn=validator,
        )
        trial_results.append(r)

        # 교차 엣지 상세 기록
        from execution_loop import CSERCrossover
        xover = CSERCrossover(macro=MACRO_A_GCD, tech=TECH_A_GCD)
        xover.compute_cser()
        cross_edges_detail.append({
            "trial": trial + 1,
            "cser": xover.cser_score,
            "cross_edges": [(m, t) for m, t in xover.cross_edges[:8]],  # 상위 8개
            "quality": r.get("quality_score", 0),
            "passed": r.get("passed", False),
        })
        time.sleep(0.5)

    summary = loop.summary()
    cross_edges_total = sum(r.get("cross_edges_count", 0) for r in trial_results)

    print(f"\n{'='*60}")
    print("사이클 79 결과 요약")
    print(f"{'='*60}")
    print(f"  통과: {summary.get('passed',0)}/{n_trials}회")
    print(f"  통과율: {summary.get('pass_rate', 0):.0%}")
    print(f"  평균 품질: {summary.get('avg_quality', 0):.3f}")
    print(f"  평균 CSER: {summary.get('avg_cser', 0):.4f}")
    print(f"  총 교차 엣지: {cross_edges_total}개 ({cross_edges_total/n_trials:.1f}개/회)")
    print()
    print("  CSER 교차 엣지 샘플 (Trial 1):")
    if cross_edges_detail:
        for m, t in cross_edges_detail[0]["cross_edges"][:4]:
            print(f"    [{m}] × [{t}]")

    results = {
        "cycle": 79,
        "problem": "GCD — 두 정수의 최대공약수",
        "condition": "A_asymmetric_cser1.0",
        "n_trials": n_trials,
        "use_llm": use_llm,
        "preview_cser": preview_cser,
        "trials": trial_results,
        "summary": summary,
        "cross_edges_total": cross_edges_total,
        "cross_edges_detail": cross_edges_detail,
        "key_finding": {
            "finding": (
                f"A 조건(CSER={preview_cser:.2f}) GCD 문제: "
                f"{summary.get('passed',0)}/{n_trials}회 통과"
            ),
            "avg_quality": summary.get("avg_quality", 0),
            "cross_edges_per_trial": cross_edges_total / max(n_trials, 1),
            "comparison_c78": (
                "사이클 78 (덧셈, O(1)): 품질=1.0 | "
                f"사이클 79 (GCD, O(log n)): 품질={summary.get('avg_quality',0):.3f}"
            ),
            "implication": (
                "더 복잡한 문제에서도 A 조건(CSER=1.0)이 "
                "에코챔버 없이 코드를 생성한다면 — H_exec 강화 근거"
            ),
        },
        "metadata": {
            "cser_threshold": ExecutionLoop.CSER_THRESHOLD,
            "quality_threshold": ExecutionLoop.QUALITY_THRESHOLD,
            "b_c_condition": "사이클 78에서 B/C 차단 확인 — 사이클 79는 A만 집중",
        },
    }

    out_path = Path(__file__).parent / "h_exec_cycle79_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  결과 저장: {out_path}")

    return results


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H_exec 사이클 79 — A 조건 GCD")
    parser.add_argument("--mock", action="store_true", help="LLM 없이 mock 실행")
    parser.add_argument("--trials", type=int, default=5)
    args = parser.parse_args()

    results = run_cycle79(n_trials=args.trials, use_llm=not args.mock)

    print(f"\n{'='*60}")
    print(f"최종: {results['summary'].get('passed',0)}/{results['n_trials']}회 통과")
    print(f"평균 품질: {results['summary'].get('avg_quality',0):.3f}")
    print(f"사이클 79 완료.")
