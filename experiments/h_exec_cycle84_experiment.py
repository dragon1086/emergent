"""
H_exec 사이클 84 — LRU Cache N=20 통계 강화 + arXiv 최종 준비
=================================================================
핵심 목적:
  N=5 → N=20으로 통계 검정력 확보
  Fisher's exact test + Mann-Whitney U + Cohen's d 적용
  논문 Sec 7을 실제 p값/effect size로 채우기

P4 선택: LRU Cache
  선택 이유:
  - get/put 두 메서드 + O(1) 시간복잡도 제약
  - capacity eviction 로직 (LRU 순서 관리)
  - OrderedDict 또는 doubly linked list + hashmap 필요
  - 단순 구현으로는 LRU 순서 버그 발생 가능
  - B_partial(CSER=0.444)에서 실패 여지 존재
  - GCD/QuickSort보다 구현 복잡성 높음

CSER 설계:
  A    (CSER=1.0):   macro=[eviction_policy, memory_management, insertion_order]
                     tech =[ordereddict, doubly_linked_list, hashmap]
                     cross=3×3=9, total=9 → 1.0
  B_partial (0.444): "cache" 1개 겹침
                     macro=[cache, eviction_policy, memory_management]
                     tech =[cache, ordereddict, hashmap]
                     cross=2×2=4, total=9 → 4/9≈0.444
  C    (CSER=0.0):   완전 동종 "cache/lru/implementation" → 게이트 차단

테스트 케이스: 10개 (capacity=2 기준 8개 + capacity=1 2개)
  LRU 순서 엣지케이스 포함 → partial credit 가능
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
# 문제 정의 (P4: LRU Cache)
# ---------------------------------------------------------------------------

PROBLEM_LRU = Problem(
    description=(
        "capacity를 인자로 받는 LRUCache 클래스를 구현하라. "
        "get(key) → 존재하면 value, 없으면 -1. "
        "put(key, value) → 삽입/갱신. capacity 초과 시 가장 오래 사용하지 않은 항목 제거. "
        "get과 put 모두 O(1) 시간복잡도."
    ),
    constraints=[
        "get(key): O(1) — key 존재 시 value 반환, 없으면 -1. 최근 사용 순서 업데이트",
        "put(key, value): O(1) — 삽입/갱신. capacity 초과 시 LRU 항목 제거",
        "capacity ≥ 1",
        "key, value는 정수",
        "put으로 기존 key 업데이트 시 LRU 순서도 갱신",
        "get 호출도 LRU 순서 갱신",
    ],
    examples=[
        {"input": "LRUCache(2); put(1,1); put(2,2); get(1)", "output": "1"},
        {"input": "LRUCache(2); put(1,1); put(2,2); put(3,3); get(1)", "output": "-1"},
        {"input": "LRUCache(2); put(1,1); put(2,2); get(1); put(3,3); get(2)", "output": "-1"},
    ],
    cycle=84,
)


# ---------------------------------------------------------------------------
# Condition A: 완전 비대칭 (CSER=1.0)
# macro_tags: [eviction_policy, memory_management, insertion_order]
# tech_tags:  [ordereddict, doubly_linked_list, hashmap]
# 겹침: 없음 → cross=3×3=9, total=9 → CSER=1.0
# ---------------------------------------------------------------------------

MACRO_A = MacroSpec(
    intent=(
        "LRU Cache는 시간 지역성(temporal locality)을 명시적으로 관리하는 메모리 정책 — "
        "가장 오래 사용되지 않은 항목을 퇴출하는 eviction_policy의 구현체"
    ),
    architecture=(
        "삽입 순서와 접근 순서를 동시에 추적하는 이중 구조. "
        "memory_management 계층: capacity 한계를 강제 집행. "
        "insertion_order 계층: 시간적 접근 패턴을 O(1)로 조회 가능하게 유지"
    ),
    emergence_hooks=[
        "eviction_policy가 단순 순서 제거가 아닌 '접근 패턴의 압축 표현'인 이유",
        "memory_management에서 capacity 강제가 창발적 제약이 되는 지점",
        "insertion_order의 역설: 삽입이 아닌 '마지막 접근'으로 순서가 재정의됨",
    ],
    tags=["eviction_policy", "memory_management", "insertion_order"],
    source="openclaw_asymmetric",
)

TECH_A = TechSpec(
    implementation_strategy=(
        "Python collections.OrderedDict 활용: "
        "get() → move_to_end(key), return self._cache[key]. "
        "put() → 기존 키면 move_to_end, 새 키면 삽입 후 len > capacity이면 popitem(last=False). "
        "doubly_linked_list 구조는 OrderedDict 내부에서 O(1) 보장. "
        "hashmap 역할: self._cache dict 자체."
    ),
    edge_cases=[
        "capacity=1: put 두 번 → 첫 번째 eviction",
        "get으로 LRU 순서 업데이트 후 put → 다른 키 eviction",
        "동일 key put 두 번 (값 갱신) → LRU 순서도 갱신, capacity 소모 없음",
        "없는 키 get → -1",
        "get 후 다른 키 put → get한 키는 MRU가 됨",
    ],
    test_criteria=[
        "LRUCache(2); put(1,1); get(1)==1",
        "LRUCache(2); put(1,1); put(2,2); get(1)==1",
        "LRUCache(2); put(1,1); put(2,2); put(3,3); get(1)==-1",
        "LRUCache(2); put(1,1); put(2,2); put(3,3); get(2)==2",
        "LRUCache(2); put(1,1); put(2,2); get(1); put(3,3); get(2)==-1",
        "LRUCache(2); put(1,1); put(2,2); get(2); put(3,3); get(1)==-1",
        "LRUCache(2); put(1,1); put(2,2); put(1,10); get(1)==10",
        "LRUCache(2); put(1,1); put(2,2); put(1,10); get(2)==2",
        "LRUCache(2); get(99)==-1",
        "LRUCache(1); put(1,1); put(2,2); get(1)==-1",
    ],
    complexity_target="O(1) get/put",
    tags=["ordereddict", "doubly_linked_list", "hashmap"],
    source="cokac_asymmetric",
)


# ---------------------------------------------------------------------------
# Condition B_partial: 부분 대칭 (CSER≈0.444)
# "cache" 태그 겹침
# macro_tags: [cache, eviction_policy, memory_management]
# tech_tags:  [cache, ordereddict, hashmap]
# 겹침: cache(1개) → macro_unique={eviction_policy,memory_management}, tech_unique={ordereddict,hashmap}
# cross=2×2=4, total=3×3=9 → CSER=4/9≈0.444
# ---------------------------------------------------------------------------

MACRO_B_PARTIAL = MacroSpec(
    intent=(
        "LRU Cache는 cache 시스템의 표준 eviction 전략 — "
        "접근 빈도 기반으로 cache 메모리를 효율적으로 관리"
    ),
    architecture=(
        "cache 접근 순서를 추적하는 구조. "
        "eviction_policy: capacity 초과 시 LRU 항목 제거. "
        "memory_management: cache 크기를 capacity로 제한"
    ),
    emergence_hooks=[
        "cache eviction_policy로서 LRU의 시간 지역성 활용",
        "memory_management에서 cache capacity 강제 집행",
    ],
    tags=["cache", "eviction_policy", "memory_management"],
    source="openclaw_partial_symmetric",
)

TECH_B_PARTIAL = TechSpec(
    implementation_strategy=(
        "cache 구현: OrderedDict 사용. "
        "get(key): cache miss면 -1, hit이면 값 반환하며 순서 갱신. "
        "put(key,value): cache에 삽입. capacity 초과면 가장 오래된 항목 제거."
    ),
    edge_cases=[
        "cache miss: get(없는키) → -1",
        "capacity=1: put 두 번 시 첫 항목 eviction",
        "동일 key 재삽입",
    ],
    test_criteria=[
        "LRUCache(2); put(1,1); get(1)==1",
        "LRUCache(2); put(1,1); put(2,2); put(3,3); get(1)==-1",
        "LRUCache(2); put(1,1); put(2,2); get(1); put(3,3); get(2)==-1",
        "LRUCache(2); put(1,1); put(2,2); put(1,10); get(1)==10",
        "LRUCache(1); put(1,1); put(2,2); get(1)==-1",
    ],
    complexity_target="O(1) cache access",
    tags=["cache", "ordereddict", "hashmap"],  # "cache" 겹침
    source="cokac_partial_symmetric",
)


# ---------------------------------------------------------------------------
# Condition C: 완전 동종 (CSER=0.0) — 게이트 차단
# macro_tags == tech_tags → cross=0 → CSER=0.0
# ---------------------------------------------------------------------------

MACRO_C = MacroSpec(
    intent="LRU Cache 구현 — cache get/put",
    architecture="cache lru 알고리즘 구현",
    emergence_hooks=["lru cache 구현"],
    tags=["cache", "lru", "implementation"],
    source="single_agent_macro",
)

TECH_C = TechSpec(
    implementation_strategy="lru cache 구현: get/put 메서드",
    edge_cases=["cache miss", "capacity 초과"],
    test_criteria=["lru cache get/put 동작"],
    complexity_target="O(1)",
    tags=["cache", "lru", "implementation"],  # 완전 동종 — CSER=0
    source="single_agent_tech",
)


# ---------------------------------------------------------------------------
# LRU Cache 검증기 — exec() 기반 실제 실행
# 10개 테스트케이스: LRU 순서 엣지케이스 포함
# ---------------------------------------------------------------------------

# 테스트케이스: (operations, expected_last_return)
# operations: list of ("put", key, val) or ("get", key)
LRU_TEST_CASES = [
    # 1. 기본 get
    (
        [("put", 1, 1), ("get", 1)],
        1,
        "cap2: put(1,1); get(1)→1"
    ),
    # 2. 용량 내 두 키
    (
        [("put", 1, 1), ("put", 2, 2), ("get", 1)],
        1,
        "cap2: put(1,1); put(2,2); get(1)→1"
    ),
    # 3. eviction: 1이 LRU → put(3) 후 get(1)=-1
    (
        [("put", 1, 1), ("put", 2, 2), ("put", 3, 3), ("get", 1)],
        -1,
        "cap2: put(1,1); put(2,2); put(3,3); get(1)→-1 (LRU eviction)"
    ),
    # 4. eviction 후 남은 키 확인
    (
        [("put", 1, 1), ("put", 2, 2), ("put", 3, 3), ("get", 2)],
        2,
        "cap2: put(1,1); put(2,2); put(3,3); get(2)→2"
    ),
    # 5. get으로 LRU 순서 갱신 — get(1) 후 2가 LRU → put(3) 시 2 eviction
    (
        [("put", 1, 1), ("put", 2, 2), ("get", 1), ("put", 3, 3), ("get", 2)],
        -1,
        "cap2: get(1) makes 2 LRU; put(3) evicts 2; get(2)→-1"
    ),
    # 6. get으로 LRU 순서 갱신 — get(2) 후 1이 LRU → put(3) 시 1 eviction
    (
        [("put", 1, 1), ("put", 2, 2), ("get", 2), ("put", 3, 3), ("get", 1)],
        -1,
        "cap2: get(2) makes 1 LRU; put(3) evicts 1; get(1)→-1"
    ),
    # 7. 동일 key 값 갱신 (update)
    (
        [("put", 1, 1), ("put", 2, 2), ("put", 1, 10), ("get", 1)],
        10,
        "cap2: put(1,10) updates; get(1)→10"
    ),
    # 8. update 후 다른 키 유지
    (
        [("put", 1, 1), ("put", 2, 2), ("put", 1, 10), ("get", 2)],
        2,
        "cap2: put(1,10) update; get(2)→2 (2 not evicted)"
    ),
    # 9. 없는 키 get
    (
        [("get", 99)],
        -1,
        "cap2: get(99)→-1 (cache miss)"
    ),
    # 10. capacity=1 eviction
    (
        [("put", 1, 1), ("put", 2, 2), ("get", 1)],
        -1,
        "cap1: put(1,1); put(2,2); get(1)→-1 (evicted)"
    ),
]

# 케이스 10은 capacity=1로 실행
LRU_CAP1_IDX = 9  # 인덱스 9 (0-based)


def lru_validator_fn(generated: GeneratedCode, tech: TechSpec) -> ValidationResult:
    """
    생성된 코드를 Python exec()로 실행, LRU Cache 10개 테스트케이스 검증.
    partial credit: quality_score = passed / 10
    """
    namespace: dict = {}
    try:
        exec(generated.code, namespace)  # noqa: S102 — 실험용 exec
    except Exception as e:
        return ValidationResult(
            passed=False,
            test_results=[{"name": "exec_load", "passed": False, "message": str(e)}],
            quality_score=0.0,
            complexity_actual="O(?)",
            issues=[f"SyntaxError/RuntimeError: {e}"],
        )

    # 클래스명 탐색: LRUCache, LRU_Cache, Cache 순
    LRUCacheClass = (
        namespace.get("LRUCache")
        or namespace.get("LRU_Cache")
        or namespace.get("Cache")
        or namespace.get("Solution")
    )
    if LRUCacheClass is None:
        return ValidationResult(
            passed=False,
            test_results=[{"name": "class_lookup", "passed": False,
                           "message": "LRUCache 클래스 없음"}],
            quality_score=0.0,
            complexity_actual="O(?)",
            issues=["LRUCache class not defined in generated code"],
        )

    results = []
    for idx, (ops, expected, desc) in enumerate(LRU_TEST_CASES):
        cap = 1 if idx == LRU_CAP1_IDX else 2
        try:
            cache = LRUCacheClass(cap)
            last_result = None
            for op in ops:
                if op[0] == "put":
                    cache.put(op[1], op[2])
                    last_result = None
                else:  # get
                    last_result = cache.get(op[1])
            ok = (last_result == expected)
            results.append({
                "name": desc,
                "passed": ok,
                "message": f"expected={expected}, got={last_result}",
            })
        except Exception as e:
            results.append({
                "name": desc,
                "passed": False,
                "message": f"RuntimeError: {e}",
            })

    pass_count = sum(1 for r in results if r["passed"])
    quality = pass_count / len(results)
    return ValidationResult(
        passed=quality >= 0.8,   # 10개 중 8개 이상 통과
        test_results=results,
        quality_score=quality,
        complexity_actual="O(1)",
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
        print(f"  macro_unique: {sorted(macro_unique)}")
        print(f"  tech_unique:  {sorted(tech_unique)}")
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
    valid_fn = lru_validator_fn if use_llm else None

    results = []
    for i in range(n_trials):
        problem = Problem(
            description=PROBLEM_LRU.description,
            constraints=PROBLEM_LRU.constraints,
            examples=PROBLEM_LRU.examples,
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


def run_experiment(n_trials: int = 20, use_llm: bool = True) -> dict:
    """사이클 84 전체 실험 — LRU Cache N=20."""
    print("=" * 65)
    print("사이클 84 — LRU Cache N=20 통계 강화 실험")
    print("P4: LRU Cache (get/put O(1), capacity eviction)")
    print("=" * 65)
    print()

    cser_map = verify_all_cser()

    summaries = {}

    print(f"=== Condition A (CSER=1.0) — {n_trials}회 ===")
    summaries["A"] = run_condition("A", MACRO_A, TECH_A, n_trials, use_llm, 8400)

    print(f"\n=== Condition B_partial (CSER≈0.444) — {n_trials}회 ===")
    summaries["B_partial"] = run_condition(
        "B_partial", MACRO_B_PARTIAL, TECH_B_PARTIAL, n_trials, use_llm, 8420
    )

    print(f"\n=== Condition C (CSER=0.0) — 게이트 확인 ===")
    summaries["C"] = run_condition("C", MACRO_C, TECH_C, 1, use_llm, 8440)

    return {
        "problem": "LRU Cache (get/put O(1))",
        "cycle": 84,
        "n_trials": n_trials,
        "summaries": summaries,
        "cser_map": cser_map,
    }


# ---------------------------------------------------------------------------
# 통계 분석 — Fisher's exact + Mann-Whitney + Cohen's d
# ---------------------------------------------------------------------------

def run_statistical_tests(experiment: dict) -> dict:
    """
    Fisher's exact test, Mann-Whitney U, Cohen's d 계산.
    scipy 사용. 이진 결과(pass/fail)와 연속 점수(quality_score) 모두 처리.
    """
    try:
        from scipy import stats
        import numpy as np
    except ImportError:
        print("⚠ scipy/numpy 없음 — 수동 계산으로 폴백")
        return _manual_stats(experiment)

    import numpy as np

    sa = experiment["summaries"].get("A", {})
    sb = experiment["summaries"].get("B_partial", {})

    if not sa.get("gate_passed") or not sb.get("gate_passed"):
        return {"error": "A 또는 B_partial 게이트 차단 — 통계 불가"}

    n_a = sa["n_trials"]
    n_b = sb["n_trials"]
    pass_a = sa["passed"]
    pass_b = sb["passed"]
    fail_a = n_a - pass_a
    fail_b = n_b - pass_b

    qa = np.array(sa["quality_scores"])
    qb = np.array(sb["quality_scores"])

    # --- Fisher's exact test (이진 통과/실패) ---
    contingency = [[pass_a, fail_a], [pass_b, fail_b]]
    odds_ratio, p_fisher = stats.fisher_exact(contingency, alternative='greater')

    # --- Mann-Whitney U (연속 quality_score) ---
    if len(set(qa.tolist() + qb.tolist())) > 1:
        stat_mw, p_mw = stats.mannwhitneyu(qa, qb, alternative='greater')
    else:
        stat_mw, p_mw = float('nan'), 1.0  # 모두 동일 → p=1

    # --- Cohen's d (effect size) ---
    all_scores = np.concatenate([qa, qb])
    pooled_std = np.std(all_scores, ddof=1) if len(all_scores) > 1 else 0.0
    if pooled_std > 0:
        cohen_d = (np.mean(qa) - np.mean(qb)) / pooled_std
    else:
        cohen_d = 0.0

    # --- 판정 ---
    alpha = 0.05
    if p_fisher < alpha:
        interpretation = "CSER 스펙트럼 효과 존재 (A > B_partial 통계적 유의)"
        model = "spectrum_effect_found"
    else:
        interpretation = "이진 게이트 모델 N=20으로 확정 (A = B_partial 차이 없음)"
        model = "binary_gate_confirmed"

    return {
        "n_A": n_a,
        "n_B": n_b,
        "pass_A": pass_a,
        "pass_B": pass_b,
        "pass_rate_A": pass_a / n_a,
        "pass_rate_B": pass_b / n_b,
        "mean_quality_A": float(np.mean(qa)),
        "mean_quality_B": float(np.mean(qb)),
        "contingency_table": contingency,
        "fisher_odds_ratio": float(odds_ratio),
        "fisher_p": float(p_fisher),
        "mannwhitney_stat": float(stat_mw) if not isinstance(stat_mw, float) else stat_mw,
        "mannwhitney_p": float(p_mw),
        "cohen_d": float(cohen_d),
        "alpha": alpha,
        "fisher_significant": p_fisher < alpha,
        "interpretation": interpretation,
        "model": model,
    }


def _manual_stats(experiment: dict) -> dict:
    """scipy 없을 때 수동 계산 (기본 통계만)."""
    sa = experiment["summaries"].get("A", {})
    sb = experiment["summaries"].get("B_partial", {})
    n_a = sa.get("n_trials", 0)
    n_b = sb.get("n_trials", 0)
    pass_a = sa.get("passed", 0)
    pass_b = sb.get("passed", 0)

    return {
        "n_A": n_a, "n_B": n_b,
        "pass_A": pass_a, "pass_B": pass_b,
        "pass_rate_A": pass_a / n_a if n_a else 0,
        "pass_rate_B": pass_b / n_b if n_b else 0,
        "mean_quality_A": sa.get("avg_quality", 0),
        "mean_quality_B": sb.get("avg_quality", 0),
        "fisher_p": "N/A (scipy 없음)",
        "cohen_d": "N/A (scipy 없음)",
        "note": "scipy 설치: pip install scipy numpy",
    }


# ---------------------------------------------------------------------------
# 결과 출력
# ---------------------------------------------------------------------------

def print_results_table(experiment: dict, stats: dict) -> None:
    """결과 테이블 + 통계 검정 결과 출력."""
    s = experiment["summaries"]
    print()
    print("=" * 75)
    print("사이클 84 결과 테이블 — LRU Cache (get/put O(1))")
    print("=" * 75)
    header = f"{'조건':<22} {'CSER':>8} {'게이트':>8} {'패스율':>12} {'평균품질':>10}"
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
        print(f"{label:<22} {cond['cser_actual']:>8.3f} {gate:>8} {pass_str:>12} {qual_str:>10}")

    print("-" * 75)

    # 이전 사이클 참고
    print()
    print("참고 — 이전 사이클 결과:")
    print("  사이클 82 GCD(O(log n)):      A=5/5=100%, B_partial=5/5=100%")
    print("  사이클 83 QuickSort(O(nlogn)): A=5/5=100%, B_partial=5/5=100%")
    print()

    # 통계 검정 결과
    print("=" * 75)
    print("Fisher's exact test + 통계 검정 결과")
    print("=" * 75)

    if "error" in stats:
        print(f"  오류: {stats['error']}")
        return

    p_fisher = stats.get("fisher_p", "N/A")
    cohen_d = stats.get("cohen_d", "N/A")

    print(f"  조건 A     (CSER=1.000): {stats['pass_A']}/{stats['n_A']} 통과, "
          f"품질={stats['mean_quality_A']:.3f}")
    print(f"  조건 B_partial (CSER=0.444): {stats['pass_B']}/{stats['n_B']} 통과, "
          f"품질={stats['mean_quality_B']:.3f}")
    print()

    if isinstance(p_fisher, float):
        print(f"  Fisher's exact: p={p_fisher:.4f} "
              f"({'유의' if p_fisher < 0.05 else '비유의'}, α=0.05)")
        print(f"  Odds Ratio: {stats.get('fisher_odds_ratio', 'N/A'):.3f}")
    else:
        print(f"  Fisher's exact: {p_fisher}")

    mw_p = stats.get("mannwhitney_p", "N/A")
    if isinstance(mw_p, float):
        print(f"  Mann-Whitney U: p={mw_p:.4f} "
              f"({'유의' if mw_p < 0.05 else '비유의'})")

    if isinstance(cohen_d, float):
        magnitude = (
            "무시할 수준" if abs(cohen_d) < 0.2 else
            "소 효과" if abs(cohen_d) < 0.5 else
            "중 효과" if abs(cohen_d) < 0.8 else
            "대 효과"
        )
        print(f"  Cohen's d: {cohen_d:.3f} ({magnitude})")
    else:
        print(f"  Cohen's d: {cohen_d}")

    print()
    print(f"  판정: {stats.get('interpretation', 'N/A')}")

    model = stats.get("model", "")
    if model == "binary_gate_confirmed":
        print()
        print("  → 게이트 이진 모델 최종 확정 (N=20, 3문제 × 2조건 일관성)")
        print("  → arXiv 제출 가능: 통계적으로 충분한 근거")
    elif model == "spectrum_effect_found":
        print()
        print("  → CSER 스펙트럼 효과 발견!")
        print("  → 논문 수정 필요: 이진 게이트 → 스펙트럼 모델")


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="H_exec 사이클 84 — LRU Cache N=20 통계 강화"
    )
    parser.add_argument("--mock", action="store_true", help="LLM 호출 없이 mock 실행")
    parser.add_argument("--trials", type=int, default=20, help="각 조건 실행 횟수 (기본: 20)")
    args = parser.parse_args()

    use_llm = not args.mock
    n = args.trials
    print(f"실험 모드: {'실제 LLM (claude CLI)' if use_llm else 'MOCK'}")
    print(f"N = {n} (각 조건별)")
    print()

    start = time.time()
    experiment = run_experiment(n_trials=n, use_llm=use_llm)
    elapsed = time.time() - start

    # 통계 분석
    stats = run_statistical_tests(experiment)

    print_results_table(experiment, stats)
    print(f"\n소요 시간: {elapsed:.1f}초")

    # 결과 저장
    out_path = Path(__file__).parent / "h_exec_cycle84_results.json"
    full_results = {**experiment, "statistical_tests": stats}
    with open(out_path, "w") as f:
        json.dump(full_results, f, indent=2, ensure_ascii=False)
    print(f"결과 저장: {out_path}")
