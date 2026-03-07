# RoleMesh Quickstart

> From zero to routing in 5 minutes

## Prerequisites

- Python 3.10+
- At least one AI CLI tool installed: `claude`, `codex`, `gemini`, `aider`, `copilot`, or `cursor`

## Step 1: Discover Your Tools

```bash
cd /path/to/emergent
python -m src.rolemesh.builder
```

Output:

```
Found 3 AI tool(s):
  - Claude Code v1.0 (Anthropic) [coding, analysis, reasoning, architecture]
  - Codex CLI v0.1 (OpenAI) [coding, refactoring, quick-edit]
  - Gemini CLI v2.0 (Google) [multimodal, search, ui-design, frontend]
```

## Step 2: Generate Routing Config

```bash
python -m src.rolemesh.builder --save
# Config saved to ~/.rolemesh/config.json
```

This creates routing rules that map each task type to the best available tool.

### Optional: Set preferences interactively

```bash
python -m src.rolemesh.builder --interactive
# Prefer Claude Code? [y/n/skip] y
# Prefer Codex CLI? [y/n/skip] skip
# Prefer Gemini CLI? [y/n/skip] n
```

## Step 3: Route a Request

```bash
# See where a task would go (no execution)
python -m src.rolemesh.router "이 함수 리팩토링해줘"
# -> Codex CLI (codex)
#    Task: refactoring (100%)
#    Strong match for 'refactoring'
```

## Step 4: Execute

```bash
# Route + execute in one step
python -m src.rolemesh.executor "UI 컴포넌트 디자인"

# Dry-run to preview the command
python -m src.rolemesh.executor --dry-run "코드 분석해줘"
```

## Step 5: Check System Health

```bash
python -m src.rolemesh.dashboard
```

This shows:
- Which tools are installed vs. missing
- Routing table (task type -> primary + fallback)
- Coverage matrix (which tools handle which tasks)
- Health score (config, tools, routing coverage)

## Common Workflows

### Route only (scripting)

```bash
# JSON output for integration
python -m src.rolemesh.router "implement a REST endpoint" --json
```

### Force a specific tool

```bash
python -m src.rolemesh.executor --tool claude "explain this code"
```

### Python integration

```python
from src.rolemesh import SetupWizard, RoleMeshRouter, RoleMeshExecutor

# One-time setup
wizard = SetupWizard()
wizard.discover()
wizard.save_config()

# Route requests
router = RoleMeshRouter()
result = router.route("이 함수 구현해줘")
print(f"{result.tool_name} will handle '{result.task_type}'")

# Route + execute
executor = RoleMeshExecutor()
result = executor.run("refactor this function")
if result.success:
    print(result.stdout)
```

## Troubleshooting

### "No AI tools found"

Install at least one supported CLI tool and ensure it's on your PATH:

```bash
which claude codex gemini aider
```

### "routing_coverage" health check fails

Not all 13 task types have routing rules. This happens when installed tools don't cover all categories. Re-run the builder after installing more tools:

```bash
python -m src.rolemesh.builder --save
```

### Routing to the wrong tool

Set user preferences to override default ranking:

```bash
python -m src.rolemesh.builder --interactive --save
```

Or edit `~/.rolemesh/config.json` directly (see [BUILDER_GUIDE.md](BUILDER_GUIDE.md#direct-config-editing)).

## Next Steps

- [ARCHITECTURE.md](ARCHITECTURE.md) — How the system works internally
- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Add custom tools and task types
- [ROUTER_GUIDE.md](ROUTER_GUIDE.md) — Classification and routing details
- [EXECUTOR_GUIDE.md](EXECUTOR_GUIDE.md) — Execution, fallback, and timeouts
- [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) — Health monitoring and CI integration
