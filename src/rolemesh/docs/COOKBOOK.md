# RoleMesh Cookbook

> Practical recipes for common workflows and integrations.

---

## Recipe 1: Cost-Optimized Routing

Route simple tasks to cheaper tools and reserve expensive tools for complex work.

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Check available tools sorted by cost
for tool in sorted(wizard.available_tools(), key=lambda t: {"low": 0, "medium": 1, "high": 2}[t.cost_tier]):
    print(f"{tool.name}: {tool.cost_tier}")

wizard.save_config()
```

The default ranking algorithm already prefers cheaper tools when capabilities are equal. To force a specific cheap tool for simple tasks, edit the config:

```json
"routing": {
  "quick-edit": { "primary": "aider", "fallback": null },
  "completion": { "primary": "copilot", "fallback": "codex" },
  "architecture": { "primary": "claude", "fallback": "codex" }
}
```

---

## Recipe 2: Dry-Run Before Execution

Preview which tool would handle a task without actually running it.

```bash
# See routing decision
python -m src.rolemesh route "refactor the auth module" --all

# See the exact command that would run
python -m src.rolemesh exec "refactor the auth module" --dry-run
```

Output:

```
  Tool: aider | Type: refactoring | [OK] | 0ms
  [dry-run] would execute: aider --message refactor the auth module
```

---

## Recipe 3: Programmatic Task Pipeline

Chain classification, routing, and execution in Python:

```python
from src.rolemesh.router import RoleMeshRouter
from src.rolemesh.executor import RoleMeshExecutor

router = RoleMeshRouter()
executor = RoleMeshExecutor()

tasks = [
    "fix the typo in README.md",
    "refactor the database connection pool",
    "explain how the auth middleware works",
]

for task in tasks:
    # Classify
    matches = router.classify_task(task)
    print(f"\nTask: {task}")
    print(f"  Classifications: {matches[:3]}")

    # Route
    route = router.route(task)
    print(f"  Routed to: {route.tool_name} (type={route.task_type})")

    # Execute (dry-run for safety)
    result = RoleMeshExecutor(dry_run=True).dispatch(task)
    print(f"  Command: {result.stdout}")
```

---

## Recipe 4: Multi-Classification Analysis

Some tasks match multiple categories. Use `route_multi` to see all matches:

```python
from src.rolemesh.router import RoleMeshRouter

router = RoleMeshRouter()

# This task spans coding + git
task = "create a new branch and implement the login feature"
results = router.route_multi(task)

for r in results:
    print(f"  {r.task_type:<20s} conf={r.confidence:.2f} -> {r.tool_name}")
```

Or via CLI:

```bash
python -m src.rolemesh route "create a branch and implement login" --all --json
```

---

## Recipe 5: Dashboard Health Monitoring

Integrate the dashboard into a CI check or startup script:

```python
from src.rolemesh.dashboard import RoleMeshDashboard

dash = RoleMeshDashboard()
data = dash.collect()

# Check all health checks pass
failures = [h for h in data.health if not h.passed]
if failures:
    for f in failures:
        print(f"FAIL: {f.name} - {f.detail}")
    exit(1)
else:
    print("All health checks passed")
```

Or as a shell one-liner:

```bash
python -m src.rolemesh dashboard --health --json | python -c "
import sys, json
data = json.load(sys.stdin)
fails = [h for h in data['health'] if not h['passed']]
sys.exit(1 if fails else 0)
"
```

---

## Recipe 6: Execution History Analysis

Analyze which tools are used most and their success rates:

```python
import json
from pathlib import Path
from collections import Counter

history_path = Path.home() / ".rolemesh" / "history.jsonl"
if not history_path.exists():
    print("No history yet")
    exit()

entries = [json.loads(line) for line in history_path.read_text().strip().split("\n")]

# Tool usage counts
tool_counts = Counter(e["tool"] for e in entries)
print("Tool usage:")
for tool, count in tool_counts.most_common():
    print(f"  {tool}: {count}")

# Success rate per tool
for tool in tool_counts:
    tool_entries = [e for e in entries if e["tool"] == tool]
    success = sum(1 for e in tool_entries if e["success"])
    rate = success / len(tool_entries) * 100
    print(f"  {tool}: {rate:.0f}% success ({success}/{len(tool_entries)})")

# Average duration per tool
for tool in tool_counts:
    tool_entries = [e for e in entries if e["tool"] == tool]
    avg_ms = sum(e["duration_ms"] for e in tool_entries) / len(tool_entries)
    print(f"  {tool}: {avg_ms:.0f}ms avg")
```

---

## Recipe 7: Custom Tool with Fallback Chain

Register a local LLM as a zero-cost fallback:

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Register local Ollama
wizard.register_tool(
    key="ollama",
    name="Ollama Local",
    vendor="Local",
    strengths=["coding", "explain", "quick-edit"],
    check_cmd=["ollama", "--version"],
    cost_tier="low",
)

wizard.save_config()
```

Then edit `executor.py` to add the command mapping:

```python
TOOL_COMMANDS["ollama"] = {"cmd": ["ollama", "run", "codellama"], "stdin_mode": True}
```

Now simple tasks route to Ollama first, with cloud tools as fallback.

---

## Recipe 8: Korean and English Mixed Tasks

The router supports both Korean and English keywords. Use either language naturally:

```bash
# Korean
python -m src.rolemesh route "auth 모듈 리팩토링해줘"

# English
python -m src.rolemesh route "refactor the auth module"

# Mixed
python -m src.rolemesh route "로그인 function 구현"
```

All three route to the correct task type with appropriate confidence.

---

## Recipe 9: JSON Output for Scripting

All CLI commands support `--json` for machine-readable output:

```bash
# Route result as JSON
python -m src.rolemesh route "fix the bug" --json

# Dashboard data as JSON
python -m src.rolemesh dashboard --json

# Execution result as JSON
python -m src.rolemesh exec "explain this code" --dry-run --json
```

Pipe to `jq` for filtering:

```bash
# Get just the primary tool name
python -m src.rolemesh route "fix bug" --json | jq -r '.tool'

# Get all available tool names
python -m src.rolemesh dashboard --json | jq '[.tools[] | select(.available) | .name]'
```

---

## Related Docs

- [QUICKSTART.md](QUICKSTART.md) — Getting started
- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Setup details
- [ROUTER.md](ROUTER.md) — Routing internals
- [EXECUTOR.md](EXECUTOR.md) — Execution details
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues
