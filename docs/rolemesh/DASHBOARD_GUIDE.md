# RoleMesh Dashboard Guide

> System status, health checks, and coverage visualization

## Quick Start

### Full dashboard

```bash
cd /path/to/emergent
python -m src.rolemesh.dashboard
```

Output:

```
==================================================
  RoleMesh Dashboard
==================================================

== Tools ==

  Installed (2):
    Claude Code v1.0 (Anthropic)  [high]  strengths: coding, analysis, reasoning, architecture
    Codex CLI v0.1 (OpenAI)  [medium]  strengths: coding, refactoring, quick-edit

  Not found (4):
    Gemini CLI (Google)
    Aider (Community)
    GitHub Copilot (GitHub)
    Cursor (Cursor)

== Routing Table ==

  Task Type            Primary         Fallback
  -------------------- --------------- ---------------
  coding               claude          codex
  refactoring          codex           claude

== Task Coverage Matrix ==

  Task Type            claude   codex
  -------------------- -------- --------
  coding               X*       X
  refactoring          .        X*
  analysis             X        .
  ...

  X = strength, * = primary route, . = not supported

== Health Check ==

  [OK] config_file: /Users/you/.rolemesh/config.json
  [OK] tools_available: 2/6 tools installed
  [!!] routing_coverage: 2/13 task types routed (missing: analysis, ...)
  [OK] config_version: v1.0.0
  [OK] no_dead_refs: All references valid

  Score: 4/5

==================================================
```

### Section-specific views

```bash
python -m src.rolemesh.dashboard --tools       # tools only
python -m src.rolemesh.dashboard --routing     # routing table
python -m src.rolemesh.dashboard --coverage    # task/tool matrix
python -m src.rolemesh.dashboard --health      # health checks
python -m src.rolemesh.dashboard --json        # JSON output
python -m src.rolemesh.dashboard --config /path/to/config.json  # custom config
```

## Programmatic Usage

```python
from src.rolemesh.dashboard import RoleMeshDashboard

dashboard = RoleMeshDashboard()
data = dashboard.collect()

# Access structured data
for tool in data.tools:
    if tool.available:
        print(f"{tool.name} ({tool.vendor}) - {tool.strengths}")

# Render individual sections
print(dashboard.render_tools())
print(dashboard.render_routing())
print(dashboard.render_coverage())
print(dashboard.render_health())

# Full dashboard
print(dashboard.render_full())

# JSON serialization
import json
print(json.dumps(data.to_dict(), indent=2))
```

## Health Checks

The dashboard runs 5 automated health checks:

| Check | Pass Condition |
|-------|---------------|
| `config_file` | `~/.rolemesh/config.json` exists on disk |
| `tools_available` | At least 1 AI CLI tool found on PATH |
| `routing_coverage` | All 13 task types have routing rules |
| `config_version` | Config version is `1.0.0` |
| `no_dead_refs` | All routing targets exist in `config.tools` |

### Fixing common issues

**`[!!] config_file`** — Run the builder to generate config:
```bash
python -m src.rolemesh.builder --save
```

**`[!!] tools_available`** — Install at least one supported AI CLI tool (claude, codex, gemini, aider, copilot, cursor).

**`[!!] routing_coverage`** — Re-run the builder to generate rules for all task types:
```bash
python -m src.rolemesh.builder --save
```

**`[!!] no_dead_refs`** — A routing rule references a tool not in the config. Either add the tool or edit `~/.rolemesh/config.json` to fix the reference.

## Coverage Matrix

The coverage matrix cross-references tools against task types:

- **X** = tool has this strength (can handle the task type)
- **\*** = tool is the primary route for this task type
- **.** = tool does not support this task type

This helps identify gaps — task types with no capable tool, or tools that are underutilized.

## Integration with CI / Scripts

Use `--json` for machine-readable output:

```bash
# Check health score in CI
SCORE=$(python -m src.rolemesh.dashboard --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
passed = sum(1 for h in data['health'] if h['passed'])
print(f'{passed}/{len(data[\"health\"])}')
")
echo "Health: $SCORE"
```
