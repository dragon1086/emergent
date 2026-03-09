# RoleMesh API Reference

## builder.py — Tool Discovery & Setup

### `discover_tools() -> list[ToolProfile]`

Probes the system PATH for all known AI CLI tools. Returns a list of `ToolProfile` objects with availability and version info.

### `ToolProfile`

```python
@dataclass
class ToolProfile:
    key: str                          # registry key (e.g. "claude")
    name: str                         # display name (e.g. "Claude Code")
    vendor: str                       # vendor (e.g. "Anthropic")
    strengths: list[str]              # capability tags
    cost_tier: str                    # "low" | "medium" | "high"
    available: bool = False           # True if found on PATH
    version: Optional[str] = None     # version string (first 80 chars)
    user_preference: Optional[int] = None  # manual rank (1=highest)
```

### `SetupWizard`

| Method | Description |
|--------|-------------|
| `discover() -> list[ToolProfile]` | Scan system for tools |
| `available_tools() -> list[ToolProfile]` | Filter to available only |
| `rank_tools(task_type: str) -> list[ToolProfile]` | Rank available tools for a task type (strength match > user pref > cost) |
| `build_config() -> dict` | Generate full routing config |
| `save_config(path?) -> Path` | Write config to disk (`~/.rolemesh/config.json`) |
| `load_config(path?) -> Optional[dict]` | Load existing config |
| `validate_config(config) -> list[str]` | Return list of validation errors |
| `register_tool(key, name, vendor, strengths, check_cmd, cost_tier) -> ToolProfile` | Add custom tool |
| `unregister_tool(key) -> bool` | Remove custom tool |
| `interactive_setup() -> dict` | Interactive CLI wizard |
| `summary() -> str` | One-line status string |

---

## router.py — Task Classification & Routing

### `TASK_PATTERNS`

List of `(task_type, (pattern1, pattern2, ...))` tuples. Each pattern is a regex supporting Korean and English keywords. Confidence = matched_patterns / total_patterns.

### `RouteResult`

```python
@dataclass
class RouteResult:
    tool: str              # tool key (e.g. "claude")
    tool_name: str         # display name
    task_type: str         # classified type (e.g. "coding")
    confidence: float      # 0.0 – 1.0
    fallback: Optional[str]  # fallback tool key
    reason: str            # human-readable explanation
```

### `RoleMeshRouter`

| Method | Description |
|--------|-------------|
| `__init__(config_path?)` | Load routing config from `~/.rolemesh/config.json` |
| `classify_task(request: str) -> list[tuple[str, float]]` | Return all matching task types with confidence, sorted descending |
| `route(request: str) -> RouteResult` | Best single route (top match → config lookup → fallback to Claude) |
| `route_multi(request: str) -> list[RouteResult]` | All matching routes |

**Default behavior**: When no config exists or no pattern matches, routes to Claude Code.

---

## executor.py — Task Dispatch

### `TOOL_COMMANDS`

Maps tool keys to CLI invocation commands:

```python
{
    "claude":  {"cmd": ["claude", "-p"],           "stdin_mode": False},
    "codex":   {"cmd": ["codex", "-p"],            "stdin_mode": False},
    "gemini":  {"cmd": ["gemini", "-p"],           "stdin_mode": False},
    "aider":   {"cmd": ["aider", "--message"],     "stdin_mode": False},
    "copilot": {"cmd": ["gh", "copilot", "-p"],    "stdin_mode": False},
    "cursor":  {"cmd": ["cursor", "-p"],           "stdin_mode": False},
}
```

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    tool: str              # tool key used
    tool_name: str         # display name
    task_type: str         # classified type
    confidence: float      # routing confidence
    exit_code: int         # process exit code
    success: bool          # exit_code == 0
    duration_ms: int       # wall-clock milliseconds
    fallback_used: bool    # True if primary failed and fallback ran
    stdout: str            # captured stdout
    stderr: str            # captured stderr
```

### `RoleMeshExecutor`

| Method | Description |
|--------|-------------|
| `__init__(config_path?, dry_run=False)` | Initialize with optional config and dry-run mode |
| `dispatch(task: str, tool?) -> ExecutionResult` | Route and execute. If primary fails, tries fallback automatically |
| `run(tool_key, task, route_result) -> ExecutionResult` | Execute a specific tool (internal) |

**Dry-run mode**: Returns a successful result with the command that would have been executed, without running it.

**History**: Each execution is appended to `~/.rolemesh/history.jsonl` as a JSON line with timestamp, tool, task_type, success, and duration_ms.

---

## dashboard.py — Terminal Dashboard

### `RoleMeshDashboard`

| Method | Description |
|--------|-------------|
| `collect() -> DashboardData` | Gather all data (tools, config, health, history) |
| `render_full() -> str` | Full dashboard (all sections) |
| `render_tools() -> str` | Tools table (name, vendor, cost, status, version) |
| `render_routing() -> str` | Routing table (task type → primary → fallback) |
| `render_coverage() -> str` | Coverage matrix (task types × tools) |
| `render_health() -> str` | Health checks (config, tools, routing, version, dead refs) |
| `render_history() -> str` | Recent execution history (last 10) |
| `to_json() -> dict` | All data as JSON-serializable dict |

### Health Checks

| Check | Passes when |
|-------|-------------|
| `config_file` | `~/.rolemesh/config.json` exists |
| `tools_available` | At least 1 AI CLI tool found on PATH |
| `routing_coverage` | All 14 task types have routing rules |
| `config_version` | Config version is `1.0.0` |
| `no_dead_refs` | No routing rules reference missing tools |

---

## CLI Commands

```
python -m src.rolemesh dashboard [--tools|--routing|--coverage|--health|--history] [--json]
python -m src.rolemesh setup [--save] [--interactive]
python -m src.rolemesh route "task" [--all] [--json]
python -m src.rolemesh exec "task" [--tool X] [--dry-run] [--json]
python -m src.rolemesh status [--json]
```

All commands support `--config PATH` to override the default config location.
