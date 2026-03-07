# Router — Task Classification & Routing

> Classifies user requests into task types and routes them to the best AI CLI tool.

---

## Overview

The Router module (`router.py`) sits between the Builder (tool discovery) and the Executor (task dispatch). It analyzes a natural-language task description, classifies it into one or more task types using regex pattern matching, and selects the optimal tool based on the routing configuration.

---

## Quick Start

### CLI usage

```bash
# Route a single task
python -m src.rolemesh route "refactor the auth module"

# Show all matching task types
python -m src.rolemesh route "refactor the auth module" --all

# JSON output
python -m src.rolemesh route "refactor the auth module" --json
```

### Example output

```
  Route: aider (refactoring, conf=0.50)
  Fallback: codex
```

With `--all`:

```
  refactoring          → aider (conf=0.50, fallback=codex)
  coding               → aider (conf=0.50, fallback=codex)
```

---

## How Classification Works

The Router uses `TASK_PATTERNS`, a list of 13 task types each with a tuple of regex patterns. For each task type:

1. All patterns in the tuple are tested against the lowercased request string
2. Confidence = (number of matching patterns) / (total patterns in tuple)
3. Results are sorted by confidence descending

```python
TASK_PATTERNS = [
    ("coding",       (r"코드|code|구현|implement|함수|function|class|클래스",
                      r"작성|write|만들어|build|생성|create|추가|add")),
    ("refactoring",  (r"리팩토링|refactor|정리|cleanup|개선|improve",
                      r"분리|split|추출|extract|단순화|simplify")),
    # ... 11 more task types
]
```

**Bilingual support**: Patterns include both Korean and English keywords, so requests in either language are classified correctly.

### Confidence scoring

| Patterns matched | Total patterns | Confidence |
|-----------------|----------------|------------|
| 2 of 2 | 2 | 1.00 |
| 1 of 2 | 2 | 0.50 |
| 0 of 2 | 2 | not included |

A request can match multiple task types. For example, "refactor this function" matches both `refactoring` (conf=0.50) and `coding` (conf=0.50).

---

## Routing Decision

After classification, the Router looks up the top task type in `~/.rolemesh/config.json`:

```
classify("refactor this function")
  → task_type = "refactoring", confidence = 0.50
  → config.routing["refactoring"] = { primary: "aider", fallback: "codex" }
  → RouteResult(tool_name="aider", fallback="codex")
```

### Fallback behavior

- If no config file exists: defaults to `claude` for all task types
- If no pattern matches: defaults to `claude` with `coding` type and confidence 0.0
- The `fallback` field is passed to the Executor, which retries on failure

---

## Task Types

| Task Type | Keywords (sample) |
|-----------|-------------------|
| `coding` | code, implement, function, class, create, add |
| `refactoring` | refactor, cleanup, improve, split, extract |
| `quick-edit` | typo, fix, change, rename, delete, remove |
| `analysis` | analyze, investigate, cause, debug, error, bug |
| `architecture` | architect, design, structure, migrate, strategy |
| `reasoning` | reason, logic, judge, evaluate, compare, decide |
| `frontend` | ui, ux, screen, layout, style, component |
| `multimodal` | image, photo, screenshot, graph, chart, visual |
| `search` | search, find, lookup, latest, news, info |
| `explain` | explain, understand, tell, mean, what is, how |
| `git-integration` | commit, branch, merge, pr, git, rebase |
| `completion` | complete, fill, continue, next, rest |
| `pair-programming` | together, pair, help, review, code review |

---

## Programmatic Usage

```python
from src.rolemesh.router import RoleMeshRouter

router = RoleMeshRouter()

# Classify without routing
matches = router.classify_task("debug this error")
# [("analysis", 0.5), ("coding", 0.5)]

# Route to best tool
result = router.route("debug this error")
print(f"{result.tool_name} ({result.task_type}, conf={result.confidence:.2f})")

# Get all route options
results = router.route_multi("debug this error")
for r in results:
    print(f"  {r.task_type} → {r.tool_name} (fallback={r.fallback})")
```

### Custom config path

```python
from pathlib import Path
router = RoleMeshRouter(config_path=Path("/custom/config.json"))
```

---

## API Reference

### `RoleMeshRouter`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(config_path=None)` | — | Loads config from path or default `~/.rolemesh/config.json` |
| `classify_task(request)` | `list[tuple[str, float]]` | Returns all matching (task_type, confidence) pairs, sorted by confidence |
| `route(request)` | `RouteResult` | Returns the best single routing decision |
| `route_multi(request)` | `list[RouteResult]` | Returns routing decisions for all matching task types |

### `RouteResult`

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Selected tool key (e.g. `"claude"`, `"aider"`) |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | Classification confidence (0.0–1.0) |
| `fallback` | `str | None` | Fallback tool key if primary fails |
| `reason` | `str | None` | Explanation when default routing is used |

---

## Related Docs

- [EXECUTOR.md](EXECUTOR.md) — Task execution and fallback handling
- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Tool discovery and setup
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration schema and routing rules
