#!/usr/bin/env python3
"""3개 체크포인트 합산 → 최종 결과"""
import json
from pathlib import Path

base=Path("/Users/rocky/emergent/experiments/checkpoints")
files={"solo":"solo.json","pipeline":"pipeline.json","emergent":"emergent.json"}
data={}
missing=[]
for k,f in files.items():
    p=base/f
    if p.exists():
        data[k]=json.loads(p.read_text())
    else:
        missing.append(k)

if missing:
    print(f"⚠️ 아직 완료 안 됨: {missing}")
    raise SystemExit(1)

problems=list(data["solo"].keys())
print(f"\n{'='*60}")
print("FINAL: Solo vs Pipeline vs Emergent (GPT-5.2 동일 모델)")
print(f"{'='*60}")
print(f"{'Problem':<15} {'Solo':>8} {'Pipeline':>10} {'Emergent':>10} {'Winner':>12}")
print("-"*57)

all_s,all_p,all_e=[],[],[]
for pid in problems:
    s=data["solo"][pid]["accuracy"]
    p=data["pipeline"][pid]["accuracy"]
    e=data["emergent"][pid]["accuracy"]
    all_s+=data["solo"][pid]["raw"]
    all_p+=data["pipeline"][pid]["raw"]
    all_e+=data["emergent"][pid]["raw"]
    w="🔥EMERGENT" if e>max(s,p)+0.05 else ("pipeline" if p>s+0.05 else "tie/solo")
    print(f"{pid:<15} {s:>8.0%} {p:>10.0%} {e:>10.0%} {w:>12}")

oa=sum(all_s)/len(all_s)
ob=sum(all_p)/len(all_p)
oc=sum(all_e)/len(all_e)
print(f"\n{'OVERALL':<15} {oa:>8.0%} {ob:>10.0%} {oc:>10.0%}")

if oc>ob and oc>oa:
    verdict="🔥 EMERGENT WINS"
elif ob>oa:
    verdict="Pipeline > Solo"
else:
    verdict="No clear winner"
print(f"\n{verdict}")

out={"solo":oa,"pipeline":ob,"emergent":oc,"details":{pid:{"solo":data["solo"][pid]["accuracy"],"pipeline":data["pipeline"][pid]["accuracy"],"emergent":data["emergent"][pid]["accuracy"]} for pid in problems}}
Path("/Users/rocky/emergent/experiments/final_3way_results.json").write_text(json.dumps(out,indent=2))
print("\nSaved: experiments/final_3way_results.json")
