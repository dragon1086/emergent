#!/usr/bin/env python3
"""
novel_ops v2: Solo(단순프롬프트) vs Pipeline vs Emergent
핵심: 실제 사용자는 최적 프롬프트 모름 → 협업 엔진이 내부에서 단계 처리
"""
import json, os, urllib.request, time, re, sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
K=os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()
PROBS=json.loads(Path("/Users/rocky/emergent/experiments/novel_ops_v2_problems.json").read_text())

def call(p,t=0.4):
    b=json.dumps({"model":"gpt-5.2","input":p,"temperature":t}).encode()
    r=urllib.request.Request("https://api.openai.com/v1/responses",data=b,
        headers={"Authorization":f"Bearer {K}","Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=60) as resp: d=json.loads(resp.read())
    for i in d.get("output",[]):
        if isinstance(i,dict) and i.get("type")=="message":
            for c in i.get("content",[]):
                if c.get("type")=="output_text": return c["text"]
    return ""

def ext(t):
    m=re.findall(r'-?\d+',t[-300:]); return m[-1] if m else ""

def solo(p):
    # 실제 사용자처럼 단순하게 물어봄 (show steps 없음)
    return call(f"Rules:\n{p['rules']}\n\nQ: {p['question']}\nAnswer (number only):",0.6)

def pipeline(p):
    r,q=p['rules'],p['question']
    s1=call(f"Given these rules:\n{r}\nIdentify what operations appear in: {q}\nList the operations to apply in order.",0.3); time.sleep(0.15)
    s2=call(f"Rules:\n{r}\nCompute ONLY the innermost/first operation in: {q}\nShow arithmetic.",0.3); time.sleep(0.15)
    s3=call(f"Rules:\n{r}\nQ: {q}\nStep 1 result:{ext(s1+s2)}\nNow apply the outer operation. Show arithmetic.",0.3); time.sleep(0.15)
    s4=call(f"Final answer for: {q}\nRules:{r}\nWork:{s2[-100:]} {s3[-100:]}\nInteger only:",0.2)
    return s4

def emergent(p):
    r,q=p['rules'],p['question']
    a=call(f"Compute {q} step by step.\nRules:\n{r}\nShow each arithmetic step.",0.5); time.sleep(0.15)
    b=call(f"Compute {q} INDEPENDENTLY. Check if Agent A is right.\nRules:\n{r}\nAgent A: {ext(a)}\nYour independent answer:",0.6); time.sleep(0.15)
    rec=call(f"A={ext(a)}, B={ext(b)}. Rules:\n{r}\nQ:{q}\nWho is right? Show why. Final answer:",0.3); time.sleep(0.15)
    v=call(f"Verify: {q}\nRules:{r}\nCandidate:{ext(rec)}\nConfirm arithmetic. Integer only:",0.2)
    return v

N=6
results={"solo":{},"pipeline":{},"emergent":{}}
for method,fn in [("solo",solo),("pipeline",pipeline),("emergent",emergent)]:
    print(f"\n{'='*45}\n{method.upper()}\n{'='*45}")
    for p in PROBS:
        pid,ans=p["id"],p["answer"]
        scores=[]
        for t in range(N):
            got=ext(fn(p)); ok=got==ans; scores.append(int(ok))
            print(f"  [{pid}] t{t+1}: {'✅' if ok else '❌'} got={got!r} (ans={ans})")
            time.sleep(0.3)
        acc=sum(scores)/N; results[method][pid]={"accuracy":acc,"raw":scores}
        print(f"  → {acc:.0%}")

# Summary
print(f"\n{'='*55}\nFINAL RESULTS\n{'='*55}")
print(f"{'':14} {'Solo':>6} {'Pipeline':>10} {'Emergent':>10}")
all_s,all_p,all_e=[],[],[]
for p in PROBS:
    pid=p["id"]
    s=results["solo"][pid]["accuracy"]
    pp=results["pipeline"][pid]["accuracy"]
    e=results["emergent"][pid]["accuracy"]
    all_s+=results["solo"][pid]["raw"]
    all_p+=results["pipeline"][pid]["raw"]
    all_e+=results["emergent"][pid]["raw"]
    print(f"{pid:14} {s:>6.0%} {pp:>10.0%} {e:>10.0%}")
oa,ob,oc=sum(all_s)/len(all_s),sum(all_p)/len(all_p),sum(all_e)/len(all_e)
print(f"{'OVERALL':14} {oa:>6.0%} {ob:>10.0%} {oc:>10.0%}")
print(f"\nSolo→협업 향상: {(max(ob,oc)-oa)*100:.0f}%p")
out={"overall":{"solo":oa,"pipeline":ob,"emergent":oc},"details":{p["id"]:{"solo":results["solo"][p["id"]]["accuracy"],"pipeline":results["pipeline"][p["id"]]["accuracy"],"emergent":results["emergent"][p["id"]]["accuracy"]} for p in PROBS}}
Path("/Users/rocky/emergent/experiments/novel_ops_v2_results.json").write_text(json.dumps(out,indent=2))
print("Saved: novel_ops_v2_results.json")
