# RoleMesh FAQ

> Frequently asked questions about RoleMesh

## General

### What is RoleMesh?

RoleMesh is an AI tool discovery and task-to-tool routing engine. It finds AI CLI tools on your system, classifies user requests by task type, and routes each request to the best-fit tool.

### Does RoleMesh require an API key?

No. RoleMesh itself makes no API calls. It discovers and dispatches existing AI CLI tools (Claude, Codex, Gemini, etc.), each of which manages its own authentication.

### Which AI tools does RoleMesh support?

Six built-in tools: Claude Code, Codex CLI, Gemini CLI, Aider, GitHub Copilot, and Cursor. You can register additional tools at runtime via `SetupWizard.register_tool()`. See [CUSTOM_TOOLS.md](CUSTOM_TOOLS.md).

### What happens if I only have one tool installed?

RoleMesh routes everything to that tool. The routing algorithm always produces a result — if only Claude is installed, all 13 task types route to Claude.

### Does routing use an LLM?

No. Classification uses regex pattern matching (~1ms per request). No LLM calls, no network round-trips, no token costs for routing decisions.

## Setup

### How do I install RoleMesh?

```bash
cd /path/to/emergent
python -m src.rolemesh.builder --save
```

This discovers installed tools and saves the routing config to `~/.rolemesh/config.json`.

### Where is the config stored?

Default: `~/.rolemesh/config.json`. You can override this path in constructors:

```python
router = RoleMeshRouter(config_path=Path("/custom/path.json"))
```

### How do I reset to defaults?

Delete the config and re-run the builder:

```bash
rm ~/.rolemesh/config.json
python -m src.rolemesh.builder --save
```

### Can I have multiple configs?

Yes. Generate configs with different settings and pass the path explicitly:

```python
router = RoleMeshRouter(config_path=Path("configs/team-frontend.json"))
```

See [COOKBOOK.md](COOKBOOK.md#recipe-3-team-specific-configs) for a full example.

## Routing

### How does routing work?

1. The router classifies the input text against 13 task types using regex patterns
2. Each matched task type is scored by pattern group coverage (e.g., 2/3 groups = 67%)
3. The highest-scoring task type is selected
4. The routing config maps that task type to a primary tool (and optional fallback)

See [ROUTER_GUIDE.md](ROUTER_GUIDE.md) for full details.

### Why is my request routing to the wrong tool?

Three common causes:

1. **Classification mismatch**: The regex patterns matched a different task type than expected. Check with:
   ```bash
   python -m src.rolemesh.router "your request here"
   ```

2. **User preference override**: A preferred tool outranks the naturally best-fit tool. Check preferences in `~/.rolemesh/config.json` under each tool's `user_preference` field.

3. **Cost tier effect**: Among equally-capable tools, cheaper ones rank higher. A `low`-cost tool with the right strength beats a `high`-cost tool.

### Can I force a specific tool?

Yes, via the executor:

```bash
python -m src.rolemesh.executor --tool claude "your request"
```

Or programmatically:

```python
result = executor.dispatch("claude", "your request")
```

### What if no task type matches?

The router defaults to `"coding"` with 0.0 confidence when no pattern matches. This ensures every request gets routed.

### Does it support Korean and English?

Yes. All 13 task type patterns include both Korean and English keywords. A request in either language is classified the same way.

## Execution

### What is dry-run mode?

Dry-run shows the command that would be executed without actually running it:

```bash
python -m src.rolemesh.executor --dry-run "refactor this"
# [dry-run] Would execute: codex <prompt>
```

### How does fallback work?

If the primary tool fails (non-zero exit code) or is not found on PATH, the executor automatically tries the fallback tool from the routing config. If both fail, it returns an error with exit code 127.

### What is the default timeout?

120 seconds. Override with `--timeout`:

```bash
python -m src.rolemesh.executor --timeout 300 "large refactoring task"
```

### Can I run tools in parallel?

RoleMesh dispatches one tool per request. For parallel execution, call the executor from multiple threads or processes:

```python
from concurrent.futures import ThreadPoolExecutor

executor = RoleMeshExecutor()
prompts = ["task 1", "task 2", "task 3"]

with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(executor.run, prompts))
```

## Configuration

### How do I add a new tool?

Two options:

1. **Runtime registration** (recommended):
   ```python
   wizard.register_tool(key="mytool", name="MyTool", ...)
   wizard.save_config()
   ```

2. **Static registry edit**: Add to `TOOL_REGISTRY` in `builder.py`.

See [CUSTOM_TOOLS.md](CUSTOM_TOOLS.md) for full details.

### How do I remove a tool?

```python
wizard.unregister_tool("cursor")
wizard.save_config()
```

### How do I change routing priority?

Set `user_preference` on tools:

```python
for tool in wizard.tools:
    if tool.key == "claude":
        tool.user_preference = 1    # prefer
    elif tool.key == "cursor":
        tool.user_preference = -1   # avoid
wizard.save_config()
```

Or edit `config.json` directly — set `user_preference` to `1`, `0`, or `-1`.

### How do I add a new task type?

Add a pattern tuple to `TASK_PATTERNS` in `router.py`:

```python
TASK_PATTERNS.append(
    ("data-science", [
        r"data|dataset|dataframe",
        r"train|predict|model|visualiz",
    ]),
)
```

See [BUILDER_GUIDE.md](BUILDER_GUIDE.md#adding-a-new-task-type) for details.

## Dashboard

### What does the health score mean?

The dashboard runs 5 checks. The score is `passed/5`:

| Check | What It Verifies |
|-------|-----------------|
| `config_file` | Config exists on disk |
| `tools_available` | At least 1 tool found on PATH |
| `routing_coverage` | All 13 task types have routing rules |
| `config_version` | Config version is `1.0.0` |
| `no_dead_refs` | All routing targets exist in config |

A score of 5/5 means the system is fully configured. 3/5 or below usually means the config is missing or needs regeneration.

### How do I fix routing_coverage warnings?

Re-run the builder to generate rules for all task types:

```bash
python -m src.rolemesh.builder --save
```

If some task types still have no route, it means no installed tool has the required strength. Install more tools or register custom ones.

## Troubleshooting

### "No AI tools found"

No supported CLI tool is on your PATH. Install at least one:

```bash
which claude codex gemini aider
```

### Config validation errors after manual edit

Run validation to find the issue:

```python
errors = SetupWizard.validate_config(config)
for e in errors:
    print(e)
```

Common issues: typos in tool keys, missing `primary` field in routing rules, referencing a removed tool.

### Tool works in terminal but RoleMesh can't find it

The tool binary might be in a PATH location not available to Python's `shutil.which()`. Check:

```bash
python -c "import shutil; print(shutil.which('claude'))"
```

If this returns `None`, add the tool's directory to your PATH in your shell profile.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.
