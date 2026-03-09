#!/usr/bin/env python3
"""
3-Way Comparison v2: regex_backref 카테고리 확장 실행 (N=10)
사이클 96: openclaw-bot 요청

기존 three_way_comparison.py 기반, regex_backref에 집중하여
통계적으로 유의한 n=10 trials 실행.

결과: experiments/three_way_comparison_results_v2.json
"""
import json, os, urllib.request, time, sys, traceback
sys.stdout.reconfigure(line_buffering=True)

API_KEY = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()
if not API_KEY:
    print("ERROR: OPENAI_API_KEY not found in ~/.zshrc")
    sys.exit(1)

N_TRIALS = 10
DRY_RUN = "--dry-run" in sys.argv
RESULTS_FILE = "/Users/rocky/emergent/experiments/three_way_comparison_results_v2.json"


def call_gpt52(prompt, temperature=0.7):
    if DRY_RUN:
        # 시뮬레이션: 간단한 regex match 구현 반환
        return """def match(pattern, text):
    import re as _re
    try:
        return bool(_re.fullmatch(pattern, text))
    except:
        return False"""

    body = json.dumps({"model": "gpt-5.2", "input": prompt, "temperature": temperature}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        r = json.loads(resp.read())
    for item in r.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c["text"].strip()
    return ""


def extract_code(text):
    code = text.strip()
    for pfx in ["```python", "```"]:
        if code.startswith(pfx):
            code = code[len(pfx):]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


# ── regex_backref 테스트 ──

PROBLEM_PROMPT = """Implement `match(pattern: str, text: str) -> bool`
Support standard regex: . * + ? | () for grouping
PLUS backreferences: \\1, \\2 etc. referring to captured groups.
Example: match(r'(a+)b\\1', 'aabaa') -> True (\\1 = 'aa')
Example: match(r'(a+)b\\1', 'aaba') -> False
No re module allowed."""


def test_regex_backref(code):
    ns = {}
    try:
        exec(code, ns)
    except Exception:
        return 0
    fn = ns.get("match")
    if not fn:
        return 0
    p, t = 0, 6
    try:
        if fn(r'(a+)b\1', 'aabaa') is True: p += 1
        if fn(r'(a+)b\1', 'aaba') is False: p += 1
        if fn(r'(.).\1', 'aba') is True: p += 1
        if fn(r'(.).\1', 'abc') is False: p += 1
        if fn(r'a*b', 'aaab') is True: p += 1
        if fn(r'((a)b)\1', 'abab') is True: p += 1
    except Exception:
        pass
    return p / t


# ═══ METHOD 1: SOLO (best-of-4) ═══

def method_solo():
    codes = []
    for i in range(4):
        raw = call_gpt52(PROBLEM_PROMPT + "\n\nReturn ONLY Python code, no markdown fences, no explanation.", temperature=0.8)
        codes.append(extract_code(raw))
        time.sleep(0.5 if not DRY_RUN else 0)
    return codes


# ═══ METHOD 2: PIPELINE (CrewAI/AutoGen 표준) ═══

def method_pipeline():
    plan = call_gpt52(f"""You are a senior software architect. Analyze this problem and create a detailed implementation plan.

Problem:
{PROBLEM_PROMPT}

Provide:
1. Key algorithm/approach to use
2. Edge cases to handle
3. Data structures needed
4. Step-by-step implementation outline

Be specific and thorough.""")
    time.sleep(0.5 if not DRY_RUN else 0)

    code_v1_raw = call_gpt52(f"""You are an expert Python developer. Implement the solution based on this plan.

Problem:
{PROBLEM_PROMPT}

Implementation Plan:
{plan}

Return ONLY Python code, no markdown fences, no explanation.""")
    code_v1 = extract_code(code_v1_raw)
    time.sleep(0.5 if not DRY_RUN else 0)

    review = call_gpt52(f"""You are a code reviewer specializing in finding bugs, edge cases, and correctness issues.

Problem:
{PROBLEM_PROMPT}

Code to review:
```python
{code_v1}
```

Find ALL bugs, missing edge cases, and correctness issues. Be thorough and specific.""")
    time.sleep(0.5 if not DRY_RUN else 0)

    code_v2_raw = call_gpt52(f"""You are an expert Python developer. Fix the code based on the review feedback.

Original problem:
{PROBLEM_PROMPT}

Current code:
```python
{code_v1}
```

Review feedback:
{review}

Fix ALL identified issues. Return ONLY the complete corrected Python code, no markdown fences, no explanation.""")
    code_v2 = extract_code(code_v2_raw)
    return [code_v2]


# ═══ METHOD 3: EMERGENT (적대적 탐색 + 관점 다양성) ═══

def method_emergent():
    code_a_raw = call_gpt52(f"""You are an algorithm specialist who thinks in terms of formal language theory, automata, and recursive descent.

Problem:
{PROBLEM_PROMPT}

Implement a solution using your algorithmic expertise. Think about:
- What formal model best captures this problem?
- What are the invariants that must hold?
- How to handle recursion/backtracking efficiently?

Return ONLY Python code, no markdown fences, no explanation.""", temperature=0.7)
    code_a = extract_code(code_a_raw)
    time.sleep(0.5 if not DRY_RUN else 0)

    attack = call_gpt52(f"""You are an adversarial tester AND an alternative solver. You have TWO jobs:

JOB 1 - ATTACK: Find inputs that will BREAK this code. Think of the nastiest edge cases.
```python
{code_a}
```

JOB 2 - ALTERNATIVE: Propose a COMPLETELY DIFFERENT approach to solving the problem.

Problem:
{PROBLEM_PROMPT}

Provide:
1. List of breaking inputs with expected vs actual behavior
2. Your alternative implementation (complete Python code)
3. What each approach handles better

Be ruthless in finding bugs. Be creative in your alternative.""", temperature=0.9)
    time.sleep(0.5 if not DRY_RUN else 0)

    code_a2_raw = call_gpt52(f"""You are an algorithm specialist. Your first implementation was attacked and an alternative was proposed.

Original problem:
{PROBLEM_PROMPT}

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
    time.sleep(0.5 if not DRY_RUN else 0)

    code_final_raw = call_gpt52(f"""You are a synthesis expert. Create the FINAL, most robust implementation.

Problem:
{PROBLEM_PROMPT}

Refined approach:
```python
{code_a2}
```

Attack analysis:
{attack[:2000]}

Return ONLY Python code, no markdown fences, no explanation.""", temperature=0.3)
    code_final = extract_code(code_final_raw)
    return [code_final]


# ═══ MAIN ═══

def main():
    mode = "[DRY-RUN] " if DRY_RUN else ""
    print(f"═══ {mode}3-Way Comparison v2: regex_backref × {N_TRIALS} trials ═══")
    print(f"  Methods: solo (best-of-4), pipeline (4-step), emergent (adversarial)")
    print(f"  API calls per trial: solo=4, pipeline=4, emergent=4")
    print(f"  Total API calls: {N_TRIALS * 3 * 4} (estimated)")
    print()

    details = []
    solo_scores = []
    pipeline_scores = []
    emergent_scores = []

    for trial in range(1, N_TRIALS + 1):
        print(f"── Trial {trial}/{N_TRIALS} ──")
        trial_result = {"trial": trial}

        for method_name, method_fn, score_list in [
            ("solo", method_solo, solo_scores),
            ("pipeline", method_pipeline, pipeline_scores),
            ("emergent", method_emergent, emergent_scores),
        ]:
            try:
                codes = method_fn()
                if method_name == "solo":
                    trial_scores = [test_regex_backref(c) for c in codes]
                    score = max(trial_scores) if trial_scores else 0
                else:
                    score = test_regex_backref(codes[0]) if codes else 0
            except Exception as e:
                print(f"  {method_name}: ERR {e}")
                traceback.print_exc()
                score = 0

            score_list.append(score)
            trial_result[method_name] = round(score, 4)
            icon = "✅" if score >= 0.7 else "⚠️" if score > 0 else "❌"
            print(f"  {method_name}: {score:.2f} {icon}")
            time.sleep(1 if not DRY_RUN else 0)

        details.append(trial_result)
        print()

    # ── 집계 ──
    solo_avg = round(sum(solo_scores) / len(solo_scores), 4) if solo_scores else 0
    pipeline_avg = round(sum(pipeline_scores) / len(pipeline_scores), 4) if pipeline_scores else 0
    emergent_avg = round(sum(emergent_scores) / len(emergent_scores), 4) if emergent_scores else 0

    winner = "emergent" if emergent_avg > max(solo_avg, pipeline_avg) else (
        "pipeline" if pipeline_avg > solo_avg else "solo"
    )

    output = {
        "experiment": "three_way_comparison_v2",
        "problem": "regex_backref",
        "n_problems": N_TRIALS,
        "solo_avg": solo_avg,
        "pipeline_avg": pipeline_avg,
        "emergent_avg": emergent_avg,
        "winner": winner,
        "solo_pass_rate": round(sum(1 for s in solo_scores if s >= 0.7) / len(solo_scores), 4),
        "pipeline_pass_rate": round(sum(1 for s in pipeline_scores if s >= 0.7) / len(pipeline_scores), 4),
        "emergent_pass_rate": round(sum(1 for s in emergent_scores if s >= 0.7) / len(emergent_scores), 4),
        "details": details,
        "dry_run": DRY_RUN,
        "source": "cokac-bot (cycle 96)",
    }

    print(f"═══ RESULTS ═══")
    print(f"  Solo avg:     {solo_avg:.4f}")
    print(f"  Pipeline avg: {pipeline_avg:.4f}")
    print(f"  Emergent avg: {emergent_avg:.4f}")
    print(f"  Winner:       {winner}")

    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {RESULTS_FILE}")

    return output


if __name__ == "__main__":
    main()
