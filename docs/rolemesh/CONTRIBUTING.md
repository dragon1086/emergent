# Contributing to RoleMesh

> How to extend, customize, and contribute to the RoleMesh routing engine

## Development Setup

```bash
# Clone and navigate
cd /path/to/emergent

# Verify Python 3.10+
python3 --version

# Run the test suite
python tests/test_rolemesh.py
```

No virtual environment or extra dependencies are required — RoleMesh uses only the Python standard library.

## Project Structure

```
src/rolemesh/
  __init__.py       # Public exports
  __main__.py       # Unified CLI entry point
  builder.py        # Tool discovery + config generation
  router.py         # Task classification + routing
  dashboard.py      # System status + health checks
  executor.py       # Subprocess dispatch + fallback

tests/
  test_rolemesh.py  # All tests (51 cases)

docs/rolemesh/
  *.md              # Documentation
```

## Adding a New AI Tool

1. Add the tool to `TOOL_REGISTRY` in `builder.py`:

```python
TOOL_REGISTRY["newtool"] = {
    "name": "New Tool",
    "vendor": "Vendor Name",
    "strengths": ["coding", "analysis"],
    "check_cmd": ["newtool", "--version"],
    "cost_tier": "medium",  # low, medium, or high
}
```

2. Add its CLI command to `TOOL_COMMANDS` in `executor.py`:

```python
TOOL_COMMANDS["newtool"] = {
    "cmd": ["newtool"],
    "stdin_mode": False,  # True if tool reads prompt from stdin
}
```

3. Add tests in `tests/test_rolemesh.py` and verify:

```bash
python tests/test_rolemesh.py
```

Alternatively, use `SetupWizard.register_tool()` for runtime registration without editing source. See [BUILDER_GUIDE.md](BUILDER_GUIDE.md#option-b-register-at-runtime-dynamic).

## Adding a New Task Type

1. Add a pattern tuple to `TASK_PATTERNS` in `router.py`:

```python
TASK_PATTERNS.append(
    ("new-category", [
        r"keyword1|keyword2|한국어키워드",
        r"keyword3|keyword4|추가패턴",
    ]),
)
```

2. Add a test:

```python
def test_classify_new_category():
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("keyword1 keyword3")
    task_names = [t for t, _ in types]
    assert "new-category" in task_names
    print("  PASS: classify_new_category")
```

3. Register the test in `run_all()` and run the suite.

## Code Style

- **No external dependencies**: stdlib only (json, pathlib, subprocess, dataclasses, re, shutil, tempfile)
- **Bilingual patterns**: All regex patterns must include both Korean and English keywords
- **Dataclass-based models**: Use `@dataclass` for all data structures; include `to_dict()` for serialization
- **Explicit defaults**: No implicit state. Config paths default to `~/.rolemesh/config.json`
- **Graceful degradation**: Every component must handle missing config, missing tools, and empty inputs without crashing

## Testing Guidelines

- All tests are in a single file: `tests/test_rolemesh.py`
- Tests use `assert` + manual `print("  PASS: ...")` (no pytest dependency)
- Use `tempfile.TemporaryDirectory()` for config files — never write to real `~/.rolemesh/`
- Use `Path("/nonexistent")` for config paths when testing without config
- Clean up `TOOL_REGISTRY` mutations in tests (e.g., `del TOOL_REGISTRY["temp"]`)
- See [TESTING_GUIDE.md](TESTING_GUIDE.md) for the full testing guide

## Commit Convention

```
feat(rolemesh): new feature description
fix(rolemesh): bug fix description
docs(rolemesh): documentation update
test(rolemesh): new or updated tests
refactor(rolemesh): code restructuring
```

## Pull Request Checklist

- [ ] All tests pass (`python tests/test_rolemesh.py`)
- [ ] New features include tests
- [ ] Bilingual support (Korean + English) for any new patterns
- [ ] No external dependencies added
- [ ] Documentation updated for public API changes
- [ ] Config validation covers new fields (if applicable)

## Architecture Principles

1. **Regex over LLM**: Task classification uses regex, not API calls (~1ms, zero cost)
2. **Config-driven**: Wizard generates once, router reads every time
3. **Cost-aware**: Cheaper tools rank higher among equally-capable options
4. **Subprocess isolation**: Tools run in subprocesses with timeout and fallback
5. **Schema validation**: `validate_config()` catches errors before they reach runtime

## Questions?

See the full documentation index in [README.md](README.md).
