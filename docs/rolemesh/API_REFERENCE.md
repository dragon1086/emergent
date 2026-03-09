# RoleMesh API Reference

> Python API for builder, router, executor, and dashboard modules

## builder - Tool Discovery & Config

### `discover_tools() -> list[ToolProfile]`

Probe the system for all known AI CLI tools. Returns a list of `ToolProfile` objects with `available` set based on `shutil.which()`.

```python
from src.rolemesh.builder import discover_tools

tools = discover_tools()
for t in tools:
    print(f"{t.name}: {'installed' if t.available else 'not found'}")
```

### `ToolProfile`

Dataclass representing a discovered tool.

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Unique identifier (e.g., `"claude"`) |
| `name` | `str` | Display name (e.g., `"Claude Code"`) |
| `vendor` | `str` | Vendor name |
| `strengths` | `list[str]` | Task types the tool excels at |
| `cost_tier` | `str` | `"low"`, `"medium"`, or `"high"` |
| `available` | `bool` | Whether the CLI binary was found on PATH |
| `version` | `str \| None` | Detected version string |
| `user_preference` | `int` | User preference score (`1` prefer, `-1` avoid, `0` neutral) |

### `SetupWizard`

Orchestrates tool discovery, ranking, and config generation.

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()
```

#### `SetupWizard(config_path: Path = ~/.rolemesh/config.json)`

Constructor. Optionally override the config file path.

#### `discover() -> list[ToolProfile]`

Run tool discovery. Populates `self.tools`.

#### `available_tools() -> list[ToolProfile]`

Return only tools where `available=True`.

#### `rank_tools(task_type: str) -> list[ToolProfile]`

Rank available tools for a task type. Sorted by: strength match > user preference > lower cost.

```python
ranked = wizard.rank_tools("refactoring")
print(f"Best tool for refactoring: {ranked[0].name}")
```

#### `build_config() -> dict`

Generate a routing config dict from discovered tools.

#### `save_config(path: Path = None) -> None`

Persist config to disk. Creates parent directories if needed.

#### `load_config(path: Path = None) -> dict`

Load existing config from disk. Returns `{}` if file doesn't exist.

#### `validate_config(config: dict) -> list[str]` (static)

Validate a config dict. Returns a list of error strings (empty = valid).

```python
errors = SetupWizard.validate_config(config)
if errors:
    raise ValueError(f"Invalid config: {errors}")
```

#### `register_tool(key, name, vendor, strengths, check_cmd, cost_tier) -> ToolProfile`

Register a custom tool into the registry and discover it.

```python
profile = wizard.register_tool(
    key="my-tool",
    name="My Tool",
    vendor="My Company",
    strengths=["coding", "analysis"],
    check_cmd=["my-tool", "--version"],
    cost_tier="low",
)
```

#### `unregister_tool(key: str) -> bool`

Remove a tool from the registry. Returns `True` if the tool was found.

#### `summary() -> str`

Human-readable summary of discovered tools.

---

## router - Task Classification & Routing

### `TASK_PATTERNS`

List of `(task_type, [regex_patterns])` tuples defining 13 bilingual task types:

`coding`, `refactoring`, `quick-edit`, `analysis`, `architecture`, `reasoning`, `frontend`, `multimodal`, `search`, `explain`, `git-integration`, `completion`, `pair-programming`

### `RouteResult`

Dataclass for routing decisions.

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `str` | Selected tool key |
| `tool_name` | `str` | Display name |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Classification confidence (0.0-1.0) |
| `fallback` | `str \| None` | Fallback tool key |
| `reason` | `str` | Human-readable routing explanation |

#### `to_dict() -> dict`

Serialize to dictionary.

### `RoleMeshRouter`

Routes tasks to the best tool based on config.

#### `RoleMeshRouter(config_path: Path = None)`

Constructor. Loads config from `~/.rolemesh/config.json` (or given path).

#### `classify_task(request: str) -> list[tuple[str, float]]`

Classify a request into task types with confidence scores. Returns sorted list of `(task_type, confidence)`.

```python
from src.rolemesh.router import RoleMeshRouter

router = RoleMeshRouter()
classifications = router.classify_task("이 함수 리팩토링해줘")
# [("refactoring", 1.0), ("quick-edit", 0.5)]
```

#### `route(request: str) -> RouteResult`

Route a request to the best tool. Takes the highest-confidence classification, looks up primary + fallback from config.

```python
result = router.route("리팩토링해줘")
print(f"{result.tool_name} (confidence: {result.confidence:.0%})")
```

#### `route_multi(request: str) -> list[RouteResult]`

Return routing suggestions for all matched task types. Useful for complex requests spanning multiple categories.

```python
results = router.route_multi("코드 리팩토링하고 UI도 수정해줘")
for r in results:
    print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool}")
