# Dashboard CLI — RoleMesh Dashboard

> Unified terminal dashboard for tool status, routing, coverage, health, and execution history.

---

## Overview

The Dashboard module (`dashboard.py`) provides a single-pane CLI view of the entire RoleMesh system state. It aggregates data from the Builder (tool discovery), Router (task-type mapping), and Executor (execution history) into a readable terminal output with ANSI color support.

---

## Quick Start

```bash
# Full dashboard (all sections)
python -m src.rolemesh dashboard

# Individual sections
python -m src.rolemesh dashboard --tools       # Discovered tools
python -m src.rolemesh dashboard --routing      # Task → tool routing table
python -m src.rolemesh dashboard --coverage     # Task type × tool coverage matrix
python -m src.rolemesh dashboard --health       # Config health checks
python -m src.rolemesh dashboard --history      # Recent execution log

# Machine-readable output
python -m src.rolemesh dashboard --json

# Custom config path
python -m src.rolemesh dashboard --config /path/to/config.json
```

---

## Sections

### 1. Header

Displays summary counters: available tools and health check pass rate.

```
  RoleMesh Dashboard
  Tools: 3/6 available | Health: 5/5 checks passed
  ============================================================
```

### 2. Tools (`--tools`)

Lists all registered AI CLI tools with availability status, version, vendor, and cost tier.

```
  Tools
    [OK] Claude Code (claude 4.1.0) — Anthropic, high
    [OK] Codex CLI (codex 0.9.2) — OpenAI, medium
    [--] Gemini CLI — Google, medium
    [OK] Aider (aider 0.82.1) — Community, low
    [--] GitHub Copilot CLI — GitHub, medium
    [--] Cursor — Cursor, medium
```

- `[OK]` = binary found on PATH, version captured
- `[--]` = binary not found

### 3. Routing Table (`--routing`)

Shows the primary and fallback tool for each configured task type.

```
  Routing Table
    analysis             → Codex CLI | fallback: Claude Code
    coding               → Aider | fallback: Codex CLI
    refactoring          → Aider | fallback: Codex CLI
```

Requires a saved config (`setup --save`). Without config, shows a hint to run setup.

### 4. Coverage Matrix (`--coverage`)

Cross-references task types (rows) against available tools (columns). A filled dot (`●`) means the tool lists that task type as a strength.

```
  Task Coverage Matrix
    Task Type              claude    codex    aider
    ————————————————————   ————————  ————————  ————————
    coding                    ●        ●        ●
    refactoring               ●        ●        ●
    analysis                  ●        ●        ·
    architecture              ●        ·        ·
    multimodal                ·        ·        ·
```

### 5. Health Checks (`--health`)

Runs 5 diagnostic checks against the current config:

| Check | What it validates |
|-------|-------------------|
| `config_file` | Config file exists at expected path |
| `tools_available` | At least one AI CLI tool is installed |
| `routing_coverage` | All known task types have routing rules |
| `config_version` | Config version matches expected `1.0.0` |
| `no_dead_refs` | No routing rules reference non-existent tool keys |

```
  Health Checks
    [PASS] config_file: /Users/you/.rolemesh/config.json
    [PASS] tools_available: 3 tool(s) found
    [FAIL] routing_coverage: Missing: multimodal, search
    [PASS] config_version: 1.0.0
    [PASS] no_dead_refs: Clean
```

### 6. Execution History (`--history`)

Shows the last 10 entries from `~/.rolemesh/history.jsonl`, logged by the Executor after each task dispatch.

```
  Recent Executions
    2026-03-07T10:15:00  claude      coding            [OK]    1200ms
    2026-03-07T10:12:30  aider       refactoring       [FAIL]  3400ms
```

---

## JSON Output (`--json`)

Returns all dashboard data as a single JSON object:

```json
{
  "tools": [
    {
      "key": "claude",
      "name": "Claude Code",
      "vendor": "Anthropic",
      "strengths": ["coding", "refactoring", "analysis", ...],
      "cost_tier": "high",
      "available": true,
      "version": "claude 4.1.0"
    }
  ],
  "routing": {
    "coding": { "primary": "aider", "fallback": "codex" }
  },
  "health": [
    { "name": "config_file", "passed": true, "detail": "..." }
  ],
  "history": [
    { "timestamp": "...", "tool": "claude", "task_type": "coding", "success": true, "duration_ms": 1200 }
  ]
}
```

---

## Architecture

```
RoleMeshDashboard
├── collect()              # Aggregates all data sources
│   ├── discover_tools()   # From builder.py
│   ├── load_config()      # From ~/.rolemesh/config.json
│   ├── _run_health_checks()
│   └── read history.jsonl
│
├── render_full()          # All sections combined
├── render_tools()         # Tools section only
├── render_routing()       # Routing table only
├── render_coverage()      # Coverage matrix only
├── render_health()        # Health checks only
├── render_history()       # Execution history only
└── to_json()              # Full JSON export
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `RoleMeshDashboard` | Main dashboard controller — collects data, renders sections |
| `DashboardData` | Dataclass holding tools, config, routing, health, history |
| `HealthCheck` | Individual check result (name, passed, detail) |
| `Color` | ANSI color helper — respects `NO_COLOR` env and non-TTY |

### File Paths

| Path | Purpose |
|------|---------|
| `~/.rolemesh/config.json` | Tool profiles + routing rules (from `setup --save`) |
| `~/.rolemesh/history.jsonl` | Execution log (appended by Executor) |

---

## Programmatic Usage

```python
from src.rolemesh.dashboard import RoleMeshDashboard

dash = RoleMeshDashboard()
data = dash.collect()

# Render to terminal
print(dash.render_full())

# Or get structured data
json_data = dash.to_json()
print(f"Available tools: {sum(1 for t in json_data['tools'] if t['available'])}")
print(f"Health passed: {sum(1 for h in json_data['health'] if h['passed'])}")
```

### Custom Config Path

```python
from pathlib import Path
dash = RoleMeshDashboard(config_path=Path("/custom/config.json"))
dash.collect()
print(dash.render_health())
```

---

## Color Support

The `Color` class auto-detects terminal capabilities:

- **Disabled** when `NO_COLOR` env var is set (per [no-color.org](https://no-color.org))
- **Disabled** when stdout is not a TTY (piped output)
- **Manually controllable** via `Color.set_enabled(False)`

All render methods produce clean, uncolored output when colors are disabled.

---

## Next Steps

- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Tool discovery and setup
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration reference
- [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) — Adding custom tools
