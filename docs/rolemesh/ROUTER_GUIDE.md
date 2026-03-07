# Router Guide

> Classify tasks and route them to the best AI tool

## Overview

The Router module (`src/rolemesh/router.py`) takes a natural-language task description, classifies it into one or more task types using regex patterns, and maps it to the best AI CLI tool based on the config built by the [Builder](BUILDER_GUIDE.md).

## Quick Start

```bash
# Route a single task
python -m src.rolemesh.router "코드 리팩토링해줘"

# JSON output for scripting
python -m src.rolemesh.router --json "UI 컴포넌트 수정"

# Show all matching task types (multi-route)
python -m src.rolemesh.router --all "이 코드 리팩토링하고 UI도 수정해줘"
```

## How Routing Works

```
User Request -> classify_task() -> route() -> RouteResult
     |               |                |            |
  "리팩토링해줘"   regex match     config lookup   tool + fallback
                  + confidence     primary/fallback
```

### Step 1: Task Classification

`classify_task(request)` matches the input against regex patterns for each task type. Each task type has multiple patterns; the confidence score is the ratio of matched patterns to total patterns.

Supported task types:

| Task Type | Example Triggers (KR/EN) |
|-----------|--------------------------|
| `coding` | 코드, code, 구현, implement, 함수, function |
| `refactoring` | 리팩토링, refactor, 정리, cleanup |
| `quick-edit` | 오타, typo, 수정, fix, 바꿔, change |
| `analysis` | 분석, analyze, 디버그, debug, 버그, bug |
| `architecture` | 아키텍처, architect, 설계, design |
| `reasoning` | 추론, reason, 비교, compare, 결정, decide |
| `frontend` | ui, ux, 화면, screen, 컴포넌트, component |
| `multimodal` | 이미지, image, 스크린샷, screenshot |
| `search` | 검색, search, 찾아, find, 문서, doc |
| `explain` | 설명, explain, 이해, understand |
| `git-integration` | 커밋, commit, 브랜치, branch, merge, pr |
| `completion` | 자동완성, complete, 이어서, continue |
| `pair-programming` | 같이, together, 페어, pair, 코드리뷰 |

### Step 2: Config Lookup

The router loads `~/.rolemesh/config.json` (built by the [Builder](BUILDER_GUIDE.md)) and looks up the routing rule for the top-ranked task type. Each rule specifies a `primary` tool and an optional `fallback`.

### Step 3: RouteResult

The result includes:

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `str` | Tool key (e.g., `"claude"`) |
| `tool_name` | `str` | Display name (e.g., `"Claude Code"`) |
| `task_type` | `str` | Classified task type |
| `confidence` | `float` | 0.0–1.0 match confidence |
| `fallback` | `str?` | Fallback tool key (if available) |
| `reason` | `str` | Human-readable routing explanation |

Confidence levels:
- `>= 0.8`: **Strong match** — high certainty on task type
- `>= 0.5`: **Good match** — reasonable certainty
- `< 0.5`: **Weak match** — consider specifying task type explicitly

## Programmatic Usage

```python
from src.rolemesh.router import RoleMeshRouter

router = RoleMeshRouter()

# Single best route
result = router.route("이 함수 리팩토링해줘")
print(f"{result.tool_name} ({result.confidence:.0%})")
# -> Claude Code (100%)

# Classify without routing
types = router.classify_task("코드 리팩토링하고 UI도 수정해줘")
for task_type, confidence in types:
    print(f"  {task_type}: {confidence:.0%}")

# Multi-route for complex requests
results = router.route_multi("코드 리팩토링하고 UI도 수정해줘")
for r in results:
    print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool_name}")
```

## Custom Config Path

```python
from pathlib import Path
router = RoleMeshRouter(config_path=Path("/custom/config.json"))
```

If no config file exists, the router defaults all tasks to `claude`.

## Default Behavior

When no task pattern matches (confidence = 0), the router falls back to:
- Tool: `claude` (Claude Code)
- Task type: `coding`
- Reason: "No task pattern matched, defaulting to Claude"

## See Also

- [Builder Guide](BUILDER_GUIDE.md) — Generate the routing config
- [Executor Guide](EXECUTOR_GUIDE.md) — Execute routed tasks
- [Config Reference](CONFIG_REFERENCE.md) — Config schema details
- [API Reference](API_REFERENCE.md) — Full Python API
