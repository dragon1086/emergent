# RoleMesh Architecture

> AI Tool Discovery & Task-to-Tool Routing Engine

## Overview

RoleMesh is a task routing layer that discovers installed AI CLI tools on the user's system, profiles their capabilities, and automatically routes user requests to the best-fit tool. It consists of four components: **Builder** (tool discovery + config generation), **Router** (task classification + routing), **Dashboard** (system status + health checks), and **Executor** (subprocess dispatch + fallback).

## Core Pipeline

```
User Request (natural language)
     |
     v
[1] Task Classifier (router.py)
     |  - Regex-based keyword matching against 13 task categories
     |  - Scores each category by pattern match ratio
     |  - Returns ranked list of (task_type, confidence)
     v
[2] Config Lookup (router.py)
     |  - Loads routing config from ~/.rolemesh/config.json
     |  - Maps task_type -> primary tool + fallback
     |  - No config: defaults to "claude"
     v
[3] RouteResult Output
     - tool: tool key (e.g., "claude", "gemini")
     - tool_name: display name (e.g., "Claude Code")
     - task_type: classified category
     - confidence: match strength (0.0 - 1.0)
     - fallback: backup tool if primary unavailable
     - reason: human-readable routing explanation
```

## Components

### Task Classifier

Classifies user input into one of 13 task categories using regex pattern matching:

| Task Type | Example Triggers |
|-----------|-----------------|
| coding | code, implement, function, class, create |
| refactoring | refactor, cleanup, improve, split, extract |
| quick-edit | typo, fix, change, rename, delete |
| analysis | analyze, investigate, cause, debug, error |
| architecture | architect, design, structure, migration, strategy |
| reasoning | reason, logic, judge, evaluate, compare |
| frontend | ui, ux, screen, layout, style, component |
| multimodal | image, photo, screenshot, graph, chart |
| search | search, find, lookup, docs, latest |
| explain | explain, understand, tell, meaning |
| git-integration | commit, branch, merge, PR, rebase |
| completion | autocomplete, fill, continue, next |
| pair-programming | together, pair, help, code review |

Supports both Korean and English keywords. Unmatched inputs default to `coding` with 0.3 confidence.

### Builder (SetupWizard)

Discovers installed AI CLI tools and generates a routing configuration:

```
SetupWizard.discover()
     |  - Probes PATH for known AI CLIs (claude, codex, gemini, aider, copilot, cursor)
     |  - Runs --version to confirm availability
     v
SetupWizard.rank_tools(task_type)
     |  - Ranks available tools by: strength match + user preference + cost tier
     v
SetupWizard.build_config()
     |  - Generates routing rules: task_type -> primary + fallback
     v
SetupWizard.validate_config(config)
     |  - Schema validation: version, tools, routing, cross-references
     |  - Returns list of errors (empty = valid)
     v
SetupWizard.save_config()
     -> ~/.rolemesh/config.json
```

**Runtime extensibility:**

```
SetupWizard.register_tool(key, name, vendor, strengths, check_cmd, cost_tier)
     |  - Adds to TOOL_REGISTRY at runtime (no source edit needed)
     |  - Probes binary availability + reads version
     |  - Replaces existing entry if same key
     v
SetupWizard.unregister_tool(key)
     |  - Removes from TOOL_REGISTRY + internal tool list
     |  - Subsequent build_config() excludes the removed tool
     v
SetupWizard.save_config()
     -> Updated config reflects additions/removals
```

### Tool Registry

Six built-in AI CLI tools are registered with their capability profiles (extensible via `register_tool`):

| Tool | Vendor | Strengths | Cost Tier |
|------|--------|-----------|-----------|
| Claude Code | Anthropic | coding, analysis, reasoning, architecture | high |
| Codex CLI | OpenAI | coding, refactoring, quick-edit | medium |
| Gemini CLI | Google | multimodal, search, ui-design, frontend | medium |
| Aider | Community | coding, git-integration, pair-programming | low |
| GitHub Copilot | GitHub | completion, quick-edit, explain | low |
| Cursor | Cursor | coding, ui, inline-edit | medium |

