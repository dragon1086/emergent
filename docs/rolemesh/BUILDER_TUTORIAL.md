# RoleMesh Builder Tutorial

> Hands-on walkthrough: discover tools, customize routing, and integrate with your workflow.

---

## Prerequisites

- Python 3.10+
- At least one AI CLI tool installed (Claude Code, Codex, Gemini, Aider, Copilot, or Cursor)

---

## 1. First-Time Setup

### Discover and save

```bash
python -m src.rolemesh setup --save
```

Output:
```
RoleMesh: 3/6 tools available
  [OK] Claude Code (v1.0.20) — Anthropic, high
  [OK] Codex CLI (v0.1.0) — OpenAI, medium
  [--] Gemini CLI — Google, medium
  [OK] Aider (v0.82.0) — Community, low
  [--] GitHub Copilot CLI — GitHub, medium
  [--] Cursor — Cursor, medium

Config saved to: /Users/you/.rolemesh/config.json
```

### Verify with status

```bash
python -m src.rolemesh status
```

```
[OK] RoleMesh: 3/6 tools (Claude Code, Codex CLI, Aider) | config: loaded
```

---

## 2. Understanding the Generated Config

After `setup --save`, inspect the config:

```bash
cat ~/.rolemesh/config.json | python -m json.tool
```

Key sections:
- **tools**: one entry per known tool, with `available: true/false`
- **routing**: one entry per task type, with `primary` and `fallback` tool keys

Example routing entry:
```json
"refactoring": {
  "primary": "aider",
  "fallback": "codex"
}
```

This means: refactoring tasks go to Aider first (low cost, has strength). If Aider fails or isn't available, Codex is the fallback.

---

## 3. Testing Routing (Dry Run)

Before executing tasks, verify routing decisions:

```bash
# See which tool handles a refactoring request
python -m src.rolemesh route "이 함수 리팩토링해줘"

# Output:
# Task:       이 함수 리팩토링해줘
# Type:       refactoring (100%)
# Tool:       Aider
# Fallback:   codex
# Reason:     Matched 'refactoring' (confidence=100%), routed to Aider
```

### Multi-match mode

```bash
python -m src.rolemesh route --all "코드 분석하고 리팩토링해줘"

# Output:
#   refactoring          -> Aider                (100%)
#   coding               -> Aider                (50%)
#   analysis             -> Claude Code           (50%)
```

Multiple task types can match a single request. The Router picks the highest-confidence match.

### Dry-run execution

```bash
python -m src.rolemesh exec --dry-run "버그 분석해줘"

# Output:
# Tool:       Claude Code
# Task:       analysis (100%)
# Status:     OK (exit 0)
# Duration:   0ms
#
# --- stdout ---
# [dry-run] claude -p 버그 분석해줘
```

---

## 4. Adding a Custom Tool

### Via Python

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Register a local wrapper script
wizard.register_tool(
    key="my-assistant",
    name="My Assistant",
    vendor="Internal",
    strengths=["coding", "quick-edit", "explain"],
    check_cmd=["my-assistant", "--version"],
    cost_tier="low",
)

# Verify it was discovered
for tool in wizard.available_tools():
    print(f"  {tool.name}: {tool.version}")

# Save config with the new tool included
wizard.save_config()
```

After saving, the custom tool participates in routing. Since it has `cost_tier="low"`, it will be preferred for task types where it has strength.

### Removing a custom tool

```python
wizard.unregister_tool("my-assistant")
wizard.save_config()
```

---

## 5. Overriding Tool Priority

By default, tools are ranked by: strength match > user preference > cost tier.

To force a specific tool as the primary for all its strengths:

```python
wizard = SetupWizard()
wizard.discover()

# Make Claude Code the top choice regardless of cost
for tool in wizard._tools:
    if tool.key == "claude":
        tool.user_preference = 1

wizard.save_config()
```

Lower `user_preference` values win. The default is `None` (treated as 999).

---

## 6. Programmatic Integration

### Use Builder in your own scripts

```python
from src.rolemesh.builder import SetupWizard

def get_best_tool(task_type: str) -> str:
    """Return the best available tool key for a task type."""
    wizard = SetupWizard()
    wizard.discover()
    ranked = wizard.rank_tools(task_type)
    if ranked:
        return ranked[0].key
    return "claude"  # default fallback

# Example
best = get_best_tool("refactoring")
print(f"Best tool for refactoring: {best}")
```

### Load existing config without re-discovery

```python
wizard = SetupWizard()
config = wizard.load_config()

if config:
    errors = wizard.validate_config(config)
    if errors:
        print(f"Config issues: {errors}")
    else:
        print(f"Config OK — {len(config['tools'])} tools, {len(config['routing'])} routes")
```

---

## 7. Dashboard Verification

After any config changes, verify with the dashboard:

```bash
# Full dashboard
python -m src.rolemesh dashboard

# Health checks only
python -m src.rolemesh dashboard --health

# Coverage matrix (task types x tools)
python -m src.rolemesh dashboard --coverage
```

All 5 health checks should pass:
- `config_file`: config exists
- `tools_available`: at least 1 tool found
- `routing_coverage`: all 13 task types covered
- `config_version`: version is 1.0.0
- `no_dead_refs`: no broken tool references

---

## 8. Troubleshooting

### "No AI CLI tools installed"

Ensure at least one tool binary is on your PATH:
```bash
which claude codex gemini aider
```

### "Missing routing for task type X"

Re-run setup to regenerate routing with current tools:
```bash
python -m src.rolemesh setup --save
```

### Config validation errors

Check for dead references (tools removed but still in routing):
```bash
python -m src.rolemesh dashboard --health
```

Fix by re-running `setup --save` or manually editing `~/.rolemesh/config.json`.

---

## Further Reading

- [Builder Guide](./BUILDER_GUIDE.md) — concepts and SetupWizard overview
- [Configuration Reference](./BUILDER_CONFIG.md) — schema and validation rules
- [API Reference](./API.md) — complete method signatures
- [Architecture](./ARCHITECTURE.md) — design decisions and data flow
