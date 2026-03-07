# RoleMesh Config Schema Reference

> Complete specification of `~/.rolemesh/config.json`

## File Location

Default: `~/.rolemesh/config.json`

Override via constructor:

```python
wizard = SetupWizard(config_path=Path("/custom/path/config.json"))
router = RoleMeshRouter(config_path=Path("/custom/path/config.json"))
```

## Schema

```json
{
  "version": "1.0.0",
  "tools": {
    "<tool_key>": {
      "key": "<tool_key>",
      "name": "Display Name",
      "vendor": "Company",
      "strengths": ["task_type_1", "task_type_2"],
      "cost_tier": "low | medium | high",
      "available": true,
      "version": "1.0.0",
      "user_preference": 0
    }
  },
  "routing": {
    "<task_type>": {
      "primary": "<tool_key>",
      "fallback": "<tool_key> | null"
    }
  }
}
```

## Field Reference

### Top-Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | yes | Config schema version. Currently `"1.0.0"` |
| `tools` | object | yes | Map of tool key -> tool profile |
| `routing` | object | yes | Map of task type -> routing rule |

### `tools.<key>`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | yes | Unique identifier (e.g., `"claude"`, `"codex"`) |
| `name` | string | yes | Human-readable name (e.g., `"Claude Code"`) |
| `vendor` | string | yes | Organization name (e.g., `"Anthropic"`) |
| `strengths` | string[] | yes | Task types this tool excels at |
| `cost_tier` | string | yes | One of `"low"`, `"medium"`, `"high"` |
| `available` | boolean | no | Whether the binary was found on PATH |
| `version` | string\|null | no | Detected version string |
| `user_preference` | integer | no | `1`=preferred, `0`=neutral, `-1`=avoid |

### `routing.<task_type>`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `primary` | string | yes | Tool key to use for this task type |
| `fallback` | string\|null | no | Backup tool key if primary fails |

## Validation Rules

`SetupWizard.validate_config(config)` enforces the following:

| Rule | Error Message |
|------|--------------|
| Config must be a dict | `Config must be a dict` |
| `version` exists and is a string | `Missing 'version' field` |
| `tools` exists and is a dict of dicts | `Missing 'tools' field` |
| `routing` exists and is a dict | `Missing 'routing' field` |
| Each routing rule has `primary` | `routing['X'] missing 'primary'` |
| `primary` references a key in `tools` | `routing['X'].primary 'Y' not found in tools` |
| `fallback` (if set) references a key in `tools` | `routing['X'].fallback 'Y' not found in tools` |

### Validate before saving

```python
config = wizard.build_config()
errors = SetupWizard.validate_config(config)
if errors:
    for e in errors:
        print(f"  ERROR: {e}")
else:
    wizard.save_config()
```

## Task Types

The router recognizes 13 task types. Routing rules can reference any of these:

| Task Type | Typical Strengths |
|-----------|------------------|
| `coding` | claude, codex, aider, cursor |
| `refactoring` | codex, claude |
| `quick-edit` | codex, copilot |
| `analysis` | claude |
| `architecture` | claude |
| `reasoning` | claude |
| `frontend` | gemini, cursor |
| `multimodal` | gemini |
| `search` | gemini |
| `explain` | copilot, claude |
| `git-integration` | aider |
| `completion` | copilot |
| `pair-programming` | aider |

## Cost Tiers

Cost tier affects tool ranking when multiple tools share a strength:

| Tier | Score Bonus | Examples |
|------|-------------|----------|
| `low` | +2.0 | aider, copilot |
| `medium` | +1.0 | codex, gemini, cursor |
| `high` | +0.0 | claude |

Lower-cost tools rank higher when strengths and preferences are equal.

## Example Configs

### Minimal (single tool)

```json
{
  "version": "1.0.0",
  "tools": {
    "claude": {
      "key": "claude",
      "name": "Claude Code",
      "vendor": "Anthropic",
      "strengths": ["coding", "analysis"],
      "cost_tier": "high",
      "available": true
    }
  },
  "routing": {
    "coding": { "primary": "claude", "fallback": null }
  }
}
```

### Multi-tool with fallbacks

```json
{
  "version": "1.0.0",
  "tools": {
    "claude": {
      "key": "claude",
      "name": "Claude Code",
      "vendor": "Anthropic",
      "strengths": ["coding", "analysis", "reasoning", "architecture"],
      "cost_tier": "high",
      "available": true
    },
    "codex": {
      "key": "codex",
      "name": "Codex CLI",
      "vendor": "OpenAI",
      "strengths": ["coding", "refactoring", "quick-edit"],
      "cost_tier": "medium",
      "available": true
    },
    "gemini": {
      "key": "gemini",
      "name": "Gemini CLI",
      "vendor": "Google",
      "strengths": ["multimodal", "search", "ui-design", "frontend"],
      "cost_tier": "medium",
      "available": true
    }
  },
  "routing": {
    "coding": { "primary": "codex", "fallback": "claude" },
    "refactoring": { "primary": "codex", "fallback": "claude" },
    "analysis": { "primary": "claude", "fallback": null },
    "frontend": { "primary": "gemini", "fallback": "claude" },
    "multimodal": { "primary": "gemini", "fallback": null }
  }
}
```

## Direct Editing

You can edit `config.json` by hand. Changes take effect on the next `RoleMeshRouter()` instantiation. Run validation after manual edits:

```python
import json
from src.rolemesh.builder import SetupWizard

config = json.loads(Path("~/.rolemesh/config.json").expanduser().read_text())
errors = SetupWizard.validate_config(config)
print(errors or "Valid")
```

## Config Generation

The recommended way to create a config is via `SetupWizard`:

```bash
# Auto-generate from discovered tools
python -m src.rolemesh.builder --save

# Interactive (set tool preferences first)
python -m src.rolemesh.builder --interactive

# Inspect without saving
python -m src.rolemesh.builder --json
```

The wizard discovers installed tools, ranks them per task type, and writes the routing rules automatically.
