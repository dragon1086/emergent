# RoleMesh API Reference

## builder.py — Tool Discovery & Setup

### `discover_tools() -> list[ToolProfile]`

Probes the system for all known AI CLI tools. Checks binary availability via `shutil.which` and extracts version strings from `--version` output.

### `ToolProfile`

```python
@dataclass
class ToolProfile:
    key: str                        # registry key (e.g. "claude")
    name: str                       # display name (e.g. "Claude Code")
    vendor: str                     # vendor name (e.g. "Anthropic")
    strengths: list[str]            # task types this tool excels at
    cost_tier: str                  # "low" | "medium" | "high"
    available: bool = False         # True if binary found on PATH
    version: Optional[str] = None   # version string from CLI
    user_preference: Optional[int] = None  # user ranking override
```

### `SetupWizard`

| Method | Returns | Description |
|---|---|---|
| `discover()` | `list[ToolProfile]` | Probe system for installed tools |
| `available_tools()` | `list[ToolProfile]` | Filter to available only |
| `rank_tools(task_type)` | `list[ToolProfile]` | Rank tools for a task type (best first) |
| `build_config()` | `dict` | Generate routing config from discovered tools |
| `save_config(path?)` | `Path` | Persist config to `~/.rolemesh/config.json` |
| `load_config(path?)` | `dict \| None` | Load existing config from disk |
| `validate_config(config)` | `list[str]` | Validate config schema; returns error list |
| `register_tool(key, name, vendor, strengths, check_cmd, cost_tier)` | `ToolProfile` | Register and discover a custom tool |
| `unregister_tool(key)` | `bool` | Remove a custom tool |
| `summary()` | `str` | Human-readable summary of discovered tools |

---

## router.py — Task Classification & Routing

### `RoleMeshRouter`

```python
router = RoleMeshRouter(config_path=None)  # loads ~/.rolemesh/config.json
```

| Method | Returns | Description |
|---|---|---|
| `classify_task(request)` | `list[tuple[str, float]]` | Classify request into task types with confidence scores |
| `route(request)` | `RouteResult` | Route to the single best tool |
| `route_multi(request)` | `list[RouteResult]` | Return suggestions for all matched task types |

### `RouteResult`

```python
@dataclass
class RouteResult:
    tool: str              # tool key (e.g. "claude")
    tool_name: str         # display name
    task_type: str         # classified task type
    confidence: float      # 0.0 - 1.0
    fallback: str | None   # fallback tool key
    reason: str            # human-readable routing explanation
```

### Task Pattern Matching

Classification uses regex patterns against the request string. Each task type has 2 pattern groups; confidence = (matched groups / total groups). Patterns support both Korean and English keywords.

Confidence levels:
- `>= 0.8`: Strong match
- `>= 0.5`: Good match
- `< 0.5`: Weak match (consider specifying task type)

---

## executor.py — Task Execution

### `RoleMeshExecutor`

```python
executor = RoleMeshExecutor(
    config_path=None,      # routing config path
    timeout=120,           # subprocess timeout (seconds)
    dry_run=False,         # if True, show command without executing
    history_path=None,     # JSONL log path (default: ~/.rolemesh/history.jsonl)
)
```

| Method | Returns | Description |
|---|---|---|
| `run(request, context?)` | `ExecutionResult` | Full pipeline: classify + route + execute (with fallback) |
| `dispatch(tool_key, prompt, context?)` | `ExecutionResult` | Direct dispatch to a specific tool (skip routing) |
| `check_tool(tool_key)` | `bool` | Check if tool binary is on PATH |
| `build_command(tool_key, prompt, context?)` | `list[str]` | Build CLI command for a tool |
| `get_history(limit=50)` | `list[dict]` | Read recent execution history |

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    tool: str              # tool key used
    tool_name: str         # display name
    task_type: str         # classified task type
    confidence: float      # routing confidence
    exit_code: int         # subprocess exit code
    stdout: str            # captured stdout
    stderr: str            # captured stderr
    duration_ms: int       # execution time
    fallback_used: bool    # True if primary tool failed

    @property
    def success(self) -> bool:  # exit_code == 0
```

### Context dict

The optional `context` parameter accepts:

| Key | Type | Description |
|---|---|---|
| `files` | `list[str]` | File paths to pass as CLI arguments |
| `cwd` | `str` | Working directory for subprocess |

### Fallback behavior

1. If primary tool is not installed: try fallback tool
2. If primary tool fails (non-zero exit): try fallback tool
3. If neither is available: return exit code 127

---

## dashboard.py — System Dashboard

### `RoleMeshDashboard`

```python
dashboard = RoleMeshDashboard(config_path=None, history_path=None)
dashboard.collect()  # gather all data
```

| Method | Returns | Description |
|---|---|---|
| `collect()` | `DashboardData` | Gather tools, config, routing, health, history |
| `render_full()` | `str` | Full dashboard (all sections) |
| `render_tools()` | `str` | Installed tools section |
| `render_routing()` | `str` | Routing table |
| `render_coverage()` | `str` | Task type x tool coverage matrix |
| `render_health()` | `str` | Health check results |
| `render_history()` | `str` | Execution history table |

### Health Checks

| Check | Passes when |
|---|---|
| `config_file` | `~/.rolemesh/config.json` exists |
| `tools_available` | At least 1 tool is installed |
| `routing_coverage` | All 13 task types have routing rules |
| `config_version` | Config version is `"1.0.0"` |
| `no_dead_refs` | No routing rules reference missing tools |

### `Color`

ANSI color helper. Respects `NO_COLOR` env var and non-TTY detection. Can be force-disabled via `Color.set_enabled(False)`.
