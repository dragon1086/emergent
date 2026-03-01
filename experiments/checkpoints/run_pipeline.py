#!/usr/bin/env python3
"""Pipeline: plan→solve→review→fix (4 calls) — 인지 편향 Round 5"""
import json,os,urllib.request,time,re,sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
K=os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call(p,t=0.4):
    b=json.dumps({"model":"gpt-5.2","input":p,"temperature":t}).encode()
    r=urllib.request.Request("https://api.openai.com/v1/responses",data=b,
        headers={"Authorization":f"Bearer {K}","Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=60) as resp:
        d=json.loads(resp.read())
    for i in d.get("output",[]):
        if isinstance(i,dict) and i.get("type")=="message":
            for c in i.get("content",[]):
                if c.get("type")=="output_text": return c["text"]
    return ""

def ex(t):
    m=re.search(r'\\boxed\{([^}]+)\}',t)
    x=m.group(1) if m else (re.findall(r'\d+',t) or [""])[-1]
    n=re.findall(r'\d+',x); return n[0] if n else x.strip()

def pipeline(prob):
    plan=call(f"Identify the exact formula/method needed.\nProblem:{prob}")
    time.sleep(0.2)
    sol=call(f"Solve step by step.\nProblem:{prob}\nMethod:{plan[:400]}\nEnd with \\boxed{{answer}}.",0.4)
    time.sleep(0.2)
    rev=call(f"Check for errors, especially probability mistakes.\nProblem:{prob}\nSolution:{sol[:600]}")
    time.sleep(0.2)
    fix=call(f"Give the corrected final answer.\nProblem:{prob}\nSolution:{sol[:400]}\nReview:{rev[:400]}\nEnd with \\boxed{{answer}}.",0.3)
    return ex(fix)

PROBLEMS=[
    ("base_rate",
     "A disease affects 1% of the population. A test has 99% accuracy (both ways). If someone tests positive, what is the probability (%) they have the disease? Round to nearest integer.",
     "50"),
    ("monty_hall_5",
     "5 doors, prize behind one. You pick door 1. Host opens 3 losing doors. You switch. What is your winning probability as a percentage?",
     "80"),
]
N=5
results={}
for pid,prob,exp in PROBLEMS:
    print(f"\n[PIPELINE] {pid} (expected={exp})")
    scores=[]
    for i in range(N):
        ans=pipeline(prob)
        ok=1 if ans==exp else 0; scores.append(ok)
        print(f"  t{i+1}: {'✅' if ok else '❌'} got={ans}")
        time.sleep(0.5)
    acc=sum(scores)/N
    results[pid]={"accuracy":acc,"raw":scores,"expected":exp}
    print(f"  → {acc:.0%}")

Path("/Users/rocky/emergent/experiments/checkpoints/pipeline.json").write_text(json.dumps(results,indent=2))
print("\n✅ Pipeline saved")
