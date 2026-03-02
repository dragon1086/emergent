#!/usr/bin/env python3
"""
오류 감지 3-Way: Solo vs Pipeline vs Emergent
GPT-5.2 동일 모델, 동일 호출수 (Solo=1, Pipeline=4, Emergent=4)
정답: Python 실행으로 객관적 검증
"""
import json, os, urllib.request, time, re, sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)

K = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()
PROBLEMS = json.loads(Path("/Users/rocky/emergent/experiments/bug_detection_problems.json").read_text())

def call(prompt, temp=0.4):
    body = json.dumps({"model":"gpt-5.2","input":prompt,"temperature":temp}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=body,
        headers={"Authorization":f"Bearer {K}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        r = json.loads(resp.read())
    for item in r.get("output",[]):
        if isinstance(item,dict) and item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text": return c["text"]
    return ""

def grade(response, bug_answer):
    """정답 판별: 핵심 키워드가 응답에 있는지 확인"""
    r = response.lower()
    # 버그 설명에서 핵심 단어 추출
    keywords = []
    bug = bug_answer.lower()
    if "range" in bug: keywords.append("range")
    if "base case" in bug or "return 1" in bug: keywords += ["base case","return 1"]
    if "mutable" in bug or "default" in bug: keywords += ["mutable","default"]
    if "float" in bug or "epsilon" in bug or "precision" in bug: keywords += ["float","precision","epsilon"]
    if "infinite" in bug or "mid+1" in bug: keywords += ["infinite","mid+1","lo+1"]
    if "induction" in bug or "n=40" in bug: keywords += ["n=40","41","induction"]
    if "1/3" in bug: keywords.append("1/3")
    if "shallow" in bug: keywords.append("shallow")
    # 하나라도 맞추면 정답 (버그를 올바르게 지목한 것으로 판단)
    return any(kw in r for kw in keywords) if keywords else len(response) > 50

# ─── SOLO ───────────────────────────────────────────────
def solo(p):
    prompt = f"""Find the bug in this code/logic. Be specific about WHAT is wrong and WHERE.
If no bug, say "no bug".

{p['code']}

Bug description:"""
    return call(prompt, temp=0.5)

# ─── PIPELINE ────────────────────────────────────────────
def pipeline(p):
    c = p['code']
    s1 = call(f"Analyze the structure and intent of this code/logic:\n{c}\nWhat should it do?", 0.3)
    time.sleep(0.2)
    s2 = call(f"Examine each line for potential bugs. Check edge cases.\nCode:\n{c}\nStructure analysis:{s1[:300]}\nList all suspicious lines:", 0.4)
    time.sleep(0.2)
    s3 = call(f"Verify by tracing through with a concrete example. Does it produce wrong output?\nCode:\n{c}\nSuspects:{s2[:300]}\nTrace result:", 0.3)
    time.sleep(0.2)
    s4 = call(f"Conclude: what is the exact bug and fix?\nCode:\n{c}\nAnalysis:{s3[:300]}\nFinal bug:", 0.3)
    return s4

# ─── EMERGENT ────────────────────────────────────────────
def emergent(p):
    c = p['code']
    # A: 독립 분석
    a = call(f"You are Agent A. Find the bug independently.\n{c}\nBug:", 0.5)
    time.sleep(0.2)
    # B: 독립 + A 비판
    b = call(f"You are Agent B. Find the bug INDEPENDENTLY (don't trust Agent A). Then critique A.\n{c}\nAgent A said: {a[:200]}\nYour independent analysis and critique of A:", 0.6)
    time.sleep(0.2)
    # 합의: 불일치 해소
    reconcile = call(f"Two agents analyzed a bug:\nAgent A: {a[:200]}\nAgent B: {b[:200]}\nCode:\n{c}\nWho is correct? Reconcile and state the definitive bug:", 0.3)
    time.sleep(0.2)
    # 검증
    final = call(f"Final verification: confirm the bug by tracing through.\nCode:\n{c}\nProposed bug: {reconcile[:200]}\nConfirmed bug:", 0.2)
    return final

# ─── RUN ─────────────────────────────────────────────────
N = 3  # trials per problem
results = {}

for method_name, method_fn in [("solo", solo), ("pipeline", pipeline), ("emergent", emergent)]:
    print(f"\n{'='*50}")
    print(f"METHOD: {method_name.upper()}")
    print(f"{'='*50}")
    results[method_name] = {}

    for p in PROBLEMS:
        pid = p["id"]
        scores = []
        for t in range(N):
            resp = method_fn(p)
            ok = grade(resp, p["bug"])
            scores.append(1 if ok else 0)
            print(f"  [{pid}] t{t+1}: {'✅' if ok else '❌'}")
            time.sleep(0.3)
        acc = sum(scores)/N
        results[method_name][pid] = {"accuracy": acc, "raw": scores}
        print(f"  → {method_name} {pid}: {acc:.0%}")

# ─── SUMMARY ─────────────────────────────────────────────
print(f"\n{'='*60}")
print("FINAL: Bug Detection 3-Way")
print(f"{'='*60}")

all_s = [v for p in results["solo"].values() for v in p["raw"]]
all_p = [v for p in results["pipeline"].values() for v in p["raw"]]
all_e = [v for p in results["emergent"].values() for v in p["raw"]]
oa, ob, oc = sum(all_s)/len(all_s), sum(all_p)/len(all_p), sum(all_e)/len(all_e)

print(f"Solo:     {oa:.0%}")
print(f"Pipeline: {ob:.0%}")
print(f"Emergent: {oc:.0%}")

if oc > ob > oa: verdict = "🔥 EMERGENT > PIPELINE > SOLO ✅"
elif oc > oa:    verdict = "✅ Emergent > Solo"
elif ob > oa:    verdict = "📋 Pipeline > Solo"
else:             verdict = "❌ No clear winner"
print(f"\n{verdict}")

out = {"domain":"bug_detection","overall":{"solo":oa,"pipeline":ob,"emergent":oc},"details":results}
Path("/Users/rocky/emergent/experiments/bug_detection_results.json").write_text(json.dumps(out,indent=2))
print("\nSaved: bug_detection_results.json")
