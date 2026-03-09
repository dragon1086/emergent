# Frequently Asked Questions

> Quick answers to common RoleMesh questions.

---

## General

### What is RoleMesh?

RoleMesh is a tool discovery, routing, and execution framework for AI CLI tools. It scans your system for installed tools (Claude Code, Codex, Gemini, Aider, Copilot, Cursor), profiles their capabilities, and routes tasks to the best tool based on task type, cost, and user preferences.

### Which AI CLI tools does RoleMesh support?

6 built-in tools:

| Tool | Vendor | Cost Tier |
|------|--------|-----------|
| Claude Code | Anthropic | high |
| Codex CLI | OpenAI | medium |
| Gemini CLI | Google | medium |
| Aider | Community | low |
| GitHub Copilot CLI | GitHub | medium |
| Cursor | Cursor | medium |

You can also register custom tools. See [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md).

### Do I need all tools installed?

No. RoleMesh works with any number of installed tools (minimum 1). It automatically adapts routing based on what's available.

---

## Setup

### How do I get started?

```bash
python -m src.rolemesh setup --save
```

This discovers installed tools and writes the config file. See [QUICKSTART.md](QUICKSTART.md) for the full walkthrough.

### Where is the config file stored?

`~/.rolemesh/config.json`. Override with `--config PATH` on any command.

### Where is execution history stored?

`~/.rolemesh/history.jsonl`. Each execution appends a JSON line with timestamp, tool, task type, success status, and duration.

### Can I edit the config manually?

Yes. The config is a plain JSON file. Common edits:

- Force a tool for a specific task type
- Disable fallback by setting it to `null`
- Add custom routing rules

Run `setup --save` to regenerate from scratch if manual edits cause issues.

---

## Routing

### How does task classification work?

The router matches your task description against 13 regex pattern groups (supporting both Korean and English). Each pattern group has 2 sub-patterns. Confidence = matched sub-patterns / total sub-patterns.

### What are the 13 task types?

`coding`, `refactoring`, `quick-edit`, `analysis`, `architecture`, `reasoning`, `frontend`, `multimodal`, `search`, `explain`, `git-integration`, `completion`, `pair-programming`.

See [BUILDER_CONFIG.md](BUILDER_CONFIG.md) for descriptions.

### What happens if no pattern matches?

RoleMesh defaults to `claude` with task type `coding` and confidence `0.0`.

### How are tools ranked for each task type?

Three-level sort:

1. **Strength match** — tools listing the task type as a strength rank first
2. **User preference** — manual rankings from interactive setup break ties
3. **Cost tier** — cheaper tools win among equals

The top-ranked tool becomes `primary`, second becomes `fallback`.

### Can I force a specific tool?

Yes, via CLI:

```bash
python -m src.rolemesh exec "my task" --tool claude
```

Or by editing `config.json` routing rules.

---

## Execution

### What is dry-run mode?

Dry-run shows the command that would be executed without actually running it:

```bash
python -m src.rolemesh exec "fix the bug" --dry-run
```

### How does fallback work?

If the primary tool returns a non-zero exit code, the executor automatically retries with the fallback tool (if configured). The result includes `fallback_used: true`.

### What is the execution timeout?

300 seconds (5 minutes). Tasks exceeding this limit are terminated and marked as failed.

### Does RoleMesh modify my code directly?

RoleMesh dispatches tasks to AI CLI tools. The actual code modifications are performed by the routed tool (e.g., Claude Code, Aider). RoleMesh itself only handles classification, routing, and process management.

---

## Dashboard

### What health checks are performed?

| Check | What it verifies |
|-------|-----------------|
| `config_file` | Config file exists at the expected path |
| `tools_available` | At least one AI CLI tool is installed |
| `routing_coverage` | All 13 task types have routing rules |
| `config_version` | Config version is `1.0.0` |
| `no_dead_refs` | No routing rules reference missing tools |

### Can I get JSON output?

Yes. All commands support `--json`:

```bash
python -m src.rolemesh dashboard --json
python -m src.rolemesh route "task" --json
python -m src.rolemesh exec "task" --dry-run --json
```

### How do I disable colors?

Set the `NO_COLOR` environment variable:

```bash
NO_COLOR=1 python -m src.rolemesh dashboard
```

Colors are also automatically disabled when output is piped (non-TTY).

---

## Custom Tools

### Can I add my own tools?

Yes, two methods:

1. **Runtime**: `SetupWizard.register_tool()` — adds at runtime, persisted via `save_config()`
2. **Static**: Add to `TOOL_REGISTRY` in `builder.py` — permanent, requires code change

See [BUILDER_EXTENDING.md](BUILDER_EXTENDING.md) for details.

### What are the requirements for a custom tool?

- Callable CLI binary on PATH
- Responds to a version command (for health checks)
- Accepts a task string via CLI flag or stdin
- Returns exit code 0 on success, non-zero on failure
- Writes output to stdout

### Can I remove a custom tool?

```python
wizard.unregister_tool("mytool")
wizard.save_config()
```

---

## Troubleshooting

### Where do I find detailed troubleshooting?

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for a comprehensive guide covering discovery, configuration, routing, execution, and environment issues.

### My tool is installed but not detected

Ensure the binary is on your `PATH`:

```bash
which <tool-binary>
```

If not found, add its directory to PATH and re-run `setup --save`.

### Config is broken after manual editing

Regenerate from scratch:

```bash
python -m src.rolemesh setup --save
```

This overwrites the config with a clean version based on currently installed tools.

---

## Related Docs

- [QUICKSTART.md](QUICKSTART.md) — Getting started
- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Setup walkthrough
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration schema
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Detailed troubleshooting
- [COOKBOOK.md](COOKBOOK.md) — Practical recipes
