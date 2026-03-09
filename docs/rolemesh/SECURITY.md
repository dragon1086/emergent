# RoleMesh Security Guide

> Trust model, safe routing, and operational security considerations

## Threat Model

RoleMesh routes user requests to AI CLI tools via subprocess. The primary attack surface is:

| Threat | Vector | Mitigation |
|--------|--------|------------|
| Prompt injection | Malicious input forwarded to tool | Tool-level sandboxing (out of scope) |
| Command injection | Crafted prompt escapes subprocess args | Argument-based dispatch, no shell=True |
| Config tampering | Modified `config.json` redirects routing | File permissions, validation on load |
| PATH hijacking | Fake binary shadows real tool | `shutil.which()` follows PATH order |
| Credential exposure | API keys in environment variables | Tools manage own credentials |

## Subprocess Safety

### No Shell Execution

RoleMesh dispatches tools via `subprocess.run()` with `shell=False` (the default). User prompts are passed as list arguments, never interpolated into shell strings:

```python
# Safe: list-based invocation
subprocess.run(["claude", "-p", user_prompt], ...)

# Never done: shell string interpolation
subprocess.run(f"claude -p '{user_prompt}'", shell=True)  # DANGEROUS
```

This prevents shell metacharacter injection (`; rm -rf /`, `$(cmd)`, etc.).

### Stdin Mode

For tools using stdin mode (codex, gemini, cursor), the prompt is piped via `stdin` using `input=` parameter — no shell redirection:

```python
subprocess.run(["codex"], input=user_prompt.encode(), ...)
```

## Config Security

### File Permissions

The config file at `~/.rolemesh/config.json` should be user-readable only:

```bash
chmod 600 ~/.rolemesh/config.json
```

The builder does not set permissions automatically. If you share a machine, restrict access manually.

### Validation on Load

The router validates config structure on initialization. Invalid configs fall back to defaults (route everything to Claude):

```python
router = RoleMeshRouter()
# If config is missing or invalid:
#   - Logs a warning
#   - Routes all tasks to "claude" (default fallback)
```

Use `SetupWizard.validate_config()` to check config integrity:

```python
import json
from pathlib import Path
from src.rolemesh.builder import SetupWizard

config = json.loads(Path("~/.rolemesh/config.json").expanduser().read_text())
errors = SetupWizard.validate_config(config)
if errors:
    print("Config integrity issues:")
    for e in errors:
        print(f"  - {e}")
```

### Dead Reference Detection

The dashboard health check (`no_dead_refs`) catches routing rules that point to tools not in the config. This prevents routing to a removed or renamed tool:

```bash
python -m src.rolemesh.dashboard --health
# [!!] no_dead_refs: routing['coding'].primary 'removed_tool' not found in tools
```

## Tool Binary Verification

### PATH Resolution

`SetupWizard.discover()` uses `shutil.which()` to locate tool binaries. This follows the system PATH order, which means:

- A user-installed binary in `~/.local/bin` may shadow a system binary
- Virtual environments can override tool locations
- Symlinks are followed transparently

### Version Probing

The builder executes `check_cmd` (e.g., `claude --version`) to extract the tool version. This runs the binary with a safe, read-only flag. If you register a custom tool, ensure `check_cmd` is side-effect-free.

```python
# Good: read-only version check
check_cmd=["mytool", "--version"]

# Bad: command with side effects
check_cmd=["mytool", "init"]  # may create files
```

## Operational Recommendations

### 1. Pin Tool Versions

Track which tool versions your config was generated with:

```bash
python -m src.rolemesh.dashboard --tools --json > tool-snapshot.json
```

Compare snapshots after system updates to detect unexpected version changes.

### 2. Audit Routing Decisions

Use dry-run mode to audit where requests are routed before execution:

```bash
python -m src.rolemesh.executor --dry-run "delete all user data"
# [dry-run] Would execute: claude -p "delete all user data"
```

### 3. Restrict Custom Tool Registration

Custom tools registered via `register_tool()` are runtime-only and not persisted to source. However, `save_config()` writes them to disk. Review `config.json` after adding custom tools to ensure no unintended entries.

### 4. Network Considerations

RoleMesh itself makes no network calls. All network activity comes from the dispatched AI CLI tools (API calls to OpenAI, Anthropic, Google, etc.). Each tool manages its own:

- API authentication (keys, tokens)
- TLS/SSL connections
- Rate limiting and retry logic

### 5. Logging

RoleMesh does not log prompts or tool outputs to disk by default. If you need audit logging, capture executor results externally:

```python
import json
from datetime import datetime

result = executor.run("some request")
audit = {
    "timestamp": datetime.now().isoformat(),
    "tool": result.tool,
    "task_type": result.task_type,
    "exit_code": result.exit_code,
    "duration_ms": result.duration_ms,
    # Omit stdout/stderr to avoid logging sensitive content
}
with open("audit.jsonl", "a") as f:
    f.write(json.dumps(audit) + "\n")
```

## Summary

| Aspect | Status |
|--------|--------|
| Shell injection | Protected (shell=False) |
| Config validation | Built-in (validate_config) |
| Credential management | Delegated to tools |
| Audit logging | Opt-in (not built-in) |
| Binary verification | PATH-based (shutil.which) |
| Network security | Tool-managed |
