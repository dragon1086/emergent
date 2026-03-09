# RoleMesh Documentation

> AI tool discovery, routing, and execution framework.

RoleMesh automatically discovers installed AI CLI tools (Claude Code, Codex, Gemini, Aider, Copilot, Cursor), profiles their capabilities, and routes tasks to the best tool based on task type classification and configurable routing rules.

---

## Modules

| Module | Description | Entry Point |
|--------|-------------|-------------|
| **Builder** | Tool discovery, profiling, config generation | `builder.py` |
| **Router** | Task classification and tool routing | `router.py` |
| **Executor** | Task dispatch with fallback and history logging | `executor.py` |
| **Dashboard** | CLI dashboard with health checks and coverage matrix | `dashboard.py` |

---

## Quick Start

```bash
# 1. Discover installed tools
python -m src.rolemesh setup

# 2. Save routing configuration
python -m src.rolemesh setup --save

# 3. Route a task
python -m src.rolemesh route "refactor this function"

# 4. Execute a task (routes automatically)
python -m src.rolemesh exec "fix the login bug" --dry-run

# 5. View dashboard
python -m src.rolemesh dashboard
```

---

## CLI Commands

```
python -m src.rolemesh <command> [options]

Commands:
  setup       Discover tools and generate config
  route       Classify a task and show routing decision
  exec        Execute a task via the routed tool
  dashboard   Display tools, routing, coverage, and health
  status      Quick status overview
```

---

## Pipeline

```
User Request
    |
    v
[Router] classify_task() --> task_type + confidence
    |
    v
[Router] route() --> tool_name + fallback (from config)
    |
    v
[Executor] dispatch() --> run tool CLI
    |                        |
    | (success)              | (failure + fallback exists)
    v                        v
  Result              [Executor] run fallback tool
                             |
                             v
                           Result
```

---

## Documentation Index

### Getting Started
- [QUICKSTART.md](QUICKSTART.md) — Zero-to-running in 2 minutes

### Builder
- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Discovery, setup, and configuration
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Config schema and validation rules
- [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) — Adding custom tools

### Core Modules
- [ROUTER.md](ROUTER.md) — Task classification and routing logic
- [EXECUTOR.md](EXECUTOR.md) — Task dispatch and fallback behavior
- [DASHBOARD_CLI.md](DASHBOARD_CLI.md) — CLI dashboard usage

### Reference
- [API.md](API.md) — Full class and function reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and data flow

---

## Supported Tools

| Tool | Vendor | Cost Tier | Key Strengths |
|------|--------|-----------|---------------|
| Claude Code | Anthropic | high | coding, refactoring, analysis, architecture, reasoning |
| Codex CLI | OpenAI | medium | coding, refactoring, quick-edit, analysis |
| Gemini CLI | Google | medium | coding, analysis, reasoning, multimodal, search |
| Aider | Community | low | coding, refactoring, quick-edit, git-integration |
| Copilot CLI | GitHub | medium | coding, completion, explain |
| Cursor | Cursor | medium | coding, refactoring, frontend, completion |

Custom tools can be added via `SetupWizard.register_tool()` or by editing `TOOL_REGISTRY` in `builder.py`. See [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md).
