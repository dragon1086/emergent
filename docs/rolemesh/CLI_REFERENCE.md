# RoleMesh CLI Reference

> Complete command reference for `python -m src.rolemesh`

## Global Options

| Flag | Description |
|------|-------------|
| `--config PATH` | Custom config file (default: `~/.rolemesh/config.json`) |

## Commands

### `dashboard` (aliases: `dash`, `d`)

Show system dashboard with tools, routing, coverage, and health.

```bash
python -m src.rolemesh dashboard              # full dashboard
python -m src.rolemesh dashboard --tools      # installed tools only
python -m src.rolemesh dashboard --routing    # routing table only
python -m src.rolemesh dashboard --coverage   # task/tool matrix
python -m src.rolemesh dashboard --health     # health checks only
python -m src.rolemesh dashboard --history    # execution history
python -m src.rolemesh dashboard --json       # JSON output
python -m src.rolemesh dashboard --no-color   # disable ANSI colors
```

| Flag | Description |
|------|-------------|
| `--tools` | Show only the tools section |
| `--routing` | Show only the routing table |
| `--coverage` | Show only the task/tool coverage matrix |
| `--health` | Show only health check results |
| `--history` | Show only execution history |
| `--json` | Output as JSON (machine-readable) |
| `--no-color` | Disable ANSI color codes |

Multiple section flags can be combined:

```bash
python -m src.rolemesh dashboard --tools --health
```

### `setup` (alias: `s`)

Discover installed AI tools and build routing config.

```bash
python -m src.rolemesh setup                  # discover and print summary
python -m src.rolemesh setup --save           # save config to disk
python -m src.rolemesh setup --interactive    # guided preference setup
python -m src.rolemesh setup --json           # JSON output
```

| Flag | Description |
|------|-------------|
| `--save` | Persist config to `~/.rolemesh/config.json` |
| `--interactive`, `-i` | Prompt for tool preferences (y/n/skip per tool) |
| `--json` | Output config as JSON |

Interactive mode asks for each available tool:

```
=== RoleMesh Setup Wizard ===
Found 3 AI tool(s):
  - Claude Code v1.0 (Anthropic) [coding, analysis, reasoning, architecture]

Prefer Claude Code? [y/n/skip] y
Prefer Codex CLI? [y/n/skip] skip
```

### `route` (alias: `r`)

Classify a task and show which tool would handle it.

```bash
python -m src.rolemesh route "이 함수 구현해줘"
# -> Claude Code (claude)
#    Task: coding (100%)

python -m src.rolemesh route --all "코드 리팩토링 개선해줘"
# Shows all matching task types with confidence scores

python -m src.rolemesh route --json "refactor this module"
```

| Flag | Description |
|------|-------------|
| `--all` | Show all matching task types (not just the top one) |
| `--json` | Output as JSON |

### `exec` (alias: `x`)

Route a task to the best tool and execute it via subprocess.

```bash
python -m src.rolemesh exec "UI 컴포넌트 디자인"
python -m src.rolemesh exec --dry-run "함수 구현해줘"   # show command only
python -m src.rolemesh exec --tool claude "분석해줘"    # force specific tool
python -m src.rolemesh exec --timeout 300 "대규모 리팩토링"
```

| Flag | Description |
|------|-------------|
| `--tool TOOL` | Skip routing, force a specific tool key |
| `--dry-run` | Print the command without executing |
| `--timeout SECS` | Subprocess timeout in seconds (default: 120) |
| `--json` | Output result as JSON |

Output includes exit code, duration, stdout/stderr, and whether a fallback tool was used.

### `history` (aliases: `hist`, `h`)

Show execution history from the JSONL log.

```bash
python -m src.rolemesh history
python -m src.rolemesh history --json
python -m src.rolemesh history --no-color
```

| Flag | Description |
|------|-------------|
| `--json` | Output history entries as JSON array |
| `--no-color` | Disable ANSI color codes |

### `status` (alias: `st`)

Quick one-line health summary.

```bash
python -m src.rolemesh status
# [OK] 3 tools (Claude Code, Codex CLI, Gemini CLI) | health 5/5

python -m src.rolemesh status --json
```

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON |
| `--no-color` | Disable ANSI color codes |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Command error or unknown subcommand |
| `127` | Unknown tool (exec with invalid `--tool`) |

## Examples

```bash
# First-time setup
python -m src.rolemesh setup --interactive --save

# Daily workflow
python -m src.rolemesh status                        # quick check
python -m src.rolemesh route "debug this crash"      # preview routing
python -m src.rolemesh exec "debug this crash"       # route + execute

# CI/scripting
python -m src.rolemesh status --json | jq '.healthy'
python -m src.rolemesh route --json "task" | jq '.tool'
python -m src.rolemesh exec --dry-run --json "task"

# Custom config path
python -m src.rolemesh --config ./my-config.json dashboard
```

## Environment

- Config default location: `~/.rolemesh/config.json`
- History log: `~/.rolemesh/history.jsonl`
- No environment variables required; all configuration is file-based
