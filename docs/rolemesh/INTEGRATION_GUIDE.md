# RoleMesh Integration Guide

> Using RoleMesh as a Python library in your own projects

## Installation

RoleMesh is a pure Python module with zero external dependencies. Add the `emergent` project to your Python path or install it as a package:

```python
import sys
sys.path.insert(0, "/path/to/emergent")

from src.rolemesh import (
    SetupWizard, ToolProfile, discover_tools,
    RoleMeshRouter,
    RoleMeshDashboard, DashboardData, HealthCheck,
    RoleMeshExecutor, ExecutionResult,
)
```

## Core Workflow

The typical integration follows a 4-step pipeline:

```
discover -> configure -> route -> execute
```

### Step 1: Discover Tools

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
profiles = wizard.discover()

for tool in wizard.available_tools():
    print(f"{tool.name} ({tool.vendor}) - {tool.strengths}")
```

### Step 2: Build & Save Config

```python
# Auto-generate routing based on discovered tools
config = wizard.build_config()

# Validate before saving
errors = SetupWizard.validate_config(config)
if not errors:
    wizard.save_config()
```

### Step 3: Route Tasks

```python
from src.rolemesh.router import RoleMeshRouter

router = RoleMeshRouter()  # reads ~/.rolemesh/config.json

# Single best match
result = router.route("implement a REST API endpoint")
print(f"Tool: {result.tool}, Type: {result.task_type}, Confidence: {result.confidence}")

# All matches (multi-classification)
results = router.route_multi("refactor and test this module")
for r in results:
    print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool}")
```

### Step 4: Execute

```python
from src.rolemesh.executor import RoleMeshExecutor

executor = RoleMeshExecutor()

# Route + execute in one call
result = executor.run("implement input validation")
print(f"Exit: {result.exit_code}, Duration: {result.duration_ms}ms")

# Direct dispatch (skip routing)
result = executor.dispatch("claude", "analyze this architecture")

# Dry run (preview command)
executor_dry = RoleMeshExecutor(dry_run=True)
result = executor_dry.run("design a UI component")
print(result.stdout)  # shows command that would run
```

## Custom Config Path

All components accept a `config_path` parameter:

```python
from pathlib import Path

config = Path("./project/.rolemesh/config.json")

wizard = SetupWizard(config_path=config)
router = RoleMeshRouter(config_path=config)
executor = RoleMeshExecutor(config_path=config)
dashboard = RoleMeshDashboard(config_path=config)
```

## Registering Custom Tools

Add tools at runtime without editing source:

```python
wizard = SetupWizard()
wizard.discover()

# Register a custom tool
profile = wizard.register_tool(
    key="my-tool",
    name="My Custom Tool",
    vendor="Internal",
    strengths=["coding", "data-science"],
    check_cmd=["my-tool", "--version"],
    cost_tier="low",
)

print(f"Available: {profile.available}")
wizard.save_config()  # persist the addition
```

Remove a tool:

```python
wizard.unregister_tool("my-tool")
wizard.save_config()
```

## Health Monitoring

```python
from src.rolemesh.dashboard import RoleMeshDashboard

dashboard = RoleMeshDashboard()
data = dashboard.collect()

# Programmatic health check
for check in data.health_checks:
    status = "OK" if check.passed else "FAIL"
    print(f"[{status}] {check.name}: {check.detail}")

# Serializable summary
summary = data.to_dict()
```

## Execution History

```python
executor = RoleMeshExecutor(
    history_path=Path("./rolemesh-history.jsonl"),
)

# History is logged automatically after each execution
result = executor.run("fix this bug")

# Read history
entries = executor.get_history(limit=10)
for entry in entries:
    print(f"{entry['timestamp']} {entry['tool']} -> {'OK' if entry['success'] else 'FAIL'}")
```

## Embedding in a Web Service

```python
from flask import Flask, request, jsonify
from src.rolemesh.router import RoleMeshRouter

app = Flask(__name__)
router = RoleMeshRouter()

@app.route("/api/route", methods=["POST"])
def route_task():
    task = request.json["task"]
    result = router.route(task)
    return jsonify(result.to_dict())

@app.route("/api/health")
def health():
    from src.rolemesh.dashboard import RoleMeshDashboard
    dashboard = RoleMeshDashboard()
    data = dashboard.collect()
    return jsonify({
        "healthy": all(c.passed for c in data.health_checks),
        "tools": len([t for t in data.tools if t.available]),
    })
```

## Key Data Classes

### RouteResult

```python
@dataclass
class RouteResult:
    tool: str           # tool key (e.g., "claude")
    tool_name: str      # display name (e.g., "Claude Code")
    task_type: str      # classified type (e.g., "coding")
    confidence: float   # 0.0 - 1.0
    fallback: str|None  # fallback tool key
    reason: str         # human-readable explanation
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    tool: str
    tool_name: str
    task_type: str
    confidence: float
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    fallback_used: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0
```

### ToolProfile

```python
@dataclass
class ToolProfile:
    key: str
    name: str
    vendor: str
    strengths: list[str]
    cost_tier: str       # "low" | "medium" | "high"
    available: bool
    version: str | None
    user_preference: int  # -1, 0, 1
```

## Thread Safety

RoleMesh components are **not** thread-safe. For concurrent usage:
- Create separate instances per thread/coroutine
- Or wrap shared instances with a lock
- Config file reads are atomic (single `read_text()` call)
- History writes append to JSONL (safe for single-writer scenarios)
