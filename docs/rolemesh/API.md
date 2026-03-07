# RoleMesh API Reference

## builder.py — Tool Discovery & Setup

### `discover_tools() -> list[ToolProfile]`

Probes the system for all known AI CLI tools. Checks binary availability via `shutil.which` and extracts version strings from `--version` output.

### `ToolProfile`

```python
@dataclass
class ToolProfile:
    key: str                       # registry key (e.g. "claude")
    name: str                      # display name (e.g. "Claude Code")
    vendor: str                    # vendor name (e.g. "Anthropic")
    strengths: list[str]           # task types this tool excels at
    cost_tier: str                 # "low" | "medium" | "high"
    available: bool = False        # True if binary found on PATH
    version: Optional[str] = None  # version string from CLI
    user_preference: int = 0       # 0=neutral, 1=preferred, -1=avoid
```

Methods:
- `to_dict() -> dict` — serialize to dictionary via `dataclasses.asdict`

### `SetupWizard`

```python
wizard = SetupWizard()
wizard.config_path  # default: ~/.rolemesh/config.json
```

| Method | Returns | Description |
|---|---|---|
| `discover()` | `list[ToolProfile]` | Probe system for installed tools |
| `available_tools()` | `list[ToolProfile]` | Filter to available only |
| `rank_tools(task_type)` | `list[ToolProfile]` | Rank tools for a task type (best first) |
| `build_config()` | `dict` | Generate routing config from discovered tools |
| `save_config(path?)` | `Path` | Persist config to `~/.rolemesh/config.json` |
| `load_config(path?)` | `dict` | Load existing config from disk |
| `summary()` | `str` | Human-readable summary of discovered tools |

#### Ranking algorithm

`rank_tools(task_type)` scores each available tool:

- +10.0 if `task_type` is in the tool's `strengths`
- +5.0 / -5.0 based on `user_preference` (1 = preferred, -1 = avoid)
- +2.0 / +1.0 / +0.0 based on `cost_tier` (low / medium / high)

Tools are sorted by descending score.

### `TOOL_REGISTRY`

Built-in dictionary of known AI CLI tools. Each entry has: `name`, `vendor`, `strengths`, `check_cmd`, `cost_tier`.

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

If no config is loaded, routes default to `claude` as `DEFAULT_TOOL`.

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

Methods:
- `to_dict() -> dict` — serialize to dictionary

### Task Pattern Matching

Classification uses regex patterns against the request string. Each task type has 2 pattern groups; confidence = (matched groups / total groups). Patterns support both Korean and English keywords.

Confidence levels:
- `>= 0.8`: Strong match — "Strong match for '{task_type}'"
- `>= 0.5`: Good match — includes alternative suggestions
- `< 0.5`: Weak match — "consider specifying task type"
- No match: defaults to `("coding", 0.3)`

### `TASK_PATTERNS`

List of `(task_type, [regex_pattern, ...])` tuples defining 13 task categories.

---

## executor.py — Task Execution

### `RoleMeshExecutor`

```python
executor = RoleMeshExecutor(
    config_path=None,   # routing config path
    dry_run=False,      # if True, show command without executing
)
```

| Method | Returns | Description |
|---|---|---|
| `dispatch(task, tool?)` | `ExecutionResult` | Classify + route + execute (optionally force a specific tool) |
| `run(tool_key, task, route_result)` | `ExecutionResult` | Execute a task with a specific tool |

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    tool: str              # tool key used
    tool_name: str         # display name
    task_type: str         # classified task type
    confidence: float      # routing confidence
    exit_code: int         # subprocess exit code (0 = success)
    success: bool          # exit_code == 0
    duration_ms: int       # execution time in milliseconds
    fallback_used: bool    # True if primary tool failed
    stdout: str            # captured stdout
    stderr: str            # captured stderr
```

### `TOOL_COMMANDS`

Maps tool keys to CLI command templates:

| Tool | Command | Mode |
|---|---|---|
| `claude` | `claude -p <prompt>` | arg |
| `codex` | `codex -p <prompt>` | arg |
| `gemini` | `gemini -p <prompt>` | arg |
| `aider` | `aider --message <prompt>` | arg |
| `copilot` | `gh copilot -p <prompt>` | arg |
| `cursor` | `cursor -p <prompt>` | arg |

### Execution behavior

- Subprocess timeout: 300 seconds
- History logged to `~/.rolemesh/history.jsonl` (JSONL format)
- Each history entry: `timestamp`, `tool`, `task_type`, `success`, `duration_ms`
- Unknown tool key returns exit code 1 with stderr message

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
| `render_history()` | `str` | Last 10 execution history entries |
| `to_json()` | `dict` | Machine-readable dashboard data |

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

### `DashboardData`

```python
@dataclass
class DashboardData:
    tools: list              # list of ToolProfile
    config: Optional[dict]   # loaded config or None
    routing: dict            # routing rules from config
    health: list             # list of HealthCheck
    history: list            # parsed JSONL history entries
```

---

## __main__.py — CLI Entry Point

Unified CLI with argparse subcommands. Dispatches to `cmd_dashboard`, `cmd_setup`, `cmd_route`, `cmd_exec`, `cmd_status`. All subcommands support `--json` output.
