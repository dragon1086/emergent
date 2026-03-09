# Dashboard Guide

> Monitor tools, routing, coverage, and system health

## Overview

The Dashboard module (`src/rolemesh/dashboard.py`) provides a unified view of the RoleMesh system: discovered tools, routing configuration, task type coverage, config health checks, and execution history.

## Quick Start

```bash
# Full dashboard
python -m src.rolemesh.dashboard

# Individual sections
python -m src.rolemesh.dashboard --tools       # installed tools
python -m src.rolemesh.dashboard --routing     # routing table
python -m src.rolemesh.dashboard --coverage    # task coverage matrix
python -m src.rolemesh.dashboard --health      # config health check
python -m src.rolemesh.dashboard --history     # execution history

# JSON output (all sections)
python -m src.rolemesh.dashboard --json

# Disable colors
python -m src.rolemesh.dashboard --no-color

# Custom config path
python -m src.rolemesh.dashboard --config /path/to/config.json
```

## Dashboard Sections

### Tools

Lists all known AI tools with their availability, version, vendor, strengths, and cost tier. Installed tools are shown in green; unavailable tools in yellow.

```
== Tools ==

  Installed (3):
    Claude Code (Anthropic) v1.0.62  [coding, refactoring, ...]  high
    Codex CLI (OpenAI) v0.1.0  [coding, refactoring, ...]  medium
    Gemini CLI (Google)  [coding, multimodal, ...]  medium
    Aider (Community)  [coding, refactoring, ...]  low
```

### Routing Table

Shows the primary and fallback tool assignment for each task type:

```
== Routing Table ==

  Task Type            Primary         Fallback
  analysis             claude          codex
  architecture         claude          -
  coding               claude          codex
  refactoring          claude          codex
  frontend             gemini          claude
```

### Task Coverage Matrix

A cross-reference of task types vs. available tools. `X` marks tools that list the task type in their strengths. The primary-routed tool is highlighted in green.

```
== Task Coverage Matrix ==

  Task Type            claude     codex      gemini
  coding               X          X          X
  refactoring          X          X          .
  frontend             .          .          X
  multimodal           .          .          X
```

### Health Check

Runs 5 automated checks on the RoleMesh configuration:

| Check | What it verifies |
|-------|------------------|
| `config_file` | Config file exists at expected path |
| `tools_available` | At least 1 tool is installed |
| `routing_coverage` | All task types have routing rules |
| `config_version` | Config version is `1.0.0` |
| `no_dead_refs` | No routing rules reference missing tools |

```
== Health Check ==

  [OK] config_file: /Users/you/.rolemesh/config.json
  [OK] tools_available: 3/6 tools installed
  [!!] routing_coverage: 10 task types routed (missing: completion, search)
  [OK] config_version: version=1.0.0
  [OK] no_dead_refs: All refs valid

  Score: 4/5
```

### Execution History

Shows recent task executions from `~/.rolemesh/history.jsonl` (logged by the [Executor](EXECUTOR_GUIDE.md)):

```
== Execution History ==

  Time                 Tool       Type            Status  Duration
  2026-03-07 10:00:00  claude     refactoring     OK      4521ms
  2026-03-07 09:55:12  gemini     frontend        OK      3201ms
  2026-03-07 09:50:00  claude     analysis        FAIL    120000ms

  2/3 succeeded
```

## Programmatic Usage

```python
from src.rolemesh.dashboard import RoleMeshDashboard

dashboard = RoleMeshDashboard()
data = dashboard.collect()

# Access structured data
for tool in data.tools:
    status = "installed" if tool.available else "missing"
    print(f"{tool.name}: {status}")

# Check health
for check in data.health_checks:
    print(f"{'PASS' if check.passed else 'FAIL'}: {check.name}")

# JSON export
import json
print(json.dumps(data.to_dict(), indent=2))

# Render individual sections
print(dashboard.render_tools())
print(dashboard.render_routing())
print(dashboard.render_coverage())
print(dashboard.render_health())
print(dashboard.render_history())
```

## Color Support

Terminal colors are enabled by default when stdout is a TTY. Disable with:

- CLI flag: `--no-color`
- Environment: `NO_COLOR=1`
- Programmatic: `Color.set_enabled(False)`

## See Also

- [Builder Guide](BUILDER_GUIDE.md) — Set up and discover tools
- [Router Guide](ROUTER_GUIDE.md) — How tasks are classified and routed
- [Executor Guide](EXECUTOR_GUIDE.md) — Execute tasks and generate history
- [Monitoring Guide](MONITORING_GUIDE.md) — Advanced monitoring setup
