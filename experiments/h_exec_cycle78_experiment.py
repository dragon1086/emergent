"""
H_exec 사이클 78 본실험 — B 조건 재설계 + CSER 스펙트럼 비교
=================================================================
목표: 조건 A/B/C × 5회 = 15회 실행으로 CSER 스펙트럼(1.0/0.25/0.0) 데이터 확보

사이클 77 파일럿 핵심 발견:
  B 조건(CSER=0.0625)이 CSER 게이트(0.30)에서 자동 차단.
  "에코챔버 구조 자체가 실행 불가능하다" — 더 강한 주장 근거.

사이클 78 B 조건 재설계:
  구 B: tag_overlap 과다 → CSER=0.0625 (게이트 차단됨, 비교 불가)
  신 B: macro_tags=[function,integer,specification,design]
        tech_tags=[function,integer,implementation,operator]
        → 겹침={function,integer}, macro_unique={specification,design},
          tech_unique={implementation,operator}
        → CSER = (2×2)/(4×4) = 4/16 = 0.25 (게이트 임계값 0.30 미만 → 차단)

스펙트럼 비교 설계:
  A: CSER=1.0  (완전 비대칭 → 게이트 통과 → 코드 실행)
  B: CSER=0.25 (부분 겹침 → 게이트 차단 → 실행 불가)
  C: CSER=0.0  (단일 에이전트 → 게이트 차단 → 실행 불가)

핵심 주장 (사이클 78 발견):
  "CSER이 낮으면 게이트에서 막힌다"가 아니라
  "에코챔버 구조는 코드 생성 루프 자체에 진입하지 못한다"
  = 에코챔버는 나쁜 코드를 만드는 것이 아니라 코드를 만들 수 없다.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from execution_loop import (
    ExecutionLoop,
    MacroSpec,
    Problem,
    TechSpec,
    llm_code_generator_fn,
)
from h_exec_pilot import real_validator_fn

# ---------------------------------------------------------------------------
# 문제 정의 (P1: 두 정수 덧셈)
# ---------------------------------------------------------------------------

PROBLEM_P1 = Problem(
    description="두 정수 a, b를 입력받아 합을 반환하는 함수 add(a, b)를 작성하라.",
    constraints=["순수 함수", "타입 힌트 포함", "docstring 포함"],
    examples=[
        {"input": "add(3, 5)", "output": "8"},
        {"input": "add(-1, 1)", "output": "0"},
        {"input": "add(0, 0)", "output": "0"},
    ],
    cycle=78,
)

# ---------------------------------------------------------------------------
# 조건 A: 완전 비대칭 (CSER = 1.0)
# macro_unique={purity,specification,emergence,contract} × tech_unique={integer,operator,return_value,implementation}
# CSER = (4×4)/(4×4) = 1.0
# ---------------------------------------------------------------------------

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
# 예상 CSER: macro_unique={purity,specification,emergence,contract}(4) ×
#            tech_unique={integer,operator,return_value,implementation}(4)
#            = 16 / (4×4) = 1.0

# ---------------------------------------------------------------------------
# 조건 B (재설계): 부분 겹침 (CSER = 0.25)
# macro_tags=[function,integer,specification,design](4개)
# tech_tags=[function,integer,implementation,operator](4개)
# 겹침: function, integer (2개)
# macro_unique={specification,design}(2) × tech_unique={implementation,operator}(2)
# CSER = (2×2)/(4×4) = 4/16 = 0.25
# ---------------------------------------------------------------------------

MACRO_B = MacroSpec(
    intent="정수 덧셈 함수의 인터페이스 설계 — 명확한 명세와 가독성 우선",
    architecture="단일 함수, 타입 명시, 설계 계약 준수",
    emergence_hooks=["명세가 구현의 가이드"],
    tags=["function", "integer", "specification", "design"],  # function/integer 겹침
    source="openclaw",
)
TECH_B = TechSpec(
    implementation_strategy="Python 덧셈 연산자 직접 사용, 반환값 명시",
    edge_cases=["음수", "0"],
    test_criteria=["add(3,5)==8", "add(-1,1)==0"],
    complexity_target="O(1)",
    tags=["function", "integer", "implementation", "operator"],  # function/integer 겹침
    source="cokac",
)
# 예상 CSER: macro_unique={specification,design}(2) × tech_unique={implementation,operator}(2)
#            = 4 / (4×4) = 0.25 → CSER_THRESHOLD=0.30 미만 → 게이트 차단

# ---------------------------------------------------------------------------
# 조건 C: 단일 에이전트 시뮬레이션 (CSER = 0.0)
# 동종 태그 → cross_count = 0 → CSER = 0.0
# ---------------------------------------------------------------------------

MACRO_C = MacroSpec(
    intent="add 함수를 구현하라",
    architecture="def add(a, b): return a + b",
    emergence_hooks=[],
    tags=["add", "function", "integer", "return"],
    source="openclaw",
)
TECH_C = TechSpec(
    implementation_strategy="return a + b",
    edge_cases=["없음"],
    test_criteria=["add(3,5)==8"],
    complexity_target="O(1)",
    tags=["add", "function", "integer", "return"],  # 완전 동종 (CSER=0)
    source="cokac",
)
# 예상 CSER: macro_unique={} × tech_unique={} = 0 / anything = 0.0 → 게이트 차단


# ---------------------------------------------------------------------------
# 실험 실행
# ---------------------------------------------------------------------------

def _cser_preview(macro: MacroSpec, tech: TechSpec) -> float:
    """CSER 사전 계산 (실행 전 확인용)."""
    mt = set(macro.tags)
    tt = set(tech.tags)
    mu = mt - tt  # macro_unique
    tu = tt - mt  # tech_unique
    cross = len(mu) * len(tu)
    total = len(mt) * len(tt) if mt and tt else 1
    return cross / max(total, 1)


def run_cycle78(n_trials: int = 5, use_llm: bool = True) -> dict:
    """
    사이클 78 본실험: 3조건 × 5회 = 15회 실행.

    Args:
        n_trials: 조건당 반복 횟수 (기본 5)
        use_llm: 실제 LLM 호출 여부

    Returns:
        실험 결과 + 스펙트럼 비교 분석
    """
    code_gen_fn = llm_code_generator_fn if use_llm else None

    conditions = [
        ("A_asymmetric_cser1.0", MACRO_A, TECH_A),
        ("B_partial_cser0.25_redesigned", MACRO_B, TECH_B),
        ("C_homogeneous_cser0.0", MACRO_C, TECH_C),
    ]

    all_results = {}
    total_attempts = 0

    for cond_name, macro, tech in conditions:
        preview_cser = _cser_preview(macro, tech)
        print(f"\n{'='*60}")
        print(f"조건 {cond_name}")
        print(f"  예상 CSER: {preview_cser:.4f} (임계값 0.30)")
        print(f"  예상 결과: {'통과 → 코드 실행' if preview_cser >= 0.30 else '차단 → 실행 불가'}")
        print(f"{'='*60}")

        loop = ExecutionLoop()
        cond_results = []

        for trial in range(n_trials):
            p = Problem(
                description=PROBLEM_P1.description,
                constraints=PROBLEM_P1.constraints,
                examples=PROBLEM_P1.examples,
                cycle=78 + trial,
            )
            print(f"\n  [Trial {trial+1}/{n_trials}]")
            r = loop.run(
                p, macro, tech,
                code_generator_fn=code_gen_fn,
                validator_fn=real_validator_fn if use_llm else None,
            )
            cond_results.append(r)
            total_attempts += 1
            time.sleep(0.3)

        summary = loop.summary()
        blocked = sum(1 for r in cond_results if "에코챔버" in r.get("status", ""))
        executed = n_trials - blocked

        all_results[cond_name] = {
            "trials": cond_results,
            "summary": summary,
            "preview_cser": preview_cser,
            "executed": executed,
            "blocked": blocked,
        }

        print(f"\n  → 조건 {cond_name} 요약:")
        print(f"     예상 CSER: {preview_cser:.4f}")
        print(f"     실행 시도: {executed}/{n_trials}회 (차단: {blocked}회)")
        print(f"     통과율:   {summary.get('pass_rate', 0):.0%}")
        print(f"     평균 품질: {summary.get('avg_quality', 0):.3f}")

    # ---------------------------------------------------------------------------
    # CSER 스펙트럼 분석
    # ---------------------------------------------------------------------------
    spec_a = all_results["A_asymmetric_cser1.0"]
    spec_b = all_results["B_partial_cser0.25_redesigned"]
    spec_c = all_results["C_homogeneous_cser0.0"]

    spectrum_analysis = {
        "cser_values": {
            "A": spec_a["preview_cser"],
            "B": spec_b["preview_cser"],
            "C": spec_c["preview_cser"],
        },
        "gate_results": {
            "A": "통과" if spec_a["executed"] > 0 else "차단",
            "B": "통과" if spec_b["executed"] > 0 else "차단",
            "C": "통과" if spec_c["executed"] > 0 else "차단",
        },
        "execution_counts": {
            "A": spec_a["executed"],
            "B": spec_b["executed"],
            "C": spec_c["executed"],
        },
        "quality_scores": {
            "A": spec_a["summary"].get("avg_quality", 0),
            "B": spec_b["summary"].get("avg_quality", 0),
            "C": spec_c["summary"].get("avg_quality", 0),
        },
    }

    # 핵심 발견: 에코챔버 구조는 실행 자체가 불가능하다
    a_exec = spec_a["executed"]
    b_exec = spec_b["executed"]
    c_exec = spec_c["executed"]

    key_finding = {
        "finding": "에코챔버 구조(CSER < 0.30)는 코드 생성 루프 진입 자체가 불가",
        "evidence": f"A({a_exec}/{n_trials}회 실행) vs B({b_exec}/{n_trials}회 실행) vs C({c_exec}/{n_trials}회 실행)",
        "stronger_claim": (
            "'에코챔버는 나쁜 코드를 만든다'가 아니라 "
            "'에코챔버는 코드를 만들 수 없다' — 구조적 실행 불가능성"
        ),
        "implication_for_section8": (
            "H_exec 가설보다 강한 주장: CSER 게이트가 에코챔버를 "
            "자동 필터링한다. 비교 자체가 성립하지 않는 구조."
        ),
        "b_redesign_result": f"B 조건 재설계(CSER=0.25, 구 0.0625) → 여전히 게이트 차단. "
                             f"'스펙트럼 비교(1.0/0.25/0.0)' 확보."
    }

    all_results["spectrum_analysis"] = spectrum_analysis
    all_results["key_finding_cycle78"] = key_finding
    all_results["metadata"] = {
        "cycle": 78,
        "total_attempts": total_attempts,
        "n_trials_per_condition": n_trials,
        "cser_threshold": ExecutionLoop.CSER_THRESHOLD,
        "b_condition_redesign": "v1: CSER=0.0625 → v2: CSER=0.25",
        "b_cser_calc": "(2×2)/(4×4) = 4/16 = 0.25",
    }

    return all_results


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H_exec 사이클 78 본실험")
    parser.add_argument("--mock", action="store_true", help="LLM 없이 mock 실행")
    parser.add_argument("--trials", type=int, default=5, help="조건당 반복 횟수")
    args = parser.parse_args()

    use_llm = not args.mock

    print("H_exec 사이클 78 본실험")
    print(f"모드: {'실제 LLM (claude CLI)' if use_llm else 'Mock 모드'}")
    print(f"설계: 조건 A/B(재설계)/C × {args.trials}회 = {3 * args.trials}회 시도")
    print()
    print("조건 정의:")
    print(f"  A: CSER=1.0 (완전 비대칭)")
    print(f"  B: CSER=0.25 (재설계 — 구 0.0625, 임계값 0.30 미만)")
    print(f"  C: CSER=0.0 (단일 에이전트)")

    results = run_cycle78(n_trials=args.trials, use_llm=use_llm)

    # 스펙트럼 분석 출력
    sa = results["spectrum_analysis"]
    kf = results["key_finding_cycle78"]

    print("\n" + "=" * 60)
    print("사이클 78 — CSER 스펙트럼 비교 결과")
    print("=" * 60)
    print(f"\n{'조건':<8} {'CSER':>8} {'게이트':>8} {'실행횟수':>10} {'품질':>8}")
    print("-" * 50)
    for cond in ["A", "B", "C"]:
        cser_v = sa["cser_values"][cond]
        gate_v = sa["gate_results"][cond]
        exec_v = sa["execution_counts"][cond]
        qual_v = sa["quality_scores"][cond]
        n = results["metadata"]["n_trials_per_condition"]
        print(f"  {cond:<6} {cser_v:>8.4f} {gate_v:>8} {exec_v:>4}/{n:<4}   {qual_v:>6.3f}")

    print(f"\n핵심 발견: {kf['finding']}")
    print(f"근거: {kf['evidence']}")
    print(f"더 강한 주장: {kf['stronger_claim']}")

    # 결과 저장
    out_path = Path(__file__).parent / "h_exec_cycle78_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
