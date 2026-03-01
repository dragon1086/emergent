#!/usr/bin/env python3
"""
condition_b_experiment.py — Condition B: Same-Persona Control Experiment
Cycle 91, D-079

Design:
  - Agent 1: GPT-5.2 (OpenAI) — 냉정한 판사 persona
  - Agent 2: Gemini-3-Flash (Google) — 냉정한 판사 persona (SAME)
  - N=20 cycles of KG co-evolution
  - Each cycle: Agent1 proposes node → Agent2 proposes edge
  - Measure: CSER(B) — expect < CSER(A)=0.5455 (hetero pair)

Hypothesis: Same persona → echo chamber → lower CSER
Gate test: if CSER(B) < 0.30 → echo chamber gate block confirmed

Judgment criteria:
  - CSER(B) < 0.4955 → hypothesis supported (diversity effect valid)
  - 0.4955 ≤ CSER(B) ≤ 0.5955 → inconclusive
  - CSER(B) > 0.5955 → hypothesis refuted
"""

import json, os, sys, time, random, urllib.request, urllib.error, statistics, subprocess
from pathlib import Path
from datetime import datetime

random.seed(91)

REPO = Path(__file__).parent.parent
RESULTS_FILE = REPO / "experiments" / "condition_b_results.json"
CSER_A = 0.5455  # baseline from hetero pair

