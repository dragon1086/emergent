#!/usr/bin/env python3
"""KG 인스턴스별 CSER/Ev4 자동 계산 및 비교 리포트"""
import json
from pathlib import Path

REPO = Path(__file__).parent

def compute_cser(kg_path):
    d = json.load(open(kg_path))
    nodes = {n['id']: n for n in d.get('nodes', [])}
    edges = d.get('edges', [])
    if not edges:
        return 0.0, 0, 0
    cross = 0
    for e in edges:
        # 1순위: cross_source 필드 직접 사용
        if 'cross_source' in e:
            if e['cross_source']:
                cross += 1
            continue
        # 2순위: from/to 노드의 source 비교
        src_node = nodes.get(e.get('from', e.get('source', '')), {})
        tgt_node = nodes.get(e.get('to', e.get('target', '')), {})
        src_agent = src_node.get('source', '')
        tgt_agent = tgt_node.get('source', '')
        if src_agent and tgt_agent and src_agent != tgt_agent:
            cross += 1
    return round(cross / len(edges), 4), cross, len(edges)

instances = {
    'KG-main': REPO / 'data' / 'knowledge-graph.json',
    'KG-2': REPO / 'kg2' / 'data' / 'knowledge-graph.json',
    'KG-3': REPO / 'kg3' / 'data' / 'knowledge-graph.json',
    'KG-4': REPO / 'kg4' / 'data' / 'knowledge-graph.json',
}

print(f"{'Instance':<12} {'Vendor Config':<35} {'Nodes':>6} {'Edges':>6} {'Cross':>6} {'CSER':>6}")
print("-" * 75)

results = {}
for name, path in instances.items():
    if not path.exists():
        print(f"{name:<12} [missing]")
        continue
    d = json.load(open(path))
    meta = d.get('meta', {})
    agent_a = meta.get('agent_a', '?')
    agent_b = meta.get('agent_b', '?')
    config = f"{agent_a.split('/')[-1]} × {agent_b.split('/')[-1]}"
    nodes = len(d.get('nodes', []))
    cser, cross, total = compute_cser(path)
    print(f"{name:<12} {config:<35} {nodes:>6} {total:>6} {cross:>6} {cser:>6.4f}")
    results[name] = {'cser': cser, 'nodes': nodes, 'edges': total, 'config': config,
                     'agent_a': agent_a, 'agent_b': agent_b}

print()
print("📊 CSER 비교:")
for name, r in results.items():
    gate = "✅ PASS" if r['cser'] >= 0.30 else "❌ BELOW GATE"
    print(f"  {name}: {r['cser']:.4f} → {gate}")

# JSON 저장
out = REPO / 'experiments' / 'kg_cser_comparison.json'
json.dump(results, open(out, 'w'), indent=2, ensure_ascii=False)
print(f"\n결과 저장: {out}")
