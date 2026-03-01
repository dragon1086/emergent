#!/usr/bin/env python3
"""
Emergent v3: 인지 편향 도메인 특화
- Agent A: 직관적 접근 (편향에 노출됨)
- Agent B: 수학적 계산으로 A를 강하게 반박
- A revises: B의 수학을 보고 재검토
- Final: 수학적 검증 확정
"""
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

def emergent(prob,kind="prob"):
    # A: 직관적 1차 답변 (편향 위험)
    a=call(f"Answer this probability problem step by step.\n{prob}\nEnd with \\boxed{{answer}}.",0.6)
    time.sleep(0.2)
    # B: 수학으로 정면 반박 (베이즈/경우의수 강제)
    b=call(
        f"CRITICAL MATH CHECK: Many people get this type of problem wrong due to base-rate neglect or probability misconceptions.\n"
        f"Problem: {prob}\n"
        f"Agent A answered: {ex(a)}%\n"
        f"NOW: Use formal mathematical calculation (Bayes theorem / tree diagram / explicit enumeration) to get the EXACT answer. "
        f"Do NOT trust intuition. Show all arithmetic. End with \\boxed{{correct_answer}}.",0.4)
    time.sleep(0.2)
    # A revises after seeing rigorous math
    a2=call(
        f"You previously answered {ex(a)}% but a mathematical checker challenged you.\n"
        f"Problem: {prob}\n"
        f"Mathematical analysis: {b[:600]}\n"
        f"Reconsider carefully. If the math is correct, update your answer. End with \\boxed{{final_answer}}.",0.3)
    time.sleep(0.2)
    # Final: double-check the number
    final=call(
        f"Final verification for: {prob}\n"
        f"Proposed answer: {ex(a2)}%\n"
        f"Verify with a quick calculation and confirm. End with \\boxed{{answer}}.",0.2)
    return ex(final)

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
    print(f"\n[EMERGENT v3] {pid} (expected={exp})")
    scores=[]
    for i in range(N):
        ans=emergent(prob)
        ok=1 if ans==exp else 0; scores.append(ok)
        print(f"  t{i+1}: {'✅' if ok else '❌'} got={ans}")
        time.sleep(0.5)
    acc=sum(scores)/N
    results[pid]={"accuracy":acc,"raw":scores,"expected":exp}
    print(f"  → {acc:.0%}")

Path("/Users/rocky/emergent/experiments/checkpoints/emergent.json").write_text(json.dumps(results,indent=2))
print("\n✅ Emergent v3 saved")
