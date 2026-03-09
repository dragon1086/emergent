# Builder Guide — RoleMesh Setup Wizard

> How to discover tools, configure routing, and get started with RoleMesh.

---

## Overview

The Builder module (`builder.py`) is the entry point for RoleMesh. It scans your system for installed AI CLI tools, profiles their capabilities, and generates a routing configuration that the Router and Executor use.

---

## Quick Start

### 1. Discover installed tools

```bash
python -m src.rolemesh setup
```

This probes your system PATH for all known AI CLI tools (Claude Code, Codex, Gemini, Aider, Copilot, Cursor) and prints a summary:

```
RoleMesh: 3/6 tools available
  [OK] Claude Code (claude 4.1.0) — Anthropic, high
  [OK] Codex CLI (codex 0.9.2) — OpenAI, medium
  [--] Gemini CLI — Google, medium
  [OK] Aider (aider 0.82.1) — Community, low
  [--] GitHub Copilot CLI — GitHub, medium
  [--] Cursor — Cursor, medium
```

### 2. Save configuration

```bash
python -m src.rolemesh setup --save
```

Writes `~/.rolemesh/config.json` with tool profiles and routing rules. The Router and Executor load this file automatically.

### 3. Interactive setup (optional)

```bash
python -m src.rolemesh setup --interactive
```

Walks you through setting manual preference rankings for each tool. Useful when you want to override the default cost-based ranking.

---

## How Discovery Works

1. **Registry scan** — iterates over `TOOL_REGISTRY` (6 built-in tools)
2. **PATH probe** — calls `shutil.which()` for each tool's binary
3. **Version capture** — runs the tool's `--version` command, captures first 80 chars
4. **Profile creation** — builds a `ToolProfile` dataclass per tool

```python
from src.rolemesh.builder import discover_tools

tools = discover_tools()
for t in tools:
    status = "available" if t.available else "missing"
    print(f"{t.name}: {status} (cost: {t.cost_tier})")
```

---

## Configuration File

After `setup --save`, the config lives at `~/.rolemesh/config.json`:

```json
{
  "version": "1.0.0",
  "tools": {
    "claude": {
      "key": "claude",
      "name": "Claude Code",
      "vendor": "Anthropic",
      "strengths": ["coding", "refactoring", "analysis", ...],
      "cost_tier": "high",
      "available": true,
      "version": "claude 4.1.0"
    }
  },
  "routing": {
    "coding": { "primary": "aider", "fallback": "codex" },
    "analysis": { "primary": "codex", "fallback": "claude" }
  }
}
```

### Routing Rule Generation

For each task type found in tool strengths, the Builder:

1. Collects all available tools that list that strength
2. Ranks by: strength match > user preference > cost tier (cheaper first)
3. Assigns rank #1 as `primary`, rank #2 as `fallback`

---

## Programmatic Usage

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Check what's available
print(wizard.summary())
available = wizard.available_tools()

# Rank tools for a specific task type
ranked = wizard.rank_tools("refactoring")
print(f"Best for refactoring: {ranked[0].name}")

# Generate and save config
config = wizard.build_config()
wizard.save_config()

# Validate an existing config
errors = wizard.validate_config(config)
if errors:
    print(f"Config issues: {errors}")
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tool shows `[--]` but is installed | Ensure the binary is on your PATH. Run `which <tool>` to verify. |
| Config validation warns about dead refs | A routing rule references a tool not in the tools dict. Re-run `setup --save`. |
| Version shows `None` | The tool's `--version` command returned empty output. Functionality is unaffected. |
| Interactive setup hangs | Press Ctrl+C to skip preferences and use auto-ranking. |

---

## Next Steps

- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration reference and schema details
- [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) — Adding custom tools to the registry
- [../API.md](../API.md) — Full class/function reference
