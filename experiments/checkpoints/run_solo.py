#!/usr/bin/env python3
"""Solo: GPT-5.2 단일 호출 — 인지 편향 도메인 Round 5"""
import json,os,urllib.request,time,re,sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
K=os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call(p,t=0.5):
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

PROBLEMS=[
    ("base_rate",
     "A disease affects 1% of the population. A test for the disease has 99% accuracy (both sensitivity and specificity). If a randomly chosen person tests positive, what is the probability (as a percentage) that they actually have the disease? Give the exact percentage rounded to nearest integer.",
     "50"),
    ("monty_hall_5",
     "There are 5 doors. Behind one is a prize. You pick door 1. The host opens 3 doors (all losers). You can switch to the remaining unopened door. What is the probability (as a percentage) of winning if you switch?",
     "80"),
]
N=5
results={}
for pid,prob,exp in PROBLEMS:
    print(f"\n[SOLO] {pid} (expected={exp})")
    scores=[]
    for i in range(N):
        ans=ex(call(prob+"\nThink step by step. Give a numeric percentage. End with \\boxed{answer}."))
        ok=1 if ans==exp else 0; scores.append(ok)
        print(f"  t{i+1}: {'✅' if ok else '❌'} got={ans}")
        time.sleep(0.3)
    acc=sum(scores)/N
    results[pid]={"accuracy":acc,"raw":scores,"expected":exp}
    print(f"  → {acc:.0%}")

Path("/Users/rocky/emergent/experiments/checkpoints/solo.json").write_text(json.dumps(results,indent=2))
print("\n✅ Solo saved")
