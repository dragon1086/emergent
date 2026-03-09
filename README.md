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