```

---

## executor - Task Dispatch & Execution

### `ExecutionResult`

Dataclass for execution outcomes.

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `str` | Tool key that was executed |
| `tool_name` | `str` | Display name |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Classification confidence |
| `exit_code` | `int` | Process exit code (`0`=success, `-1`=timeout, `126`=OS error, `127`=not found) |
| `stdout` | `str` | Standard output |
| `stderr` | `str` | Standard error |
| `duration_ms` | `int` | Execution time in milliseconds |
| `fallback_used` | `bool` | Whether the fallback tool was used |

#### `success -> bool` (property)

Returns `True` if `exit_code == 0`.

#### `to_dict() -> dict`

Serialize to dictionary.

### `RoleMeshExecutor`

Full pipeline: route, check availability, dispatch, fallback, log.

#### `RoleMeshExecutor(config_path=None, timeout=120, dry_run=False, history_path=None)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `config_path` | `~/.rolemesh/config.json` | Config file path |
| `timeout` | `120` | Subprocess timeout in seconds |
| `dry_run` | `False` | If `True`, show commands without executing |
| `history_path` | `~/.rolemesh/history.jsonl` | History log path |

#### `run(request: str, context: dict = None) -> ExecutionResult`

Full pipeline execution. Routes the request, checks tool availability, dispatches, and falls back on failure.

```python
from src.rolemesh.executor import RoleMeshExecutor

executor = RoleMeshExecutor()
result = executor.run("이 함수 리팩토링해줘")
if result.success:
    print(result.stdout)
else:
    print(f"Failed: {result.stderr}")
```

The `context` parameter accepts an optional dict with a `files` key listing file paths to pass to the tool.

#### `dispatch(tool_key: str, prompt: str, context: dict = None) -> ExecutionResult`

Dispatch directly to a specific tool, bypassing the router.

```python
result = executor.dispatch("codex", "explain this function")
```

#### `check_tool(tool_key: str) -> bool`

Check if a tool's CLI binary is available on PATH.

#### `build_command(tool_key: str, prompt: str, context: dict = None) -> list[str]`

Build the CLI command list for a tool without executing it. Returns empty list for unknown tools.

#### `get_history(limit: int = 50) -> list[dict]`

Read recent entries from `history.jsonl`.

---

## dashboard - Status & Health

### `HealthCheck`

Dataclass for health check results.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Check identifier |
| `passed` | `bool` | Whether the check passed |
| `detail` | `str` | Human-readable detail |

### `DashboardData`

Aggregated dashboard state.

| Field | Type | Description |
|-------|------|-------------|
| `tools` | `list[ToolProfile]` | All discovered tools |
| `config` | `dict` | Loaded config |
| `routing` | `dict` | Routing rules from config |
| `health_checks` | `list[HealthCheck]` | Health check results |
| `task_types` | `list[str]` | All 13 task type names |
| `history` | `list[dict]` | Recent execution history |

#### `to_dict() -> dict`

Serialize to dictionary (used for `--json` output).

### `RoleMeshDashboard`

Collects system status and renders views.

#### `RoleMeshDashboard(config_path=None, history_path=None)`

Constructor. Paths default to `~/.rolemesh/`.

#### `collect() -> DashboardData`

Gather all dashboard data: discover tools, load config, run health checks, load history.

```python
from src.rolemesh.dashboard import RoleMeshDashboard

dashboard = RoleMeshDashboard()
dashboard.collect()
print(dashboard.render_full())
```

#### Render methods

| Method | Description |
|--------|-------------|
| `render_tools()` | Tool list with availability, versions, strengths |
| `render_routing()` | Routing table (task type -> primary/fallback) |
| `render_coverage()` | Task type x tool coverage matrix |
| `render_health()` | 5 health checks with pass/fail |
| `render_history()` | Recent execution history with status/duration |
| `render_full()` | All sections combined |

### `Color`

ANSI color helper. Respects `NO_COLOR` env var and TTY detection.

```python
from src.rolemesh.dashboard import Color

Color.set_enabled(False)  # Disable colors programmatically
```

Static methods: `green()`, `red()`, `yellow()`, `cyan()`, `bold()`, `dim()`.
