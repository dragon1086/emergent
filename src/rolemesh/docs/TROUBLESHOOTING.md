# Troubleshooting Guide

> Common issues, diagnostics, and solutions for RoleMesh.

---

## Diagnostics First

Before troubleshooting, run the health check to identify issues:

```bash
python -m src.rolemesh dashboard --health
```

This runs 5 automated checks: config file, tools available, routing coverage, config version, and dead references.

---

## Tool Discovery Issues

### Tool shows `[--]` but is installed

**Cause**: The tool's binary is not on your shell `PATH`.

```bash
# Verify the binary location
which claude
which codex
which gemini

# If missing, check common install paths
ls ~/.local/bin/ | grep -E "claude|codex|gemini|aider"
ls /usr/local/bin/ | grep -E "claude|codex|gemini|aider"
```

**Fix**: Add the binary's directory to your PATH, then re-run setup:

```bash
export PATH="$HOME/.local/bin:$PATH"
python -m src.rolemesh setup --save
```

### Version shows `None`

**Cause**: The tool's `--version` command returned empty output or timed out (5s limit).

**Impact**: None. Discovery and routing work normally without version info.

**Fix**: This is cosmetic. If it bothers you, verify the tool responds to its version command:

```bash
claude --version
codex --version
```

### Discovery finds 0 tools

**Cause**: No recognized AI CLI tools are installed, or none are on PATH.

```bash
# Quick check
python -m src.rolemesh status
```

**Fix**: Install at least one supported tool:

| Tool | Install |
|------|---------|
| Claude Code | `npm install -g @anthropic-ai/claude-code` |
| Codex CLI | `npm install -g @openai/codex` |
| Aider | `pip install aider-chat` |

---

## Configuration Issues

### "Config not found" warning

**Cause**: No config file exists at `~/.rolemesh/config.json`.

**Fix**: Run setup with `--save`:

```bash
python -m src.rolemesh setup --save
```

### "Dead references" in health check

**Cause**: A routing rule points to a tool key that doesn't exist in the `tools` section of `config.json`. This typically happens after manually editing the config.

**Fix**: Regenerate the config:

```bash
python -m src.rolemesh setup --save
```

Or manually fix the reference in `~/.rolemesh/config.json`.

### Config validation errors

Run validation programmatically for detailed diagnostics:

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
config = wizard.load_config()
if config:
    errors = wizard.validate_config(config)
    for e in errors:
        print(f"  WARN: {e}")
else:
    print("No config file found")
```

---

## Routing Issues

### Task routes to wrong tool

**Cause**: The task description doesn't match the expected pattern, or routing rules don't reflect your preferences.

**Diagnose**: Check what the classifier sees:

```bash
python -m src.rolemesh route "your task description" --all
```

This shows all matched task types with confidence scores.

**Fix options**:

1. **Rephrase the task** to include keywords that match the desired task type (see `TASK_PATTERNS` in `router.py`)
2. **Override manually** with `--tool`:
   ```bash
   python -m src.rolemesh exec "your task" --tool claude
   ```
3. **Edit routing rules** in `~/.rolemesh/config.json`:
   ```json
   "routing": {
     "coding": { "primary": "claude", "fallback": "aider" }
   }
   ```

### "no pattern match, defaulting" message

**Cause**: The task description didn't match any of the 13 task type patterns.

**Impact**: RoleMesh defaults to `claude` with task type `coding`.

**Fix**: Use more descriptive task text. The router matches Korean and English keywords. See `BUILDER_CONFIG.md` for the full task type vocabulary.

### Confidence score is low

Confidence is calculated as `matched_patterns / total_patterns` for each task type. Each task type has 2 pattern groups.

| Confidence | Meaning |
|-----------|---------|
| 1.0 | Both pattern groups matched |
| 0.5 | One pattern group matched |
| 0.0 | No match (default routing) |

---

## Execution Issues

### Tool execution times out

**Cause**: The default execution timeout is 300 seconds (5 minutes).

**Impact**: The task fails and fallback is attempted if configured.

**Fix**: For long-running tasks, consider breaking them into smaller subtasks.

### Fallback not triggering

**Cause**: Fallback only triggers when the primary tool returns a non-zero exit code.

**Check**: Verify fallback is configured:

```bash
python -m src.rolemesh dashboard --routing
```

If fallback shows `--`, no fallback tool is assigned for that task type. Re-run `setup --save` with more tools installed.

### "Unknown tool" error

**Cause**: The tool key passed via `--tool` doesn't exist in `TOOL_COMMANDS`.

**Fix**: Use one of the recognized tool keys: `claude`, `codex`, `gemini`, `aider`, `copilot`, `cursor`.

For custom tools, register them first (see `BUILDER_EXTENDING.md`).

---

## Dashboard Issues

### Colors not showing

**Cause**: The `NO_COLOR` environment variable is set, or output is not a TTY.

**Fix**: Unset `NO_COLOR` or pipe through `less -R`:

```bash
unset NO_COLOR
python -m src.rolemesh dashboard | less -R
```

### History section is empty

**Cause**: No tasks have been executed yet, or `~/.rolemesh/history.jsonl` doesn't exist.

**Fix**: Execute a task (even a dry-run) to create the first history entry:

```bash
python -m src.rolemesh exec "test task" --dry-run
```

---

## Environment Issues

### Import errors

```
ModuleNotFoundError: No module named 'src.rolemesh'
```

**Fix**: Run from the project root directory:

```bash
cd /path/to/emergent
python -m src.rolemesh status
```

### Permission denied on config directory

**Cause**: `~/.rolemesh/` directory has restrictive permissions.

**Fix**:

```bash
chmod 755 ~/.rolemesh
chmod 644 ~/.rolemesh/config.json
```

---

## Related Docs

- [BUILDER_GUIDE.md](BUILDER_GUIDE.md) — Setup walkthrough
- [BUILDER_CONFIG.md](BUILDER_CONFIG.md) — Configuration schema
- [DASHBOARD_CLI.md](DASHBOARD_CLI.md) — Dashboard usage
- [FAQ.md](FAQ.md) — Frequently asked questions
