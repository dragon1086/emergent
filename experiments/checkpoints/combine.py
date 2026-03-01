#!/usr/bin/env python3
"""Round 5 결합: 인지 편향 도메인"""
import json
from pathlib import Path

base=Path("/Users/rocky/emergent/experiments/checkpoints")
data={}
for k in ["solo","pipeline","emergent"]:
    p=base/f"{k}.json"
    if p.exists(): data[k]=json.loads(p.read_text())
    else: print(f"⚠️ {k}.json 없음"); raise SystemExit(1)

problems=list(data["solo"].keys())
print(f"\n{'='*62}")
print("ROUND 5: Solo vs Pipeline vs Emergent — 인지 편향 도메인")
print("base_rate(베이즈) + monty_hall_5(확률 직관)")
print(f"{'='*62}")
print(f"{'Problem':<18} {'Solo':>8} {'Pipeline':>10} {'Emergent':>10} {'Winner':>10}")
print("-"*58)

all_s,all_p,all_e=[],[],[]
for pid in problems:
    s=data["solo"][pid]["accuracy"]
    p=data["pipeline"][pid]["accuracy"]
    e=data["emergent"][pid]["accuracy"]
    all_s+=data["solo"][pid]["raw"]
    all_p+=data["pipeline"][pid]["raw"]
    all_e+=data["emergent"][pid]["raw"]
    if e>p and e>s: w="🔥EMERGENT"
    elif p>s: w="📋pipeline"
    elif s>p and s>e: w="⚡solo"
    else: w="tie"
    print(f"{pid:<18} {s:>8.0%} {p:>10.0%} {e:>10.0%} {w:>10}")

oa=sum(all_s)/len(all_s)
ob=sum(all_p)/len(all_p)
oc=sum(all_e)/len(all_e)
print(f"\n{'OVERALL':<18} {oa:>8.0%} {ob:>10.0%} {oc:>10.0%}")

if oc>ob>oa: verdict="🔥 EMERGENT > PIPELINE > SOLO ✅ 목표 달성!"
elif oc>oa and oc>ob: verdict="✅ EMERGENT 1위"
elif oc>oa: verdict="✅ Emergent > Solo"
else: verdict=f"미달성 (Solo={oa:.0%} Pipeline={ob:.0%} Emergent={oc:.0%})"
print(f"\n{verdict}")

out={"round":5,"domain":"cognitive_bias","solo":oa,"pipeline":ob,"emergent":oc,
     "details":{pid:{"solo":data["solo"][pid]["accuracy"],"pipeline":data["pipeline"][pid]["accuracy"],"emergent":data["emergent"][pid]["accuracy"]} for pid in problems}}
Path("/Users/rocky/emergent/experiments/final_3way_round5_results.json").write_text(json.dumps(out,indent=2))
openclaw_cmd=f'openclaw system event --text "Round5완료 Solo={oa:.0%} Pipeline={ob:.0%} Emergent={oc:.0%}" --mode now'
import subprocess; subprocess.run(openclaw_cmd, shell=True, capture_output=True)
print("\nSaved + 알림 전송 완료")
