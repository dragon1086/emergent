# Executor — Task Dispatch & Execution

> Dispatches classified tasks to AI CLI tools with automatic fallback and history logging.

---

## Overview

The Executor module (`executor.py`) is the final stage of the RoleMesh pipeline. It receives a routing decision from the Router, builds the appropriate CLI command, runs the AI tool as a subprocess, and logs the result. If the primary tool fails, it automatically retries with the fallback tool.

---

## Quick Start

### CLI usage

```bash
# Execute a task (auto-routed)
python -m src.rolemesh exec "add input validation to login"

# Force a specific tool
python -m src.rolemesh exec "add input validation" --tool claude

# Dry run (show command without executing)
python -m src.rolemesh exec "add input validation" --dry-run

# JSON output
python -m src.rolemesh exec "add input validation" --json
```

### Example output

```
  Tool: aider | Type: coding | [OK] | 4200ms
```

With `--dry-run`:

```
  Tool: aider | Type: coding | [OK] | 0ms
  [dry-run] would execute: aider --message add input validation to login
```

---

## Pipeline Flow

```
User request
  → Router.route()          # classify + select tool
  → Executor.dispatch()     # build command + run
    → run(primary)          # try primary tool
    → if fail: run(fallback)# retry with fallback
    → log_history()         # append to history.jsonl
  → ExecutionResult
```

---

## Tool Commands

Each registered tool maps to a CLI command pattern:

| Tool Key | Command | Mode |
|----------|---------|------|
| `claude` | `claude -p "<task>"` | flag |
| `codex` | `codex -p "<task>"` | flag |
| `gemini` | `gemini -p "<task>"` | flag |
| `aider` | `aider --message "<task>"` | flag |
| `copilot` | `gh copilot -p "<task>"` | flag |
| `cursor` | `cursor -p "<task>"` | flag |

Custom tools can use `stdin_mode: True` to pipe the task string to stdin instead of passing it as a CLI flag. See [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) for details.

---

## Fallback Mechanism

When the primary tool returns a non-zero exit code:

1. The Executor checks if a `fallback` tool was specified in the routing config
2. If available, the same task is dispatched to the fallback tool
3. The fallback result has `fallback_used = True`
4. If no fallback is configured (or fallback also fails), the original failure is returned

```
dispatch("analyze this code")
  → route: primary=codex, fallback=claude
  → run(codex) → exit_code=1 (FAIL)
  → run(claude) → exit_code=0 (OK, fallback_used=True)
  → return claude result
```

---

## Execution History

Every execution is logged to `~/.rolemesh/history.jsonl` (append-only):

```json
{"timestamp": "2026-03-07T10:15:00", "tool": "claude", "task_type": "coding", "success": true, "duration_ms": 1200}
{"timestamp": "2026-03-07T10:12:30", "tool": "aider", "task_type": "refactoring", "success": false, "duration_ms": 3400}
```

View history via the dashboard:

```bash
python -m src.rolemesh dashboard --history
```

### History fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `string` | ISO 8601 local time |
| `tool` | `string` | Tool key that was executed |
| `task_type` | `string` | Classified task type |
| `success` | `boolean` | Whether exit code was 0 |
| `duration_ms` | `integer` | Wall-clock execution time in milliseconds |

---

## Programmatic Usage

```python
from src.rolemesh.executor import RoleMeshExecutor

# Standard execution
executor = RoleMeshExecutor()
result = executor.dispatch("refactor the auth module")
print(f"Tool: {result.tool_name} | Success: {result.success} | Time: {result.duration_ms}ms")

# Force a specific tool
result = executor.dispatch("refactor the auth module", tool="claude")

# Dry run
executor = RoleMeshExecutor(dry_run=True)
result = executor.dispatch("any task")
print(result.stdout)  # "[dry-run] would execute: ..."
```

### Custom config path

```python
from pathlib import Path
executor = RoleMeshExecutor(config_path=Path("/custom/config.json"))
```

---

## API Reference

### `RoleMeshExecutor`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(config_path=None, dry_run=False)` | — | Initializes with a Router instance and optional dry-run mode |
| `dispatch(task, tool=None)` | `ExecutionResult` | Routes and executes a task. Optionally forces a specific tool. Handles fallback automatically. |
| `run(tool_key, task, route_result=None)` | `ExecutionResult` | Executes a task with a specific tool. Called internally by `dispatch`. |

### `ExecutionResult`

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Tool that was executed |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Classification confidence |
| `success` | `bool` | Whether exit code was 0 |
| `exit_code` | `int` | Process exit code (-1 for internal errors) |
| `duration_ms` | `int` | Wall-clock execution time in milliseconds |
| `stdout` | `str` | Captured stdout from the tool |
| `stderr` | `str` | Captured stderr from the tool |
| `fallback_used` | `bool` | Whether this result came from a fallback tool |

### Timeout

All tool executions have a 300-second (5-minute) timeout. If exceeded, the process is killed and the result returns `success=False` with the timeout error in `stderr`.

---

## Related Docs

- [ROUTER.md](ROUTER.md) — Task classification and routing
- [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) — Adding custom tools with command mappings
- [DASHBOARD_CLI.md](DASHBOARD_CLI.md) — Viewing execution history
