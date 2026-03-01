#!/usr/bin/env python3
"""
Round 3: Logic Reasoning 3-Way Comparison
Solo vs Pipeline vs Emergent (독립2경로+합의, adversarial 금지)
Domain: 논리 추론 퍼즐 (수학 계산 제외)
Target: Emergent > Pipeline > Solo
"""
import json, os, urllib.request, time, sys, re
from collections import Counter
from itertools import permutations
sys.stdout.reconfigure(line_buffering=True)

API_KEY = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call(prompt, temp=0.6):
    body = json.dumps({"model":"gpt-5.2","input":prompt,"temperature":temp}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=body,
        headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        r = json.loads(resp.read())
    for item in r.get("output",[]):
        if isinstance(item,dict) and item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text": return c["text"].strip()
    return ""

def extract_number(text):
    """Extract final integer answer from response text."""
    # Try \boxed{}
    m = re.search(r'\\boxed\{([^}]+)\}', text)
    if m: return m.group(1).strip()
    # Try "answer is N" / "result is N" / "total is N" / "there are N"
    m = re.search(r'(?:answer|result|total|there\s+are|count\s+is)\s+(?:is\s+)?(\d+)', text, re.I)
    if m: return m.group(1).strip()
    # Try "= N" near end
    m = re.search(r'=\s*(\d+)\s*(?:valid|way|assignment|arrangement|solution)?\s*\.?\s*$', text, re.I | re.M)
    if m: return m.group(1).strip()
    # Final number in text
    nums = re.findall(r'\b\d+\b', text)
    return nums[-1] if nums else ""

def check(ans_str, expected):
    try:
        return int(ans_str) == int(expected)
    except:
        return str(ans_str).strip() == str(expected).strip()

# ── GROUND TRUTH VERIFICATION ──
def gt_digit_arrangement():
    """A+B>C+D+E, A odd, B>C, D<E for permutations of {1,2,3,4,5}"""
    count = 0
    for A,B,C,D,E in permutations([1,2,3,4,5]):
        if A+B > C+D+E and A%2==1 and B>C and D<E:
            count += 1
    return count

def gt_knights_knaves():
    """5-person knights/knaves puzzle - count consistent assignments"""
    count = 0
    for bits in range(32):
        a,b,c,d,e = [(bits>>i)&1 for i in reversed(range(5))]
        # speaker_is_knight(1) == statement_is_true(1)
        if a != int(b==0 or c==0): continue  # Alice: "Bob or Carol is lying"
        if b != int(d==1): continue           # Bob: "Dave is truth-teller"
        if c != int(e==0): continue           # Carol: "Eve is liar"
        if d != int(a==0): continue           # Dave: "Alice is liar"
        if e != int(c==0 and d==0): continue  # Eve: "Carol AND Dave are both liars"
        count += 1
    return count  # = 3

print("=" * 60)
print("GROUND TRUTH VERIFICATION")
gt1 = gt_digit_arrangement()
gt2 = gt_knights_knaves()
print(f"  digit_arrangement: {gt1} (expected 8)")
print(f"  knights_knaves:    {gt2} (expected 3)")
assert gt1 == 8, f"BUG: digit_arrangement answer is {gt1}"
assert gt2 == 3, f"BUG: knights_knaves answer is {gt2}"
print("  ✅ Both verified correct")
print()

# ── PROBLEMS ──
PROBLEMS = [
    {
        "id": "digit_arrangement",
        "problem": (
            "Digits 1, 2, 3, 4, and 5 are each assigned exactly once to five variables "
            "A, B, C, D, E (forming a permutation of 1-5). Count ALL assignments satisfying "
            "ALL of these constraints simultaneously:\n"
            "  1. A + B > C + D + E  (sum of first two strictly exceeds sum of last three)\n"
            "  2. A is an odd number  (A ∈ {1, 3, 5})\n"
            "  3. B > C\n"
            "  4. D < E\n\n"
            "How many valid assignments exist? Give your final answer as a single integer."
        ),
        "answer": "8",
    },
    {
        "id": "knights_knaves",
        "problem": (
            "Five people — Alice, Bob, Carol, Dave, Eve — each are EITHER a truth-teller "
            "(always tells the truth) OR a liar (always lies). They make exactly these statements:\n"
            "  • Alice says: \"At least one of Bob or Carol is a liar.\"\n"
            "  • Bob says: \"Dave is a truth-teller.\"\n"
            "  • Carol says: \"Eve is a liar.\"\n"
            "  • Dave says: \"Alice is a liar.\"\n"
            "  • Eve says: \"Both Carol and Dave are liars.\"\n\n"
            "How many consistent truth-teller/liar assignments for all 5 people exist "
            "(i.e., where every statement is consistent with the speaker's type)? "
            "Give your final answer as a single integer."
        ),
        "answer": "3",
    },
]

# ── METHOD 1: SOLO (1 call) ──
def method_solo(problem):
    resp = call(
        f"{problem}\n\n"
        "Think step by step, considering all cases carefully. "
        "Give your final answer as a single integer at the end.",
        temp=0.7
    )
    return extract_number(resp), resp[:400]

# ── METHOD 2: PIPELINE (plan→solve→review→fix, 4 calls) ──
def method_pipeline(problem):
    # Step 1: Plan
    plan = call(
        f"You are a logic puzzle analyst. Analyze this problem and outline a solution strategy.\n\n"
        f"Problem:\n{problem}\n\n"
        "Provide:\n"
        "1. Problem type and what's being asked\n"
        "2. Key constraints to track\n"
        "3. Recommended solution approach (enumeration, deduction, or hybrid)\n"
        "4. Common pitfalls to avoid",
        temp=0.5
    )
    time.sleep(0.5)

    # Step 2: Solve
    solution = call(
        f"Solve this logic puzzle following the analysis.\n\n"
        f"Problem:\n{problem}\n\n"
        f"Analysis:\n{plan}\n\n"
        "Work through every case. Be systematic and complete. "
        "Give your final answer as a single integer.",
        temp=0.6
    )
    time.sleep(0.5)

    # Step 3: Review
    review = call(
        f"Carefully review this solution for logic errors.\n\n"
        f"Problem:\n{problem}\n\n"
        f"Solution:\n{solution}\n\n"
        "Check:\n"
        "1. Are ALL constraints correctly applied?\n"
        "2. Is the enumeration complete (no cases missed or double-counted)?\n"
        "3. Is the final count/answer correct?\n\n"
        "List specific errors if found, or confirm correctness with reasoning.",
        temp=0.5
    )
    time.sleep(0.5)

    # Step 4: Fix
    fixed = call(
        f"Finalize the solution based on the review.\n\n"
        f"Problem:\n{problem}\n\n"
        f"Original solution:\n{solution}\n\n"
        f"Review:\n{review}\n\n"
        "If errors were identified, correct them. If the solution is correct, confirm it. "
        "Give your final answer as a single integer.",
        temp=0.4
    )

    return extract_number(fixed), [plan[:200], solution[:200], review[:200], fixed[:200]]

# ── METHOD 3: EMERGENT (독립2경로 + 합의, 4 calls) ──
def method_emergent(problem):
    """
    두 독립 경로:
    - Path A: Systematic enumeration (브루트포스 방식)
    - Path B: Logical deduction (제약 전파 방식)
    합의: 같으면 확정, 다르면 tiebreaker (제3독립 계산)
    """
    # Path A: Systematic enumeration
    sol_a = call(
        f"Solve this logic puzzle using SYSTEMATIC ENUMERATION.\n\n"
        f"Problem:\n{problem}\n\n"
        "Approach: List and check each possible case methodically. "
        "Try every possibility and verify constraints for each. "
        "Be exhaustive — do not skip cases. "
        "Give your final answer as a single integer.",
        temp=0.6
    )
    time.sleep(0.5)

    # Path B: Logical deduction / constraint propagation
    sol_b = call(
        f"Solve this logic puzzle using LOGICAL DEDUCTION.\n\n"
        f"Problem:\n{problem}\n\n"
        "Approach: Apply constraints to eliminate impossible cases step by step. "
        "Use inference chains and constraint propagation, not brute-force enumeration. "
        "Give your final answer as a single integer.",
        temp=0.6
    )
    time.sleep(0.5)

    ans_a = extract_number(sol_a)
    ans_b = extract_number(sol_b)

    if ans_a and ans_b and ans_a == ans_b:
        # Consensus - independent verification
        verify = call(
            f"Two independent solvers agree on an answer to this logic puzzle. "
            f"Please independently verify.\n\n"
            f"Problem:\n{problem}\n\n"
            f"Both solvers got: {ans_a}\n\n"
            "Do a quick independent check. Is this answer correct? "
            "If wrong, state the correct answer. "
            "Give your final answer as a single integer.",
            temp=0.3
        )
        final_ans = extract_number(verify)
        return (final_ans or ans_a), [sol_a[:200], sol_b[:200], f"Consensus A=B={ans_a}", verify[:200]]
    else:
        # Disagreement - tiebreaker (3rd independent solver)
        tiebreak = call(
            f"Two solvers disagree on this logic puzzle. Solve it independently to find the truth.\n\n"
            f"Problem:\n{problem}\n\n"
            f"Solver A (enumeration) got: {ans_a}\n"
            f"Solver B (deduction) got: {ans_b}\n\n"
            "Ignore their work — solve it fresh from scratch using whichever approach you prefer. "
            "Give your final answer as a single integer.",
            temp=0.5
        )
        final_ans = extract_number(tiebreak)
        return final_ans, [sol_a[:200], sol_b[:200], f"Disagreement A={ans_a} B={ans_b}", tiebreak[:200]]

# ── RUN EXPERIMENT ──
N_TRIALS = 5
all_results = {}

for prob in PROBLEMS:
    pid = prob["id"]
    expected = prob["answer"]
    print(f"\n{'='*60}")
    print(f"PROBLEM: {pid} | Expected answer: {expected}")
    print(f"{'='*60}")
    all_results[pid] = {}

    for method_name, method_fn in [
        ("solo",     lambda p: method_solo(p)),
        ("pipeline", lambda p: method_pipeline(p)),
        ("emergent", lambda p: method_emergent(p)),
    ]:
        print(f"\n  [{method_name.upper()}] N={N_TRIALS}")
        scores = []
        for t in range(N_TRIALS):
            try:
                ans, trace = method_fn(prob["problem"])
                ok = check(ans, expected)
                scores.append(1 if ok else 0)
                print(f"    t{t+1}: {'✅' if ok else '❌'} (got {ans!r})")
            except Exception as ex:
                print(f"    t{t+1}: ERR {ex}")
                scores.append(0)
            time.sleep(1.0)
        acc = sum(scores) / len(scores)
        all_results[pid][method_name] = {"accuracy": acc, "raw": scores}
        print(f"    → {method_name}: {acc:.0%} ({sum(scores)}/{len(scores)})")

# ── FINAL SUMMARY ──
print(f"\n{'='*65}")
print("ROUND 3 FINAL: Solo vs Pipeline vs Emergent | Logic Reasoning")
print(f"{'='*65}")
print(f"{'Problem':<25} {'Solo':>8} {'Pipeline':>10} {'Emergent':>10} {'Winner':>12}")
print("-" * 65)

all_s, all_p, all_e = [], [], []
emergent_wins = 0
for pid in all_results:
    s = all_results[pid].get("solo",{}).get("accuracy", 0)
    p = all_results[pid].get("pipeline",{}).get("accuracy", 0)
    e = all_results[pid].get("emergent",{}).get("accuracy", 0)
    all_s += all_results[pid].get("solo",{}).get("raw", [])
    all_p += all_results[pid].get("pipeline",{}).get("raw", [])
    all_e += all_results[pid].get("emergent",{}).get("raw", [])
    if e > max(s, p) + 0.05:
        winner = "EMERGENT🔥"
        emergent_wins += 1
    elif p > s + 0.05:
        winner = "pipeline"
    else:
        winner = "solo/tie"
    print(f"{pid:<25} {s:>8.0%} {p:>10.0%} {e:>10.0%} {winner:>14}")

os_ = sum(all_s)/len(all_s) if all_s else 0
op_ = sum(all_p)/len(all_p) if all_p else 0
oe_ = sum(all_e)/len(all_e) if all_e else 0
print(f"\n{'OVERALL':<25} {os_:>8.0%} {op_:>10.0%} {oe_:>10.0%}")
print(f"Emergent wins: {emergent_wins}/{len(all_results)} problems")

if oe_ > op_ > os_:
    verdict = "🔥 EMERGENT > PIPELINE > SOLO — 창발성 증명!"
elif oe_ > os_:
    verdict = "✅ EMERGENT > SOLO — 협업 효과 확인"
elif op_ > os_:
    verdict = "📋 PIPELINE > SOLO — 순차 협업 효과"
else:
    verdict = "⚖️  방법 간 차이 미미"
print(f"\n{verdict}")

solo_pct  = round(os_ * 100)
pipe_pct  = round(op_ * 100)
emg_pct   = round(oe_ * 100)

output = {
    "model":   "gpt-5.2",
    "domain":  "logic_reasoning_puzzles",
    "round":   3,
    "n_trials": N_TRIALS,
    "problems": [p["id"] for p in PROBLEMS],
    "overall": {"solo": os_, "pipeline": op_, "emergent": oe_},
    "results": all_results,
    "verdict": verdict,
    "summary": f"Solo={solo_pct}% Pipeline={pipe_pct}% Emergent={emg_pct}%",
    "emergent_design": "independent_2path_consensus",
}

out_path = "/Users/rocky/emergent/experiments/final_3way_round3_results.json"
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved: {out_path}")
print(f"\nSOLO={solo_pct} PIPELINE={pipe_pct} EMERGENT={emg_pct}")
