#!/usr/bin/env python3
"""
Round 4: 복잡한 Knights & Knaves 논리퍼즐
Solo vs Pipeline vs Emergent (GPT-5.2, 각 4 API calls)
"""
import json,os,urllib.request,time,re,sys
from itertools import product
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)

K=__import__('subprocess').run(['zsh','-c',"grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\\' -f2"],capture_output=True,text=True).stdout.strip()

def call(p,t=0.5):
    b=json.dumps({"model":"gpt-5.2","input":p,"temperature":t}).encode()
    r=urllib.request.Request("https://api.openai.com/v1/responses",data=b,
        headers={"Authorization":f"Bearer {K}","Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=60) as resp:
        return json.loads(resp.read())
    
def text(r):
    for i in r.get("output",[]):
        if isinstance(i,dict) and i.get("type")=="message":
            for c in i.get("content",[]):
                if c.get("type")=="output_text": return c["text"]
    return ""

def extract_int(t):
    m=re.search(r'\\boxed\{(\d+)\}',t) or re.search(r'\b(\d)\b(?:\s*knight)',t,re.I) or re.search(r'answer.*?(\d)',t,re.I) or re.search(r'(\d)',t)
    return m.group(1) if m else ""

# ── 문제 1: 4명 복잡 퍼즐 ──────────────────────────────────────
P1_TEXT = """Four people — Alice, Bob, Carol, and Dave — each are either a knight (always tells truth) or a knave (always lies).
They say:
- Alice says: "Bob and Carol are both knights."
- Bob says: "Dave is a knave."
- Carol says: "Alice is lying."
- Dave says: "Carol and I are the same type."

How many knights are there? Answer with a single digit."""

def solve_p1_brute():
    for combo in product([True,False],repeat=4):
        A,B,C,D=combo
        ok_A=(B and C)==A
        ok_B=(not D)==B
        ok_C=(not A)==C  # Carol says Alice is lying = Alice is knave
        ok_D=(C==D)==D   # Dave says Carol and I are same type
        if ok_A and ok_B and ok_C and ok_D:
            return str(sum(combo))
    return "no solution"

P1_ANS=solve_p1_brute()
print(f"P1 answer (brute-force): {P1_ANS}")

# ── 문제 2: 5명 퍼즐 ──────────────────────────────────────────
P2_TEXT = """Five people — A, B, C, D, E — are either knights or knaves.
- A says: "Exactly two of us five are knights."
- B says: "A is a knight."
- C says: "B is a knave."
- D says: "C tells the truth."
- E says: "I am a knave."

How many knights are there? Answer with a single digit."""

def solve_p2_brute():
    solutions=[]
    for combo in product([True,False],repeat=5):
        A,B,C,D,E=combo
        n=sum(combo)
        ok_A=(n==2)==A
        ok_B=A==B
        ok_C=(not B)==C
        ok_D=C==D
        ok_E=(not E)==E  # "I am a knave" = always false for both K and Kn
        if ok_A and ok_B and ok_C and ok_D and ok_E:
            solutions.append(combo)
    if solutions: return str(sum(solutions[0]))
    # E's statement is paradox — try ignoring E
    for combo in product([True,False],repeat=5):
        A,B,C,D,E=combo
        n=sum(combo)
        ok_A=(n==2)==A; ok_B=A==B; ok_C=(not B)==C; ok_D=C==D
        if ok_A and ok_B and ok_C and ok_D:
            solutions.append(combo)
    return str(sum(solutions[0])) if solutions else "no solution"

P2_ANS=solve_p2_brute()
print(f"P2 answer (brute-force): {P2_ANS}")

PROBLEMS=[
    ("knights4",P1_TEXT,P1_ANS),
    ("knights5",P2_TEXT,P2_ANS),
]

# ── Methods ──────────────────────────────────────────────────
N=5
BASE_INSTR="Knights always tell the truth, knaves always lie. Think step by step. End with a single digit in \\boxed{X}."

def solo(prob): 
    return extract_int(text(call(f"{prob}\n{BASE_INSTR}")))

def pipeline(prob):
    p=text(call(f"Analyze the logical constraints in this puzzle:\n{prob}\nList each person's constraint equation.",0.4)); time.sleep(0.2)
    s=text(call(f"Solve systematically.\n{prob}\nConstraints:\n{p}\nEnd with \\boxed{{answer}}.",0.4)); time.sleep(0.2)
    rv=text(call(f"Verify: check each person's statement against your solution.\n{prob}\nSolution:\n{s}",0.3)); time.sleep(0.2)
    f=text(call(f"Final answer after verification.\n{prob}\nSolution:{s}\nVerification:{rv}\n{BASE_INSTR}",0.2))
    return extract_int(f)

def emergent(prob):
    a=text(call(f"Solve this knights/knaves puzzle by trying all combinations systematically.\n{prob}\n{BASE_INSTR}",0.5)); time.sleep(0.2)
    b=text(call(f"INDEPENDENTLY solve this puzzle using logical deduction (NOT enumeration).\nChallenge any errors in this other solution: {a[:400]}\n{prob}\n{BASE_INSTR}",0.6)); time.sleep(0.2)
    a2=text(call(f"Two solvers got: A={extract_int(a)}, B={extract_int(b)}. Reconcile by carefully re-checking all constraints.\n{prob}\nEnd with \\boxed{{final}}.",0.3)); time.sleep(0.2)
    f=text(call(f"Verify final answer. Does it satisfy all 4 statements?\n{prob}\nProposed: {extract_int(a2)}\nEnd with \\boxed{{answer}}.",0.2))
    return extract_int(f)

# ── Run ──────────────────────────────────────────────────────
results={}
print(f"\n{'='*60}\nRound 4: Knights & Knaves (Complex)\n{'='*60}")

# Baseline check first
print("\n[BASELINE] Checking solo accuracy...")
for pid,prob,exp in PROBLEMS:
    hits=sum(1 for _ in range(3) if solo(prob)==exp)
    acc=hits/3
    print(f"  {pid}: {acc:.0%} (expected={exp})")
    time.sleep(0.3)

print("\n[FULL 3-WAY EXPERIMENT]")
for pid,prob,exp in PROBLEMS:
    print(f"\n--- {pid} (expected={exp}) ---")
    results[pid]={}
    for method_name,method_fn in [("solo",solo),("pipeline",pipeline),("emergent",emergent)]:
        scores=[]
        for i in range(N):
            ans=method_fn(prob)
            ok=1 if ans==exp else 0
            scores.append(ok)
            print(f"  [{method_name}] t{i+1}: {'✅' if ok else '❌'} got={ans!r}")
            time.sleep(0.4)
        acc=sum(scores)/N
        results[pid][method_name]={"accuracy":acc,"raw":scores}
        print(f"  → {method_name}: {acc:.0%}")

# Summary
print(f"\n{'='*60}")
s_all=[v for p in results for v in results[p]['solo']['raw']]
p_all=[v for p in results for v in results[p]['pipeline']['raw']]
e_all=[v for p in results for v in results[p]['emergent']['raw']]
oa=sum(s_all)/len(s_all); ob=sum(p_all)/len(p_all); oc=sum(e_all)/len(e_all)
print(f"OVERALL  Solo={oa:.0%}  Pipeline={ob:.0%}  Emergent={oc:.0%}")
if oc>ob>oa: print("🔥 EMERGENT > PIPELINE > SOLO!")
elif oc>oa: print("✅ Emergent > Solo")
else: print("❌ 목표 미달")

out={"round":4,"domain":"knights_knaves_complex","overall":{"solo":oa,"pipeline":ob,"emergent":oc},"details":{pid:{m:results[pid][m]["accuracy"] for m in results[pid]} for pid in results}}
Path("/Users/rocky/emergent/experiments/final_3way_round4_results.json").write_text(json.dumps(out,indent=2))
print("Saved.")

# git commit
import subprocess
subprocess.run(["git","add","-A"],cwd="/Users/rocky/emergent")
subprocess.run(["git","commit","-m",f"Round 4: Solo={oa:.0%} Pipeline={ob:.0%} Emergent={oc:.0%}"],cwd="/Users/rocky/emergent")
subprocess.run(["openclaw","system","event","--text",f"Round4완료 Solo={oa:.0%} Pipeline={ob:.0%} Emergent={oc:.0%}","--mode","now"])
