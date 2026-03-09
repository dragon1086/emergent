# Extending the Builder — Custom Tools

> How to add, register, and manage custom AI CLI tools in RoleMesh.

---

## Overview

RoleMesh ships with 6 built-in tools, but you can register any CLI tool that accepts a text prompt and returns output. Custom tools participate in routing, execution, fallback, and dashboard display just like built-in tools.

---

## Method 1: Runtime Registration (Programmatic)

Use `SetupWizard.register_tool()` to add a tool at runtime:

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Register a custom tool
profile = wizard.register_tool(
    key="mytool",
    name="My Custom Tool",
    vendor="Internal",
    strengths=["coding", "analysis"],
    check_cmd=["mytool", "--version"],
    cost_tier="low",
)

print(f"Registered: {profile.name}, available={profile.available}")

# Save config so Router and Executor can use it
wizard.save_config()
```

### What happens during registration

1. The tool is added to the in-memory `TOOL_REGISTRY`
2. `shutil.which()` checks if the binary exists on PATH
3. If found, the version command is executed and captured
4. A `ToolProfile` is created and appended to the wizard's tool list
5. On `save_config()`, the tool appears in `config.json` and routing rules are regenerated

### Removing a custom tool

```python
wizard.unregister_tool("mytool")
wizard.save_config()
```

This removes the tool from the registry, tool list, and regenerated routing rules.

---

## Method 2: Static Registry (Source Code)

For permanent additions, add an entry to `TOOL_REGISTRY` in `builder.py`:

```python
TOOL_REGISTRY = {
    # ... existing tools ...
    "mytool": {
        "name": "My Custom Tool",
        "vendor": "Internal",
        "strengths": ["coding", "analysis", "data-science"],
        "check_cmd": ["mytool", "--version"],
        "cost_tier": "low",
    },
}
```

Then add the CLI command mapping in `executor.py`:

```python
TOOL_COMMANDS = {
    # ... existing commands ...
    "mytool": {"cmd": ["mytool", "--prompt"], "stdin_mode": False},
}
```

Finally, regenerate the config:

```bash
python -m src.rolemesh setup --save
```

---

## Tool Requirements

For a custom tool to work with RoleMesh:

| Requirement | Detail |
|-------------|--------|
| **CLI binary** | Must be callable from PATH |
| **Version command** | Should respond to `--version` (or similar) for health checks |
| **Prompt flag** | Must accept a task string via a CLI flag (e.g. `-p`, `--prompt`, `--message`) |
| **Exit codes** | Return 0 on success, non-zero on failure (enables fallback) |
| **stdout output** | Task results should be written to stdout |

### stdin mode

If your tool reads prompts from stdin instead of a flag, set `stdin_mode: True` in `TOOL_COMMANDS`:

```python
"mytool": {"cmd": ["mytool"], "stdin_mode": True},
```

The Executor will pipe the task string to the process's stdin.

---

## Strengths and Task Types

When registering a tool, the `strengths` list determines which task types it can handle. Use values from the standard vocabulary:

```
coding, refactoring, quick-edit, analysis, architecture,
reasoning, frontend, multimodal, search, explain,
git-integration, completion, pair-programming
```

You can also define custom task types. Add a corresponding pattern to `TASK_PATTERNS` in `router.py` so the Router can classify tasks into your new type:

```python
# router.py
TASK_PATTERNS = [
    # ... existing patterns ...
    ("data-science", (r"데이터|data|분석|pandas|numpy|plot|차트",
                      r"통계|statistics|regression|모델링|modeling")),
]
```

---

## Verification

After adding a custom tool, verify the integration:

### 1. Check discovery

```bash
python -m src.rolemesh setup
```

Your tool should appear with `[OK]` if the binary is on PATH.

### 2. Check routing

```bash
python -m src.rolemesh route "analyze this data" --all
```

Verify your tool appears in the routing results for relevant task types.

### 3. Check dashboard

```bash
python -m src.rolemesh dashboard --tools
python -m src.rolemesh dashboard --coverage
python -m src.rolemesh dashboard --health
```

- **Tools view**: tool should appear with correct status
- **Coverage matrix**: tool should show capabilities for its strength tags
- **Health check**: `no_dead_refs` should pass (no routing rules pointing to missing tools)

### 4. Dry-run execution

```bash
python -m src.rolemesh exec "test task" --tool mytool --dry-run
```

Confirms the CLI command that would be executed without actually running it.

---

## Example: Adding a Local LLM Tool

```python
# Register a local Ollama-based tool
wizard.register_tool(
    key="ollama",
    name="Ollama Local",
    vendor="Local",
    strengths=["coding", "explain", "quick-edit"],
    check_cmd=["ollama", "--version"],
    cost_tier="low",  # free to run locally
)
wizard.save_config()
```

In `executor.py`:
```python
"ollama": {"cmd": ["ollama", "run", "codellama"], "stdin_mode": True},
```

This gives you a zero-cost fallback for simple tasks while routing complex work to cloud tools.

---

## Related Docs

- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Getting started with the Builder
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration schema and validation
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — System design and extension points
