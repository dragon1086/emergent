# RoleMesh

> AI tool discovery, routing, and execution — one CLI to rule them all.

RoleMesh discovers which AI CLI tools are installed on your system (Claude Code, Codex, Gemini, Aider, Copilot, Cursor), classifies incoming tasks by type, and routes each task to the best-fit tool automatically.

---

## Quick Start

```bash
# 1. Discover installed tools and save config
python -m src.rolemesh setup --save

# 2. Check system status
python -m src.rolemesh status

# 3. Route a task (dry-run)
python -m src.rolemesh exec --dry-run "이 함수 리팩토링해줘"

# 4. Execute for real
python -m src.rolemesh exec "코드 리팩토링해줘"
```

## Commands

| Command | Description |
|---|---|
| `setup [--save] [--interactive]` | Discover tools, build routing config |
| `route "task" [--all] [--json]` | Classify and route a task (no execution) |
| `exec "task" [--tool X] [--dry-run]` | Route + execute via subprocess |
| `dashboard [--tools\|--routing\|--coverage\|--health\|--history]` | Visual system dashboard |
| `status [--json]` | One-line health summary |

All commands accept `--json` for machine-readable output and `--config <path>` to override the default config location (`~/.rolemesh/config.json`).

## Supported Tools

| Tool | Vendor | Strengths | Cost |
|---|---|---|---|
| Claude Code | Anthropic | coding, analysis, reasoning, architecture | high |
| Codex CLI | OpenAI | coding, refactoring, quick-edit | medium |
| Gemini CLI | Google | multimodal, search, ui-design, frontend | medium |
| Aider | Community | coding, git-integration, pair-programming | low |
| GitHub Copilot CLI | GitHub | completion, quick-edit, explain | low |
| Cursor | Cursor | coding, ui, inline-edit | medium |

## Task Types

RoleMesh recognizes 13 task categories via regex pattern matching (supports Korean and English):

`coding`, `refactoring`, `quick-edit`, `analysis`, `architecture`, `reasoning`, `frontend`, `multimodal`, `search`, `explain`, `git-integration`, `completion`, `pair-programming`

## Config

Config is stored at `~/.rolemesh/config.json` after running `setup --save`. It contains:

- **tools**: discovered tool profiles (name, vendor, version, strengths, cost tier)
- **routing**: task-type-to-tool mapping with primary + fallback

Execution history is logged to `~/.rolemesh/history.jsonl`.

## Further Reading

- [API Reference](./API.md) — classes, methods, data structures
- [Architecture](./ARCHITECTURE.md) — design decisions, data flow, extension points
