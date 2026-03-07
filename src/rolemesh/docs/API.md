# RoleMesh API Reference

> Complete class and function reference for all RoleMesh modules.

---

## Module Overview

```
src/rolemesh/
  builder.py      # Tool discovery & setup wizard
  router.py       # Task classification & routing
  executor.py     # Task dispatch & execution
  dashboard.py    # Terminal dashboard & health checks
  __main__.py     # CLI entry point
```

### Pipeline

```
Builder (discover tools) → Router (classify & route) → Executor (dispatch & run)
                                                            ↓
                                                    Dashboard (visualize)
```

---

## builder.py

### `discover_tools() -> list[ToolProfile]`

Scans `TOOL_REGISTRY` for all known AI CLI tools, checks PATH availability, and captures version strings.

```python
from src.rolemesh.builder import discover_tools
tools = discover_tools()
```

### `ToolProfile`

Dataclass representing a discovered tool.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key` | `str` | — | Unique identifier (e.g. `"claude"`) |
| `name` | `str` | — | Display name |
| `vendor` | `str` | — | Vendor name |
| `strengths` | `list[str]` | — | Capability tags |
| `cost_tier` | `str` | — | `"low"`, `"medium"`, or `"high"` |
| `available` | `bool` | `False` | Whether binary was found on PATH |
| `version` | `str | None` | `None` | Version string (first 80 chars) |
| `user_preference` | `int | None` | `None` | Manual ranking (lower = preferred) |

### `SetupWizard`

| Method | Returns | Description |
|--------|---------|-------------|
| `discover()` | `None` | Populates internal tool list via `discover_tools()` |
| `available_tools()` | `list[ToolProfile]` | Returns only tools where `available=True` |
| `rank_tools(task_type)` | `list[ToolProfile]` | Sorts available tools by strength match, user pref, cost |
| `build_config()` | `dict` | Generates full config dict with tools and routing |
| `save_config(path=None)` | `None` | Writes config JSON to `~/.rolemesh/config.json` |
| `load_config(path=None)` | `dict | None` | Reads config from disk, returns `None` if missing |
| `validate_config(config)` | `list[str]` | Returns list of validation error messages |
| `register_tool(key, name, vendor, strengths, check_cmd, cost_tier)` | `ToolProfile` | Adds a custom tool at runtime |
| `unregister_tool(key)` | `bool` | Removes a tool from registry and tool list |
| `interactive_setup()` | `dict` | Runs interactive CLI wizard with user preference input |
| `summary()` | `str` | Returns formatted multi-line summary string |

### `TOOL_REGISTRY`

Module-level dict of 6 built-in tools:

| Key | Name | Vendor | Cost |
|-----|------|--------|------|
| `claude` | Claude Code | Anthropic | high |
| `codex` | Codex CLI | OpenAI | medium |
| `gemini` | Gemini CLI | Google | medium |
| `aider` | Aider | Community | low |
| `copilot` | GitHub Copilot CLI | GitHub | medium |
| `cursor` | Cursor | Cursor | medium |

---

## router.py

### `RoleMeshRouter`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(config_path=None)` | — | Loads routing config from JSON file |
| `classify_task(request)` | `list[tuple[str, float]]` | Pattern-matches request against all task types |
| `route(request)` | `RouteResult` | Returns best routing decision for a request |
| `route_multi(request)` | `list[RouteResult]` | Returns routing decisions for all matching types |

### `RouteResult`

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Selected tool key |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Match confidence (0.0–1.0) |
| `fallback` | `str | None` | Fallback tool key |
| `reason` | `str | None` | Explanation for default routing |

### `TASK_PATTERNS`

Module-level list of 13 task types, each with regex pattern tuples supporting Korean and English keywords. See [ROUTER.md](ROUTER.md) for the full list.

---

## executor.py

### `RoleMeshExecutor`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(config_path=None, dry_run=False)` | — | Initializes Router and history path |
| `dispatch(task, tool=None)` | `ExecutionResult` | Routes and executes with automatic fallback |
| `run(tool_key, task, route_result=None)` | `ExecutionResult` | Executes a single tool invocation |

### `ExecutionResult`

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Executed tool key |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Classification confidence |
| `success` | `bool` | Whether exit code was 0 |
| `exit_code` | `int` | Process exit code |
| `duration_ms` | `int` | Execution time in ms |
| `stdout` | `str` | Captured stdout |
| `stderr` | `str` | Captured stderr |
| `fallback_used` | `bool` | Whether fallback tool was used |

### `TOOL_COMMANDS`

Module-level dict mapping tool keys to CLI command templates:

```python
{
    "claude": {"cmd": ["claude", "-p"], "stdin_mode": False},
    "codex":  {"cmd": ["codex", "-p"],  "stdin_mode": False},
    # ...
}
```

---

## dashboard.py

### `RoleMeshDashboard`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(config_path=None)` | — | Initializes with optional custom config path |
| `collect()` | `DashboardData` | Aggregates tools, config, health checks, and history |
| `render_full()` | `str` | All dashboard sections combined |
| `render_tools()` | `str` | Discovered tools section |
| `render_routing()` | `str` | Routing table section |
| `render_coverage()` | `str` | Task type x tool coverage matrix |
| `render_health()` | `str` | Health check results |
| `render_history()` | `str` | Recent execution history |
| `to_json()` | `dict` | Full dashboard data as JSON-serializable dict |

### `DashboardData`

| Field | Type | Description |
|-------|------|-------------|
| `tools` | `list[ToolProfile]` | All discovered tools |
| `config` | `dict | None` | Loaded config or None |
| `health` | `list[HealthCheck]` | Health check results |
| `history` | `list[dict]` | Recent execution history entries |

### `HealthCheck`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Check identifier |
| `passed` | `bool` | Whether the check passed |
| `detail` | `str` | Human-readable detail string |

### `Color`

Static ANSI color helper class.

| Method | Returns | Description |
|--------|---------|-------------|
| `Color.green(text)` | `str` | Green-colored text |
| `Color.red(text)` | `str` | Red-colored text |
| `Color.yellow(text)` | `str` | Yellow-colored text |
| `Color.dim(text)` | `str` | Dimmed text |
| `Color.bold(text)` | `str` | Bold text |
| `Color.set_enabled(flag)` | `None` | Force enable/disable colors |

Colors are automatically disabled when `NO_COLOR` env var is set or stdout is not a TTY.

---

## CLI Commands

All commands are available via `python -m src.rolemesh <command>`:

| Command | Description |
|---------|-------------|
| `setup [--save] [--interactive]` | Discover tools and optionally save config |
| `route "<task>" [--all] [--json]` | Classify and route a task |
| `exec "<task>" [--tool T] [--dry-run] [--json]` | Execute a task via routed tool |
| `dashboard [--tools\|--routing\|--coverage\|--health\|--history] [--json] [--config PATH]` | Show dashboard |
| `status [--json]` | Quick status overview |

---

## File Paths

| Path | Purpose |
|------|---------|
| `~/.rolemesh/config.json` | Tool profiles + routing rules |
| `~/.rolemesh/history.jsonl` | Append-only execution log |

---

## Related Docs

- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Getting started with tool discovery
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration schema and validation
- [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) — Adding custom tools
- [ROUTER.md](ROUTER.md) — Task classification and routing
- [EXECUTOR.md](EXECUTOR.md) — Task execution and fallback
- [DASHBOARD_CLI.md](DASHBOARD_CLI.md) — Terminal dashboard
