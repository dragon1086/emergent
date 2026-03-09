# RoleMesh Executor Guide

> Route and dispatch tasks to AI CLI tools via subprocess

## Overview

The Executor completes the RoleMesh pipeline: **discover -> route -> execute**. It takes a natural language request, routes it to the best tool via the Router, and dispatches it as a subprocess call.

```
User Request
     |
     v
[Router] classify + route
     |
     v
[Executor] check tool -> build command -> subprocess
     |
     v
ExecutionResult (stdout, stderr, exit_code, duration)
```

## Quick Start

### CLI

```bash
# Auto-route and execute
python -m src.rolemesh.executor "이 함수 리팩토링해줘"

# Dry-run (show command without executing)
python -m src.rolemesh.executor --dry-run "UI 컴포넌트 수정"

# Force a specific tool (skip routing)
python -m src.rolemesh.executor --tool claude "explain this code"

# Custom timeout (default: 120s)
python -m src.rolemesh.executor --timeout 300 "대규모 리팩토링"

# JSON output
python -m src.rolemesh.executor --json "함수 구현해줘"
```

### Programmatic

```python
from src.rolemesh.executor import RoleMeshExecutor

executor = RoleMeshExecutor()

# Full pipeline: route + execute
result = executor.run("이 함수 구현해줘")
print(result.tool)        # "claude"
print(result.success)     # True/False
print(result.stdout)      # tool output
print(result.duration_ms) # execution time

# Direct dispatch to a specific tool
result = executor.dispatch("codex", "refactor this function")

# With file context
result = executor.run("이 파일 리팩토링해줘", context={
    "files": ["src/main.py", "src/utils.py"],
    "cwd": "/path/to/project",
})
```

## Constructor Options

```python
RoleMeshExecutor(
    config_path=None,   # Path to routing config (default: ~/.rolemesh/config.json)
    timeout=120,        # Subprocess timeout in seconds
    dry_run=False,      # If True, show commands without executing
)
```

## Fallback Behavior

The executor has automatic fallback logic:

1. **Primary tool not on PATH** → try fallback tool from routing config
2. **Primary tool fails (non-zero exit)** → try fallback tool
3. **Both unavailable** → return error with exit_code 127

```python
result = executor.run("some task")
if result.fallback_used:
    print(f"Primary failed, used fallback: {result.tool}")
```

## Tool Commands

Each tool maps to a CLI invocation pattern:

| Tool | Command | Input Mode |
|------|---------|------------|
| claude | `claude -p <prompt>` | args |
| codex | `codex` (stdin) | stdin |
| gemini | `gemini` (stdin) | stdin |
| aider | `aider --message <prompt>` | args |
| copilot | `gh copilot suggest <prompt>` | args |
| cursor | `cursor` (stdin) | stdin |

**Args mode**: prompt is passed as a command-line argument.
**Stdin mode**: prompt is piped via stdin.

## ExecutionResult

```python
@dataclass
class ExecutionResult:
    tool: str           # Tool key (e.g., "claude")
    tool_name: str      # Display name
    task_type: str      # Classified task category
    confidence: float   # Routing confidence (0.0 - 1.0)
    exit_code: int      # Process exit code (0 = success)
    stdout: str         # Tool output
    stderr: str         # Error output
    duration_ms: int    # Execution time in milliseconds
    fallback_used: bool # Whether fallback tool was used

    @property
    def success(self) -> bool:  # exit_code == 0
```

**Special exit codes:**
- `0` — success
- `-1` — timeout
- `126` — OS error (permission denied, etc.)
- `127` — tool not found on PATH

## Dry-Run Mode

Test routing decisions without executing:

```python
executor = RoleMeshExecutor(dry_run=True)
result = executor.run("UI 디자인")
print(result.stdout)
# [dry-run] Would execute: gemini <prompt>
```

## Adding a New Tool

1. Add the CLI command mapping in `src/rolemesh/executor.py`:

```python
TOOL_COMMANDS["windsurf"] = {
    "cmd": ["windsurf", "--prompt"],
    "stdin_mode": False,
}
```

2. Add the tool profile in `src/rolemesh/builder.py` (see BUILDER_GUIDE.md).
3. Re-run the builder: `python -m src.rolemesh.builder --save`
