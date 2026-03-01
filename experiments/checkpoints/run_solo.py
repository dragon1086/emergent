#!/usr/bin/env python3
"""Solo: GPT-5.2 단일 1호출 (진짜 Solo)"""
import json,os,urllib.request,time,re,sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
K=os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call(p,t=0.6):
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

PROBLEMS=[
    ("fib_mod","What is F(100) mod 1000, where F(1)=1, F(2)=1?","75"),
    ("combo","Calculate C(20,7) using C(n,k)=n!/(k!*(n-k)!)","77520"),
]
N=4
results={}
for pid,prob,exp in PROBLEMS:
    print(f"\n[SOLO] {pid}")
    scores=[]
    for i in range(N):
        ans=extract(call(prob+"\nStep by step. End with \\boxed{answer}."))
        ok=1 if ans==exp else 0
        scores.append(ok)
        print(f"  t{i+1}: {'✅' if ok else '❌'} got={ans}")
        time.sleep(0.3)
    acc=sum(scores)/N
    results[pid]={"accuracy":acc,"raw":scores,"expected":exp}
    print(f"  → {acc:.0%}")

Path("/Users/rocky/emergent/experiments/checkpoints/solo.json").write_text(json.dumps(results,indent=2))
print("\n✅ Solo saved")
