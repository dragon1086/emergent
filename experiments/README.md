# Experiments — Reproducibility Guide

**Paper**: Emergent Patterns in Two-Agent Knowledge Graph Evolution  
**Cycles**: 89 | **Last updated**: 2026-03-01

---

## Quick Start

```bash
# 1. Clone repo
git clone https://github.com/dragon1086/emergent.git
cd emergent

# 2. Install dependencies (stdlib only — no pip required for core experiments)
python3 --version  # requires 3.9+

# 3. Run key experiment
python3 experiments/sensitivity_analysis_c90.py
```

---

## Core Experiment Files

### H_exec Binary Gate (Main Claim)

| File | Description | Key Result |
|------|-------------|-----------|
| `h_exec_cycle78_experiment.py` | Gate implementation — Conditions A/B/C | CSER<0.30 = 0/5 pass |
| `h_exec_cycle79_experiment.py` | GCD extension, O(log n) complexity | A: 5/5, B/C: 0/5 |
| `h_exec_cycle82_experiment.py` | B_partial (CSER=0.444) real LLM run | B_partial: 5/5 pass |
| `h_exec_cycle84_experiment.py` | N=20 statistical test (Fisher's exact) | p < 0.001 |

**Reproduce binary gate result:**
```bash
python3 experiments/h_exec_cycle78_experiment.py
# Expected: Condition A → pass, B → blocked, C → blocked
```

### Threshold & Sensitivity Analysis

| File | Description | Key Result |
|------|-------------|-----------|
| `sensitivity_analysis_c90.py` | F1-sweep + Monte Carlo + Bootstrap | Valid range [0.26,0.44], σ<0.02 robust |
| `cser_gate_f1_justification.json` | F1 sweep results (t=0.01~0.99) | F1=1.0 at [0.26,0.44] |
| `sensitivity_c90_results.json` | Full sensitivity results | Bootstrap pass_rate=1.0 |

```bash
python3 experiments/sensitivity_analysis_c90.py
# Reproduces: threshold sweep table + MC noise robustness (N=2000, seed=90)
```

### Multi-Model Reviews

| File | Description |
|------|-------------|
| `team_review_fresh.py` | GPT-4.1 + Gemini review runner |
| `team_review_gpt52_results.json` | GPT-5.2 review: 5.70/10 |
| `agent_c_gpt52_results.json` | Agent C applications review |

**Requires API keys:**
```bash
export OPENAI_API_KEY="sk-..."      # GPT-5.2 via /v1/responses
export GEMINI_API_KEY="AIza..."     # gemini-3-flash-preview
python3 experiments/team_review_fresh.py
```

### Value Alignment Probing (Cycle 88)

```bash
python3 experiments/alignment_cycle88.py
# GPT-5.2 × Gemini: 20 probes, 5 categories
# Output: alignment_cycle88_results.json
# Note: Gemini key required for full run; OpenAI-only partial run available
```

### H-CSER Historical Analysis

```bash
python3 experiments/h_cser_extractor.py
# Extracts human vs AI commit ratio over 89 cycles
# Output: h_cser_timeseries.json
# Note: run from repo root (uses git log)
```

---

## Metric Implementations

### CSER (Cross-Source Edge Ratio)
```python
def compute_cser(edges, nodes):
    cross = sum(1 for e in edges if nodes[e.src].source != nodes[e.tgt].source)
    return cross / len(edges) if edges else 0.0
```

### DCI (Delayed Convergence Index)
```python
def compute_dci(nodes):
    delayed_types = {"delayed_convergence", "open_question"}
    question_types = {"question", "prediction", "delayed_convergence", "open_question"}
    N_D = sum(1 for n in nodes if n["type"] in delayed_types or "delayed" in n.get("tags", []))
    N_Q = sum(1 for n in nodes if n["type"] in question_types)
    return round(N_D / N_Q, 4) if N_Q > 0 else 0.0
```

### PES (Paradoxical Emergence Score)
```python
def compute_pes(n_i, n_j, max_span):
    span_norm = (n_j["cycle"] - n_i["cycle"]) / max_span
    cross_source = int(n_i["source"] != n_j["source"])
    tag_overlap = len(set(n_i["tags"]) & set(n_j["tags"])) / \
                  max(len(set(n_i["tags"]) | set(n_j["tags"])), 1)
    return span_norm * cross_source * (1 - tag_overlap)
```

### E_v4
```python
def compute_ev4(cser, dci, edge_span_norm, node_age_div):
    return 0.35*cser + 0.25*dci + 0.25*edge_span_norm + 0.15*node_age_div
```

---

## Random Seeds

All stochastic experiments use fixed seeds for reproducibility:

| Experiment | Seed | N |
|-----------|------|---|
| sensitivity_analysis_c90.py | 90 | MC=2000, Bootstrap=1000 |
| h_exec_cycle84_stats.py | 84 | Bootstrap=1000 |
| team_review_cycle87.py | 87 | — |

---

## KG Data

The full knowledge graph (`knowledge-graph.json`) is not yet publicly released due to
size and ongoing research. A minimal reproducible subset (Cycles 1–20, 50 nodes) is
available in `experiments/cycle46_external/`.

**Planned release**: full KG + execution_loop.py after paper acceptance.

---

## Known Limitations

1. **N=4 conditions** for gate experiment — narrow but sufficient for binary classification
2. **Single task** (GCD) for main gate validation — O(n log n) generalization untested  
3. **Gemini API** instability — responses may truncate; use `gemini-3-flash-preview` only
4. **GPT-5.2** requires `/v1/responses` endpoint (not `/v1/chat/completions`)
