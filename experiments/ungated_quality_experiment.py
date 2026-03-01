#!/usr/bin/env python3
"""
사이클92 실험 R3: CSER 게이트 비활성화 후 품질 측정

목적: CSER 게이트가 동어반복이 아님을 증명
- 게이트를 제거하고 모든 CSER 수준에서 코드를 생성
- CSER↔quality 상관관계를 직접 측정
- quality 하락이 관찰되면 → 게이트의 경험적 정당성 확보

실험 조건:
- Condition A: 이종 페르소나 (CSER ≈ 0.84~1.00)
- Condition B_partial: 부분 동종 (CSER ≈ 0.44)  
- Condition C: 완전 동종 (CSER ≈ 0.00~0.08)

과제: GCD, QuickSort, LRU Cache (기존) + FizzBuzz variant (간단 대조)

핵심: 게이트 없이 Condition C에서도 코드 생성 → quality 측정
"""

import json
import os
import sys
import random
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import urllib.request

# ── 설정 ──
SEED = 92
random.seed(SEED)
N_TRIALS = 10  # per condition per problem
API_KEY = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

# ── 페르소나 정의 ──
PERSONA_MACRO = """You are a macro-level software architect. You think about:
- System design patterns, scalability, maintainability
- Edge cases from a user/product perspective  
- Code organization and API design
You approach problems top-down, from requirements to implementation."""

PERSONA_TECH = """You are a low-level technical implementer. You think about:
- Algorithm efficiency, time/space complexity
- Memory management, bit manipulation, data structure internals
- Performance optimization and correctness proofs
You approach problems bottom-up, from primitives to composition."""

PERSONA_SAME = """You are a confident software architect (확신의 건축가). You think about:
- System design patterns, scalability, maintainability
- Edge cases from a user/product perspective
- Code organization and API design
You approach problems top-down, from requirements to implementation."""

# ── 과제 정의 ──
PROBLEMS = {
    "gcd": {
        "prompt": "Implement a function `gcd(a: int, b: int) -> int` that returns the greatest common divisor of two non-negative integers using Euclid's algorithm.",
        "test_cases": [
            {"input": (12, 8), "expected": 4},
            {"input": (100, 75), "expected": 25},
            {"input": (17, 13), "expected": 1},
            {"input": (0, 5), "expected": 5},
            {"input": (48, 18), "expected": 6},
        ]
    },
    "quicksort": {
        "prompt": "Implement a function `quicksort(arr: list[int]) -> list[int]` that sorts a list of integers using the quicksort algorithm. Return a new sorted list.",
        "test_cases": [
            {"input": ([3,1,4,1,5,9,2,6],), "expected": [1,1,2,3,4,5,6,9]},
            {"input": ([],), "expected": []},
            {"input": ([1],), "expected": [1]},
            {"input": ([5,4,3,2,1],), "expected": [1,2,3,4,5]},
            {"input": ([1,1,1],), "expected": [1,1,1]},
        ]
    },
    "lru_cache": {
        "prompt": """Implement an LRUCache class with:
- `__init__(self, capacity: int)` - Initialize with positive capacity
- `get(self, key: int) -> int` - Return value if key exists, else -1. Marks as recently used.
- `put(self, key: int, value: int) -> None` - Insert/update key-value. If over capacity, evict LRU.
Both get and put must be O(1) time complexity.""",
        "test_fn": "test_lru_cache"  # special test
    },
    "matrix_multiply": {
        "prompt": "Implement `matrix_multiply(A: list[list[int]], B: list[list[int]]) -> list[list[int]]` that multiplies two matrices. Raise ValueError if dimensions don't match.",
        "test_cases": [
            {"input": ([[1,2],[3,4]], [[5,6],[7,8]]), "expected": [[19,22],[43,50]]},
            {"input": ([[1,0],[0,1]], [[5,6],[7,8]]), "expected": [[5,6],[7,8]]},
            {"input": ([[2]],[[3]]), "expected": [[6]]},
        ]
    }
}

def test_lru_cache(code_str: str) -> tuple[int, int]:
    """Returns (pass_count, total_tests)."""
    ns = {}
    try:
        exec(code_str, ns)
        LRUCache = ns.get("LRUCache")
        if not LRUCache:
            return 0, 5
    except:
        return 0, 5
    
    passed = 0
    total = 5
    try:
        # Test 1: basic put/get
        c = LRUCache(2)
        c.put(1, 1); c.put(2, 2)
        if c.get(1) == 1: passed += 1
        # Test 2: eviction
        c.put(3, 3)  # evicts 2
        if c.get(2) == -1: passed += 1
        # Test 3: update doesn't evict
        c = LRUCache(2)
        c.put(1, 1); c.put(2, 2); c.get(1); c.put(3, 3)  # evicts 2
        if c.get(2) == -1 and c.get(1) == 1: passed += 1
        # Test 4: capacity 1
        c = LRUCache(1)
        c.put(1, 1); c.put(2, 2)
        if c.get(1) == -1 and c.get(2) == 2: passed += 1
        # Test 5: overwrite
        c = LRUCache(2)
        c.put(1, 1); c.put(1, 10)
        if c.get(1) == 10: passed += 1
    except:
        pass
    return passed, total

