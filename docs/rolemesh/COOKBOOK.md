# RoleMesh Cookbook

> Practical recipes for common scenarios

## Recipe 1: Cost-Optimized Routing

Route to the cheapest capable tool first, falling back to premium tools only when needed.

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()

# Prefer cheaper tools
for tool in wizard.tools:
    if tool.available:
        if tool.cost_tier == "low":
            tool.user_preference = 1    # prefer
        elif tool.cost_tier == "high":
            tool.user_preference = -1   # avoid unless necessary

wizard.save_config()
```

Result: Aider and Copilot handle coding tasks when they can; Claude is the fallback for complex analysis and architecture.

## Recipe 2: Single-Tool Setup

Force all requests through one tool (useful for testing or when only one tool is installed).

```python
wizard = SetupWizard()
wizard.discover()

# Remove all tools except Claude
for tool in list(wizard.tools):
    if tool.key != "claude":
        wizard.unregister_tool(tool.key)

wizard.save_config()
```

Or via CLI:

```bash
python -m src.rolemesh.builder --save
# If only claude is on PATH, config will only contain claude routes
```

## Recipe 3: Team-Specific Configs

Generate different configs for different teams or projects.

```python
from pathlib import Path

wizard = SetupWizard()
wizard.discover()

# Frontend team: prefer Gemini for UI work
for tool in wizard.tools:
    if tool.key == "gemini":
        tool.user_preference = 1
    elif tool.key == "codex":
        tool.user_preference = -1

wizard.save_config(path=Path("configs/frontend-config.json"))

# Backend team: prefer Claude for architecture
wizard2 = SetupWizard()
wizard2.discover()
for tool in wizard2.tools:
    if tool.key == "claude":
        tool.user_preference = 1

wizard2.save_config(path=Path("configs/backend-config.json"))
```

Use the config:

```python
router = RoleMeshRouter(config_path=Path("configs/frontend-config.json"))
result = router.route("UI component design")
```

## Recipe 4: CI Health Gate

Add a RoleMesh health check to your CI pipeline.

```bash
#!/bin/bash
# ci-health-check.sh

SCORE=$(python -m src.rolemesh.dashboard --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
passed = sum(1 for h in data['health'] if h['passed'])
total = len(data['health'])
print(f'{passed}/{total}')
score = passed / total
sys.exit(0 if score >= 0.8 else 1)
")

echo "RoleMesh health: $SCORE"
```

```yaml
# .github/workflows/ci.yml
- name: RoleMesh health check
  run: bash ci-health-check.sh
```

## Recipe 5: Batch Routing Analysis

Analyze routing decisions for a set of prompts without executing them.

```python
from src.rolemesh.router import RoleMeshRouter

router = RoleMeshRouter()

prompts = [
    "Refactor this function to use async/await",
    "Design the database schema for user management",
    "Fix the CSS layout on the dashboard page",
    "Explain how the authentication flow works",
    "Write unit tests for the payment module",
]

for prompt in prompts:
    result = router.route(prompt)
    print(f"  [{result.task_type:15s}] -> {result.tool_name:15s} ({result.confidence:.0%})")
    print(f"    Prompt: {prompt}")
    print()
```

Output:

```
  [refactoring    ] -> Codex CLI        (100%)
    Prompt: Refactor this function to use async/await

  [architecture   ] -> Claude Code      (100%)
    Prompt: Design the database schema for user management

  [frontend       ] -> Gemini CLI       (100%)
    Prompt: Fix the CSS layout on the dashboard page

  [explain        ] -> GitHub Copilot   (50%)
    Prompt: Explain how the authentication flow works

  [coding         ] -> Codex CLI        (50%)
    Prompt: Write unit tests for the payment module
```

## Recipe 6: Add a Local LLM Tool

Register Ollama (or any local model server) as a custom tool.

```python
from src.rolemesh.builder import SetupWizard
from src.rolemesh.executor import TOOL_COMMANDS

# Step 1: Register
wizard = SetupWizard()
wizard.discover()
wizard.register_tool(
    key="ollama",
    name="Ollama (CodeLlama)",
    vendor="Ollama",
    strengths=["coding", "explain", "quick-edit"],
    check_cmd=["ollama", "--version"],
    cost_tier="low",
)
wizard.save_config()

# Step 2: Add executor mapping
TOOL_COMMANDS["ollama"] = {
    "cmd": ["ollama", "run", "codellama"],
    "stdin_mode": True,
}

# Step 3: Verify routing
from src.rolemesh.router import RoleMeshRouter
router = RoleMeshRouter()
result = router.route("explain this code")
print(result.tool_name)
# Ollama (CodeLlama) — low cost + explain strength = high rank
```

## Recipe 7: Routing Comparison Report

Compare how different configs route the same prompts.

```python
from pathlib import Path
from src.rolemesh.router import RoleMeshRouter

configs = {
    "default": Path("~/.rolemesh/config.json").expanduser(),
    "frontend": Path("configs/frontend-config.json"),
    "backend": Path("configs/backend-config.json"),
}

prompts = [
    "implement the login page",
    "optimize the database query",
    "add CSS animations",
]

# Header
print(f"{'Prompt':<35s}", end="")
for name in configs:
    print(f"  {name:<15s}", end="")
print()
print("-" * 80)

# Rows
for prompt in prompts:
    print(f"{prompt:<35s}", end="")
    for name, path in configs.items():
        router = RoleMeshRouter(config_path=path)
        result = router.route(prompt)
        print(f"  {result.tool_name:<15s}", end="")
    print()
```

## Recipe 8: Executor with Retry

Wrap the executor to retry with the next-best tool on failure.

```python
from src.rolemesh.executor import RoleMeshExecutor

executor = RoleMeshExecutor()

def run_with_retry(prompt, max_attempts=3):
    """Try primary, then fallback, then any remaining tool."""
    result = executor.run(prompt)
    if result.success:
        return result

    # Fallback was already tried by executor if configured.
    # Log the failure for analysis.
    print(f"Failed: {result.tool} (exit {result.exit_code})")
    if result.fallback_used:
        print(f"Fallback also failed")

    return result

result = run_with_retry("implement a REST endpoint")
```

## Recipe 9: Dashboard Snapshot Diff

Track routing changes over time by comparing dashboard snapshots.

```bash
# Save today's snapshot
python -m src.rolemesh.dashboard --json > snapshots/$(date +%Y%m%d).json

# Compare with yesterday
diff <(jq '.routing' snapshots/20260306.json) \
     <(jq '.routing' snapshots/20260307.json)
```

## Recipe 10: Programmatic Config Merge

Merge routing rules from multiple configs (e.g., team defaults + personal overrides).

```python
import json
from pathlib import Path

def merge_configs(base_path, override_path):
    base = json.loads(Path(base_path).read_text())
    override = json.loads(Path(override_path).read_text())

    # Override tools
    base["tools"].update(override.get("tools", {}))

    # Override routing (per task type)
    base["routing"].update(override.get("routing", {}))

    return base

merged = merge_configs(
    "~/.rolemesh/config.json",
    "project/.rolemesh-overrides.json"
)

# Validate
from src.rolemesh.builder import SetupWizard
errors = SetupWizard.validate_config(merged)
if not errors:
    Path("~/.rolemesh/config.json").expanduser().write_text(
        json.dumps(merged, indent=2)
    )
```
