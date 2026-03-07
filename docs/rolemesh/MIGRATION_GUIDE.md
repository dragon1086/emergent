# RoleMesh Migration Guide

> Config versioning, upgrade paths, and breaking changes

## Config Versions

RoleMesh configs include a `version` field for forward compatibility. The current version is `1.0.0`.

```json
{
  "version": "1.0.0",
  "tools": { ... },
  "routing": { ... }
}
```

## Version History

### v1.0.0 (Current)

Initial stable config format.

**Schema:**

```json
{
  "version": "1.0.0",
  "tools": {
    "<key>": {
      "key": "<string>",
      "name": "<string>",
      "vendor": "<string>",
      "strengths": ["<string>", ...],
      "cost_tier": "low|medium|high",
      "available": true|false,
      "version": "<string>|null",
      "user_preference": -1|0|1
    }
  },
  "routing": {
    "<task_type>": {
      "primary": "<tool_key>",
      "fallback": "<tool_key>|null"
    }
  }
}
```

**Required top-level fields:** `version`, `tools`, `routing`

## Upgrading from No Config

If you previously used RoleMesh without a saved config (relying on defaults), generate one:

```bash
python -m src.rolemesh setup --save
```

This creates `~/.rolemesh/config.json` with auto-discovered tools and routing rules.

## Validating After Upgrade

Always validate your config after manual edits or version upgrades:

```python
from src.rolemesh.builder import SetupWizard
import json

with open("~/.rolemesh/config.json") as f:
    config = json.load(f)

errors = SetupWizard.validate_config(config)
if errors:
    for e in errors:
        print(f"  ERROR: {e}")
else:
    print("Config is valid")
```

Or via CLI:

```bash
python -m src.rolemesh dashboard --health
# The "config_version" health check validates the version field
# The "no_dead_refs" check catches broken routing references
```

## Common Migration Scenarios

### Adding a New Tool

When a new AI CLI tool is released:

```bash
# Option 1: Re-run discovery (regenerates routing)
python -m src.rolemesh setup --save

# Option 2: Register at runtime (preserves existing routing)
python -c "
from src.rolemesh.builder import SetupWizard
w = SetupWizard()
w.discover()
w.register_tool(
    key='newtool', name='New Tool', vendor='Vendor',
    strengths=['coding'], check_cmd=['newtool', '--version'],
    cost_tier='medium',
)
w.save_config()
"
```

### Removing a Deprecated Tool

```python
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
wizard.discover()
wizard.unregister_tool("old-tool")
wizard.save_config()
```

After removal, run health checks to ensure no dead routing references:

```bash
python -m src.rolemesh dashboard --health
```

### Changing Tool Preferences

Edit preferences without re-discovering:

```python
import json
from pathlib import Path

config_path = Path.home() / ".rolemesh" / "config.json"
config = json.loads(config_path.read_text())

# Adjust preference
config["tools"]["claude"]["user_preference"] = 1   # prefer
config["tools"]["codex"]["user_preference"] = -1    # avoid

config_path.write_text(json.dumps(config, indent=2))
```

Or re-run interactive setup:

```bash
python -m src.rolemesh setup --interactive --save
```

### Moving Config to a Project Directory

By default, config lives at `~/.rolemesh/config.json` (global). For project-specific configs:

```bash
# Save to project directory
python -m src.rolemesh --config ./rolemesh.json setup --save

# Use project config
python -m src.rolemesh --config ./rolemesh.json route "task"
python -m src.rolemesh --config ./rolemesh.json exec "task"
```

## Graceful Degradation

RoleMesh is designed to work without any config:

| Scenario | Behavior |
|----------|----------|
| No config file | Routes all tasks to `claude` (default) |
| Config exists but tool is missing | Falls back to next available tool |
| Empty `routing` section | Defaults to `claude` for all task types |
| Invalid config format | Falls back to default routing |

This means upgrades are never destructive — a missing or broken config simply reverts to safe defaults.

## Breaking Change Policy

- **Patch versions** (1.0.x): Bug fixes only. No config changes.
- **Minor versions** (1.x.0): New fields may be added. Old configs remain valid.
- **Major versions** (x.0.0): Schema may change. Migration script will be provided.

When a major version introduces breaking changes, a migration function will be added:

```python
# Future API (not yet needed)
from src.rolemesh.builder import SetupWizard

wizard = SetupWizard()
migrated = wizard.migrate_config(old_config, from_version="1.0.0", to_version="2.0.0")
```

## Backup & Restore

Before any migration, back up your config:

```bash
cp ~/.rolemesh/config.json ~/.rolemesh/config.json.bak
```

Restore if something goes wrong:

```bash
cp ~/.rolemesh/config.json.bak ~/.rolemesh/config.json
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Missing 'version' field` | Add `"version": "1.0.0"` to your config |
| `routing['X'].primary 'Y' not found` | Tool was removed but routing still references it. Re-run `setup --save` |
| Config not being read | Check `--config` path or verify `~/.rolemesh/config.json` exists |
| Preferences lost after `setup --save` | `--save` regenerates routing from scratch. Use `--interactive` to re-set preferences |
