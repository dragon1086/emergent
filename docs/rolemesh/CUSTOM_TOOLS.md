# Custom Tools Guide

> Register, manage, and route to your own AI CLI tools

## Overview

RoleMesh ships with 6 built-in tool definitions, but you can register any CLI tool that accepts a text prompt. Custom tools participate in discovery, ranking, routing, and execution just like built-in ones.

## Registering a Tool

Use `SetupWizard.register_tool()` to add a custom tool at runtime:

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()  # discover built-in tools first

profile = wizard.register_tool(
    key="my-tool",
    name="My Custom Tool",
    vendor="My Company",
    strengths=["coding", "analysis", "search"],
    check_cmd=["my-tool", "--version"],
    cost_tier="low",
)

print(f"Registered: {profile.name}, available={profile.available}")
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | `str` | Yes | Unique identifier (used in config and routing) |
| `name` | `str` | Yes | Human-readable display name |
| `vendor` | `str` | Yes | Vendor or author name |
| `strengths` | `list[str]` | Yes | Task types the tool excels at (see below) |
| `check_cmd` | `list[str]` | Yes | Command to check availability and version |
| `cost_tier` | `str` | Yes | `"low"`, `"medium"`, or `"high"` |

### Valid Strength Values

Use any of the 13 built-in task types:

```
coding          refactoring     quick-edit      analysis
architecture    reasoning       frontend        multimodal
search          explain         git-integration completion
pair-programming
```

Custom strength strings are allowed but won't match any built-in classification pattern. They can still be used for direct dispatch.

### Cost Tier Effects

Cost tier affects ranking when tools tie on strength and preference:

| Tier | Ranking Bias | Typical Use |
|------|-------------|-------------|
| `low` | Preferred when tied | Local/free tools, open-source |
| `medium` | Neutral | SaaS with moderate pricing |
| `high` | Deprioritized when tied | Premium API-based tools |

## Removing a Tool

```python
removed = wizard.unregister_tool("my-tool")
print(f"Removed: {removed}")  # True if found, False if not
```

This removes the tool from both the in-memory registry and the wizard's tool list. Re-save config to persist the change:

```python
wizard.save_config()
```

## Replacing a Built-in Tool

If you register a tool with a key that matches a built-in (e.g., `"claude"`), the custom definition replaces it:

```python
# Override Claude's strengths
wizard.register_tool(
    key="claude",
    name="Claude Code (Custom)",
    vendor="Anthropic",
    strengths=["coding", "architecture", "reasoning"],
    check_cmd=["claude", "--version"],
    cost_tier="high",
)
```

## Persisting Custom Tools

`register_tool()` modifies the in-memory `TOOL_REGISTRY` and wizard state. To persist:

```python
wizard.save_config()
```

The saved config includes all tool profiles. However, the registry itself resets on next import. For permanent custom tools, create a setup script:

```python
#!/usr/bin/env python3
"""my_rolemesh_setup.py - Register custom tools and save config."""

from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Register custom tools
wizard.register_tool(
    key="local-llm",
    name="Local LLM",
    vendor="Self-hosted",
    strengths=["coding", "explain", "completion"],
    check_cmd=["ollama", "list"],
    cost_tier="low",
)

wizard.register_tool(
    key="internal-agent",
    name="Internal Agent",
    vendor="My Corp",
    strengths=["analysis", "search", "reasoning"],
    check_cmd=["internal-agent", "--ping"],
    cost_tier="low",
)

wizard.save_config()
print(wizard.summary())
```

## Execution Integration

Custom tools work with the Executor if they follow the standard CLI pattern:

```bash
<tool-binary> -p "<prompt>"
```

If your tool uses a different invocation pattern, you'll need to add an entry to `TOOL_COMMANDS` in `executor.py`:

```python
# executor.py
TOOL_COMMANDS = {
    # ...existing entries...
    "my-tool": {"cmd": "my-tool", "stdin": False},
}
```

Set `stdin: True` if the tool reads the prompt from stdin instead of a `-p` flag.

## Validation

After registering custom tools and saving, validate the config:

```python
config = wizard.build_config()
errors = SetupWizard.validate_config(config)
assert not errors, f"Config errors: {errors}"
```

Common validation errors:
- **Empty key or name**: Both are required and must be non-empty strings
- **Invalid cost_tier**: Must be exactly `"low"`, `"medium"`, or `"high"`
- **Dead routing references**: A routing rule points to a tool key not present in `tools`

## Example: Multi-Tool Routing

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Add a specialized search tool
wizard.register_tool(
    key="perplexity",
    name="Perplexity CLI",
    vendor="Perplexity",
    strengths=["search", "explain", "analysis"],
    check_cmd=["pplx", "--version"],
    cost_tier="medium",
)

# Now "search" tasks may route to Perplexity instead of Gemini
config = wizard.build_config()
print(config["routing"].get("search"))
# {"primary": "perplexity", "fallback": "gemini"}
```

## See Also

- [Builder Guide](BUILDER_GUIDE.md) - Discovery and setup walkthrough
- [Config Reference](CONFIG_REFERENCE.md) - Config schema details
- [API Reference](API_REFERENCE.md) - Full `SetupWizard` API
