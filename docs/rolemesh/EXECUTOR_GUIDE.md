# Executor Guide

> Route and execute tasks via AI CLI tools

## Overview

The Executor module (`src/rolemesh/executor.py`) completes the RoleMesh pipeline. It takes a task description, routes it via the [Router](ROUTER_GUIDE.md), dispatches the command to the selected AI CLI tool, and handles fallback on failure.

## Quick Start

```bash
# Full pipeline: classify -> route -> execute
python -m src.rolemesh.executor "이 함수 리팩토링해줘"

# Dry run (show command without executing)
python -m src.rolemesh.executor --dry-run "UI 컴포넌트 수정"

# Force a specific tool (skip routing)
python -m src.rolemesh.executor --tool claude "explain this code"

# Custom timeout
python -m src.rolemesh.executor --timeout 300 "대규모 리팩토링"

# JSON output
python -m src.rolemesh.executor --json "코드 분석"
```

## Execution Pipeline

```
User Request -> Router.route() -> check_tool() -> dispatch() -> [fallback?] -> result
     |               |                |              |               |            |
  "리팩토링"    classify+route   shutil.which()   subprocess    on failure   ExecutionResult
                                                   (timeout)    try fallback
```

### Step 1: Route

The Executor delegates to `RoleMeshRouter.route()` to classify the task and select the best tool.

### Step 2: Availability Check

Before dispatching, the Executor verifies the selected tool binary exists on `PATH` via `shutil.which()`. If the primary tool is unavailable:
- If a fallback exists and is available, it switches automatically
- If neither is available, returns exit code `127` with an error message

### Step 3: Dispatch

The Executor builds a CLI command and runs it via `subprocess.run()`:

```
[tool_binary] -p "user prompt" [file1] [file2] ...
```

### Step 4: Fallback

If the primary tool fails (non-zero exit code) and a fallback tool is configured and available, the Executor retries with the fallback. The result's `fallback_used` flag is set to `True`.

## Supported Tools

| Key | Binary | Prompt Mode |
|-----|--------|-------------|
| `claude` | `claude` | `-p` flag |
| `codex` | `codex` | `-p` flag |
| `gemini` | `gemini` | `-p` flag |
| `aider` | `aider` | `-p` flag |
| `copilot` | `copilot` | `-p` flag |
| `cursor` | `cursor` | `-p` flag |

## ExecutionResult

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `str` | Tool key used |
| `tool_name` | `str` | Display name |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Routing confidence |
| `exit_code` | `int` | Process exit code (0 = success) |
| `stdout` | `str` | Tool's stdout output |
| `stderr` | `str` | Tool's stderr output |
| `duration_ms` | `int` | Execution time in milliseconds |
| `fallback_used` | `bool` | Whether fallback tool was used |
| `success` | `bool` | Property: `exit_code == 0` |

Special exit codes:
- `0`: Success
- `-1`: Timeout expired
- `126`: OS error (permission denied, etc.)
- `127`: Tool not found on PATH

## Programmatic Usage

```python
from src.rolemesh.executor import RoleMeshExecutor

# Full pipeline
executor = RoleMeshExecutor(timeout=120)
result = executor.run("이 함수 리팩토링해줘")
print(f"[{'OK' if result.success else 'FAIL'}] {result.tool_name}")
print(f"  Duration: {result.duration_ms}ms")

# Direct dispatch (skip routing)
result = executor.dispatch("claude", "explain this code")

# Dry run
executor = RoleMeshExecutor(dry_run=True)
result = executor.run("코드 분석")
print(result.stdout)  # "[dry-run] Would execute: claude -p ..."

# With file context
result = executor.run(
    "이 파일 리팩토링해줘",
    context={"files": ["src/main.py", "src/utils.py"]},
)
```

## Execution History

Every execution (except dry runs) is logged to `~/.rolemesh/history.jsonl` as a JSONL record:

```json
{
  "timestamp": "2026-03-07T10:00:00+00:00",
  "request": "이 함수 리팩토링해줘",
  "tool": "claude",
  "task_type": "refactoring",
  "confidence": 1.0,
  "success": true,
  "exit_code": 0,
  "duration_ms": 4521,
  "fallback_used": false
}
```

Read history programmatically:

```python
entries = executor.get_history(limit=50)
for e in entries:
    print(f"{e['timestamp']} {e['tool']} -> {'OK' if e['success'] else 'FAIL'}")
```

## See Also

- [Router Guide](ROUTER_GUIDE.md) — How tasks are classified and routed
- [Builder Guide](BUILDER_GUIDE.md) — Generate the routing config
- [Dashboard Guide](DASHBOARD_GUIDE.md) — Monitor execution history and health
- [API Reference](API_REFERENCE.md) — Full Python API
