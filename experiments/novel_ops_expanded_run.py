#!/usr/bin/env python3
"""
novel_ops 확장 실험 (N=8, 문제 3개)
검증된 새 규칙 문제들 — GPT가 학습 데이터에서 본 적 없는 연산
"""
import json, os, urllib.request, time, re, sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
K=os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def call(p, t=0.4):
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

def extract(t):
    nums = re.findall(r'-?\d+', t[-400:])
    return nums[-1] if nums else ""

PROBLEMS = [
    {
        "id": "vex",
        "rules": "a⊕b = a×b - a - b + 1\na⊗b = a + b - floor(a×b / 2)",
        "question": "Compute (3⊕4)⊗(2⊕5)",
        "answer": "-2",
        "hint": "3⊕4=6, 2⊕5=4, 6⊗4=6+4-12=-2"
    },
    {
        "id": "zork",
        "rules": "a◆b = 2×a + b - 1\na◇b = a×b - a + 1",
        "question": "Compute (4◆3)◇2",
        "answer": "11",
        "hint": "4◆3=10, 10◇2=10×2-10+1=11"
    },
    {
        "id": "fseq",
        "rules": "f(1)=1, f(2)=2\nFor n>2: f(n)=f(n-1)+f(n-2) if n is odd\n         f(n)=f(n-1)×f(n-2)-1 if n is even",
        "question": "Find f(8)",
        "answer": "1832",
        "hint": "f(3)=3,f(4)=5,f(5)=8,f(6)=39,f(7)=47,f(8)=47×39-1=1832"
    },
]

N = 6
results = {}

for method in ["solo", "pipeline", "emergent"]:
    results[method] = {}
    print(f"\n{'='*50}\nMETHOD: {method.upper()}\n{'='*50}")

    for prob in PROBLEMS:
        pid = prob["id"]
        scores = []

        for t in range(N):
            if method == "solo":
                q = f"New math system rules:\n{prob['rules']}\n\nQuestion: {prob['question']}\nShow steps. Final answer (integer only):"
                resp = call(q, 0.5)
                ans = extract(resp)

            elif method == "pipeline":
                r1 = call(f"Parse these rules carefully:\n{prob['rules']}\n\nStep 1: Apply each operation one at a time for: {prob['question']}\nCompute only the innermost operation first.", 0.3)
                time.sleep(0.15)
                r2 = call(f"Rules:\n{prob['rules']}\nQuestion: {prob['question']}\nPrevious step got: {extract(r1)}\nVerify by computing each step from scratch with explicit arithmetic.", 0.3)
                time.sleep(0.15)
                r3 = call(f"Rules:\n{prob['rules']}\nQuestion: {prob['question']}\nStep A: {r1[-150:]}\nStep B: {r2[-150:]}\nCheck for arithmetic errors. What is the correct value?", 0.3)
                time.sleep(0.15)
                r4 = call(f"Final answer only (integer) for: {prob['question']}\nRules: {prob['rules']}\nWork so far: {r3[-200:]}\nAnswer:", 0.2)
                ans = extract(r4)

            else:  # emergent
                a = call(f"Agent A: Compute {prob['question']} step by step.\nRules:\n{prob['rules']}\nShow explicit arithmetic for each step.", 0.5)
                time.sleep(0.15)
                b = call(f"Agent B: Compute {prob['question']} INDEPENDENTLY. Do NOT trust Agent A.\nRules:\n{prob['rules']}\nYour computation:\nAgent A claims: {extract(a)}\nAre they right?", 0.6)
                time.sleep(0.15)
                r = call(f"Reconcile:\nAgent A: {extract(a)}\nAgent B: {extract(b)}\nRules:\n{prob['rules']}\nQuestion: {prob['question']}\nTrace through carefully. Which is correct?", 0.3)
                time.sleep(0.15)
                f = call(f"Final verification for {prob['question']}.\nRules:\n{prob['rules']}\nCandidate answer: {extract(r)}\nConfirm with explicit arithmetic. Integer only:", 0.2)
                ans = extract(f)

            ok = ans == prob["answer"]
            scores.append(int(ok))
            print(f"  [{pid}] t{t+1}: {'✅' if ok else '❌'} got={ans!r}")
            time.sleep(0.3)

        acc = sum(scores)/N
        results[method][pid] = {"accuracy": acc, "raw": scores}
        print(f"  → {method} {pid}: {acc:.0%}")

# Summary
print(f"\n{'='*60}")
print("EXPANDED RESULTS: Solo vs Pipeline vs Emergent")
print(f"{'='*60}")
print(f"{'Problem':<12} {'Solo':>8} {'Pipeline':>10} {'Emergent':>10}")
print("-"*42)

all_s, all_p, all_e = [], [], []
for pid in [p["id"] for p in PROBLEMS]:
    s = results["solo"][pid]["accuracy"]
    p = results["pipeline"][pid]["accuracy"]
    e = results["emergent"][pid]["accuracy"]
    all_s.extend(results["solo"][pid]["raw"])
    all_p.extend(results["pipeline"][pid]["raw"])
    all_e.extend(results["emergent"][pid]["raw"])
    print(f"{pid:<12} {s:>8.0%} {p:>10.0%} {e:>10.0%}")

oa, ob, oc = sum(all_s)/len(all_s), sum(all_p)/len(all_p), sum(all_e)/len(all_e)
print(f"\n{'OVERALL':<12} {oa:>8.0%} {ob:>10.0%} {oc:>10.0%}")
print(f"\nSolo vs 협업: {oa:.0%} → {max(ob,oc):.0%} ({(max(ob,oc)-oa)*100:.0f}%p 향상)")

if oc > ob > oa: verdict = "🔥 EMERGENT > PIPELINE > SOLO"
elif ob > oc > oa: verdict = "📋 PIPELINE > EMERGENT > SOLO"
elif min(ob,oc) > oa: verdict = "✅ 협업 > Solo (방식 무관)"
else: verdict = "❌ 불명확"
print(f"\n{verdict}")

out = {
    "domain": "novel_ops_expanded",
    "n_trials": N,
    "problems": [p["id"] for p in PROBLEMS],
    "overall": {"solo": oa, "pipeline": ob, "emergent": oc},
    "details": results,
    "verdict": verdict
}
Path("/Users/rocky/emergent/experiments/novel_ops_expanded.json").write_text(
    json.dumps(out, indent=2))
print("\nSaved: novel_ops_expanded.json")
