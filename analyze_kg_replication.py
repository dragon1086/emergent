#!/usr/bin/env python3
"""
4-way KG replication CSER 분석
논문의 2x2 실험 결과를 LaTeX 표 형태로 출력
"""
import json
from pathlib import Path

REPO = Path(__file__).parent

def get_cser(path):
    d = json.load(open(path))
    edges = d.get('edges', [])
    if not edges:
        return 0.0, 0, len(d.get('nodes', []))
    cross = sum(1 for e in edges if e.get('cross_source', False))
    if cross == 0:  # fallback: node source comparison
        nodes = {n['id']: n for n in d.get('nodes', [])}
        for e in edges:
            sn = nodes.get(e.get('from',''), {})
            tn = nodes.get(e.get('to',''), {})
            if sn.get('source','') != tn.get('source','') and sn.get('source','') and tn.get('source',''):
                cross += 1
    return round(cross/len(edges), 4), len(edges), len(d.get('nodes', []))

instances = [
    ('KG-main', 'data/knowledge-graph.json', 'claude-sonnet-4-6', 'gpt-5.2', 'Cross-vendor'),
    ('KG-2',    'kg2/data/knowledge-graph.json', 'gpt-4o', 'gpt-4o-mini', 'Same-vendor (OpenAI)'),
    ('KG-3',    'kg3/data/knowledge-graph.json', 'gpt-4o', 'gemini-2.0-flash', 'Cross-vendor'),
    ('KG-4',    'kg4/data/knowledge-graph.json', 'gemini-2.0-flash', 'gemini-2.0-pro', 'Same-vendor (Google)'),
]

results = []
for name, rel_path, agent_a, agent_b, vendor_type in instances:
    path = REPO / rel_path
    cser, edges, nodes = get_cser(path)
    gate = "✅" if cser >= 0.30 else "❌"
    results.append((name, agent_a, agent_b, vendor_type, nodes, edges, cser, gate))
    print(f"{name} ({vendor_type}): {agent_a} × {agent_b}")
    print(f"  nodes={nodes}, edges={edges}, CSER={cser:.4f} {gate}")

print()
print("=" * 60)
print("LaTeX 표 출력:")
print("=" * 60)
print(r"\begin{table}[h!]\centering\small")
print(r"\begin{tabular}{llcccc}")
print(r"\toprule")
print(r"Instance & Configuration & Vendor & Edges & CSER & Gate \\")
print(r"\midrule")
for name, agent_a, agent_b, vendor_type, nodes, edges, cser, gate in results:
    a_short = agent_a.split('/')[-1] if '/' in agent_a else agent_a
    b_short = agent_b.split('/')[-1] if '/' in agent_b else agent_b
    gate_tex = r"\checkmark" if cser >= 0.30 else r"\times"
    vtype_short = "Same" if "Same" in vendor_type else "Cross"
    print(f"{name} & {a_short} $\\times$ {b_short} & {vtype_short} & {edges} & {cser:.4f} & ${gate_tex}$ \\\\")
print(r"\bottomrule")
print(r"\end{tabular}")
print(r"\caption{Four KG instances: CSER values (preliminary, ongoing).}")
print(r"\end{table}")
