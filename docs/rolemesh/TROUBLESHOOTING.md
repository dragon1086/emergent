# RoleMesh Troubleshooting

> Common issues, error messages, and how to fix them

## Quick Diagnostics

Run the dashboard to see your system status at a glance:

```bash
python -m src.rolemesh dashboard
```

This shows installed tools, routing rules, coverage matrix, and health checks. Any `[!!]` markers indicate issues.

## Common Issues

### "No AI tools found"

**Symptom:** `wizard.summary()` returns `"No AI tools found"`.

**Cause:** None of the known CLI binaries are on PATH.

**Fix:**
1. Verify at least one AI CLI is installed:
   ```bash
   which claude codex gemini aider
   ```
2. If installed but not found, check your PATH:
   ```bash
   echo $PATH
   ```
3. Some tools install to non-standard locations. Add to PATH or use a symlink.

### Config file not found

**Symptom:** Router always defaults to Claude regardless of routing rules.

**Cause:** `~/.rolemesh/config.json` doesn't exist.

**Fix:**
```bash
python -m src.rolemesh.builder --save
```

### Dead routing references

**Symptom:** Dashboard health check `no_dead_refs` shows `[!!]`.

**Cause:** A routing rule references a tool key that doesn't exist in the `tools` section.

**Fix:**
```python
from src.rolemesh.builder import SetupWizard
import json
from pathlib import Path

config = json.loads(Path("~/.rolemesh/config.json").expanduser().read_text())
errors = SetupWizard.validate_config(config)
for e in errors:
    print(e)
# Fix: regenerate config
wizard = SetupWizard()
wizard.discover()
wizard.save_config()
```

### Low routing coverage

**Symptom:** Dashboard health check `routing_coverage` shows `[!!]` with missing task types.

**Cause:** The config doesn't have routing rules for all 13 task types. This is normal if you only have 1-2 tools installed — they may not cover every task type.

**Fix:** Either install more tools or manually add routing rules:
```json
{
  "routing": {
    "multimodal": { "primary": "claude", "fallback": null }
  }
}
```

### Wrong tool selected for a task

**Symptom:** A request routes to an unexpected tool.

**Diagnosis:**
```python
router = RoleMeshRouter()

# Check classification
types = router.classify_task("your request here")
print(types)  # shows all matched task types + confidence

# Check routing for each type
results = router.route_multi("your request here")
for r in results:
    print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool}")
```

**Possible causes:**
- The request matches a different task type than expected
- The routing config maps that task type to a different tool
- User preference is overriding cost-based ranking

**Fix:** Adjust routing rules in config or set `user_preference`:
```python
wizard = SetupWizard()
wizard.discover()
for tool in wizard.available_tools():
    if tool.key == "claude":
        tool.user_preference = 1  # prefer for tied scores
wizard.save_config()
```

### register_tool raises ValueError

**Symptom:** `ValueError: cost_tier must be low/medium/high`

**Fix:** Use one of the three valid values:
```python
wizard.register_tool(..., cost_tier="medium")  # not "free", "ultra", etc.
```

**Symptom:** `ValueError: key and name are required`

**Fix:** Both `key` and `name` must be non-empty strings.

### Executor returns exit code 127

**Symptom:** `ExecutionResult.exit_code == 127` with `"Unknown tool"` in stderr.

**Cause:** The tool key doesn't have a command mapping in `TOOL_COMMANDS`.

**Fix:** Add the command mapping:
```python
from src.rolemesh.executor import TOOL_COMMANDS
TOOL_COMMANDS["mytool"] = {
    "cmd": ["mytool"],
    "stdin_mode": False,
}
```

### Executor returns exit code -1

**Symptom:** `ExecutionResult.exit_code == -1`

**Cause:** The subprocess timed out (default: 120 seconds).

**Fix:** Increase the timeout:
```python
executor = RoleMeshExecutor(timeout=300)  # 5 minutes
```

### Version detection fails

**Symptom:** `ToolProfile.version` is `None` even though the tool is installed.

**Cause:** The `--version` output doesn't match the expected format (first word with a digit).

**Impact:** None — version is informational only and doesn't affect routing.

## Resetting Configuration

### Full reset

Delete the config and regenerate:

```bash
rm ~/.rolemesh/config.json
python -m src.rolemesh.builder --save
```

### Reset to defaults (no preferences)

```python
wizard = SetupWizard()
wizard.discover()
# All user_preference = 0 (neutral)
wizard.save_config()
```

## Test Suite

Run the full test suite to verify your installation:

```bash
cd /path/to/emergent
python tests/test_rolemesh.py
```

Expected output:
```
Running 44 tests...
  PASS: tool_registry_complete
  PASS: discover_returns_profiles
  ...
Results: 44 passed, 0 failed, 44 total
```

If any tests fail, check the error message for details on which component is broken.

## Getting Help

- **Architecture overview:** `docs/rolemesh/ARCHITECTURE.md`
- **API reference:** `docs/rolemesh/API_REFERENCE.md`
- **Builder guide:** `docs/rolemesh/BUILDER_GUIDE.md`
- **Custom tools:** `docs/rolemesh/CUSTOM_TOOLS.md`
- **Config schema:** `docs/rolemesh/CONFIG_SCHEMA.md`
