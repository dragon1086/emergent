# RoleMesh Builder Guide

> How to discover tools, customize routing, and extend the registry

## Quick Start

### Auto-discover installed tools

```bash
cd /path/to/emergent
python -m src.rolemesh.builder
# Found 3 AI tool(s):
#   - Claude Code v1.0 (Anthropic) [coding, analysis, reasoning, architecture]
#   - Codex CLI v0.1 (OpenAI) [coding, refactoring, quick-edit]
#   - Gemini CLI v2.0 (Google) [multimodal, search, ui-design, frontend]
```

### Save config to disk

```bash
python -m src.rolemesh.builder --save
# Config saved to ~/.rolemesh/config.json
```

### Interactive setup (set preferences)

```bash
python -m src.rolemesh.builder --interactive
# === RoleMesh Setup Wizard ===
# Prefer Claude Code? [y/n/skip] y
# Prefer Codex CLI? [y/n/skip] skip
# Prefer Gemini CLI? [y/n/skip] n
```

### JSON output (for scripting)

```bash
python -m src.rolemesh.builder --json
```

## Adding a New Tool to the Registry

### Option A: Edit the registry (static)

Edit `src/rolemesh/builder.py` and add an entry to `TOOL_REGISTRY`:

```python
TOOL_REGISTRY["windsurf"] = {
    "name": "Windsurf",
    "vendor": "Codeium",
    "strengths": ["coding", "inline-edit", "completion"],
    "check_cmd": ["windsurf", "--version"],
    "cost_tier": "medium",
}
```

After adding, re-run the wizard:

```bash
python -m src.rolemesh.builder --save
```

### Option B: Register at runtime (dynamic)

Use `SetupWizard.register_tool()` to add tools without editing source:

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

profile = wizard.register_tool(
    key="windsurf",
    name="Windsurf",
    vendor="Codeium",
    strengths=["coding", "inline-edit", "completion"],
    check_cmd=["windsurf", "--version"],
    cost_tier="medium",
)

print(profile.available)  # True if windsurf is on PATH
print(profile.version)    # Detected version, or None
wizard.save_config()
```

The method adds the tool to `TOOL_REGISTRY`, probes the system for the binary, reads the version if available, and replaces any existing entry with the same key.

**Required fields:**

| Field | Type | Description |
|-------|------|-------------|
| `key` | str | Unique registry key (e.g., `"windsurf"`) |
| `name` | str | Display name |
| `vendor` | str | Company/org name |
| `strengths` | list[str] | Task types this tool excels at |
| `check_cmd` | list[str] | Command to verify installation |
| `cost_tier` | str | `"low"`, `"medium"`, or `"high"` |

**Validation:** `cost_tier` must be one of `low`, `medium`, `high`. Both `key` and `name` are required. Invalid values raise `ValueError`.

## Removing a Tool

Use `SetupWizard.unregister_tool()` to remove a tool from the registry:

```python
wizard = SetupWizard()
wizard.discover()

removed = wizard.unregister_tool("cursor")
print(removed)  # True if found and removed

wizard.save_config()  # Persist the change
```

This removes the tool from both `TOOL_REGISTRY` and the wizard's internal tool list. Routing rules referencing the removed tool will no longer appear in generated configs.

## Validating a Config

Use `SetupWizard.validate_config()` to check a config dict against the expected schema:

```python
config = wizard.build_config()
errors = SetupWizard.validate_config(config)

if errors:
    for err in errors:
        print(f"  ERROR: {err}")
else:
    print("Config is valid")
```

### What it checks

| Check | Error message |
|-------|--------------|
| Top-level type | `Config must be a dict` |
| `version` field exists and is a string | `Missing 'version' field` |
| `tools` field exists and is a dict of dicts | `Missing 'tools' field` |
| `routing` field exists and is a dict | `Missing 'routing' field` |
| Each routing rule has a `primary` key | `routing['X'] missing 'primary'` |
| `primary` tool exists in `tools` | `routing['X'].primary 'Y' not found in tools` |
| `fallback` tool (if set) exists in `tools` | `routing['X'].fallback 'Y' not found in tools` |

### Validating before save

```python
wizard = SetupWizard()
wizard.discover()
config = wizard.build_config()
errors = SetupWizard.validate_config(config)
if not errors:
    wizard.save_config()
else:
    raise RuntimeError(f"Invalid config: {errors}")
```

## Adding a New Task Type

Edit `src/rolemesh/router.py` and add a tuple to `TASK_PATTERNS`:

```python
TASK_PATTERNS.append(
    ("data-science", [
        r"데이터|data|분석|analy|통계|statistic|모델|model",
        r"학습|train|예측|predict|시각화|visualiz",
    ]),
)
```

Each task type has a list of regex patterns. The classifier scores by counting how many pattern groups match (e.g., 1/2 = 0.5 confidence, 2/2 = 1.0).

### Add tests for the new task type

In `tests/test_rolemesh.py`:

```python
def test_classify_data_science():
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("데이터 분석하고 시각화해줘")
    task_names = [t for t, _ in types]
    assert "data-science" in task_names
    print("  PASS: classify_data_science")
```

Add the test to the `run_all()` function's test list.

## Customizing Routing Rules

### Via SetupWizard (recommended)

```python
from src.rolemesh.builder import SetupWizard, ToolProfile

wizard = SetupWizard()
wizard.discover()

# Set user preferences
for tool in wizard.available_tools():
    if tool.key == "claude":
        tool.user_preference = 1   # prefer
    elif tool.key == "cursor":
        tool.user_preference = -1  # avoid

wizard.save_config()
```

### Direct config editing

Edit `~/.rolemesh/config.json`:

```json
{
  "version": "1.0.0",
  "tools": { ... },
  "routing": {
    "coding": {
      "primary": "claude",
      "fallback": "codex"
    },
    "frontend": {
      "primary": "gemini",
      "fallback": "claude"
    }
  }
}
```

The router reads this file on initialization. Changes take effect immediately on next `RoleMeshRouter()` instantiation.

## Ranking Algorithm

When multiple tools share a strength, `rank_tools()` scores them:

```
score = 0.0
if task_type in tool.strengths:   score += 10.0
score += user_preference * 5.0    # -1, 0, or 1
score += cost_bonus               # low=2.0, medium=1.0, high=0.0
```

**Ranking priority**: strength match (10) > user preference (5) > cost tier (2).

This means:
- A tool with the right strength always beats one without
- User preference overrides cost within equally-capable tools
- Cheaper tools win among equally-preferred tools with same strengths

## Running Tests

```bash
cd /path/to/emergent
python tests/test_rolemesh.py

# Running 16 tests...
#   PASS: tool_registry_complete
#   PASS: discover_returns_profiles
#   ...
# Results: 16 passed, 0 failed, 16 total
```

## Checklist for Extensions

- [ ] New tool: entry added to `TOOL_REGISTRY` in `builder.py`
- [ ] New task type: pattern tuple added to `TASK_PATTERNS` in `router.py`
- [ ] Test cases added to `tests/test_rolemesh.py`
- [ ] Test suite passes (`python tests/test_rolemesh.py`)
- [ ] Config regenerated (`python -m src.rolemesh.builder --save`)
