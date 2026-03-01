#!/usr/bin/env python3
"""
3-Way Comparison: Solo vs Pipeline vs Emergent

공정한 비교를 위한 설계 원칙:
- Pipeline = 업계 표준 방식 (planner → coder → reviewer → fix)
- Emergent = 우리 창발 방식 (적대적 탐색 + 다양성 강제 + 축적 학습)
- Solo = 단일 호출 baseline

Pipeline은 CrewAI/AutoGen 스타일의 보편적 패턴을 따름:
1. Planner: 문제 분석 + 전략 수립
2. Coder: 구현
3. Reviewer: 코드 리뷰 + 버그 탐색
4. Coder: 리뷰 반영 수정 (1회 iteration)

총 API 호출 수를 동일하게 맞춤 (공정성):
- Solo: 1회 (best-of-4로 4회)
- Pipeline: 4회 (planner + coder + reviewer + fix)
- Emergent: 4회 (agent_a + agent_b_attack + agent_a_fix + synthesis)
"""
import json, os, urllib.request, time, sys, traceback
sys.stdout.reconfigure(line_buffering=True)

API_KEY = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call_gpt52(prompt, temperature=0.7):
    body = json.dumps({"model":"gpt-5.2","input":prompt,"temperature":temperature}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=body,
        headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        r = json.loads(resp.read())
    for item in r.get("output",[]):
        if isinstance(item,dict) and item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text":
                    return c["text"].strip()
    return ""

def extract_code(text):
    code = text.strip()
    for pfx in ["```python","```"]:
        if code.startswith(pfx): code=code[len(pfx):]
    if code.endswith("```"): code=code[:-3]
    return code.strip()

# ── 테스트 문제들 (GPT-5.2 solo 70~90% 구간) ──

PROBLEMS = {
    "regex_backref": {
        "prompt": """Implement `match(pattern: str, text: str) -> bool`
Support standard regex: . * + ? | () for grouping
PLUS backreferences: \\1, \\2 etc. referring to captured groups.
Example: match(r'(a+)b\\1', 'aabaa') -> True (\\1 = 'aa')
Example: match(r'(a+)b\\1', 'aaba') -> False
No re module allowed.""",
        "test_fn": "_test_regex_backref",
    },
    "balanced_brackets_gen": {
        "prompt": """Implement `generate_balanced(n: int) -> list[str]`
Generate ALL valid combinations of n pairs of balanced parentheses, 
brackets, and braces: (), [], {}
Rules: each type must be independently balanced AND 
no interleaving violations (e.g., '([)]' is INVALID, '([])' is VALID).
Return sorted list. For n=1: ['()','[]','{}']
For n=2: all valid 2-pair combos sorted.""",
        "test_fn": "_test_balanced",
    },
    "json_patch": {
        "prompt": """Implement `apply_patch(doc: dict, patch: list[dict]) -> dict`
Implement RFC 6902 JSON Patch. Each patch op is a dict with:
- {"op":"add","path":"/a/b","value":1}
- {"op":"remove","path":"/a/b"}  
- {"op":"replace","path":"/a/b","value":2}
- {"op":"move","from":"/a/b","path":"/c/d"}
- {"op":"copy","from":"/a/b","path":"/c/d"}
- {"op":"test","path":"/a/b","value":1} (raises ValueError if mismatch)
Path uses JSON Pointer (RFC 6901): /foo/0/bar (0=array index).
Raise ValueError for invalid operations.
Return the modified document (deep copy, don't mutate input).""",
        "test_fn": "_test_json_patch",
    },
}

def _test_regex_backref(code):
    ns = {}
    try: exec(code, ns)
    except: return 0
    fn = ns.get("match")
    if not fn: return 0
    p, t = 0, 6
    try:
        if fn(r'(a+)b\1', 'aabaa') == True: p+=1
        if fn(r'(a+)b\1', 'aaba') == False: p+=1
        if fn(r'(.).\1', 'aba') == True: p+=1
        if fn(r'(.).\1', 'abc') == False: p+=1
        if fn(r'a*b', 'aaab') == True: p+=1
        if fn(r'((a)b)\1', 'abab') == True: p+=1
    except: pass
    return p/t

def _test_balanced(code):
    ns = {}
    try: exec(code, ns)
    except: return 0
    fn = ns.get("generate_balanced")
    if not fn: return 0
    p, t = 0, 4
    try:
        r1 = fn(1)
        if sorted(r1) == ['()','[]','{}']: p+=1
        r2 = fn(2)
        # Must include valid combos like '()()', '([])', etc.
        if isinstance(r2, list) and len(r2) > 3: p+=1
        # Check no interleaving violations
        def is_valid(s):
            stack=[]
            pairs={'(':')','[':']','{':'}'}
            for c in s:
                if c in pairs: stack.append(pairs[c])
                elif stack and stack[-1]==c: stack.pop()
                else: return False
            return len(stack)==0
        if all(is_valid(x) for x in r2): p+=1
        # n=0
        r0 = fn(0)
        if r0 == [''] or r0 == []: p+=1
    except: pass
    return p/t

def _test_json_patch(code):
    ns = {}
    try: exec(code, ns)
    except: return 0
    fn = ns.get("apply_patch")
    if not fn: return 0
    p, t = 0, 6
    try:
        import copy
        # add
        r = fn({"a":1}, [{"op":"add","path":"/b","value":2}])
        if r.get("b")==2 and r.get("a")==1: p+=1
        # remove
        r2 = fn({"a":1,"b":2}, [{"op":"remove","path":"/b"}])
        if "b" not in r2 and r2.get("a")==1: p+=1
        # replace
        r3 = fn({"a":1}, [{"op":"replace","path":"/a","value":99}])
        if r3.get("a")==99: p+=1
        # nested path
        r4 = fn({"a":{"b":1}}, [{"op":"replace","path":"/a/b","value":2}])
        if r4["a"]["b"]==2: p+=1
        # test pass
        r5 = fn({"a":1}, [{"op":"test","path":"/a","value":1}])
        if r5 == {"a":1}: p+=1
        # test fail
        try:
            fn({"a":1}, [{"op":"test","path":"/a","value":2}])
        except ValueError:
            p+=1
    except: pass
    return p/t

TEST_FNS = {
    "_test_regex_backref": _test_regex_backref,
    "_test_balanced": _test_balanced,
    "_test_json_patch": _test_json_patch,
}

# ═══════════════════════════════════════════════════════════
# METHOD 1: SOLO (best-of-4)
# ═══════════════════════════════════════════════════════════

def method_solo(problem_prompt):
    """4회 독립 호출, 최고 점수 채택."""
    codes = []
    for i in range(4):
        raw = call_gpt52(problem_prompt + "\n\nReturn ONLY Python code, no markdown fences, no explanation.", temperature=0.8)
        codes.append(extract_code(raw))
        time.sleep(0.5)
    return codes  # return all 4 for scoring

# ═══════════════════════════════════════════════════════════
# METHOD 2: PIPELINE (CrewAI/AutoGen 표준 패턴)
# ═══════════════════════════════════════════════════════════

def method_pipeline(problem_prompt):
    """
    업계 표준 4단계 파이프라인:
    1. Planner: 문제 분석 + 접근법 결정
    2. Coder: 구현
    3. Reviewer: 코드 리뷰 + 버그/엣지케이스 지적
    4. Coder: 리뷰 반영 수정
    """
    # Step 1: Planner
    plan = call_gpt52(f"""You are a senior software architect. Analyze this problem and create a detailed implementation plan.

Problem:
{problem_prompt}

Provide:
1. Key algorithm/approach to use
2. Edge cases to handle
3. Data structures needed
4. Step-by-step implementation outline

Be specific and thorough.""")
    time.sleep(0.5)

    # Step 2: Coder (uses plan)
    code_v1_raw = call_gpt52(f"""You are an expert Python developer. Implement the solution based on this plan.

Problem:
{problem_prompt}

Implementation Plan:
{plan}

Return ONLY Python code, no markdown fences, no explanation.""")
    code_v1 = extract_code(code_v1_raw)
    time.sleep(0.5)

    # Step 3: Reviewer
    review = call_gpt52(f"""You are a code reviewer specializing in finding bugs, edge cases, and correctness issues.

Problem:
{problem_prompt}

Code to review:
```python
{code_v1}
```

Find ALL bugs, missing edge cases, and correctness issues. Be thorough and specific.
For each issue, explain what's wrong and how to fix it.""")
    time.sleep(0.5)

    # Step 4: Coder fixes based on review
    code_v2_raw = call_gpt52(f"""You are an expert Python developer. Fix the code based on the review feedback.

Original problem:
{problem_prompt}

Current code:
```python
{code_v1}
```

Review feedback:
{review}

Fix ALL identified issues. Return ONLY the complete corrected Python code, no markdown fences, no explanation.""")
    code_v2 = extract_code(code_v2_raw)

    return [code_v2]  # final output

# ═══════════════════════════════════════════════════════════
# METHOD 3: EMERGENT (적대적 탐색 + 관점 다양성)
# ═══════════════════════════════════════════════════════════

def method_emergent(problem_prompt):
    """
    창발적 증폭 엔진:
    1. Agent A (알고리즘 전문가): 첫 구현
    2. Agent B (적대적 테스터): 반례 공격 + 대안 접근법 제시
    3. Agent A: 공격 반영 수정 + B의 대안 통합
    4. Synthesizer: 두 관점 최적 통합
    """
    # Step 1: Agent A — 알고리즘 관점에서 구현
    code_a_raw = call_gpt52(f"""You are an algorithm specialist who thinks in terms of formal language theory, automata, and recursive descent.

Problem:
{problem_prompt}

Implement a solution using your algorithmic expertise. Think about:
- What formal model best captures this problem?
- What are the invariants that must hold?
- How to handle recursion/backtracking efficiently?

Return ONLY Python code, no markdown fences, no explanation.""", temperature=0.7)
    code_a = extract_code(code_a_raw)
    time.sleep(0.5)

    # Step 2: Agent B — 적대적 공격 + 완전히 다른 접근법
    attack = call_gpt52(f"""You are an adversarial tester AND an alternative solver. You have TWO jobs:

JOB 1 - ATTACK: Find inputs that will BREAK this code. Think of the nastiest edge cases.
```python
{code_a}
```

JOB 2 - ALTERNATIVE: Propose a COMPLETELY DIFFERENT approach to solving the problem.
If the code above uses recursion, suggest iteration. If it uses NFA, suggest backtracking with memoization. etc.

Problem:
{problem_prompt}

Provide:
1. List of breaking inputs with expected vs actual behavior
2. Your alternative implementation (complete Python code)
3. What each approach handles better

Be ruthless in finding bugs. Be creative in your alternative.""", temperature=0.9)
    time.sleep(0.5)

    # Step 3: Agent A — 공격 흡수 + 대안 통합
    code_a2_raw = call_gpt52(f"""You are an algorithm specialist. Your first implementation was attacked and an alternative was proposed.

Original problem:
{problem_prompt}

Your first implementation:
```python
{code_a}
```

Attack results and alternative approach:
{attack}

Now create an IMPROVED implementation that:
1. Fixes ALL identified breaking inputs
2. Incorporates the BEST ideas from both approaches
3. Handles edge cases neither approach alone would catch

Return ONLY Python code, no markdown fences, no explanation.""", temperature=0.5)
    code_a2 = extract_code(code_a2_raw)
    time.sleep(0.5)

    # Step 4: Synthesizer — 최종 통합 (두 접근법의 장점 결합)
    code_final_raw = call_gpt52(f"""You are a synthesis expert. You have seen two different approaches to this problem and their strengths/weaknesses.

Problem:
{problem_prompt}

Approach 1 (algorithm-first, refined):
```python
{code_a2}
```

Attack analysis that informed the refinement:
{attack[:2000]}

Create the FINAL, most robust implementation by:
- Using the most reliable core algorithm
- Ensuring ALL edge cases from the attack are handled
- Keeping the code clean and correct

Return ONLY Python code, no markdown fences, no explanation.""", temperature=0.3)
    code_final = extract_code(code_final_raw)

    return [code_final]

# ═══════════════════════════════════════════════════════════
# MAIN EXPERIMENT
# ═══════════════════════════════════════════════════════════

N_TRIALS = 4
results = {}

for prob_id, prob_data in PROBLEMS.items():
    print(f"\n{'='*60}")
    print(f"PROBLEM: {prob_id}")
    print(f"{'='*60}")
    
    test_fn = TEST_FNS[prob_data["test_fn"]]
    prompt = prob_data["prompt"]
    results[prob_id] = {}
    
    for method_name, method_fn in [("solo", method_solo), ("pipeline", method_pipeline), ("emergent", method_emergent)]:
        print(f"\n  --- {method_name} ---")
        scores = []
        for trial in range(N_TRIALS):
            try:
                codes = method_fn(prompt)
                # For solo (best-of-4), take best score
                if method_name == "solo":
                    trial_scores = [test_fn(c) for c in codes]
                    score = max(trial_scores) if trial_scores else 0
                else:
                    score = test_fn(codes[0]) if codes else 0
            except Exception as e:
                print(f"    t{trial+1}: ERR {e}")
                score = 0
            scores.append(score)
            s = "✅" if score >= 0.7 else "⚠️" if score > 0 else "❌"
            print(f"    t{trial+1}: {score:.2f} {s}")
            time.sleep(1)
        
        avg = sum(scores)/len(scores)
        pass_rate = sum(1 for s in scores if s >= 0.7) / len(scores)
        results[prob_id][method_name] = {"avg": avg, "pass_rate": pass_rate, "raw": scores}
        print(f"    → avg={avg:.3f} pass={pass_rate:.0%}")

# ── FINAL SUMMARY ──
print(f"\n{'='*60}")
print("FINAL COMPARISON")
print(f"{'='*60}")
print(f"{'Problem':<25} {'Solo':>8} {'Pipeline':>10} {'Emergent':>10} {'Winner':>10}")
print("-"*65)
for pid in results:
    s = results[pid]["solo"]["avg"]
    p = results[pid]["pipeline"]["avg"]
    e = results[pid]["emergent"]["avg"]
    winner = "EMERGENT" if e > max(s,p) else ("PIPELINE" if p > s else "SOLO")
    print(f"{pid:<25} {s:>8.3f} {p:>10.3f} {e:>10.3f} {winner:>10}")

# Overall
all_s = [s for pid in results for s in results[pid]["solo"]["raw"]]
all_p = [s for pid in results for s in results[pid]["pipeline"]["raw"]]
all_e = [s for pid in results for s in results[pid]["emergent"]["raw"]]
print(f"\n{'OVERALL':<25} {sum(all_s)/len(all_s):>8.3f} {sum(all_p)/len(all_p):>10.3f} {sum(all_e)/len(all_e):>10.3f}")

with open("/Users/rocky/emergent/experiments/three_way_results.json","w") as f:
    json.dump(results, f, indent=2)
print("\nSaved.")
