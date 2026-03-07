# RoleMesh Troubleshooting

> Common issues, diagnostics, and solutions

## Quick Diagnostics

Run these commands first to understand your system state:

```bash
# Overall health check
python -m src.rolemesh status

# Detailed health with specific checks
python -m src.rolemesh dashboard --health

# Full system view
python -m src.rolemesh dashboard
```

## Tool Discovery Issues

### Tool not detected despite being installed

**Symptom**: `python -m src.rolemesh setup` doesn't list a tool you know is installed.

**Diagnosis**:

```bash
# Check if the binary is on PATH
which claude
which codex
which gemini

# Verify the tool responds to version check
claude --version
codex --version
gemini --version
```

**Solutions**:

1. **Binary not on PATH**: Add the tool's install directory to your `PATH` in `~/.zshrc` or `~/.bashrc`:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   source ~/.zshrc
   ```

2. **Version check times out**: The builder runs each `--version` check with a 5-second timeout. If your tool is slow to start, it may time out. Check manually:
   ```bash
   time claude --version
   ```

3. **Tool installed via package manager**: Some tools install with different binary names. Verify the exact binary name matches what's in `TOOL_REGISTRY`.

### No tools found at all

**Symptom**: `Found 0 AI tool(s)` or "No AI tools found."

**Solutions**:

1. Install at least one supported tool (claude, codex, gemini, aider, copilot, cursor)
2. Ensure your shell profile is loaded (the builder inherits the current shell's `PATH`)
3. If running from a different user or cron, set `PATH` explicitly

### Custom tool not persisting

**Symptom**: `register_tool()` works in one session but the tool disappears on restart.

**Cause**: `register_tool()` modifies the in-memory `TOOL_REGISTRY`. The registry resets on each import.

**Solution**: Always call `save_config()` after registering, and create a setup script for repeatable registration:

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()
wizard.register_tool(
    key="my-tool", name="My Tool", vendor="Me",
    strengths=["coding"], check_cmd=["my-tool", "--version"],
    cost_tier="low",
)
wizard.save_config()
```

## Configuration Issues

### "Missing 'version' field" or "Missing 'tools' field"

**Cause**: Corrupted or manually created config file.

**Solution**: Regenerate from scratch:

```bash
python -m src.rolemesh setup --save
```

### "routing references unknown tool"

**Cause**: A routing rule points to a tool key that doesn't exist in the `tools` section. This happens when you manually edit `config.json` and remove a tool but leave its routing references.

**Solution**:

```python
from src.rolemesh.builder import SetupWizard
import json

config = json.load(open("~/.rolemesh/config.json".replace("~", __import__("os").path.expanduser("~"))))
errors = SetupWizard.validate_config(config)
for e in errors:
    print(f"  ERROR: {e}")
```

Then either re-run `setup --save` or fix the dead references manually.

### Config file not found

**Symptom**: Router defaults everything to Claude.

**Cause**: No config file at `~/.rolemesh/config.json`.

**Solution**:

```bash
python -m src.rolemesh setup --save
# Verify
ls -la ~/.rolemesh/config.json
```

### Config path override not working

Check the priority order (highest wins):
1. Constructor argument: `SetupWizard(config_path=Path(...))`
2. CLI flag: `--config /path/to/config.json`
3. Environment variable: `ROLEMESH_CONFIG=/path/to/config.json`
4. Default: `~/.rolemesh/config.json`

## Routing Issues

### Everything routes to Claude

**Possible causes**:

1. **No config file**: Run `setup --save` to generate one
2. **Only Claude installed**: If Claude is the only available tool, all routes point to it
3. **User preferences**: Check if preferences are skewing routing:
   ```python
   config = json.load(open("~/.rolemesh/config.json"))
   for key, tool in config["tools"].items():
       print(f"{key}: preference={tool.get('user_preference', 0)}")
   ```

### Wrong tool selected for task type

**Diagnosis**:

```bash
# See all matches, not just the top one
python -m src.rolemesh route --all "your task description"
```

**Solutions**:

1. **Be more specific**: Include keywords that match the intended task type patterns
2. **Override routing**: Edit `config.json` to force a specific tool for a task type:
   ```json
   {
     "routing": {
       "refactoring": { "primary": "codex", "fallback": "claude" }
     }
   }
   ```
