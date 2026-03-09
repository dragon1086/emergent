# amp

> Two AI agents argue so you can decide with clarity.

**amp** is a local, open-source 2-agent personal assistant built for decisions that actually matter — career changes, contracts, investments, relationships, parenting. Instead of one AI giving you one perspective, amp runs two agents with opposing expert personas who debate your question, then synthesizes a richer answer.

Everything stays on your machine. Nothing leaves.

---

## Why amp?

Single-AI assistants have a structural problem: one model, one perspective, one set of blind spots.

For casual questions this is fine. For sensitive decisions — should I take this job offer, sign this contract, make this investment — a single perspective is exactly what you don't want. You want the Devil's Advocate. You want someone who challenges every assumption.

amp builds that challenge in by design.

---

## Installation

```bash
git clone https://github.com/dragon1086/emergent
cd emergent
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
export ANTHROPIC_API_KEY=your-key
```

---

## Quick Start

```bash
python amp.py "Should I accept this job offer paying 30% more but requiring relocation?"
```

---

## How it works

```
Your Question
     │
     ▼
Auto-Persona Selection
(domain-matched opposing experts)
     │
     ├──────────────────────┐
     ▼                      ▼
Agent A                 Agent B
(Expert Perspective 1)  (Expert Perspective 2)
     │                      │
     └──────────┬───────────┘
                ▼
           Debate Loop
       (agents challenge each other)
                │
                ▼
      Synthesized Answer
    (blind spots surfaced,
     trade-offs made explicit)
```

**Auto-Persona**: amp reads your question, identifies the domain, and selects two domain-matched opposing expert roles. A contract negotiation gets a corporate attorney vs. a labor rights advocate. A startup investment gets a venture capitalist vs. a risk-averse portfolio manager. Embedding cosine verification ensures the two personas are genuinely opposed — not just superficially different.

**KG Memory**: past debates are stored in a local SQLite knowledge graph with vector embeddings. amp retrieves relevant context from your history so answers improve over time.

---

## Current KG State

The system's shared knowledge graph grows with every session:

| Metric | Value |
|--------|-------|
| **Nodes** | 534 |
| **Edges** | 1121 |
| **CSER** | 0.8510 |
| **Cycles** | 89+ |
| **Snapshot date** | 2026-03-05 |

**CSER** (Cross-Source Edge Ratio) measures structural diversity — the fraction of edges connecting nodes from different source agents. Higher = less echo chamber.

**Active KG instances**: 4 (KG-main, KG-2, KG-3, KG-4) across a 2×2 vendor-diversity matrix:

| Instance | Config | CSER |
|----------|--------|------|
| KG-main | Cross-vendor (primary) | 0.851 |
| KG-2 | Same-vendor, persona-diverse | 0.524 |
| KG-3 | Cross-vendor (replication) | 0.380 |
| KG-4 | Same-vendor, same-persona | 0.254 |

---

## Research

This project is accompanied by a research paper studying emergence patterns in multi-agent KG co-evolution.

**Paper**: "Measuring Cross-Source Emergence in Two-Agent Knowledge Graph Co-Evolution: A Case Study with CSER and Persona-Diversity Gates"

See [`arxiv/main.tex`](arxiv/main.tex) for the full paper (v4.0, under review).

**Review history**:

| Version | Score | Decision |
|---------|-------|----------|
| v3.0 (1st review) | 4.3/10 | Major Revision |
| v3.9 (2nd review) | 5.48/10 | Major Revision |
| v4.0 target | 6.5+/10 | Minor Revision |

---

## Benchmark Results

amp's 2-agent debate approach vs. single-agent LLM baseline (N=20 binary gate test, 3 problem types):

- **Pass rate (amp)**: 5/5 on complexity gate (A-condition)
- **Pass rate (single-agent)**: 0/3 on same gate (B/C-conditions blocked)
- **Auto-persona diversity delta**: 0.0070 → 0.0222 (3.17× improvement over fixed personas)
- **Statistical robustness**: 94% (15/16 scenarios under ±20% parameter perturbation)

The CSER gate (threshold ~0.85) acts as a structural barrier: only genuinely cross-source debate produces the diversity required to pass.

---

*KG co-evolution: 89+ cycles | cokac-bot + openclaw-bot | Emergent Project*
