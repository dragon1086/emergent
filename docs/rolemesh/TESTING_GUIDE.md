# RoleMesh Testing Guide

> How to run, write, and organize tests for the RoleMesh routing engine

## Running Tests

```bash
cd /path/to/emergent
python tests/test_rolemesh.py
```

Expected output:

```
Running 51 tests...

  PASS: tool_registry_complete
  PASS: discover_returns_profiles
  ...
  PASS: executor_dry_run_no_history

========================================
Results: 51 passed, 0 failed, 51 total
```

Exit code: `0` on success, `1` on any failure.

## Test Organization

All tests live in a single file (`tests/test_rolemesh.py`) organized by component:

| Section | Tests | What It Covers |
|---------|-------|----------------|
| Builder Tests | 7 | Registry completeness, discovery, ranking, config generation, save/load |
| Router Tests | 9 | Task classification (Korean/English), routing with/without config, multi-route |
| Dashboard Tests | 10 | Data collection, health checks, rendering (tools/routing/coverage/health) |
| Executor Tests | 10 | Dry-run, unknown tools, command building, file context, result serialization |
| Custom Tool Registration | 5 | register_tool, unregister_tool, validation, replacement |
| Config Validation | 5 | Valid config, missing fields, dead references, non-dict input |
| Execution History | 4 | JSONL logging, limit, missing file, dry-run skips logging |

**Total: 51 tests**

## Test Infrastructure

### No External Dependencies

Tests use only the Python standard library:

- `assert` for assertions
- `print("  PASS: test_name")` for output
- `tempfile.TemporaryDirectory()` for isolated file operations
- `pathlib.Path("/nonexistent")` for "no config" scenarios

No pytest, unittest, or other test frameworks required.

### Test Runner

The `run_all()` function at the bottom of the test file:

1. Iterates through all registered test functions
2. Catches exceptions per test (one failure doesn't block others)
3. Reports pass/fail count and error details
4. Returns `True` if all passed

```python
def run_all():
    tests = [
        test_tool_registry_complete,
        test_discover_returns_profiles,
        # ... all test functions
    ]
    # ...
    return failed == 0
```

### Registering New Tests

After writing a test function, add it to the `tests` list in `run_all()`:

```python
tests = [
    # ... existing tests ...
    # New test
    test_my_new_feature,
]
```

## Writing Tests

### Builder Tests

Test tool discovery and config generation using mock `ToolProfile` objects:

```python
def test_my_builder_feature():
    wizard = SetupWizard()
    wizard.tools = [
        ToolProfile(key="claude", name="Claude", vendor="Anthropic",
                    strengths=["coding"], cost_tier="high", available=True),
    ]
    # Test your feature
    result = wizard.some_method()
    assert result == expected_value
    print("  PASS: my_builder_feature")
```

### Router Tests

Test classification and routing with temporary config files:

```python
def test_my_routing_scenario():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config = {
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude Code", "key": "claude"}},
            "routing": {
                "coding": {"primary": "claude", "fallback": None},
            },
        }
        config_path.write_text(json.dumps(config))

        router = RoleMeshRouter(config_path=config_path)
        result = router.route("test request")
        assert result.tool == "claude"
    print("  PASS: my_routing_scenario")
```

### Dashboard Tests

Use the `_make_dashboard_with_tools()` helper to create dashboards with mock tools and config:

```python
def test_my_dashboard_feature():
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        output = dashboard.render_something()
        assert "expected text" in output
    print("  PASS: my_dashboard_feature")
```

### Executor Tests

Use `dry_run=True` to test routing and command building without executing real subprocesses:

```python
def test_my_executor_feature():
    executor = RoleMeshExecutor(config_path=Path("/nonexistent"), dry_run=True)
    result = executor.run("test request")
    assert result.success
    assert "[dry-run]" in result.stdout
    print("  PASS: my_executor_feature")
```

### Registry Mutation Tests

When testing `register_tool` / `unregister_tool`, always clean up `TOOL_REGISTRY`:

```python
def test_my_registration():
    wizard = SetupWizard()
    wizard.tools = []
    wizard.register_tool(key="temp", name="Temp", vendor="V",
                         strengths=["x"], check_cmd=["no_bin"],
                         cost_tier="low")
    # ... assertions ...
    # Cleanup: remove from global registry
    del TOOL_REGISTRY["temp"]
    print("  PASS: my_registration")
```

## Common Patterns

### Testing Without Config

```python
router = RoleMeshRouter(config_path=Path("/nonexistent"))
```

This creates a router that returns `"claude"` for all requests (default behavior).

### Testing Classification Confidence

```python
types = router.classify_task("리팩토링 해줘")
# types = [("refactoring", 1.0), ("coding", 0.5), ...]
assert types[0][0] == "refactoring"
assert types[0][1] >= 0.5
```

### Testing Health Checks

```python
checks = {c.name: c for c in dashboard.data.health_checks}
assert checks["config_file"].passed is True
assert checks["tools_available"].passed is True
```

### Testing Error Cases

```python
# Invalid input
try:
    wizard.register_tool(key="bad", ..., cost_tier="ultra")
    assert False, "Should have raised ValueError"
except ValueError:
    pass
```

## Troubleshooting

### Import Errors

The test file adds the project root to `sys.path`:

```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```

Run tests from the project root:

```bash
cd /path/to/emergent
python tests/test_rolemesh.py
```

### Flaky Tests

All tests are deterministic — no network calls, no random data, no timing dependencies. If a test fails, it indicates a real code issue.

### Registry State Leaks

If a test fails mid-execution, `TOOL_REGISTRY` may retain test entries. Re-run to get a clean state, or restart the Python process.
