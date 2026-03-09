# RoleMesh Architecture

> System design, data flow, and extension points.

---

## Design Principles

1. **Convention over configuration** — Works out of the box with zero config; `setup --save` enables customization
2. **Graceful degradation** — Falls back to `claude` when no config exists or no pattern matches
3. **Cost-aware routing** — Cheaper tools preferred when capability is equal
4. **Extensibility** — Custom tools plug into the same pipeline as built-in tools

---

## System Overview

```
                    ┌─────────────────────────────────────┐
                    │           __main__.py                │
                    │        (CLI entry point)             │
                    └───┬───────┬───────┬───────┬─────────┘
                        │       │       │       │
              ┌─────────┘   ┌───┘   ┌───┘   ┌───┘
              v             v       v       v
         ┌─────────┐  ┌─────────┐ ┌──────┐ ┌───────────┐
         │ Builder  │  │ Router  │ │ Exec │ │ Dashboard │
         │builder.py│  │router.py│ │utor  │ │dashboard. │
         └────┬─────┘  └────┬────┘ └──┬───┘ │   py      │
              │              │        │      └───────────┘
              v              v        v
    ~/.rolemesh/      TASK_PATTERNS   TOOL_COMMANDS
    config.json       (regex map)    (CLI dispatch)
```

---

## Module Responsibilities

### Builder (`builder.py`)

**Purpose**: Discover installed tools and generate routing configuration.

| Component | Role |
|-----------|------|
| `TOOL_REGISTRY` | Static registry of 6 known AI CLI tools |
| `ToolProfile` | Dataclass: key, name, vendor, strengths, cost_tier, available, version |
| `discover_tools()` | Scans PATH, probes versions, returns `list[ToolProfile]` |
| `SetupWizard` | Orchestrates discovery, ranking, config generation, validation |

**Data flow**: `TOOL_REGISTRY` → `discover_tools()` → `ToolProfile[]` → `build_config()` → `config.json`

### Router (`router.py`)

**Purpose**: Classify user requests into task types and select the best tool.

| Component | Role |
|-----------|------|
| `TASK_PATTERNS` | 13 task types, each with Korean+English regex patterns |
| `RouteResult` | Dataclass: tool_name, task_type, confidence, fallback, reason |
| `RoleMeshRouter` | Loads config, classifies tasks, returns routing decisions |

**Classification algorithm**:
1. Lowercase the request
2. Match against each task type's regex patterns
3. Score = (matched patterns / total patterns) per type
4. Sort by descending confidence
5. Look up the top task type in config routing rules
6. Return primary tool + fallback

**Default behavior**: When no config exists or no pattern matches, defaults to `claude` with `confidence=0.0`.

### Executor (`executor.py`)

**Purpose**: Dispatch tasks to AI CLI tools and handle fallback.

| Component | Role |
|-----------|------|
| `TOOL_COMMANDS` | Maps tool keys to CLI commands and flags |
| `ExecutionResult` | Dataclass: tool, type, confidence, success, exit_code, duration, stdout/stderr |
| `RoleMeshExecutor` | Runs routing → execution → fallback → history logging |

**Execution flow**:
1. Route the task via `RoleMeshRouter.route()`
2. Build CLI command from `TOOL_COMMANDS`
3. Run subprocess with 300s timeout
4. If failure + fallback exists → retry with fallback tool
5. Log result to `~/.rolemesh/history.jsonl`

**Dry-run mode**: Returns the command that would execute without running it.

### Dashboard (`dashboard.py`)

**Purpose**: Unified visibility into tools, routing, coverage, and health.

| Component | Role |
|-----------|------|
| `Color` | ANSI color helper (respects `NO_COLOR` and non-TTY) |
| `HealthCheck` | Dataclass: name, passed, detail |
| `DashboardData` | Aggregate container for all dashboard data |
| `RoleMeshDashboard` | Collects data, runs health checks, renders views |

**Health checks** (5 total):
1. `config_file` — config.json exists
2. `tools_available` — at least 1 tool found
3. `routing_coverage` — all 13 task types have routing rules
4. `config_version` — version is `"1.0.0"`
5. `no_dead_refs` — no routing rules pointing to missing tools

---

## Data Flow

```
[User Request]
      │
      ▼
 ┌──────────┐     ┌──────────────┐
 │  Router   │────▶│ config.json  │
 │ classify  │     │  (routing    │
 │ + route   │◀────│   rules)     │
 └─────┬─────┘     └──────────────┘
       │
       ▼
 ┌──────────┐     ┌──────────────┐
 │ Executor │────▶│  AI CLI Tool  │
 │ dispatch  │     │ (subprocess) │
 └─────┬─────┘     └──────┬───────┘
       │                   │
       │    ┌──────────┐   │
       └───▶│ history  │◀──┘
            │ .jsonl   │
            └──────────┘
```

---

## File Layout

```
src/rolemesh/
├── __init__.py          # Package declaration
├── __main__.py          # CLI entry point (argparse subcommands)
├── builder.py           # Tool discovery and config generation
├── router.py            # Task classification and routing
├── executor.py          # Task dispatch and fallback
├── dashboard.py         # CLI dashboard and health checks
└── docs/
    ├── README.md            # This index
    ├── QUICKSTART.md        # Zero-to-running guide
    ├── ARCHITECTURE.md      # System design (this file)
    ├── BUILDER_GUIDE.md     # Builder getting started
    ├── BUILDER_CONFIG.md    # Config schema reference
    ├── BUILDER_EXTENDING.md # Custom tool registration
    ├── ROUTER.md            # Router internals
    ├── EXECUTOR.md          # Executor internals
    ├── DASHBOARD_CLI.md     # Dashboard CLI usage
    └── API.md               # Class/function reference
```

---

## Configuration

```
~/.rolemesh/
├── config.json      # Generated by Builder (tools + routing rules)
└── history.jsonl    # Append-only execution log (written by Executor)
```

---

## Extension Points

| Extension | Method | Reference |
|-----------|--------|-----------|
| Add a new tool | `SetupWizard.register_tool()` or edit `TOOL_REGISTRY` | [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) |
| Add a task type | Add regex patterns to `TASK_PATTERNS` in `router.py` | [ROUTER.md](ROUTER.md) |
| Add a CLI command | Add entry to `TOOL_COMMANDS` in `executor.py` | [EXECUTOR.md](EXECUTOR.md) |
| Add a health check | Extend `_run_health_checks()` in `dashboard.py` | [DASHBOARD_CLI.md](DASHBOARD_CLI.md) |
| Add a dashboard view | Add `render_*()` method to `RoleMeshDashboard` | [DASHBOARD_CLI.md](DASHBOARD_CLI.md) |

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Regex-based classification (not LLM) | Zero latency, zero cost, deterministic |
| Subprocess execution (not SDK) | Uniform interface across all CLI tools |
| JSONL history (not SQLite) | Append-only, no schema migrations, easy to grep |
| Config at `~/.rolemesh/` (not project-local) | Tool availability is machine-global, not project-specific |
| Default to `claude` on no match | Safe fallback — Claude handles the widest range of tasks |
| Cost-tier ranking | Prefer cheaper tools when capabilities are equal |