def test_code(problem_key: str, code_str: str) -> float:
    """Test generated code, return quality score 0.0~1.0."""
    prob = PROBLEMS[problem_key]
    
    if problem_key == "lru_cache":
        passed, total = test_lru_cache(code_str)
        return passed / total
    
    ns = {}
    try:
        exec(code_str, ns)
    except Exception as e:
        return 0.0
    
    fn_name = problem_key
    if fn_name == "matrix_multiply":
        fn = ns.get("matrix_multiply")
    elif fn_name == "quicksort":
        fn = ns.get("quicksort")
    elif fn_name == "gcd":
        fn = ns.get("gcd")
    else:
        fn = None
    
    if fn is None:
        return 0.0
    
    passed = 0
    total = len(prob["test_cases"])
    for tc in prob["test_cases"]:
        try:
            result = fn(*tc["input"])
            if result == tc["expected"]:
                passed += 1
        except:
            pass
    return passed / total

def compute_local_cser(persona_a: str, persona_b: str) -> float:
    """Compute a simplified local CSER based on persona word overlap."""
    words_a = set(persona_a.lower().split())
    words_b = set(persona_b.lower().split())
    overlap = len(words_a & words_b)
    total = len(words_a | words_b)
    # CSER = 1 - overlap_ratio (high overlap = low cross-source)
    if total == 0:
        return 0.0
    overlap_ratio = overlap / total
    return 1.0 - overlap_ratio

def generate_code(problem_key: str, persona_a: str, persona_b: str, trial: int) -> tuple[str, float]:
    """Generate code using two-persona collaboration, return (code, local_cser)."""
    prob = PROBLEMS[problem_key]
    prompt_text = prob["prompt"] if isinstance(prob.get("prompt"), str) else prob.get("prompt", "")
    
    local_cser = compute_local_cser(persona_a, persona_b)
    
    system_prompt = f"""You are collaborating with another AI to solve a coding problem.

Agent A's perspective:
{persona_a}

Agent B's perspective:  
{persona_b}

Combine BOTH perspectives to produce the best solution.
Return ONLY the Python code, no explanations, no markdown fences."""

    body = json.dumps({
        "model": "gpt-5.2",
        "input": [
            {"role": "user", "content": system_prompt + f"\n\nProblem:\n{prompt_text}\n\nProvide ONLY the Python code, no explanations, no markdown fences."}
        ],
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        
        output_text = ""
        for item in result.get("output", []):
            if isinstance(item, dict) and item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        output_text = c["text"]
        
        # Strip markdown fences if present
        code = output_text.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()
        
        return code, local_cser
    except Exception as e:
        print(f"  API error: {e}")
        return "", local_cser

def run_experiment():
    """Run the full ungated quality experiment."""
    conditions = {
        "A_heterogeneous": (PERSONA_MACRO, PERSONA_TECH),
        "B_partial": (PERSONA_MACRO, PERSONA_SAME),
        "C_homogeneous": (PERSONA_SAME, PERSONA_SAME),
    }
    
    problems = ["gcd", "quicksort", "lru_cache", "matrix_multiply"]
    results = {}
    
    for cond_name, (pa, pb) in conditions.items():
        print(f"\n{'='*60}")
        print(f"Condition: {cond_name}")
        print(f"{'='*60}")
        results[cond_name] = {}
        
        for prob in problems:
            print(f"\n  Problem: {prob}")
            qualities = []
            csers = []
            
            for trial in range(N_TRIALS):
                code, local_cser = generate_code(prob, pa, pb, trial)
                quality = test_code(prob, code) if code else 0.0
                qualities.append(quality)
                csers.append(local_cser)
                status = "✅" if quality >= 0.7 else "⚠️" if quality > 0 else "❌"
                print(f"    Trial {trial+1:2d}: quality={quality:.2f} CSER={local_cser:.3f} {status}")
            
            avg_q = sum(qualities) / len(qualities)
            avg_cser = sum(csers) / len(csers)
            pass_rate = sum(1 for q in qualities if q >= 0.7) / len(qualities)
            
            results[cond_name][prob] = {
                "qualities": qualities,
                "avg_quality": avg_q,
                "pass_rate": pass_rate,
                "local_cser": avg_cser,
                "n": N_TRIALS,
            }
            print(f"    → Avg quality: {avg_q:.3f}, Pass rate: {pass_rate:.1%}, CSER: {avg_cser:.3f}")
    
    # ── Summary ──
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for cond_name in conditions:
        cond_data = results[cond_name]
        all_q = [q for p in cond_data.values() for q in p["qualities"]]
        overall_avg = sum(all_q) / len(all_q) if all_q else 0
        overall_pass = sum(1 for q in all_q if q >= 0.7) / len(all_q) if all_q else 0
        cser = list(cond_data.values())[0]["local_cser"]
        print(f"  {cond_name}: avg_quality={overall_avg:.3f}, pass_rate={overall_pass:.1%}, CSER={cser:.3f}")
    
    # ── Correlation ──
    all_csers = []
    all_quals = []
    for cond_data in results.values():
        for prob_data in cond_data.values():
            for i, q in enumerate(prob_data["qualities"]):
                all_csers.append(prob_data["local_cser"])
                all_quals.append(q)
    
    n = len(all_csers)
    mean_c = sum(all_csers) / n
    mean_q = sum(all_quals) / n
    cov = sum((c - mean_c) * (q - mean_q) for c, q in zip(all_csers, all_quals)) / n
    std_c = (sum((c - mean_c)**2 for c in all_csers) / n) ** 0.5
    std_q = (sum((q - mean_q)**2 for q in all_quals) / n) ** 0.5
    pearson_r = cov / (std_c * std_q) if std_c > 0 and std_q > 0 else 0
    
    print(f"\n  Pearson r(CSER, quality) = {pearson_r:.4f} (N={n})")
    
    results["correlation"] = {
        "pearson_r": pearson_r,
        "n": n,
        "mean_cser": mean_c,
        "mean_quality": mean_q,
    }
    
    # Save
    out_path = Path(__file__).parent / "ungated_quality_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")

if __name__ == "__main__":
    run_experiment()
