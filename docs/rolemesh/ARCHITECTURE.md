# RoleMesh Architecture

Design decisions, data flow, and extension points.

---

## Overview

RoleMesh is a 4-stage pipeline that turns a natural-language task description into an executed CLI command on the best-fit AI tool:

```
Task Request
    |
    v
[1. Builder]  -- discover installed tools, build config
    |
    v
[2. Router]   -- classify task type, select tool
    |
    v
[3. Executor] -- dispatch to CLI, handle fallback
    |
    v
[4. Dashboard] -- visualize state, health, history
```

---

## Stage 1: Builder (builder.py)

**Purpose**: Discover what AI CLI tools are available on the system.

**How it works**:
1. Iterates `TOOL_REGISTRY` (6 known tools)
2. For each tool, checks `shutil.which(binary)` for availability
3. Runs `check_cmd` (e.g. `claude --version`) to capture version
4. Returns `ToolProfile` list with availability and version info

**Config generation**:
- `SetupWizard.build_config()` creates a routing table by iterating all known task types (union of all tool strengths) and ranking available tools by: strength match, user preference, cost tier
- Config schema: `{ version, tools: {}, routing: {} }`
- Persisted to `~/.rolemesh/config.json`

**Extension**: Add tools via `SetupWizard.register_tool()` or by adding entries to `TOOL_REGISTRY`.

---

## Stage 2: Router (router.py)

**Purpose**: Given a task description, determine what type of task it is and which tool should handle it.

**Classification algorithm**:
1. Lowercase the request
2. Match against `TASK_PATTERNS` -- 13 task types, each with 2 regex patterns (Korean + English keywords)
3. Confidence = matched_patterns / total_patterns per type
4. Return all matches sorted by confidence descending

**Routing algorithm**:
1. Take the highest-confidence classification
2. Look up `routing[task_type]` in config
3. Return `primary` tool with `fallback` from config
4. If no config: default to `claude`

**Design decision**: Regex-based classification was chosen over LLM classification for zero-latency routing. The bilingual patterns (Korean + English) support the primary user base.

---

## Stage 3: Executor (executor.py)

**Purpose**: Run the selected tool's CLI with the task as input.

**Execution flow**:
```
dispatch(task)
    |
    +--> router.route(task) --> RouteResult
    |
    +--> TOOL_COMMANDS[tool_key] --> CLI command
    |
    +--> subprocess.run(cmd + [task], timeout=300s)
    |
    +--> success? --> return ExecutionResult
    |
    +--> failure + fallback? --> retry with fallback tool
    |
    +--> log to history.jsonl
```

**Fallback**: If the primary tool fails (non-zero exit code) and a fallback is configured, the executor automatically retries with the fallback tool. `ExecutionResult.fallback_used` indicates this occurred.

**Dry-run**: When `dry_run=True`, returns immediately with the command that would have been executed, without actually running it.

**History**: Every execution (including dry-runs) is logged to `~/.rolemesh/history.jsonl` as a JSONL entry with timestamp, tool, task type, success status, and duration.

---

## Stage 4: Dashboard (dashboard.py)

**Purpose**: Provide a unified view of the system state.

**Render modes**:
| Mode | Flag | Content |
|---|---|---|
| Full | (default) | All sections combined |
| Tools | `--tools` | Availability + version for each tool |
| Routing | `--routing` | Task type -> primary/fallback mapping |
| Coverage | `--coverage` | Matrix of task types x available tools |
| Health | `--health` | 5 config health checks (PASS/FAIL) |
| History | `--history` | Last 10 executions from history.jsonl |
| JSON | `--json` | Machine-readable output of all data |

**Color**: Uses ANSI escape codes. Disabled when `NO_COLOR` env var is set or stdout is not a TTY.

---

## Data Flow

```
~/.rolemesh/
    config.json      <-- SetupWizard.save_config()
                     --> RoleMeshRouter.__init__()
                     --> RoleMeshDashboard.collect()

    history.jsonl    <-- RoleMeshExecutor._log_history()
                     --> RoleMeshDashboard.collect()
```

All persistent state lives under `~/.rolemesh/`. No other directories are written to.

---

## CLI Entry Point (__main__.py)

The unified CLI dispatches to the 4 stages:

| Subcommand | Stage | Handler |
|---|---|---|
| `setup` | Builder | `cmd_setup()` |
| `route` | Router | `cmd_route()` |
| `exec` | Executor | `cmd_exec()` |
| `dashboard` | Dashboard | `cmd_dashboard()` |
| `status` | Builder (light) | `cmd_status()` |

All subcommands support `--json` for machine-readable output.

---

## Design Principles

1. **Zero-config start**: Works with no config file -- defaults to Claude for all tasks
2. **Zero-latency routing**: Regex classification, no LLM calls for routing
3. **Graceful degradation**: Fallback tools, missing tools handled cleanly
4. **Bilingual patterns**: Korean + English regex for task classification
5. **Observable**: Dashboard, health checks, execution history, JSON output
6. **Extensible**: `register_tool()` for custom tools, `TOOL_REGISTRY` for built-in tools
