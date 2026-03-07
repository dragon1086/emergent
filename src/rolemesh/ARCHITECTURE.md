# RoleMesh Architecture

## Design Philosophy

RoleMesh treats AI CLI tools as interchangeable execution backends. Instead of hardcoding one tool, it:

1. **Discovers** what's installed (zero config required)
2. **Routes** tasks to the best tool by matching task semantics to tool strengths
3. **Executes** with automatic fallback if the primary tool fails
4. **Observes** via dashboard and execution history

This enables multi-tool workflows where each task goes to the most capable (and cost-effective) tool.

---

## Layer Diagram

```
┌─────────────────────────────────────────────────┐
│                    CLI Layer                      │
│               __main__.py                        │
│    dashboard | setup | route | exec | status     │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────┐
│              Execution Layer                     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Builder  │  │  Router  │  │   Executor    │  │
│  │          │→ │          │→ │               │  │
│  │ discover │  │ classify │  │ dispatch      │  │
│  │ profile  │  │ route    │  │ run           │  │
│  │ config   │  │          │  │ fallback      │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│                                                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────┐
│             Observation Layer                    │
│                                                  │
│  ┌──────────────────────────────────────┐       │
│  │            Dashboard                  │       │
│  │  tools | routing | coverage | health  │       │
│  │  history | JSON export                │       │
│  └──────────────────────────────────────┘       │
│                                                  │
└─────────────────────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────┐
│             Persistence Layer                    │
│                                                  │
│  ~/.rolemesh/config.json     routing config      │
│  ~/.rolemesh/history.jsonl   execution log       │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Data Flow

### Setup Flow (one-time)

```
discover_tools()
  → probe PATH for each TOOL_REGISTRY entry
  → capture version string
  → build ToolProfile list
  → rank by (strength_match, user_preference, cost_tier)
  → generate routing config
  → write ~/.rolemesh/config.json
```

### Execution Flow (per task)

```
user request: "이 코드 리팩토링해줘"
  │
  ├─ classify_task()
  │    → scan TASK_PATTERNS (14 types × bilingual regex)
  │    → score: matched_patterns / total_patterns
  │    → result: [("refactoring", 1.0), ("quick-edit", 0.5)]
  │
  ├─ route()
  │    → take top match: "refactoring"
  │    → lookup config.routing["refactoring"]
  │    → result: RouteResult(tool="claude", fallback="aider")
  │
  └─ dispatch()
       → build command: ["claude", "-p", "이 코드 리팩토링해줘"]
       → subprocess.run(timeout=300s)
       → if exit_code != 0 and fallback exists:
       │    → retry with fallback tool
       └─ log to history.jsonl
```

---

## Routing Algorithm

### Task Classification

Each task type has a tuple of regex patterns (Korean + English). Confidence = how many patterns matched out of total patterns for that type.

Example for `refactoring`:
```
patterns: (r"리팩토링|refactor|정리|cleanup|개선|improve",
           r"분리|split|추출|extract|단순화|simplify")

"리팩토링해줘"     → matches pattern 1 only  → confidence 0.5
"코드 리팩토링 분리" → matches both patterns  → confidence 1.0
```

### Tool Selection

Within a task type, tools are ranked by:
1. **Strength match** — does the tool list this task type in its strengths?
2. **User preference** — manual rank from interactive setup (1 = highest)
3. **Cost tier** — low < medium < high (prefer cheaper when tied)

The top-ranked tool becomes `primary`, second becomes `fallback`.

---

## Fallback Strategy

```
dispatch(task)
  │
  ├─ run(primary_tool)
  │    ├─ success → return result
  │    └─ failure ─┐
  │                │
  │   (if no forced tool AND fallback exists)
  │                │
  │                ▼
  │            run(fallback_tool)
  │                ├─ success → return result (fallback_used=True)
  │                └─ failure → return failure result
  │
  └─ (if forced tool) → return failure result directly
```

Fallback is skipped when `tool` parameter is explicitly set (user forced a specific tool).

---

## Extension Points

### Adding a New Tool

1. Add entry to `TOOL_REGISTRY` in `builder.py`:
```python
"newtool": {
    "name": "New Tool",
    "vendor": "Vendor",
    "strengths": ["coding", "analysis"],
    "check_cmd": ["newtool", "--version"],
    "cost_tier": "medium",
}
```

2. Add CLI command to `TOOL_COMMANDS` in `executor.py`:
```python
"newtool": {"cmd": ["newtool", "-p"], "stdin_mode": False},
```

3. Re-run `setup --save` to regenerate routing config.

### Runtime Registration

```python
wizard = SetupWizard()
wizard.discover()
wizard.register_tool(
    key="mytool", name="My Tool", vendor="Custom",
    strengths=["coding"], check_cmd=["mytool", "--version"],
    cost_tier="low",
)
wizard.save_config()
```

### Adding a New Task Type

Add a pattern tuple to `TASK_PATTERNS` in `router.py`:

```python
("new-type", (r"keyword1|키워드1", r"keyword2|키워드2")),
```

The dashboard coverage matrix and health checks automatically pick up new task types.

---

## File Layout

```
src/rolemesh/
├── __init__.py        # package marker
├── __main__.py        # unified CLI entry point
├── builder.py         # tool discovery + config generation
├── router.py          # task classification + routing
├── executor.py        # CLI dispatch + fallback + history
├── dashboard.py       # terminal dashboard + health checks
├── README.md          # module overview
├── API.md             # class/function reference
└── ARCHITECTURE.md    # this file
```

---

## Persistence

| File | Format | Purpose |
|------|--------|---------|
| `~/.rolemesh/config.json` | JSON | Tool profiles + routing rules |
| `~/.rolemesh/history.jsonl` | JSON Lines | Execution log (append-only) |

Config is versioned (`"version": "1.0.0"`) and validated on load. History is unbounded; dashboard shows last 10 entries.
