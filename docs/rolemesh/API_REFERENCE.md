# RoleMesh API Reference

> Public interface for tool discovery, config generation, and task routing

## Module: `src.rolemesh`

```python
from src.rolemesh import SetupWizard, ToolProfile, discover_tools, RoleMeshRouter
```

---

## Router (`src.rolemesh.router`)

### `RoleMeshRouter`

Routes user requests to the best available AI tool based on config.

```python
router = RoleMeshRouter(config_path=None)
```

**Parameters:**
- `config_path` (Path, optional): Path to routing config. Defaults to `~/.rolemesh/config.json`

---

### `RoleMeshRouter.classify_task(request: str) -> list[tuple[str, float]]`

Classifies a request into task types with confidence scores.

**Parameters:**
- `request` (str): Natural language task description (Korean or English)

**Returns:** Sorted list of `(task_type, confidence)` tuples, highest confidence first.

**Example:**
```python
router = RoleMeshRouter()
types = router.classify_task("이 함수 리팩토링해줘")
# [("refactoring", 1.0), ("coding", 0.5)]
```

If no patterns match, returns `[("coding", 0.3)]` as default.

---

### `RoleMeshRouter.route(request: str) -> RouteResult`

Routes a request to the best tool. Uses the highest-confidence classification and looks up the routing config.

**Parameters:**
- `request` (str): Task description

**Returns:** `RouteResult`

**Example:**
```python
result = router.route("UI 컴포넌트 디자인")
print(result.tool)       # "gemini"
print(result.tool_name)  # "Gemini CLI"
print(result.task_type)  # "frontend"
print(result.confidence) # 1.0
print(result.fallback)   # "claude"
print(result.reason)     # "Strong match for 'frontend'"
```

Without config, always returns `tool="claude"`.

---

### `RoleMeshRouter.route_multi(request: str) -> list[RouteResult]`

Returns routing suggestions for all matched task types. Useful for complex requests that span multiple categories.

**Parameters:**
- `request` (str): Task description

**Returns:** List of `RouteResult` objects, one per matched task type.

**Example:**
```python
results = router.route_multi("코드 리팩토링 개선해줘")
for r in results:
    print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool_name}")
# [100%] refactoring -> Codex CLI
# [ 50%] coding -> Claude Code
```

---

### `RouteResult`

```python
@dataclass
class RouteResult:
    tool: str              # Tool key (e.g., "claude", "gemini")
    tool_name: str         # Display name (e.g., "Claude Code")
    task_type: str         # Classified task category
    confidence: float      # Match strength (0.0 - 1.0)
    fallback: Optional[str]  # Backup tool key, or None
    reason: str            # Human-readable routing explanation
```

**Methods:**
- `to_dict() -> dict`: Serializes to dictionary (confidence rounded to 2 decimals)

---

## Builder (`src.rolemesh.builder`)

### `discover_tools() -> list[ToolProfile]`

Probes the system for all known AI CLI tools. Checks PATH for each tool's binary and attempts to read its version.

**Returns:** List of `ToolProfile` objects for all registered tools (both available and unavailable).

**Example:**
```python
from src.rolemesh import discover_tools

profiles = discover_tools()
for p in profiles:
    status = "installed" if p.available else "not found"
    print(f"  {p.name}: {status}")
```

---

### `SetupWizard`

Orchestrates tool discovery, ranking, and config generation.

```python
wizard = SetupWizard(config_path=None)
```

**Parameters:**
- `config_path` (Path, optional): Where to save/load config. Defaults to `~/.rolemesh/config.json`

---

### `SetupWizard.discover() -> list[ToolProfile]`

Runs `discover_tools()` and stores results internally.

**Returns:** List of all `ToolProfile` objects.

---

### `SetupWizard.available_tools() -> list[ToolProfile]`

Filters to only tools with `available=True`.

---

### `SetupWizard.rank_tools(task_type: str) -> list[ToolProfile]`

Ranks available tools for a given task type by relevance.