### Dashboard

Collects and displays a unified view of the system:

```
RoleMeshDashboard.collect()
     |  - Runs discover_tools()
     |  - Loads routing config
     |  - Enumerates all 13 task types
     v
_run_health_checks()
     |  - config_file: exists?
     |  - tools_available: >=1 on PATH?
     |  - routing_coverage: all 13 task types routed?
     |  - config_version: v1.0.0?
     |  - no_dead_refs: all routing targets valid?
     v
render_full()
     -> Tools list + Routing table + Coverage matrix + Health score
```

### Executor

Dispatches tasks to AI CLI tools via subprocess:

```
RoleMeshExecutor.run(request)
     |  - Router classifies + routes the request
     |  - Checks primary tool on PATH
     |  - Builds CLI command (args or stdin mode)
     v
subprocess.run(cmd, timeout=120)
     |  - On success: return ExecutionResult
     |  - On failure: try fallback tool
     |  - On timeout: return exit_code=-1
     v
ExecutionResult(tool, stdout, stderr, exit_code, duration_ms)
```

## Data Flow

```
Full pipeline (route + execute):
  -> RoleMeshExecutor.run(request)
       -> RoleMeshRouter.route(request)
            -> classify_task(request)           # regex matching
            -> load config (~/.rolemesh/config.json)
            -> lookup routing[task_type]        # primary + fallback
            <- RouteResult(tool, task_type, confidence, ...)
       -> check_tool(tool_key)                  # binary on PATH?
       -> build_command(tool_key, prompt)        # CLI args
       -> subprocess.run(cmd)                    # dispatch
       <- ExecutionResult(stdout, stderr, exit_code, duration_ms)

Route only (no execution):
  -> RoleMeshRouter.route(request)
       <- RouteResult(tool, task_type, confidence, ...)

Config generation (one-time):
  -> SetupWizard.discover()               # probe system
  -> SetupWizard.build_config()           # generate routing rules
  -> SetupWizard.save_config()            # persist to disk

Status check:
  -> RoleMeshDashboard.collect()           # tools + config + health
  -> dashboard.render_full()               # formatted output
```

## Design Decisions

1. **Regex over LLM classification**: Task classification uses regex patterns, not LLM calls. This keeps routing instant (~1ms) and free of API costs.
2. **Config-driven routing**: Routing rules are persisted to disk so they survive across sessions. The wizard runs once; the router reads the config every time.
3. **Cost-aware ranking**: When multiple tools can handle a task type, cheaper tools rank higher by default. User preferences override cost ranking.
4. **Bilingual patterns**: All regex patterns include both Korean and English keywords to support bilingual users.
5. **Graceful degradation**: No config file → default to Claude. No pattern match → assume coding with low confidence. No available tools → informative error message.

## File Structure

```
src/rolemesh/
  __init__.py          # Public exports: SetupWizard, ToolProfile, discover_tools,
                       #   RoleMeshRouter, RoleMeshDashboard, DashboardData,
                       #   HealthCheck, RoleMeshExecutor, ExecutionResult
  builder.py           # Tool discovery, SetupWizard, config generation
  router.py            # Task classification, routing logic, CLI
  dashboard.py         # System status, health checks, coverage matrix
  executor.py          # Subprocess dispatch, fallback logic, CLI

tests/
  test_rolemesh.py     # Builder + Router + Dashboard tests (27 test cases)

docs/rolemesh/
  ARCHITECTURE.md      # This file
  BUILDER_GUIDE.md     # How to extend and customize
  API_REFERENCE.md     # Public interface documentation
  DASHBOARD_GUIDE.md   # System status and health monitoring
  EXECUTOR_GUIDE.md    # Task dispatch and execution
```
