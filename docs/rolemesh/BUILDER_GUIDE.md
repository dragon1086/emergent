# Builder Guide

> Getting started with RoleMesh tool discovery and setup

## Overview

The Builder module (`src/rolemesh/builder.py`) is the entry point for RoleMesh. It discovers which AI CLI tools are installed on your system, profiles their capabilities, and generates a routing configuration that the Router and Executor consume.

## Quick Start

```bash
# Discover installed tools (display only)
python -m src.rolemesh setup

# Discover and save config
python -m src.rolemesh setup --save

# Interactive setup with preference prompts
python -m src.rolemesh setup --interactive --save

# JSON output for scripting
python -m src.rolemesh setup --json
```

## How Discovery Works

The Builder follows a 4-step pipeline:

```
TOOL_REGISTRY -> discover_tools() -> rank_tools() -> build_config()
      |                |                  |                |
  static list    shutil.which()     sort by fit      config.json
  of known       + version check    + preference
  AI tools                          + cost
```

### Step 1: Tool Registry

`TOOL_REGISTRY` defines the known AI CLI tools:

| Key | Tool | Vendor | Check Command | Cost Tier |
|-----|------|--------|---------------|-----------|
| `claude` | Claude Code | Anthropic | `claude --version` | high |
| `codex` | Codex CLI | OpenAI | `codex --version` | medium |
| `gemini` | Gemini CLI | Google | `gemini --version` | medium |
| `aider` | Aider | Community | `aider --version` | low |
| `copilot` | GitHub Copilot CLI | GitHub | `copilot --version` | medium |
| `cursor` | Cursor | Cursor | `cursor --version` | medium |

### Step 2: Discovery

For each registered tool, the Builder:

1. Checks if the binary exists on `PATH` via `shutil.which()`
2. Runs the `check_cmd` (e.g., `claude --version`) with a 5-second timeout
3. Parses the version string from stdout
4. Creates a `ToolProfile` with availability and version info

### Step 3: Ranking

`rank_tools(task_type)` sorts available tools by three criteria (in priority order):

1. **Strength match** - Does the tool list this task type in its strengths?
2. **User preference** - Manual preference score (`1` = prefer, `-1` = avoid, `0` = neutral)
3. **Cost tier** - Lower cost preferred when other factors are equal

### Step 4: Config Generation

`build_config()` iterates all task types found across available tools and assigns:
- **primary**: the highest-ranked tool for that task type
- **fallback**: the second-ranked tool (if one exists)

## Interactive Setup

The `--interactive` flag runs a guided wizard:

```bash
python -m src.rolemesh setup --interactive --save
```

```
=== RoleMesh Setup Wizard ===

Found 3 AI tool(s):
  - Claude Code (Anthropic) [coding, refactoring, analysis, ...]
  - Codex CLI (OpenAI) [coding, refactoring, quick-edit, ...]
  - Gemini CLI (Google) [coding, multimodal, search, ...]

Prefer Claude Code? [y/n/skip] y
Prefer Codex CLI? [y/n/skip] skip
Prefer Gemini CLI? [y/n/skip] n
```

Preferences influence routing order: tools you prefer rank higher; tools you mark `n` rank lower.

## Programmatic Usage

```python
from src.rolemesh.builder import SetupWizard

# Basic discovery
wizard = SetupWizard()
wizard.discover()
print(wizard.summary())

# Check what's available
for tool in wizard.available_tools():
    print(f"{tool.name} v{tool.version} [{tool.cost_tier}]")

# Rank for a specific task
ranked = wizard.rank_tools("refactoring")
best = ranked[0] if ranked else None

# Build and save config
config = wizard.build_config()
wizard.save_config()
```

## Config File Location

Default: `~/.rolemesh/config.json`

Override via:
- Constructor: `SetupWizard(config_path=Path("/custom/path.json"))`
- CLI: `python -m src.rolemesh setup --config /custom/path.json`
- Environment: `ROLEMESH_CONFIG=/custom/path.json`

## Troubleshooting

### Tool not detected

```bash
# Verify the binary is on PATH
which claude
claude --version
```

If the tool is installed but not detected, ensure your shell profile exports the correct `PATH`.

### Config validation errors

```python
from src.rolemesh.builder import SetupWizard

config = wizard.load_config()
errors = SetupWizard.validate_config(config)
if errors:
    for e in errors:
        print(f"  ERROR: {e}")
```

Common issues:
- Missing `version` or `tools` field (corrupted file)
- Routing rules reference a tool key that doesn't exist in `tools`
- Manually edited config with typos

### Re-running discovery

If you install or remove tools, re-run setup to update:

```bash
python -m src.rolemesh setup --save
```

This overwrites the existing config with a fresh discovery.

## See Also

- [Custom Tools](CUSTOM_TOOLS.md) - Register your own AI tools
- [Config Reference](CONFIG_REFERENCE.md) - Schema and validation details
- [API Reference](API_REFERENCE.md) - Full Python API
