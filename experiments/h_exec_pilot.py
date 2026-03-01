"""
H_exec 파일럿 실험 — 사이클 77
=================================
목표: 조건 A/B/C × 3회 = 9회 실행으로 H_exec 첫 데이터 포인트 획득

H_exec 가설:
  CSER이 높은 협업 컨텍스트(조건 A)에서 생성된 코드가
  중간(조건 B) 또는 단일 에이전트(조건 C)보다
  실제 테스트 통과율이 높다.

조건 정의:
  A: 완전 비대칭 (Roki 이론 태그 ↔ cokac 구현 태그, tag_overlap=0 → CSER→1.0)
  B: 부분 겹침 (일부 공유 태그, tag_overlap~0.3 → CSER→0.5)
  C: 단일 에이전트 시뮬레이션 (동종 태그, tag_overlap→1.0 → CSER→0.0)

문제 P1: 두 정수 a, b를 입력받아 합을 반환하는 add(a, b) 함수 작성
  테스트: add(3,5)==8, add(-1,1)==0, add(0,0)==0, add(100,-50)==50

실행 후 results를 experiments/h_exec_pilot_results.json에 저장.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# src 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from execution_loop import (
    ExecutionLoop,
    MacroSpec,
    Problem,
    TechSpec,
    llm_code_generator_fn,
)

# ---------------------------------------------------------------------------
# 실제 코드 품질 검증기 — 생성된 코드를 실제로 실행
# ---------------------------------------------------------------------------

def real_validator_fn(generated, tech):
    """
    생성된 코드를 실제로 exec() 실행하고 테스트 케이스를 검증.
    모의 검증 대신 실제 Python 실행.
    """
    from execution_loop import ValidationResult

    code = generated.code
    test_cases = [
        ("add(3, 5)", 8),
        ("add(-1, 1)", 0),
        ("add(0, 0)", 0),
        ("add(100, -50)", 50),
    ]

    # 코드 실행 환경
    namespace = {}
    tests = []
    exec_error = None

    try:
        exec(code, namespace)  # noqa: S102
    except Exception as e:
        exec_error = str(e)

    if exec_error:
        for expr, expected in test_cases:
            tests.append({"name": expr, "passed": False, "message": f"exec 실패: {exec_error}"})
        return ValidationResult(
            passed=False,
            test_results=tests,
            quality_score=0.0,
            complexity_actual="unknown",
            issues=[f"코드 실행 오류: {exec_error}"],
        )

    if "add" not in namespace:
        for expr, expected in test_cases:
            tests.append({"name": expr, "passed": False, "message": "add 함수 미정의"})
        return ValidationResult(
            passed=False,
            test_results=tests,
            quality_score=0.0,
            complexity_actual="unknown",
            issues=["add 함수가 코드에 없음"],
        )

    # 테스트 실행
    for expr, expected in test_cases:
        try:
            actual = eval(expr, namespace)  # noqa: S307
            passed = actual == expected
            tests.append({
                "name": expr,
                "passed": passed,
                "message": f"반환={actual}, 기대={expected}",
            })
        except Exception as e:
            tests.append({"name": expr, "passed": False, "message": str(e)})

    pass_rate = sum(1 for t in tests if t["passed"]) / len(tests)

    # 품질 점수 계산 (통과율 + 코드 스타일 보너스)
    quality = pass_rate
    if "def add" in code:
        quality = min(quality + 0.05, 1.0)
    if "->" in code or ": int" in code:  # 타입 힌트
        quality = min(quality + 0.05, 1.0)
    if '"""' in code or "'''" in code:  # docstring
        quality = min(quality + 0.05, 1.0)

    from execution_loop import ExecutionLoop as EL
    passed_overall = pass_rate >= EL.QUALITY_THRESHOLD

    return ValidationResult(
        passed=passed_overall,
        test_results=tests,
        quality_score=quality,
        complexity_actual="O(1)",
        issues=[t["message"] for t in tests if not t["passed"]],
    )