**Parameters:**
- `task_type` (str): Task category to rank for (e.g., `"coding"`, `"frontend"`)

**Returns:** Available tools sorted by score (best first).

**Scoring:**
- Strength match: +10.0
- User preference: +5.0 (preferred), 0 (neutral), -5.0 (avoid)
- Cost tier: +2.0 (low), +1.0 (medium), +0.0 (high)

**Example:**
```python
wizard = SetupWizard()
wizard.discover()
ranked = wizard.rank_tools("coding")
print(ranked[0].name)  # Best tool for coding tasks
```

---

### `SetupWizard.build_config() -> dict`

Generates a complete routing configuration from discovered tools.

**Returns:** Config dict with structure:
```json
{
  "version": "1.0.0",
  "tools": {
    "claude": { "key": "claude", "name": "Claude Code", ... }
  },
  "routing": {
    "coding": { "primary": "claude", "fallback": "codex" }
  }
}
```

---

### `SetupWizard.save_config(path=None) -> Path`

Persists config to disk. Creates parent directories if needed.

**Returns:** Path where config was saved.

---

### `SetupWizard.load_config(path=None) -> dict`

Loads existing config from disk. Returns empty dict if file doesn't exist.

---

### `SetupWizard.summary() -> str`

Returns a human-readable summary of discovered tools.

**Example:**
```python
print(wizard.summary())
# Found 3 AI tool(s):
#   - Claude Code v1.0 (Anthropic) [coding, analysis, reasoning, architecture]
#   - Codex CLI v0.1 (OpenAI) [coding, refactoring, quick-edit]
#   - Gemini CLI v2.0 (Google) [multimodal, search, ui-design, frontend]
```

---

## Data Types

### `ToolProfile`

```python
@dataclass
class ToolProfile:
    key: str                    # Registry key (e.g., "claude")
    name: str                   # Display name (e.g., "Claude Code")
    vendor: str                 # Company (e.g., "Anthropic")
    strengths: list[str]        # Task types this tool excels at
    cost_tier: str              # "low", "medium", or "high"
    available: bool = False     # Whether binary found on PATH
    version: Optional[str] = None  # Detected version string
    user_preference: int = 0    # 1=preferred, 0=neutral, -1=avoid
```

**Methods:**
- `to_dict() -> dict`: Serializes all fields to dictionary

---

## CLI Usage

### Router CLI

```bash
# Route a single request
python -m src.rolemesh.router "이 함수 구현해줘"
# -> Claude Code (claude)
#    Task: coding (100%)
#    Strong match for 'coding'

# JSON output
python -m src.rolemesh.router "UI 디자인" --json

# Show all matching task types
python -m src.rolemesh.router "코드 리팩토링" --all
```

### Builder CLI

```bash
# Discover tools (display only)
python -m src.rolemesh.builder

# Save config
python -m src.rolemesh.builder --save

# Interactive setup with preferences
python -m src.rolemesh.builder --interactive

# JSON output
python -m src.rolemesh.builder --json
```

---

## Constants

### `TOOL_REGISTRY` (builder.py)

Dict of known AI CLI tools and their profiles. Keys: `claude`, `codex`, `gemini`, `aider`, `copilot`, `cursor`.

### `TASK_PATTERNS` (router.py)

List of `(task_type, [regex_patterns])` tuples defining the 13 task categories. Patterns support Korean and English.

### `RoleMeshRouter.DEFAULT_TOOL`

Fallback tool when no config exists. Value: `"claude"`.

---

## Dashboard (`src.rolemesh.dashboard`)

### `RoleMeshDashboard`

Collects and displays unified system status: tools, routing, coverage, and health.

```python
dashboard = RoleMeshDashboard(config_path=None)
```

**Parameters:**
- `config_path` (Path, optional): Path to routing config. Defaults to `~/.rolemesh/config.json`

---

### `RoleMeshDashboard.collect() -> DashboardData`

Gathers all dashboard data: discovers tools, loads config, runs health checks.

