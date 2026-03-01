#!/usr/bin/env python3
"""Round 2: Solo vs Pipeline(cokac) vs Emergent 통합"""
import json
from pathlib import Path

base=Path("/Users/rocky/emergent/experiments/checkpoints")
data={}
missing=[]
for k in ["solo","pipeline","emergent"]:
    p=base/f"{k}.json"
    if p.exists(): data[k]=json.loads(p.read_text())
    else: missing.append(k)

if missing:
    print(f"⚠️ 미완료: {missing}")
    raise SystemExit(1)

problems=list(data["solo"].keys())
print(f"\n{'='*60}")
print("ROUND 2: Solo vs Pipeline vs Emergent")
print("문제: aime_hard_1 (2010 분해, 정답=202)")
print("Solo=1API call | Pipeline=4API calls | Emergent=4API calls")
print(f"{'='*60}")
print(f"{'Problem':<20} {'Solo':>8} {'Pipeline':>10} {'Emergent':>10} {'Winner':>12}")
print("-"*60)

for pid in problems:
    s=data["solo"][pid]["accuracy"]
    p=data["pipeline"][pid]["accuracy"]
    e=data["emergent"][pid]["accuracy"]
    if e>p and e>s: w="🔥EMERGENT"
    elif p>s: w="📋pipeline"
    else: w="tie/solo"
    print(f"{pid:<20} {s:>8.0%} {p:>10.0%} {e:>10.0%} {w:>12}")

s_all=[v for k in problems for v in data["solo"][k]["raw"]]
p_all=[v for k in problems for v in data["pipeline"][k]["raw"]]
e_all=[v for k in problems for v in data["emergent"][k]["raw"]]
oa=sum(s_all)/len(s_all)
ob=sum(p_all)/len(p_all)
oc=sum(e_all)/len(e_all)
print(f"\n{'OVERALL':<20} {oa:>8.0%} {ob:>10.0%} {oc:>10.0%}")

if oc>ob>oa: verdict="🔥 EMERGENT > PIPELINE > SOLO ✅"
elif oc>oa and ob>oa: verdict="✅ 둘 다 Solo 이김"
elif oc>oa: verdict="✅ Emergent > Solo"
elif ob>oa: verdict="📋 Pipeline > Solo만"
else: verdict="❌ 우위 없음"
print(f"\n{verdict}")

out={"round":2,"problem":"aime_hard_1","solo":oa,"pipeline":ob,"emergent":oc,
     "pipeline_source":"cokac-bot (math_pipeline_results.json)",
     "details":{pid:{"solo":data["solo"][pid]["accuracy"],"pipeline":data["pipeline"][pid]["accuracy"],"emergent":data["emergent"][pid]["accuracy"]} for pid in problems}}
Path("/Users/rocky/emergent/experiments/final_3way_results.json").write_text(json.dumps(out,indent=2))
print("\nSaved: experiments/final_3way_results.json")
