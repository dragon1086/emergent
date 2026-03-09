# RoleMesh Custom Tools Guide

> Register, manage, and integrate third-party AI CLI tools at runtime

## Overview

RoleMesh ships with 6 built-in tools (Claude, Codex, Gemini, Aider, Copilot, Cursor). You can extend this with any CLI tool via `register_tool()` — no source edits required.

## Registering a Custom Tool

### Basic Registration

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()  # discover built-in tools first

profile = wizard.register_tool(
    key="windsurf",
    name="Windsurf",
    vendor="Codeium",
    strengths=["coding", "inline-edit", "completion"],
    check_cmd=["windsurf", "--version"],
    cost_tier="medium",
)

print(profile.available)  # True if binary found on PATH
print(profile.version)    # Detected version string, or None
```

### What Happens Internally

1. Entry added to `TOOL_REGISTRY` (runtime, not persisted to source)
2. Binary probed via `shutil.which(check_cmd[0])`
3. If found, `check_cmd` is executed to extract version
4. `ToolProfile` created with `available` and `version` populated
5. Existing tool with the same key is replaced (not duplicated)

### Required Parameters

| Parameter | Type | Constraints |
|-----------|------|-------------|
| `key` | str | Non-empty, unique identifier |
| `name` | str | Non-empty display name |
| `vendor` | str | Organization/author |
| `strengths` | list[str] | Task types this tool handles |
| `check_cmd` | list[str] | Command to verify installation |
| `cost_tier` | str | Must be `"low"`, `"medium"`, or `"high"` |

### Validation

```python
# Invalid cost_tier raises ValueError
wizard.register_tool(key="x", name="X", vendor="V",
                     strengths=[], check_cmd=["x"],
                     cost_tier="ultra")
# ValueError: cost_tier must be low/medium/high, got 'ultra'

# Empty key or name raises ValueError
wizard.register_tool(key="", name="", vendor="V",
                     strengths=[], check_cmd=["x"])
# ValueError: key and name are required
```

## Persisting Custom Tools

`register_tool()` modifies in-memory state only. To persist:

```python
wizard.register_tool(key="windsurf", ...)
wizard.save_config()  # writes to ~/.rolemesh/config.json
```

The saved config includes the custom tool in `tools` and any auto-generated routing rules in `routing`.

**Note:** The `TOOL_REGISTRY` modification is runtime-only. On next process start, you need to re-register custom tools or load from config.

## Replacing an Existing Tool

Calling `register_tool()` with an existing key replaces the old entry:

```python
# Original
wizard.register_tool(key="mytool", name="MyTool v1", vendor="Me",
                     strengths=["coding"], check_cmd=["mytool"],
                     cost_tier="low")

# Replace
wizard.register_tool(key="mytool", name="MyTool v2", vendor="Me",
                     strengths=["coding", "refactoring"], check_cmd=["mytool"],
                     cost_tier="medium")

# Only one entry with key="mytool" exists
assert len([t for t in wizard.tools if t.key == "mytool"]) == 1
assert wizard.tools[-1].name == "MyTool v2"
```

## Unregistering a Tool

```python
removed = wizard.unregister_tool("cursor")
print(removed)  # True if found and removed

wizard.save_config()  # persist the removal
```

Returns `False` if the key doesn't exist:

```python
wizard.unregister_tool("nonexistent")  # False
```

Unregistering removes the tool from both `TOOL_REGISTRY` and the wizard's internal tool list. Subsequent `build_config()` calls exclude the removed tool from routing rules.

## Choosing Strengths

Strengths determine which task types the tool is eligible to handle. Use the 13 built-in task types:

| Strength | Routes To |
|----------|-----------|
| `coding` | Code writing, implementation |
| `refactoring` | Code restructuring, cleanup |
| `quick-edit` | Small fixes, renames, typos |
| `analysis` | Debugging, investigation |
| `architecture` | System design, strategy |
| `reasoning` | Logic, evaluation, comparison |
| `frontend` | UI/UX, layout, styling |
| `multimodal` | Images, charts, screenshots |
| `search` | Information lookup, docs |
| `explain` | Explanations, documentation |
| `git-integration` | Commits, branches, PRs |
| `completion` | Autocomplete, fill-in |
| `pair-programming` | Collaborative review |

You can also define custom strengths. They won't match built-in task patterns but will appear in `build_config()` routing rules.

## Choosing cost_tier

Cost tier affects ranking when multiple tools share the same strength:

| Tier | When to Use |
|------|-------------|
| `low` | Free or open-source tools, local models |
| `medium` | Mid-price commercial APIs, freemium tools |
| `high` | Premium APIs with per-token billing |

The ranking algorithm prefers cheaper tools when strengths and user preferences are equal.

## Choosing check_cmd

`check_cmd` is used to verify the tool is installed. Requirements:

- First element must be the binary name (checked via `shutil.which()`)
- Full command is executed to extract version from stdout
- Version parsing looks for the first word containing a digit

Examples:

```python
# Simple --version flag
check_cmd=["windsurf", "--version"]

# Subcommand
check_cmd=["gh", "copilot", "--version"]

# Version flag variant
check_cmd=["aider", "--version"]
```

If the binary doesn't exist on PATH, `available` is set to `False` and the tool is excluded from routing.

## Integration with Executor

Custom tools need a corresponding entry in `TOOL_COMMANDS` (executor.py) to be dispatchable:

```python
from src.rolemesh.executor import TOOL_COMMANDS

TOOL_COMMANDS["windsurf"] = {
    "cmd": ["windsurf"],
    "stdin_mode": False,   # True if prompt goes via stdin
}
```

Without this entry, the executor can route to the tool but `build_command()` returns `None` and `dispatch()` returns an error with exit code 127.

## End-to-End Example

```python
from src.rolemesh.builder import SetupWizard
from src.rolemesh.executor import RoleMeshExecutor, TOOL_COMMANDS

# 1. Register the tool
wizard = SetupWizard()
wizard.discover()
wizard.register_tool(
    key="ollama",
    name="Ollama",
    vendor="Ollama",
    strengths=["coding", "explain"],
    check_cmd=["ollama", "--version"],
    cost_tier="low",
)
wizard.save_config()

# 2. Add executor command mapping
TOOL_COMMANDS["ollama"] = {
    "cmd": ["ollama", "run", "codellama"],
    "stdin_mode": True,
}

# 3. Use it
executor = RoleMeshExecutor(dry_run=True)
result = executor.run("이 코드 설명해줘")
print(result.tool)  # may route to ollama (low cost + explain strength)
```
