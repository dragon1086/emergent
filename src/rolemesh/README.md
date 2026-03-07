# RoleMesh

> AI tool discovery, routing, and execution for multi-agent workflows.

RoleMesh automatically discovers installed AI CLI tools (Claude Code, Codex, Gemini, Aider, Copilot, Cursor), classifies user tasks by type, and routes each task to the best-fit tool — with automatic fallback if the primary tool fails.

---

## Quick Start

```bash
# Discover installed tools and save config
python -m src.rolemesh setup --save

# Route a task (dry run)
python -m src.rolemesh route "이 함수 리팩토링해줘"

# Execute a task
python -m src.rolemesh exec "코드 분석해줘" --dry-run

# View dashboard
python -m src.rolemesh dashboard

# One-line status
python -m src.rolemesh status
```

---

## Pipeline

```
discover_tools()          SetupWizard            RoleMeshRouter           RoleMeshExecutor
    │                         │                       │                        │
    ▼                         ▼                       ▼                        ▼
Probe system PATH     Build routing config     Classify task type      Dispatch to CLI tool
for AI CLI tools      (strengths × cost)       via regex patterns      with fallback chain
    │                         │                       │                        │
    └─────────────────────────┴───────────────────────┴────────────────────────┘
                                        │
                                        ▼
                              RoleMeshDashboard
                         (unified view of everything)
```

---

## Supported Tools

| Tool | Vendor | Strengths | Cost Tier |
|------|--------|-----------|-----------|
| Claude Code | Anthropic | coding, refactoring, analysis, architecture, reasoning, explain, pair-programming | high |
| Codex CLI | OpenAI | coding, refactoring, quick-edit, analysis, completion | medium |
| Gemini CLI | Google | coding, analysis, reasoning, multimodal, search, explain | medium |
| Aider | Community | coding, refactoring, quick-edit, git-integration, pair-programming | low |
| GitHub Copilot CLI | GitHub | coding, completion, explain, quick-edit | medium |
| Cursor | Cursor | coding, refactoring, frontend, completion, pair-programming | medium |

Custom tools can be registered via `SetupWizard.register_tool()`.

---

## Task Types

RoleMesh classifies requests into 14 task types using bilingual (Korean/English) regex patterns:

`coding` | `refactoring` | `quick-edit` | `analysis` | `architecture` | `reasoning` | `frontend` | `multimodal` | `search` | `explain` | `git-integration` | `completion` | `pair-programming`

Each task type maps to a primary tool and an optional fallback in the routing config.

---

## Configuration

Config is stored at `~/.rolemesh/config.json`:

```json
{
  "version": "1.0.0",
  "tools": { ... },
  "routing": {
    "coding": { "primary": "claude", "fallback": "codex" },
    "analysis": { "primary": "gemini", "fallback": "claude" }
  }
}
```

Generate it with `python -m src.rolemesh setup --save` or interactively with `--interactive`.

---

## Modules

| Module | Purpose |
|--------|---------|
| `builder.py` | Tool discovery, profiling, config generation, interactive setup |
| `router.py` | Task classification (regex) and tool routing |
| `executor.py` | CLI dispatch with fallback and history logging |
| `dashboard.py` | Terminal dashboard with tools, routing, coverage, health views |
| `__main__.py` | Unified CLI entry point |

See [API.md](API.md) for class/function reference and [ARCHITECTURE.md](ARCHITECTURE.md) for design details.