# ---------------------------------------------------------------------------
# 3가지 조건 정의
# ---------------------------------------------------------------------------

PROBLEM_P1 = Problem(
    description="두 정수 a, b를 입력받아 합을 반환하는 함수 add(a, b)를 작성하라.",
    constraints=["순수 함수", "타입 힌트 포함", "docstring 포함"],
    examples=[
        {"input": "add(3, 5)", "output": "8"},
        {"input": "add(-1, 1)", "output": "0"},
        {"input": "add(0, 0)", "output": "0"},
    ],
    cycle=77,
)

# 조건 A: 완전 비대칭 (이론↔구현, tag_overlap=0)
MACRO_A = MacroSpec(
    intent="기초 연산의 명확한 명세화 — 복잡성보다 명료성 우선",
    architecture="단일 순수 함수, 부수효과 없음, 인터페이스 계약 명시",
    emergence_hooks=["단순함이 복잡한 시스템의 토대", "명세가 곧 설계"],
    tags=["purity", "specification", "emergence", "contract"],
    source="openclaw",
)
TECH_A = TechSpec(
    implementation_strategy="Python 내장 덧셈 연산자, 타입 힌트 int → int",
    edge_cases=["음수 입력", "0 입력", "Python 임의 정밀도 정수 — 오버플로 없음"],
    test_criteria=["add(3,5)==8", "add(-1,1)==0", "add(0,0)==0", "add(100,-50)==50"],
    complexity_target="O(1)",
    tags=["integer", "operator", "return_value", "implementation"],
    source="cokac",
)

# 조건 B: 부분 겹침 (일부 공유 태그, tag_overlap~0.3)
MACRO_B = MacroSpec(
    intent="정수 덧셈 함수 구현",
    architecture="함수 하나로 처리",
    emergence_hooks=["간단한 덧셈"],
    tags=["integer", "function", "specification", "implementation"],  # 겹침 태그 포함
    source="openclaw",
)
TECH_B = TechSpec(
    implementation_strategy="덧셈 연산자 사용",
    edge_cases=["음수", "0"],
    test_criteria=["add(3,5)==8", "add(-1,1)==0"],
    complexity_target="O(1)",
    tags=["integer", "function", "implementation", "return_value"],  # 겹침 태그 포함
    source="cokac",
)

# 조건 C: 단일 에이전트 시뮬레이션 (동종 태그, tag_overlap→1.0)
MACRO_C = MacroSpec(
    intent="add 함수를 구현하라",
    architecture="def add(a, b): return a + b",
    emergence_hooks=[],
    tags=["add", "function", "integer", "return"],  # 완전 동종
    source="openclaw",
)
TECH_C = TechSpec(
    implementation_strategy="return a + b",
    edge_cases=["없음"],
    test_criteria=["add(3,5)==8"],
    complexity_target="O(1)",
    tags=["add", "function", "integer", "return"],  # 완전 동종 (CSER→0)
    source="cokac",
)


# ---------------------------------------------------------------------------
# 실험 실행
# ---------------------------------------------------------------------------

