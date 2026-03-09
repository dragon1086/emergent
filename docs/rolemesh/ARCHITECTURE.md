# RoleMesh Architecture

## Overview

RoleMesh is a 4-layer pipeline that turns a natural-language task request into an executed AI CLI command:

```
User Request
     |
     v
[1. Builder]    discover installed tools, build config
     |
     v
[2. Router]     classify task type, select best tool
     |
     v
[3. Executor]   dispatch via subprocess, handle fallback
     |
     v
[4. Dashboard]  visualize status, health, history
```

Each layer is independent and can be used standalone.

## Module Dependency Graph

```
__main__.py  (CLI entry point, subcommand dispatch)
     |
     +--- builder.py   (no internal deps)
     |
     +--- router.py    (no internal deps)
     |
     +--- executor.py  (imports router)
     |
     +--- dashboard.py (imports builder, router)
```

## Data Flow

### Setup (one-time)

```
TOOL_REGISTRY (built-in dict in builder.py)
     |
     v
discover_tools()          # shutil.which + --version probe for each tool
     |
     v
SetupWizard.build_config()  # rank tools per task type, generate routing rules
     |
     v
~/.rolemesh/config.json   # persisted config (version, tools, routing)
```

### Runtime (per request)

```
request string
     |
     v
classify_task()           # regex pattern matching -> [(task_type, confidence)]
     |
     v
route()                   # lookup config routing table -> RouteResult
     |
     v
TOOL_COMMANDS[key]        # construct CLI args (e.g. ["claude", "-p", task])
     |
     v
subprocess.run()          # execute with 300s timeout
     |
     v
~/.rolemesh/history.jsonl # append execution record (timestamp, tool, type, success, duration)
```

## Design Decisions

### Why regex over LLM for classification?

Task classification uses regex pattern matching instead of an LLM call because:

1. **Zero latency** — no API call, no network dependency
2. **Deterministic** — same input always produces same routing
3. **Offline** — works without API keys or internet
4. **Auditable** — patterns are visible in `TASK_PATTERNS`

The confidence score (matched pattern groups / total groups) provides a simple but effective ranking signal.

### Why subprocess over SDK?

AI CLI tools are invoked via `subprocess.run()` rather than importing their SDKs because:

1. **Universal** — any CLI tool can be integrated without SDK dependency
2. **Isolation** — tool crashes don't affect RoleMesh
3. **Simple** — no version coupling between RoleMesh and tool SDKs

### Fallback strategy

The executor implements automatic fallback:

1. Route the task to the primary tool via config
2. If primary tool fails (non-zero exit code) and a fallback is configured, retry with the fallback tool
3. The `fallback_used` flag on `ExecutionResult` tracks whether fallback was triggered

### Ranking algorithm

`SetupWizard.rank_tools(task_type)` sorts available tools by a 3-level key:

1. **Strength match** — 0 if task_type is in the tool's strengths, 1 otherwise
2. **User preference** — integer rank set during interactive setup (lower = preferred)
3. **Cost tier** — low=0, medium=1, high=2

This ensures task-fit tools are preferred, then user favorites, then cheaper options.

### Config schema

Config uses a flat JSON structure with version field for future migration:

```json
{
  "version": "1.0.0",
  "tools": {
    "<key>": {
      "key": "claude",
      "name": "Claude Code",
      "vendor": "Anthropic",
      "strengths": ["coding", "refactoring", "..."],
      "cost_tier": "high",
      "available": true,
      "version": "1.0.46"
    }
  },
  "routing": {
    "<task_type>": { "primary": "<tool_key>", "fallback": "<tool_key>" }
  }
}
```

Validation (`SetupWizard.validate_config`) checks for missing fields (`version`, `tools`, `routing`) and dead references in routing rules (primary/fallback pointing to non-existent tool keys).

## Extension Points

### Adding a new tool

1. Add entry to `TOOL_REGISTRY` in `builder.py` with name, vendor, strengths, check_cmd, cost_tier
2. Add command config to `TOOL_COMMANDS` in `executor.py`
3. Run `setup --save` to regenerate config

Or use the `SetupWizard.register_tool()` API for runtime registration.

### Adding a new task type

1. Add pattern tuple to `TASK_PATTERNS` in `router.py` (each tuple: task_type name + two regex group strings)
2. Add the task type string to relevant tools' `strengths` lists in `TOOL_REGISTRY`
3. Regenerate config

### Custom routing logic

Subclass `RoleMeshRouter` and override `route()` for custom logic (e.g., cost-aware routing, time-of-day rules, user preference weighting).

## File Layout

```
src/rolemesh/
  __init__.py       # package docstring
  __main__.py       # CLI entry point (argparse subcommands)
  builder.py        # TOOL_REGISTRY, ToolProfile, SetupWizard, discover_tools()
  router.py         # TASK_PATTERNS, RouteResult, RoleMeshRouter
  executor.py       # TOOL_COMMANDS, ExecutionResult, RoleMeshExecutor
  dashboard.py      # Color, HealthCheck, DashboardData, RoleMeshDashboard

~/.rolemesh/
  config.json       # routing config (generated by setup)
  history.jsonl     # execution log (appended by executor)
```