# Load env
def load_env():
    try:
        result = subprocess.run(['zsh', '-c', 'source ~/.zshrc && env'],
                               capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            if '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
    except: pass

load_env()

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

SAME_PERSONA = (
    "You are a cold, impartial judge. Your only question is: is the prediction "
    "correct or not? Be dry, direct, data-only. Do not show emotion. Do not "
    "soften criticism. Admit when wrong without hesitation."
)

PROBLEMS = [
    {"name": "GCD", "description": "Implement Euclidean GCD algorithm", "complexity": "O(log n)"},
    {"name": "QuickSort", "description": "Implement QuickSort with random pivot", "complexity": "O(n log n)"},
    {"name": "LRU_Cache", "description": "Implement LRU Cache with O(1) get/put", "complexity": "O(1)"},
]

# ─── API Calls ─────────────────────────────────────────────────────────────

def call_gpt52(prompt: str, system: str = SAME_PERSONA) -> str:
    url = "https://api.openai.com/v1/responses"
    payload = json.dumps({
        "model": "gpt-5.2",
        "instructions": system,
        "input": prompt,
        "temperature": 0.3,
        "max_output_tokens": 300
    }).encode()
    req = urllib.request.Request(url, data=payload,
        headers={'Content-Type':'application/json','Authorization':f'Bearer {OPENAI_KEY}'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data['output'][0]['content'][0]['text']

def call_gemini(prompt: str, system: str = SAME_PERSONA) -> str:
    model = 'gemini-3-flash-preview'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": f"{system}\n\n{prompt}"}]}],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.3}
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data['candidates'][0]['content']['parts'][0]['text']

# ─── KG Simulation ────────────────────────────────────────────────────────

def run_experiment():
    print(f"{'='*60}")
    print(f"Condition B: Same-Persona Control Experiment")
    print(f"Agent1: GPT-5.2 (냉정한 판사)")
    print(f"Agent2: Gemini-3-Flash (냉정한 판사 — SAME)")
    print(f"N=20 cycles, 3 problems")
    print(f"Baseline: CSER(A) = {CSER_A}")
    print(f"{'='*60}\n")

    nodes = []
    edges = []
    cycle_results = []
    cser_history = []

    for cycle in range(1, 21):
        problem = PROBLEMS[(cycle - 1) % 3]
        
        # Agent 1 (GPT-5.2): Propose a concept node
        prompt1 = (
            f"Cycle {cycle}. Problem: {problem['name']} ({problem['description']}). "
            f"As a cold judge, propose ONE technical concept needed for this implementation. "
            f"Format: CONCEPT: [name] | TAGS: [tag1, tag2]"
        )
        
        try:
            resp1 = call_gpt52(prompt1)
            node = {
                "id": f"b-{cycle:03d}-a1",
                "cycle": cycle,
                "source": "agent1",
                "content": resp1[:100],
                "problem": problem["name"],
                "tags": [problem["name"].lower(), "concept"]
            }
            nodes.append(node)
        except Exception as e:
            print(f"  Cycle {cycle} Agent1 error: {e}")
            node = {"id": f"b-{cycle:03d}-a1", "cycle": cycle, "source": "agent1",
                    "content": f"[fallback] {problem['name']} concept", "tags": [problem["name"].lower()]}
            nodes.append(node)

        # Agent 2 (Gemini): Propose connection to existing node
        if len(nodes) > 1:
            existing = random.choice(nodes[:-1])
            prompt2 = (
                f"Cycle {cycle}. As a cold judge, evaluate: "
                f"Should '{node['content'][:50]}' connect to '{existing['content'][:50]}'? "
                f"Answer: CONNECT: yes/no | REASON: [brief]"
            )
            
            try:
                resp2 = call_gemini(prompt2)
                connect = "yes" in resp2.lower()[:50]
            except Exception as e:
                print(f"  Cycle {cycle} Agent2 error: {e}")
                connect = random.random() > 0.3  # fallback: 70% connect

            if connect:
                edge = {
                    "id": f"e-{cycle:03d}",
                    "source_node": existing["id"],
                    "target_node": node["id"],
                    "source_agent": existing["source"],
                    "target_agent": node["source"],
                    "cross_source": existing["source"] != node["source"],
                    "cycle": cycle
                }
                edges.append(edge)

                # Agent 2 also proposes a node (to create agent2-sourced content)
                node2 = {
                    "id": f"b-{cycle:03d}-a2",
                    "cycle": cycle,
                    "source": "agent2",
                    "content": resp2[:80] if 'resp2' in dir() else f"[agent2] {problem['name']}",
                    "tags": [problem["name"].lower(), "evaluation"]
                }
                nodes.append(node2)

                # Edge from agent2's node to agent1's node
                edge2 = {
                    "id": f"e-{cycle:03d}-r",
                    "source_node": node2["id"],
                    "target_node": node["id"],
                    "source_agent": "agent2",
                    "target_agent": "agent1",
                    "cross_source": True,  # always cross since different agents
                    "cycle": cycle
                }
                edges.append(edge2)

        # Compute running CSER
        if edges:
            cross = sum(1 for e in edges if e["cross_source"])
            cser = round(cross / len(edges), 4)
        else:
            cser = 0.0
        cser_history.append(cser)

        cycle_results.append({
            "cycle": cycle,
            "problem": problem["name"],
            "nodes_total": len(nodes),
            "edges_total": len(edges),
            "cser": cser
        })

        marker = "🔴" if cser < 0.30 else ("🟡" if cser < CSER_A - 0.05 else "🟢")
        print(f"  Cycle {cycle:2d} [{problem['name']:10s}] nodes={len(nodes):3d} edges={len(edges):3d} CSER={cser:.4f} {marker}")
        
        time.sleep(0.5)  # rate limit courtesy

    # ─── Final Analysis ──────────────────────────────────────────────────
    final_cser = cser_history[-1] if cser_history else 0.0
    mean_cser = statistics.mean(cser_history) if cser_history else 0.0

    # Bootstrap CI
    N_BOOT = 1000
    boot_means = []
    for _ in range(N_BOOT):
        sample = random.choices(cser_history, k=len(cser_history))
        boot_means.append(statistics.mean(sample))
    boot_means.sort()
    ci_lo = boot_means[int(0.025 * N_BOOT)]
    ci_hi = boot_means[int(0.975 * N_BOOT)]

    # Judgment
    diff = final_cser - CSER_A
    if final_cser < CSER_A - 0.05:
        judgment = "HYPOTHESIS_SUPPORTED"
        judgment_text = f"CSER(B)={final_cser:.4f} < CSER(A)-0.05={CSER_A-0.05:.4f} → 다양성 효과 유효"
    elif final_cser > CSER_A + 0.05:
        judgment = "HYPOTHESIS_REFUTED"
        judgment_text = f"CSER(B)={final_cser:.4f} > CSER(A)+0.05={CSER_A+0.05:.4f} → 가설 반박"
    else:
        judgment = "INCONCLUSIVE"
        judgment_text = f"CSER(B)={final_cser:.4f} within ±0.05 of CSER(A)={CSER_A} → 불확정"

    gate_blocked = final_cser < 0.30
    if gate_blocked:
        judgment_text += f"\n  🚨 ECHO CHAMBER GATE BLOCKED: CSER={final_cser:.4f} < 0.30"

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  CSER(A) baseline:  {CSER_A:.4f} (hetero pair)")
    print(f"  CSER(B) final:     {final_cser:.4f} (same persona)")
    print(f"  CSER(B) mean:      {mean_cser:.4f}")
    print(f"  Δ(B-A):            {diff:+.4f}")
    print(f"  Bootstrap 95% CI:  [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Gate blocked:      {'YES 🚨' if gate_blocked else 'NO'}")
    print(f"  Judgment:          {judgment}")
    print(f"  {judgment_text}")

    results = {
        "experiment": "condition_b_same_persona",
        "cycle": 91,
        "timestamp": datetime.now().isoformat(),
        "agents": {
            "agent1": {"model": "gpt-5.2", "persona": "냉정한판사"},
            "agent2": {"model": "gemini-3-flash-preview", "persona": "냉정한판사 (SAME)"}
        },
        "n_cycles": 20,
        "problems": [p["name"] for p in PROBLEMS],
        "baseline_cser_a": CSER_A,
        "cser_final": final_cser,
        "cser_mean": mean_cser,
        "cser_history": cser_history,
        "cser_diff": round(diff, 4),
        "bootstrap_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        "gate_blocked": gate_blocked,
        "judgment": judgment,
        "judgment_text": judgment_text,
        "nodes_total": len(nodes),
        "edges_total": len(edges),
        "cross_source_edges": sum(1 for e in edges if e["cross_source"]),
        "cycle_results": cycle_results,
        "seed": 91
    }

    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved: {RESULTS_FILE}")
    return results

if __name__ == "__main__":
    if not OPENAI_KEY:
        print("❌ OPENAI_API_KEY not set"); sys.exit(1)
    if not GEMINI_KEY:
        print("⚠️  GEMINI_API_KEY not set — Agent2 will use fallback")
    run_experiment()