def run_pilot(n_trials: int = 3, use_llm: bool = True) -> dict:
    """
    9회 파일럿 실험 실행.

    Args:
        n_trials: 조건당 반복 횟수 (기본 3)
        use_llm: 실제 LLM 호출 여부 (False면 mock 사용)

    Returns:
        실험 결과 딕셔너리
    """
    code_gen_fn = llm_code_generator_fn if use_llm else None

    conditions = [
        ("A_asymmetric_high_cser", MACRO_A, TECH_A),
        ("B_partial_mid_cser", MACRO_B, TECH_B),
        ("C_homogeneous_low_cser", MACRO_C, TECH_C),
    ]

    all_results = {}
    total_runs = 0

    for cond_name, macro, tech in conditions:
        print(f"\n{'='*55}")
        print(f"조건 {cond_name} — {n_trials}회 실행")
        print(f"{'='*55}")

        loop = ExecutionLoop()
        cond_results = []

        for trial in range(n_trials):
            p = Problem(
                description=PROBLEM_P1.description,
                constraints=PROBLEM_P1.constraints,
                examples=PROBLEM_P1.examples,
                cycle=77 + trial,
            )
            print(f"\n  [Trial {trial+1}/{n_trials}]")
            r = loop.run(
                p, macro, tech,
                code_generator_fn=code_gen_fn,
                validator_fn=real_validator_fn if use_llm else None,
            )
            cond_results.append(r)
            total_runs += 1
            time.sleep(0.5)  # CLI 호출 간 간격

        summary = loop.summary()
        all_results[cond_name] = {
            "trials": cond_results,
            "summary": summary,
        }

        print(f"\n  → 조건 {cond_name} 요약:")
        print(f"     통과율: {summary.get('pass_rate', 0):.0%}")
        print(f"     평균 품질: {summary.get('avg_quality', 0):.3f}")
        print(f"     평균 CSER: {summary.get('avg_cser', 0):.4f}")

    # H_exec 가설 평가
    q_a = all_results["A_asymmetric_high_cser"]["summary"].get("avg_quality", 0)
    q_b = all_results["B_partial_mid_cser"]["summary"].get("avg_quality", 0)
    q_c = all_results["C_homogeneous_low_cser"]["summary"].get("avg_quality", 0)

    h_exec_supported = q_a > q_b and q_a > q_c

    conclusion = {
        "h_exec_supported": h_exec_supported,
        "verdict": "지지됨 ✓" if h_exec_supported else "기각됨 — 재검토 필요",
        "quality_A": q_a,
        "quality_B": q_b,
        "quality_C": q_c,
        "delta_A_minus_B": round(q_a - q_b, 4),
        "delta_A_minus_C": round(q_a - q_c, 4),
        "total_runs": total_runs,
        "note": (
            "파일럿 (n=3×3=9). 사이클 78에서 n=100×3=300회 본실험 예정."
        ),
    }

    all_results["conclusion"] = conclusion

    return all_results


# ---------------------------------------------------------------------------
# 결과 저장
# ---------------------------------------------------------------------------

def save_results(results: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {path}")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H_exec 파일럿 실험")
    parser.add_argument("--mock", action="store_true", help="LLM 호출 없이 mock 실행")
    parser.add_argument("--trials", type=int, default=3, help="조건당 반복 횟수")
    args = parser.parse_args()

    use_llm = not args.mock

    print("H_exec 파일럿 실험 시작")
    print(f"모드: {'실제 LLM (claude CLI)' if use_llm else 'Mock 모드'}")
    print(f"설계: 조건 A/B/C × {args.trials}회 = {3 * args.trials}회 총 실행")
    print()

    results = run_pilot(n_trials=args.trials, use_llm=use_llm)

    # 결론 출력
    c = results["conclusion"]
    print("\n" + "=" * 55)
    print("H_exec 파일럿 결론")
    print("=" * 55)
    print(f"  가설 H_exec: {c['verdict']}")
    print(f"  조건 A (고CSER) 평균 품질: {c['quality_A']:.3f}")
    print(f"  조건 B (중CSER) 평균 품질: {c['quality_B']:.3f}")
    print(f"  조건 C (저CSER) 평균 품질: {c['quality_C']:.3f}")
    print(f"  Δ(A-B): {c['delta_A_minus_B']:+.4f}")
    print(f"  Δ(A-C): {c['delta_A_minus_C']:+.4f}")
    print(f"  총 실행: {c['total_runs']}회")
    print(f"  참고: {c['note']}")

    # 결과 저장
    out_path = Path(__file__).parent / "h_exec_pilot_results.json"
    save_results(results, out_path)
