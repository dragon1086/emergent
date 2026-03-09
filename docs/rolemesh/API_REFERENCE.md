# RoleMesh API Reference

Complete reference for all public classes, functions, and data types.

---

## builder.py

### `discover_tools() -> list[ToolProfile]`

Scans `TOOL_REGISTRY` for all known AI CLI tools. For each tool, checks if the binary is available via `shutil.which()` and attempts to capture its version string.

Returns a list of `ToolProfile` instances with `available` and `version` populated.

### `ToolProfile`

```python
@dataclass
class ToolProfile:
    key: str                          # Registry key (e.g. "claude")
    name: str                         # Display name (e.g. "Claude Code")
    vendor: str                       # Vendor (e.g. "Anthropic")
    strengths: list[str]              # Task types this tool handles well
    cost_tier: str                    # "low" | "medium" | "high"
    available: bool = False           # Whether the binary was found
    version: Optional[str] = None     # Captured version string
    user_preference: Optional[int] = None  # User ranking (1 = highest)
```

### `SetupWizard`

Main orchestrator for tool discovery and config management.

| Method | Description |
|---|---|
| `discover()` | Populate internal tool list via `discover_tools()` |
| `available_tools() -> list[ToolProfile]` | Filter to tools where `available=True` |
| `rank_tools(task_type: str) -> list[ToolProfile]` | Sort available tools by: strength match > user preference > cost tier |
| `build_config() -> dict` | Generate full config dict with `version`, `tools`, and `routing` |
| `save_config(path?)` | Write config JSON to `~/.rolemesh/config.json` (or custom path) |
| `load_config(path?) -> Optional[dict]` | Read existing config from disk |
| `validate_config(config: dict) -> list[str]` | Return list of validation errors (empty = valid) |
| `register_tool(key, name, vendor, strengths, check_cmd, cost_tier?) -> ToolProfile` | Add a custom tool to the registry at runtime |
| `unregister_tool(key: str) -> bool` | Remove a tool from the registry |
| `interactive_setup() -> dict` | Interactive CLI wizard: discover, rank, save |
| `summary() -> str` | One-line status of all tools |

**Config path**: `~/.rolemesh/config.json`

---

## router.py

### `RouteResult`

```python
@dataclass
class RouteResult:
    tool_name: str           # Selected tool key
    task_type: str           # Classified task type
    confidence: float        # Match confidence (0.0 - 1.0)
    fallback: Optional[str]  # Fallback tool key (from config)
    reason: Optional[str]    # Explanation when defaulting
```

### `RoleMeshRouter`

| Method | Description |
|---|---|
| `__init__(config_path?)` | Load routing config from `~/.rolemesh/config.json` |
| `classify_task(request: str) -> list[tuple[str, float]]` | Match request against `TASK_PATTERNS`, return `[(task_type, confidence)]` sorted by confidence descending |
| `route(request: str) -> RouteResult` | Classify and return the best route. Uses config routing if available, defaults to `claude` |
| `route_multi(request: str) -> list[RouteResult]` | Return all matching routes, not just the best one |

### `TASK_PATTERNS`

List of `(task_type, (pattern1, pattern2))` tuples. Each pattern is a regex string supporting both Korean and English keywords. Confidence = matched_patterns / total_patterns.

Recognized task types: `coding`, `refactoring`, `quick-edit`, `analysis`, `architecture`, `reasoning`, `frontend`, `multimodal`, `search`, `explain`, `git-integration`, `completion`, `pair-programming`.

---

## executor.py

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    tool_name: str        # Tool that ran
    task_type: str        # Classified task type
    confidence: float     # Routing confidence
    success: bool         # True if exit code == 0
    exit_code: int        # Process exit code (-1 for errors)
    duration_ms: int      # Execution time in milliseconds
    stdout: str = ""      # Captured stdout
    stderr: str = ""      # Captured stderr
    fallback_used: bool = False  # True if primary failed and fallback ran
```

### `RoleMeshExecutor`

| Method | Description |
|---|---|
| `__init__(config_path?, dry_run=False)` | Initialize with router and optional dry-run mode |
| `dispatch(task: str, tool?) -> ExecutionResult` | Route the task, execute via CLI, auto-fallback on failure |
| `run(tool_key: str, task: str, route_result?) -> ExecutionResult` | Execute a specific tool directly. In dry-run mode, returns without running |

**Execution flow**:
1. `dispatch()` calls `router.route(task)` to classify
2. Builds CLI command from `TOOL_COMMANDS` registry
3. Runs subprocess with 300s timeout
4. On failure, retries with `fallback` tool if configured
5. Logs result to `~/.rolemesh/history.jsonl`

### `TOOL_COMMANDS`

Maps tool keys to CLI invocation:

```python
{
    "claude": {"cmd": ["claude", "-p"], "stdin_mode": False},
    "codex":  {"cmd": ["codex", "-p"],  "stdin_mode": False},
    "gemini": {"cmd": ["gemini", "-p"], "stdin_mode": False},
    "aider":  {"cmd": ["aider", "--message"], "stdin_mode": False},
    "copilot": {"cmd": ["gh", "copilot", "-p"], "stdin_mode": False},
    "cursor": {"cmd": ["cursor", "-p"], "stdin_mode": False},
}
```

---

## dashboard.py

### `RoleMeshDashboard`

| Method | Description |
|---|---|
| `__init__(config_path?, history_path?)` | Initialize with optional custom paths |
| `collect() -> DashboardData` | Gather all data: tools, config, routing, health, history |
| `render_full() -> str` | Full dashboard output (all sections) |
| `render_tools() -> str` | Tool availability table |
| `render_routing() -> str` | Routing table with primary/fallback |
| `render_coverage() -> str` | Task type x tool coverage matrix |
| `render_health() -> str` | Health check results |
| `render_history() -> str` | Last 10 execution entries |
| `to_json() -> dict` | All data as JSON-serializable dict |

### Health Checks (5 total)

| Check | Pass Condition |
|---|---|
| `config_file` | `~/.rolemesh/config.json` exists |
| `tools_available` | At least 1 AI CLI tool is installed |
| `routing_coverage` | All 13 task types have routing rules |
| `config_version` | Config version is `1.0.0` |
| `no_dead_refs` | No routing rules reference missing tools |

### `DashboardData`

```python
@dataclass
class DashboardData:
    tools: list                    # list[ToolProfile]
    config: Optional[dict]         # Loaded config or None
    routing: dict                  # Config routing section
    health: list                   # list[HealthCheck]
    history: list                  # list[dict] from history.jsonl
```

### `HealthCheck`

```python
@dataclass
class HealthCheck:
    name: str       # Check identifier
    passed: bool    # True if check passed
    detail: str     # Human-readable detail
```

### `Color`

ANSI color helper class. Respects `NO_COLOR` env var and non-TTY detection.

Methods: `bold()`, `green()`, `red()`, `yellow()`, `cyan()`, `dim()`, `wrap()`, `set_enabled()`, `is_enabled()`.
