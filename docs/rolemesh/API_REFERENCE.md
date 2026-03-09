# RoleMesh API Reference

> Public interface for persona selection and verification

## Module: `rolemesh`

### `select_personas(question: str) -> PersonaPair`

Main entry point. Classifies the question domain and returns an opposition-verified persona pair.

**Parameters:**
- `question` (str): The user's input question

**Returns:** `PersonaPair` with fields:
- `domain` (str): Detected domain name
- `agent_a` (Persona): First expert persona
- `agent_b` (Persona): Second expert persona (opposed)
- `cosine_distance` (float): Measured opposition distance
- `source` (str): `"preset"` or `"dynamic"`

**Example:**
```python
from src.rolemesh import select_personas

pair = select_personas("Should I quit my job to start a company?")
print(pair.domain)           # "career"
print(pair.agent_a.name)     # "Executive Recruiter"
print(pair.agent_b.name)     # "Burnout Recovery Coach"
print(pair.cosine_distance)  # 0.41
print(pair.source)           # "preset"
```

**Raises:**
- `OppositionError`: If opposition threshold cannot be met after max retries

---

### `classify_domain(question: str) -> str`

Classifies a question into a domain name.

**Parameters:**
- `question` (str): User input

**Returns:** Domain name string (one of the 10 presets, or `"custom"`)

**Example:**
```python
from src.rolemesh import classify_domain

domain = classify_domain("Is this contract fair?")
# "legal"
```

---

### `verify_opposition(pair: PersonaPair) -> bool`

Checks if a persona pair meets the opposition threshold.

**Parameters:**
- `pair` (PersonaPair): Pair to verify

**Returns:** `True` if cosine distance >= `OPPOSITION_THRESHOLD`, `False` otherwise

**Example:**
```python
from src.rolemesh import verify_opposition

is_valid = verify_opposition(pair)
# True
```

---

### `generate_dynamic_pair(question: str) -> PersonaPair`

Forces dynamic (LLM-generated) persona pair creation, bypassing presets.

**Parameters:**
- `question` (str): User input for context

**Returns:** `PersonaPair` (unverified — call `verify_opposition` separately)

**Example:**
```python
from src.rolemesh import generate_dynamic_pair, verify_opposition

pair = generate_dynamic_pair("Should I homeschool my children?")
if verify_opposition(pair):
    print("Valid pair")
```

---

## Data Types

### `Persona`

```python
@dataclass
class Persona:
    name: str           # Display name (e.g., "Venture Capitalist")
    role: str           # One-line role description
    stance: str         # Position label (e.g., "pro-risk")
    system_prompt: str  # Full system prompt for the agent
```

### `PersonaPair`

```python
@dataclass
class PersonaPair:
    domain: str              # Detected domain
    agent_a: Persona         # First persona
    agent_b: Persona         # Second persona (opposed)
    cosine_distance: float   # Measured opposition (0.0 - 1.0)
    source: str              # "preset" or "dynamic"
```

### `OppositionError`

Raised when `select_personas` exhausts all regeneration attempts without meeting the opposition threshold.

```python
class OppositionError(Exception):
    def __init__(self, domain: str, best_distance: float, threshold: float):
        self.domain = domain
        self.best_distance = best_distance
        self.threshold = threshold
```

---

## Configuration Constants

| Constant | Type | Default | Location |
|----------|------|---------|----------|
| `OPPOSITION_THRESHOLD` | float | 0.35 | `src/config.py` |
| `MAX_REGEN_ATTEMPTS` | int | 3 | `src/config.py` |
| `EMBEDDING_MODEL` | str | "text-embedding-3-small" | `src/config.py` |
| `DYNAMIC_PERSONA_MODEL` | str | "gpt-4o" | `src/config.py` |

Override via environment variables:

```bash
OPPOSITION_THRESHOLD=0.45 MAX_REGEN_ATTEMPTS=5 python amp.py
```

---

## Integration with Orchestrator

The orchestrator calls RoleMesh once per user question:

```python
# In orchestrator.py
from src.rolemesh import select_personas

def run_debate(question: str):
    pair = select_personas(question)
    agent_a = build_agent(pair.agent_a)
    agent_b = build_agent(pair.agent_b)
    return debate_loop(agent_a, agent_b, question)
```

RoleMesh is stateless. KG context injection happens in the orchestrator after persona selection, not within RoleMesh.
