# RoleMesh Quickstart

> Zero to running in 2 minutes.

---

## Prerequisites

- Python 3.10+
- At least one AI CLI tool installed: `claude`, `codex`, `gemini`, `aider`, `gh copilot`, or `cursor`

---

## Step 1: Discover Tools

```bash
python -m src.rolemesh setup
```

Output:
```
RoleMesh: 2/6 tools available
  [OK] Claude Code (claude 4.1.0) — Anthropic, high
  [--] Codex CLI — OpenAI, medium
  [OK] Gemini CLI (gemini 2.5) — Google, medium
  [--] Aider — Community, low
  [--] GitHub Copilot CLI — GitHub, medium
  [--] Cursor — Cursor, medium
```

---

## Step 2: Save Configuration

```bash
python -m src.rolemesh setup --save
```

This generates `~/.rolemesh/config.json` with tool profiles and routing rules. The Router and Executor load this file automatically.

---

## Step 3: Route a Task

```bash
python -m src.rolemesh route "이 함수를 리팩토링해줘"
```

Output:
```
  Route: claude (refactoring, conf=1.00)
  Fallback: gemini
```

See all matching task types:

```bash
python -m src.rolemesh route "코드 분석하고 버그 수정해줘" --all
```

---

## Step 4: Execute (Dry Run)

```bash
python -m src.rolemesh exec "fix the null pointer bug in auth.py" --dry-run
```

Output:
```
  Tool: claude | Type: analysis | [OK] | 0ms
  [dry-run] would execute: claude -p fix the null pointer bug in auth.py
```

Remove `--dry-run` to actually execute via the routed tool.

---

## Step 5: Check Dashboard

```bash
python -m src.rolemesh dashboard
```

Shows a unified view of:
- **Tools**: installed vs missing, versions, cost tiers
- **Routing Table**: which tool handles which task type
- **Coverage Matrix**: tool capabilities vs task types
- **Health Checks**: config validity, dead references, coverage gaps

### Focused views

```bash
python -m src.rolemesh dashboard --tools      # tools only
python -m src.rolemesh dashboard --routing     # routing table
python -m src.rolemesh dashboard --coverage    # capability matrix
python -m src.rolemesh dashboard --health      # config health
python -m src.rolemesh dashboard --history     # execution log
python -m src.rolemesh dashboard --json        # machine-readable
```

---

## Step 6: Quick Status

```bash
python -m src.rolemesh status
```

One-line summary of available tools and config state.

---

## Programmatic Usage

```python
from src.rolemesh.builder import SetupWizard
from src.rolemesh.router import RoleMeshRouter
from src.rolemesh.executor import RoleMeshExecutor

# Discover and save
wizard = SetupWizard()
wizard.discover()
wizard.save_config()

# Route a task
router = RoleMeshRouter()
result = router.route("implement user authentication")
print(f"Use: {result.tool_name} (type: {result.task_type})")

# Execute (dry run)
executor = RoleMeshExecutor(dry_run=True)
result = executor.dispatch("add input validation to forms")
print(f"Would run: {result.stdout}")
```

---

## What's Next?

- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Detailed Builder usage and configuration
- [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) — Add custom tools to the registry
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and data flow
- [API.md](API.md) — Full class and function reference
