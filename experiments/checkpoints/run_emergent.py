#!/usr/bin/env python3
"""Emergent: 적대적 검증 + 대안 접근 강제 (GPT-5.2 4호출)"""
import json,os,urllib.request,time,re,sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
K=os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call(p,t=0.5):
    b=json.dumps({"model":"gpt-5.2","input":p,"temperature":t}).encode()
    r=urllib.request.Request("https://api.openai.com/v1/responses",data=b,headers={"Authorization":f"Bearer {K}","Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=60) as resp:
        d=json.loads(resp.read())
    for i in d.get("output",[]):
        if isinstance(i,dict) and i.get("type")=="message":
            for c in i.get("content",[]):
                if c.get("type")=="output_text": return c["text"]
    return ""

def extract(t):
    m=re.search(r'\\boxed\{([^}]+)\}',t)
    x=m.group(1) if m else (re.findall(r'\d+',t) or [""])[-1]
    n=re.findall(r'\d+',x); return n[0] if n else x.strip()

def emergent(prob):
    # Agent A: solve
    a=call(f"Solve carefully step by step.\nProblem:{prob}\nEnd with \\boxed{{answer}}.",0.5)
    time.sleep(0.2)
    # Agent B: attack with a COMPLETELY DIFFERENT method
    b=call(f"You are an adversarial checker. INDEPENDENTLY solve this using a COMPLETELY DIFFERENT method than typical, then find any flaw in Agent A's reasoning.\nProblem:{prob}\nAgent A:{a[:600]}\nSolve independently first, then critique A. End with \\boxed{{your_answer}}.",0.7)
    time.sleep(0.2)
    # A revises seeing B's challenge
    a2=call(f"Two solvers disagreed or one found errors. Determine the correct answer.\nProblem:{prob}\nSolver1:{a[:500]}\nSolver2(adversarial):{b[:500]}\nCarefully check arithmetic. End with \\boxed{{answer}}.",0.3)
    time.sleep(0.2)
    # Final verification
    final=call(f"Final answer verification. Compute once more independently.\nProblem:{prob}\nProposed:{extract(a2)}\nConfirm or correct. End with \\boxed{{answer}}.",0.2)
    return extract(final)

PROBLEMS=[
    ("fib_mod","What is F(100) mod 1000, where F(1)=1, F(2)=1?","75"),
    ("combo","Calculate C(20,7) using C(n,k)=n!/(k!*(n-k)!)","77520"),
]
N=3
results={}
for pid,prob,exp in PROBLEMS:
    print(f"\n[EMERGENT] {pid}")
    scores=[]
    for i in range(N):
        ans=emergent(prob)
        ok=1 if ans==exp else 0
        scores.append(ok)
        print(f"  t{i+1}: {'✅' if ok else '❌'} got={ans}")
        time.sleep(0.5)
    acc=sum(scores)/N
    results[pid]={"accuracy":acc,"raw":scores,"expected":exp}
    print(f"  → {acc:.0%}")

out=Path("/Users/rocky/emergent/experiments/checkpoints/emergent.json")
out.write_text(json.dumps(results,indent=2))
print(f"\n✅ Emergent saved: {out}")
