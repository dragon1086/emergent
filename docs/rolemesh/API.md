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
| `discover()` | `None` | Probe system for installed tools (populates internal list) |
| `available_tools()` | `list[ToolProfile]` | Filter to available only |
| `rank_tools(task_type)` | `list[ToolProfile]` | Rank available tools for a task type (best first) |
| `build_config()` | `dict` | Generate routing config from discovered tools |
| `save_config(path?)` | `None` | Persist config to `~/.rolemesh/config.json` |
| `load_config(path?)` | `dict \| None` | Load existing config from disk |
| `validate_config(config)` | `list[str]` | Validate config schema; returns error list |
| `register_tool(key, name, vendor, strengths, check_cmd, cost_tier)` | `ToolProfile` | Register and discover a custom tool |
| `unregister_tool(key)` | `bool` | Remove a custom tool |
| `interactive_setup()` | `dict` | Interactive CLI wizard with user ranking prompts |
| `summary()` | `str` | Human-readable summary of discovered tools |

Ranking score for `rank_tools()`: `(task_type match, user_preference, cost_tier)` — lower is better. Task-type match is binary (0 if in strengths, 1 otherwise), then user preference, then cost (low=0, medium=1, high=2).

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
| `route_multi(request)` | `list[RouteResult]` | Return all matched task types with their routed tools |

### `RouteResult`

```python
@dataclass
class RouteResult:
    tool_name: str              # tool key (e.g. "claude")
    task_type: str              # classified task type
    confidence: float           # 0.0 - 1.0
    fallback: Optional[str] = None   # fallback tool key
    reason: Optional[str] = None     # routing explanation (set when no config/no match)
```

### Task Pattern Matching

Classification uses regex patterns against the lowercased request string. Each task type has 2 pattern groups (tuples of regex); confidence = (matched groups / total groups). Patterns support both Korean and English keywords.

Confidence levels:
- `1.0`: Both pattern groups matched
- `0.5`: One pattern group matched
- `0.0`: No match (task type not returned)

When no pattern matches at all, `route()` defaults to `claude` with `confidence=0.0`.

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
| `dispatch(task, tool?)` | `ExecutionResult` | Full pipeline: route + execute (with automatic fallback) |
| `run(tool_key, task, route_result?)` | `ExecutionResult` | Direct execution of a specific tool |

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    tool_name: str          # tool key used
    task_type: str          # classified task type
    confidence: float       # routing confidence
    success: bool           # True if exit_code == 0
    exit_code: int          # subprocess exit code (-1 for errors)
    duration_ms: int        # execution time in milliseconds
    stdout: str = ""        # captured stdout
    stderr: str = ""        # captured stderr
    fallback_used: bool = False  # True if primary failed and fallback was used
```

### Tool Commands

Each tool maps to a CLI invocation pattern (`TOOL_COMMANDS`):

| Tool Key | Command | Notes |
|---|---|---|
| `claude` | `claude -p "<task>"` | Anthropic Claude Code |
| `codex` | `codex -p "<task>"` | OpenAI Codex CLI |
| `gemini` | `gemini -p "<task>"` | Google Gemini CLI |
| `aider` | `aider --message "<task>"` | Aider |
| `copilot` | `gh copilot -p "<task>"` | GitHub Copilot CLI |
| `cursor` | `cursor -p "<task>"` | Cursor |

### Fallback Behavior

1. `dispatch()` routes the task via `RoleMeshRouter`
2. Primary tool executes via `subprocess.run()` (timeout: 300s)
3. If primary fails (non-zero exit) and a fallback tool exists, fallback executes
4. `fallback_used=True` is set on the result when fallback was triggered

### Execution History

Each execution appends a JSON line to `~/.rolemesh/history.jsonl`:

```json
{"timestamp": "2026-03-07T12:00:00", "tool": "claude", "task_type": "coding", "success": true, "duration_ms": 1234}
```

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
| `render_history()` | `str` | Last 10 execution entries |
| `to_json()` | `dict` | Full dashboard data as JSON-serializable dict |

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