3. **Force a tool**: Use `--tool` to bypass routing entirely:
   ```bash
   python -m src.rolemesh exec --tool codex "your task"
   ```

### Low confidence classification

**Symptom**: `route()` returns confidence < 0.5.

**Cause**: The request text doesn't match enough regex patterns for any task type.

**Solutions**:

1. Use task-specific keywords (see [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) for the full pattern list)
2. Write in Korean or English (both are supported natively)
3. For ambiguous requests, use `route_multi()` to see all candidate matches

## Execution Issues

### Tool fails with exit code 127

**Meaning**: Tool binary not found on PATH at execution time.

**Cause**: Tool was detected during `setup` but is no longer available (uninstalled, PATH changed, different shell session).

**Solution**:

```bash
# Re-check availability
python -m src.rolemesh setup

# If the tool is truly gone, re-save config
python -m src.rolemesh setup --save
```

### Tool fails with exit code 126

**Meaning**: OS-level error (permission denied, etc.).

**Solutions**:

```bash
# Check permissions
ls -la $(which claude)

# Try running directly
claude --version
```

### Timeout (exit code -1)

**Meaning**: Tool didn't respond within the timeout window (default: 120s).

**Solutions**:

1. Increase timeout:
   ```bash
   python -m src.rolemesh exec --timeout 300 "complex task"
   ```
   ```python
   executor = RoleMeshExecutor(timeout=300)
   ```

2. Check if the tool is hanging:
   ```bash
   # Test with a simple prompt
   python -m src.rolemesh exec --timeout 10 "hello"
   ```

### Fallback not triggering

**Cause**: No fallback tool configured for the task type, or the fallback tool is also unavailable.

**Diagnosis**:

```bash
python -m src.rolemesh dashboard --routing
```

Check that routing rules include `fallback` entries. If not, re-run setup with more tools installed.

## Dashboard Issues

### No colors in terminal

**Cause**: `NO_COLOR` environment variable is set, or output is not a TTY.

**Solution**:

```bash
# Force colors (if your terminal supports them)
unset NO_COLOR
python -m src.rolemesh dashboard
```

### History shows no entries

**Cause**: No executions logged yet, or history file doesn't exist.

**Check**:

```bash
ls -la ~/.rolemesh/history.jsonl
cat ~/.rolemesh/history.jsonl | wc -l
```

History is only written by `executor.run()` (not `dispatch()` in dry-run mode).

### Dashboard health check fails

| Check | Fix |
|-------|-----|
| `config_file` | Run `setup --save` |
| `tools_available` | Install at least one AI CLI tool |
| `routing_coverage` | Re-run `setup --save` with more tools |
| `config_version` | Regenerate config (version should be "1.0.0") |
| `no_dead_refs` | Fix or regenerate config to remove dead routing references |

## Environment-Specific Issues

### Running in Docker

AI CLI tools need API keys and network access. Mount credentials:

```bash
docker run -v ~/.config:/root/.config \
           -v ~/.rolemesh:/root/.rolemesh \
           -e OPENAI_API_KEY \
           -e ANTHROPIC_API_KEY \
           rolemesh exec "task"
```

### Running in CI/CD

- Set `NO_COLOR=1` for clean log output
- Use `--json` for parseable results
- Run `setup --save` before any routing/execution steps
- Ensure AI CLI tools are installed in the CI image

### Different Python version

RoleMesh requires Python 3.10+ (uses `dict[str, dict]` type hints and `dataclasses`).

```bash
python --version  # Must be 3.10+
```

## Getting Help

1. Run `python -m src.rolemesh dashboard` for a full system overview
2. Check [Best Practices](BEST_PRACTICES.md) for recommended patterns
3. Review [Architecture](ARCHITECTURE.md) for understanding the pipeline
4. Validate config: `SetupWizard.validate_config(config)`

## See Also

- [Builder Guide](BUILDER_GUIDE.md) - Discovery and setup walkthrough
- [Config Reference](CONFIG_REFERENCE.md) - Schema and validation details
- [Monitoring Guide](MONITORING_GUIDE.md) - Metrics and alerting
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Docker and CI/CD setup
