# Contributing to RoleMesh

> Guidelines for contributing code, docs, and tests

## Getting Started

### Prerequisites

- Python 3.10+
- At least one supported AI CLI tool installed (for integration testing)
- Git

### Setup

```bash
git clone https://github.com/dragon1086/emergent.git
cd emergent
pip install -e .

# Verify
python -m src.rolemesh status
```

## Project Structure

```
src/rolemesh/
  __main__.py    # CLI entry point (argparse subcommands)
  builder.py     # Tool discovery & config generation
  router.py      # Task classification & tool routing
  executor.py    # Subprocess dispatch & fallback
  dashboard.py   # Status visualization & health checks

docs/rolemesh/   # Documentation
tests/           # Test suite
```

## Development Workflow

### 1. Create a feature branch

```bash
git checkout main
git pull origin main
git checkout -b feat/your-feature-name
```

### 2. Make changes

Follow these conventions:

- **Code style**: Match the existing patterns. No external linters are enforced, but keep consistent formatting.
- **Type hints**: Use built-in generics (`dict[str, str]`, `list[int]`) — no `typing.Dict` / `typing.List`.
- **Dataclasses**: Use `@dataclass` for structured data. Include `to_dict()` for serialization.
- **Docstrings**: Module-level docstrings with usage examples. Class/method docstrings where intent isn't obvious.
- **Imports**: Standard library only. No external dependencies.

### 3. Test your changes

```bash
python tests/test_rolemesh.py
```

All tests must pass before submitting a PR. Use isolated config paths in tests:

```python
import tempfile
from pathlib import Path
from src.rolemesh.builder import SetupWizard

with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / "config.json"
    wizard = SetupWizard(config_path=config_path)
    wizard.discover()
    # Test with isolated config
```

### 4. Commit and push

```bash
git add <specific files>
git commit -m "feat: description of change"
git push origin feat/your-feature-name
```

### 5. Open a PR

Target the `main` branch. Include:
- Summary of changes
- Test plan or evidence that tests pass

## Commit Convention

```
feat: new feature or capability
fix: bug fix
docs: documentation changes
refactor: code restructuring (no behavior change)
test: test additions or modifications
chore: build/config/tooling changes
```

Keep commit messages concise (under 72 chars for the subject line). Use the body for details when needed.

## What to Contribute

### Adding a new built-in tool

1. Add an entry to `TOOL_REGISTRY` in `builder.py`:
   ```python
   "new-tool": {
       "name": "New Tool",
       "vendor": "Vendor",
       "strengths": ["coding", "analysis"],
       "check_cmd": ["new-tool", "--version"],
       "cost_tier": "medium",
   },
   ```

2. Add a command entry to `TOOL_COMMANDS` in `executor.py`:
   ```python
   "new-tool": {"cmd": "new-tool", "stdin_mode": False},
   ```

3. Add tests for the new tool in the test suite.

4. Update documentation: README.md (tool table), BUILDER_GUIDE.md, CUSTOM_TOOLS.md.

### Adding a new task type

1. Add a pattern tuple to `TASK_PATTERNS` in `router.py`:
   ```python
   ("new-type", [
       r"korean_pattern|english_pattern",
       r"more_korean|more_english",
   ]),
   ```

2. Include both Korean and English regex patterns (bilingual support is mandatory).

3. Add corresponding strengths to relevant tools in `TOOL_REGISTRY`.

4. Update CONFIG_REFERENCE.md with the new task type and its patterns.

### Adding a new health check

1. Add the check logic in `dashboard.py` within the `collect()` method:
   ```python
   self.data.health_checks.append(HealthCheck(
       name="my_check",
       passed=condition,
       detail="Description of result",
   ))
   ```

2. Update the health check count in ARCHITECTURE.md and MONITORING_GUIDE.md.

### Improving documentation

- Fix typos, clarify explanations, add examples
- Keep code examples runnable and accurate
- Update cross-references when adding new docs
- Add the new doc to README.md's "Further Reading" section

## Testing Guidelines

### Test structure

- One test file per module (or a combined `test_rolemesh.py`)
- Use `unittest.TestCase` or plain `assert` statements
- Name tests descriptively: `test_classify_task_returns_refactoring_for_korean_input`

### What to test

- **Builder**: Discovery with mocked `shutil.which`, config generation, validation
- **Router**: Classification accuracy for all 13 task types, both Korean and English
- **Executor**: Command building, dry-run mode, error handling (timeout, OS error, not found)
- **Dashboard**: Health check logic, data collection, render output format

### Test isolation

- Never depend on the user's real `~/.rolemesh/config.json`
- Use `tempfile.TemporaryDirectory()` for config/history paths
- Mock `subprocess.run` and `shutil.which` for deterministic results

## Code Review Checklist

- [ ] Tests pass (`python tests/test_rolemesh.py`)
- [ ] No external dependencies added (stdlib only)
- [ ] Type hints on all public functions
- [ ] Bilingual support maintained (Korean + English) for any new patterns
- [ ] Config changes are backward-compatible or documented as breaking
- [ ] Documentation updated for user-facing changes
- [ ] `validate_config()` catches any new config structure requirements

## Architecture Principles

1. **Subprocess isolation**: Tools run as external processes, never imported as libraries
2. **Regex over LLM**: Task classification uses fast regex, not LLM calls
3. **Config-driven**: Routing rules in JSON, not hardcoded
4. **Bilingual-first**: All patterns support Korean and English natively
5. **Zero dependencies**: Standard library only — no pip packages required
6. **Append-only history**: JSONL format for safe concurrent writes

## See Also

- [Architecture](ARCHITECTURE.md) - System design and module responsibilities
- [API Reference](API_REFERENCE.md) - Full Python API
- [Best Practices](BEST_PRACTICES.md) - Patterns and anti-patterns
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and fixes
