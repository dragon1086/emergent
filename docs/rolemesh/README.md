# RoleMesh

> AI Tool Discovery, Task Routing & Execution Framework

RoleMesh discovers installed AI CLI tools (Claude, Codex, Gemini, Aider, Copilot, Cursor), classifies incoming task requests by type, and routes them to the best-fit tool with automatic fallback.

## Quick Start

```bash
# 1. Discover installed tools and save config
python -m src.rolemesh setup --save

# 2. Check system status
python -m src.rolemesh status

# 3. Route a task (classify only)
python -m src.rolemesh route "이 함수 리팩토링해줘"

# 4. Execute a task (route + run)
python -m src.rolemesh exec "코드 분석해줘"

# 5. View full dashboard
python -m src.rolemesh dashboard
```

## Pipeline

```
Request -> Classify (router) -> Route (config) -> Execute (subprocess) -> Result
                                    |                    |
                                    v                    v
                              best-fit tool        fallback tool
```

1. **Builder** discovers which AI CLIs are installed and generates `~/.rolemesh/config.json`
2. **Router** classifies the task description against 13 bilingual (KR/EN) task patterns and selects the best tool from config
3. **Executor** dispatches via subprocess, with automatic fallback on failure
4. **Dashboard** visualizes tools, routing, coverage, health, and execution history

## CLI Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `setup` | `s` | Discover tools, build config (`--save`, `--interactive`) |
| `route` | `r` | Classify and route a task (`--all`, `--json`) |
| `exec` | `x` | Route and execute (`--dry-run`, `--tool`, `--timeout`) |
| `dashboard` | `d` | System dashboard (`--tools`, `--routing`, `--coverage`, `--health`, `--history`) |
| `status` | `st` | One-line health summary |

All commands support `--json` for machine-readable output and `--config` for custom config paths.

## Supported Tools

| Key | Tool | Vendor | Strengths |
|-----|------|--------|-----------|
| `claude` | Claude Code | Anthropic | coding, refactoring, analysis, architecture, reasoning, explain, pair-programming |
| `codex` | Codex CLI | OpenAI | coding, refactoring, quick-edit, completion, git-integration |
| `gemini` | Gemini CLI | Google | coding, multimodal, search, explain, frontend, analysis |
| `aider` | Aider | Community | coding, refactoring, quick-edit, git-integration |
| `copilot` | GitHub Copilot CLI | GitHub | coding, completion, explain |
| `cursor` | Cursor | Cursor | coding, refactoring, frontend, completion |

Custom tools can be registered via `SetupWizard.register_tool()`.

## Task Types

RoleMesh classifies requests into 13 task types using bilingual regex patterns:

`coding`, `refactoring`, `quick-edit`, `analysis`, `architecture`, `reasoning`, `frontend`, `multimodal`, `search`, `explain`, `git-integration`, `completion`, `pair-programming`

Both Korean and English inputs are supported natively. Mixed-language requests work equally well.

## Config

Config is stored at `~/.rolemesh/config.json` (override with `ROLEMESH_CONFIG` env var):

```json
{
  "version": "1.0.0",
  "tools": { "<key>": { "key", "name", "vendor", "strengths", "cost_tier", "available", "version" } },
  "routing": { "<task_type>": { "primary": "<tool_key>", "fallback": "<tool_key>" } }
}
```

Execution history is appended to `~/.rolemesh/history.jsonl`.

## Further Reading

- [Builder Guide](BUILDER_GUIDE.md) - Discovery and setup walkthrough
- [Custom Tools](CUSTOM_TOOLS.md) - Register your own AI tools
- [Config Reference](CONFIG_REFERENCE.md) - Schema and validation details
- [Architecture](ARCHITECTURE.md) - System design and data flow
- [API Reference](API_REFERENCE.md) - Programmatic Python API
- [Best Practices](BEST_PRACTICES.md) - Patterns and anti-patterns
- [Monitoring Guide](MONITORING_GUIDE.md) - Metrics and alerting
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Docker, CI/CD, team setup