**Returns:** `DashboardData` with all fields populated.

**Example:**
```python
dashboard = RoleMeshDashboard()
data = dashboard.collect()
print(f"{len(data.tools)} tools, {len(data.task_types)} task types")
```

---

### `RoleMeshDashboard.render_tools() -> str`

Renders installed and missing tools as formatted text.

### `RoleMeshDashboard.render_routing() -> str`

Renders the routing table (task type -> primary + fallback).

### `RoleMeshDashboard.render_coverage() -> str`

Renders the task/tool coverage matrix with strength and route markers.

### `RoleMeshDashboard.render_health() -> str`

Renders health check results with pass/fail indicators and score.

### `RoleMeshDashboard.render_full() -> str`

Renders all sections combined into a full dashboard view.

---

### `DashboardData`

```python
@dataclass
class DashboardData:
    tools: list[ToolProfile]          # All discovered tools
    config: dict                       # Loaded config
    routing: dict                      # Routing rules from config
    health_checks: list[HealthCheck]   # Health check results
    task_types: list[str]              # All known task types
```

**Methods:**
- `to_dict() -> dict`: Serializes to dictionary for JSON output

---

### `HealthCheck`

```python
@dataclass
class HealthCheck:
    name: str       # Check identifier (e.g., "config_file")
    passed: bool    # Whether the check passed
    detail: str     # Human-readable detail message
```

---

## Executor (`src.rolemesh.executor`)

### `RoleMeshExecutor`

Routes and dispatches tasks to AI CLI tools via subprocess.

```python
executor = RoleMeshExecutor(config_path=None, timeout=120, dry_run=False)
```

**Parameters:**
- `config_path` (Path, optional): Path to routing config
- `timeout` (int): Subprocess timeout in seconds (default: 120)
- `dry_run` (bool): If True, show commands without executing

---

### `RoleMeshExecutor.run(request: str, context: dict = None) -> ExecutionResult`

Full pipeline: classify, route, check availability, execute (with fallback on failure).

**Parameters:**
- `request` (str): Natural language task description
- `context` (dict, optional): `{"files": [...], "cwd": "/path"}`

**Returns:** `ExecutionResult`

**Example:**
```python
executor = RoleMeshExecutor()
result = executor.run("이 함수 구현해줘")
if result.success:
    print(result.stdout)
else:
    print(f"Failed: {result.stderr}")
```

---

### `RoleMeshExecutor.dispatch(tool_key: str, prompt: str, context: dict = None) -> ExecutionResult`

Dispatches directly to a specific tool, skipping the router.

**Parameters:**
- `tool_key` (str): Tool key (e.g., `"claude"`, `"codex"`)
- `prompt` (str): Task prompt
- `context` (dict, optional): File and working directory context

---

### `RoleMeshExecutor.check_tool(tool_key: str) -> bool`

Checks if a tool's CLI binary is available on PATH.

### `RoleMeshExecutor.build_command(tool_key: str, prompt: str, context: dict = None) -> list[str] | None`

Builds the CLI command list for a given tool. Returns None for unknown tools.

---

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    tool: str              # Tool key
    tool_name: str         # Display name
    task_type: str         # Classified task category
    confidence: float      # Routing confidence (0.0 - 1.0)
    exit_code: int         # Process exit code (0 = success)
    stdout: str            # Tool output
    stderr: str            # Error output
    duration_ms: int       # Execution time in milliseconds
    fallback_used: bool    # Whether fallback tool was used
```

**Properties:**
- `success -> bool`: True if `exit_code == 0`

**Methods:**
- `to_dict() -> dict`: Serializes all fields to dictionary

**Special exit codes:** `0` = success, `-1` = timeout, `126` = OS error, `127` = tool not found

---

## Constants

### `TOOL_COMMANDS` (executor.py)

Dict mapping tool keys to CLI command configs. Keys: `claude`, `codex`, `gemini`, `aider`, `copilot`, `cursor`. Each entry has `cmd` (command list) and `stdin_mode` (bool).
