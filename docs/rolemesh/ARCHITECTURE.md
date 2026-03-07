# RoleMesh Architecture

> Auto-Persona matching engine for amp's 2-agent debate system

## Overview

RoleMesh is the persona selection and opposition-verification layer within amp. It takes a user question, identifies the decision domain, and returns two genuinely opposed expert personas for the debate loop.

## Core Pipeline

```
User Question
     |
     v
[1] Domain Classifier
     |  - Embedding-based topic detection
     |  - Maps to one of 10 preset domains (or "custom")
     v
[2] Persona Selector
     |  - Preset domains: lookup from persona_presets.py
     |  - Custom domains: LLM-generated pair via persona_dynamic.py
     v
[3] Opposition Verifier
     |  - Compute cosine distance between persona embeddings
     |  - Threshold: distance >= 0.35 (tuned via benchmark)
     |  - If below threshold: regenerate until opposition confirmed
     v
[4] Persona Pair Output
     - agent_a: {name, role, system_prompt, stance}
     - agent_b: {name, role, system_prompt, stance}
```

## Components

### Domain Classifier

Classifies user input into one of the following domains:

| Domain | Trigger patterns |
|--------|-----------------|
| Career | job, promotion, resign, career change |
| Relationship | partner, marriage, breakup, family |
| Business | startup, revenue, strategy, launch |
| Investment | stock, portfolio, fund, valuation |
| Legal | contract, lawsuit, compliance, rights |
| Technology | architecture, stack, migration, security |
| Health | diagnosis, treatment, lifestyle, symptoms |
| Education | degree, course, certification, learning |
| Conflict | dispute, negotiation, confrontation |
| Creative | writing, design, art, publishing |

Unmatched inputs fall through to dynamic persona generation.

### Persona Selector

Two paths:

1. **Preset path** (`persona_presets.py`): Hardcoded opposing expert pairs per domain. Fast, deterministic, no LLM call.
2. **Dynamic path** (`persona_dynamic.py`): Generates a custom pair via single LLM call. Slower but handles any domain.

### Opposition Verifier

Uses `text-embedding-3-small` to embed both persona descriptions, then computes cosine distance. This prevents degenerate pairs where both agents argue from similar positions.

```python
# Verification logic (simplified)
emb_a = embed(persona_a.description)
emb_b = embed(persona_b.description)
distance = 1 - cosine_similarity(emb_a, emb_b)

if distance < OPPOSITION_THRESHOLD:
    regenerate()  # up to 3 retries
```

## Data Flow

```
amp.py (entry)
  -> orchestrator.py
       -> rolemesh.select_personas(question)
            -> domain_classifier.classify(question)
            -> persona_selector.get_pair(domain)
            -> opposition_verifier.verify(pair)
       <- (persona_a, persona_b)
       -> agents.py (construct prompts with personas)
       -> debate loop
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OPPOSITION_THRESHOLD` | 0.35 | Minimum cosine distance for valid pair |
| `MAX_REGEN_ATTEMPTS` | 3 | Retries before falling back to generic pair |
| `EMBEDDING_MODEL` | text-embedding-3-small | Model for opposition verification |
| `DYNAMIC_PERSONA_MODEL` | gpt-4o | Model for custom persona generation |

## Design Decisions

1. **Embedding verification over prompt-only**: Prompt instructions alone cannot guarantee genuine opposition. Embedding distance is a measurable, reproducible metric.
2. **Preset-first, dynamic-fallback**: Presets are faster and more reliable for common domains. Dynamic generation handles the long tail.
3. **Stateless selection**: RoleMesh does not retain state between questions. KG context is injected upstream by the orchestrator, not by RoleMesh itself.
