# RoleMesh Builder Guide

> How to extend RoleMesh with new domains, personas, and verification rules

## Adding a New Preset Domain

### 1. Define the persona pair

Edit `src/persona_presets.py` and add an entry to `DOMAIN_PRESETS`:

```python
DOMAIN_PRESETS["parenting"] = {
    "domain": "parenting",
    "trigger_keywords": ["child", "parenting", "discipline", "school", "teenager"],
    "agent_a": {
        "name": "Structured Development Advocate",
        "role": "Child development specialist favoring structured guidance",
        "stance": "pro-structure",
        "system_prompt": "You are a child development expert who believes..."
    },
    "agent_b": {
        "name": "Autonomy-First Educator",
        "role": "Progressive educator favoring child-led exploration",
        "stance": "pro-autonomy",
        "system_prompt": "You are a progressive educator who believes..."
    }
}
```

### 2. Verify opposition

Run the opposition check to confirm your pair has sufficient cosine distance:

```bash
python -m src.persona_verify --domain parenting
# Expected output:
# Domain: parenting
# Cosine distance: 0.42 (threshold: 0.35)
# Status: PASS
```

If the distance is below threshold, revise the persona descriptions to make the opposition more explicit.

### 3. Add trigger tests

Add test cases to `tests/test_rolemesh.py`:

```python
def test_parenting_domain_classification():
    domain = classify("My teenager refuses to do homework")
    assert domain == "parenting"

def test_parenting_opposition():
    pair = select_personas("Should I let my kid skip college?")
    assert pair.domain == "parenting"
    assert verify_opposition(pair) is True
```

### 4. Run the test suite

```bash
cd /path/to/emergent
python -m pytest tests/test_rolemesh.py -v
```

## Customizing the Dynamic Generator

When no preset matches, RoleMesh generates personas dynamically. The generation prompt lives in `src/persona_dynamic.py`:

```python
DYNAMIC_PROMPT = """
Given the user's question: "{question}"

Generate two opposing expert personas for a structured debate.
Requirements:
- Both must be domain experts (not generic roles)
- Their positions must be genuinely opposed
- Each persona needs: name, role, stance, system_prompt

Output JSON:
{
  "agent_a": {"name": ..., "role": ..., "stance": ..., "system_prompt": ...},
  "agent_b": {"name": ..., "role": ..., "stance": ..., "system_prompt": ...}
}
"""
```

To modify generation behavior, edit this prompt. Common adjustments:
- Add constraints for specific output formats
- Adjust stance intensity (moderate vs. extreme opposition)
- Add domain-specific expertise requirements

## Tuning Opposition Threshold

The `OPPOSITION_THRESHOLD` (default 0.35) controls how different personas must be.

| Value | Effect |
|-------|--------|
| 0.25 | Loose — allows moderate opposition |
| 0.35 | Default — balanced |
| 0.45 | Strict — requires strong opposition |

To experiment:

```bash
OPPOSITION_THRESHOLD=0.45 python amp.py
```

Higher thresholds increase regeneration frequency but produce sharper debates.

## File Structure

```
src/
  persona_presets.py    # Preset domain definitions (edit to add domains)
  persona_dynamic.py    # LLM-based custom pair generation
  persona_verify.py     # Embedding opposition verification
  domain_classifier.py  # Question -> domain mapping

tests/
  test_rolemesh.py      # Domain classification + opposition tests
```

## Checklist for New Domains

- [ ] Persona pair defined in `persona_presets.py`
- [ ] Trigger keywords cover common phrasings
- [ ] Opposition verification passes (cosine distance >= threshold)
- [ ] Test cases added for classification and opposition
- [ ] Test suite passes
