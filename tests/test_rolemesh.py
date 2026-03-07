#!/usr/bin/env python3
"""Tests for RoleMesh Builder & Router."""

import json
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rolemesh.builder import SetupWizard, ToolProfile, TOOL_REGISTRY, discover_tools
from src.rolemesh.router import RoleMeshRouter, TASK_PATTERNS
from src.rolemesh.dashboard import RoleMeshDashboard, DashboardData, HealthCheck


# ===== Builder Tests =====

def test_tool_registry_complete():
    """All registry entries have required fields."""
    required = {"name", "vendor", "strengths", "check_cmd", "cost_tier"}
    for key, info in TOOL_REGISTRY.items():
        missing = required - set(info.keys())
        assert not missing, f"Tool '{key}' missing fields: {missing}"
        assert isinstance(info["strengths"], list)
        assert info["cost_tier"] in ("low", "medium", "high")
    print("  PASS: tool_registry_complete")


def test_discover_returns_profiles():
    """discover_tools() returns ToolProfile list for all known tools."""
    profiles = discover_tools()
    assert len(profiles) == len(TOOL_REGISTRY)
    for p in profiles:
        assert isinstance(p, ToolProfile)
        assert p.key in TOOL_REGISTRY
    print("  PASS: discover_returns_profiles")


def test_wizard_rank_tools():
    """SetupWizard ranks tools correctly by task type."""
    wizard = SetupWizard()
    wizard.tools = [
        ToolProfile(key="claude", name="Claude", vendor="Anthropic",
                    strengths=["coding", "analysis"], cost_tier="high", available=True),
        ToolProfile(key="codex", name="Codex", vendor="OpenAI",
                    strengths=["coding", "quick-edit"], cost_tier="medium", available=True),
        ToolProfile(key="gemini", name="Gemini", vendor="Google",
                    strengths=["multimodal", "frontend"], cost_tier="medium", available=True),
    ]

    # For "coding" - codex should rank higher (cheaper, same strength)
    ranked = wizard.rank_tools("coding")
    assert ranked[0].key == "codex", f"Expected codex first for coding, got {ranked[0].key}"

    # For "analysis" - only claude has it
    ranked = wizard.rank_tools("analysis")
    assert ranked[0].key == "claude"

    # For "multimodal" - only gemini has it
    ranked = wizard.rank_tools("multimodal")
    assert ranked[0].key == "gemini"

    print("  PASS: wizard_rank_tools")


def test_wizard_user_preference():
    """User preference overrides cost-based ranking."""
    wizard = SetupWizard()
    wizard.tools = [
        ToolProfile(key="claude", name="Claude", vendor="Anthropic",
                    strengths=["coding"], cost_tier="high", available=True,
                    user_preference=1),
        ToolProfile(key="codex", name="Codex", vendor="OpenAI",
                    strengths=["coding"], cost_tier="low", available=True,
                    user_preference=0),
    ]
    ranked = wizard.rank_tools("coding")
    assert ranked[0].key == "claude", "User preference should override cost"
    print("  PASS: wizard_user_preference")


def test_wizard_build_config():
    """build_config generates valid routing config."""
    wizard = SetupWizard()
    wizard.tools = [
        ToolProfile(key="claude", name="Claude", vendor="Anthropic",
                    strengths=["coding", "analysis"], cost_tier="high", available=True),
        ToolProfile(key="codex", name="Codex", vendor="OpenAI",
                    strengths=["coding"], cost_tier="medium", available=True),
    ]
    config = wizard.build_config()

    assert config["version"] == "1.0.0"
    assert "claude" in config["tools"]
    assert "codex" in config["tools"]
    assert "coding" in config["routing"]
    assert "analysis" in config["routing"]
    assert config["routing"]["coding"]["primary"] in ("claude", "codex")
    assert config["routing"]["coding"]["fallback"] is not None
    print("  PASS: wizard_build_config")


def test_wizard_save_load_config():
    """Config can be saved and loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        wizard = SetupWizard(config_path=config_path)
        wizard.tools = [
            ToolProfile(key="claude", name="Claude", vendor="Anthropic",
                        strengths=["coding"], cost_tier="high", available=True),
        ]
        wizard.save_config()
        assert config_path.exists()

        loaded = wizard.load_config()
        assert loaded["version"] == "1.0.0"
        assert "claude" in loaded["tools"]
    print("  PASS: wizard_save_load_config")


def test_wizard_no_tools():
    """Summary handles no available tools gracefully."""
    wizard = SetupWizard()
    wizard.tools = [
        ToolProfile(key="fake", name="Fake", vendor="Test",
                    strengths=["x"], cost_tier="low", available=False),
    ]
    summary = wizard.summary()
    assert "No AI tools found" in summary
    print("  PASS: wizard_no_tools")


# ===== Router Tests =====

def test_classify_coding():
    """Coding tasks are classified correctly."""
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("이 함수 구현해줘")
    assert types[0][0] == "coding", f"Expected coding, got {types[0][0]}"
    print("  PASS: classify_coding")


def test_classify_refactoring():
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("이 코드 리팩토링 해줘")
    task_names = [t for t, _ in types]
    assert "refactoring" in task_names
    print("  PASS: classify_refactoring")


def test_classify_architecture():
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("마이크로서비스 아키텍처 설계")
    assert types[0][0] == "architecture"
    print("  PASS: classify_architecture")


def test_classify_frontend():
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("UI 컴포넌트 레이아웃 수정")
    task_names = [t for t, _ in types]
    assert "frontend" in task_names
    print("  PASS: classify_frontend")


def test_classify_unknown_defaults_coding():
    """Unknown requests default to coding."""
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    types = router.classify_task("xyzzy foobar baz")
    assert types[0][0] == "coding"
    assert types[0][1] == 0.3  # low confidence
    print("  PASS: classify_unknown_defaults_coding")


def test_route_with_config():
    """Router uses config to pick the right tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config = {
            "version": "1.0.0",
            "tools": {
                "claude": {"name": "Claude Code", "key": "claude"},
                "gemini": {"name": "Gemini CLI", "key": "gemini"},
            },
            "routing": {
                "frontend": {"primary": "gemini", "fallback": "claude"},
                "coding": {"primary": "claude", "fallback": "gemini"},
            },
        }
        config_path.write_text(json.dumps(config))

        router = RoleMeshRouter(config_path=config_path)

        # Frontend -> gemini
        result = router.route("UI 컴포넌트 디자인")
        assert result.tool == "gemini", f"Expected gemini, got {result.tool}"

        # Coding -> claude
        result = router.route("함수 구현해줘")
        assert result.tool == "claude", f"Expected claude, got {result.tool}"

    print("  PASS: route_with_config")


def test_route_no_config_defaults():
    """Without config, routes to default tool."""
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    result = router.route("아무거나 해줘")
    assert result.tool == "claude"
    print("  PASS: route_no_config_defaults")


def test_route_multi():
    """route_multi returns all matching types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config = {
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude"}},
            "routing": {
                "coding": {"primary": "claude", "fallback": None},
                "refactoring": {"primary": "claude", "fallback": None},
            },
        }
        config_path.write_text(json.dumps(config))
        router = RoleMeshRouter(config_path=config_path)
        results = router.route_multi("코드 리팩토링 개선해줘")
        assert len(results) >= 2
        task_types = {r.task_type for r in results}
        assert "refactoring" in task_types
    print("  PASS: route_multi")


def test_route_result_to_dict():
    """RouteResult serializes to dict correctly."""
    router = RoleMeshRouter(config_path=Path("/nonexistent"))
    result = router.route("함수 만들어줘")
    d = result.to_dict()
    assert "tool" in d
    assert "task_type" in d
    assert "confidence" in d
    assert isinstance(d["confidence"], float)
    print("  PASS: route_result_to_dict")


# ===== Dashboard Tests =====

def _make_dashboard_with_tools(tmpdir):
    """Helper: create a dashboard with mock tools and config."""
    config_path = Path(tmpdir) / "config.json"
    config = {
        "version": "1.0.0",
        "tools": {
            "claude": {"name": "Claude Code", "key": "claude"},
            "codex": {"name": "Codex CLI", "key": "codex"},
        },
        "routing": {
            "coding": {"primary": "claude", "fallback": "codex"},
            "refactoring": {"primary": "codex", "fallback": "claude"},
        },
    }
    config_path.write_text(json.dumps(config))

    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.wizard.tools = [
        ToolProfile(key="claude", name="Claude Code", vendor="Anthropic",
                    strengths=["coding", "analysis"], cost_tier="high", available=True, version="1.0"),
        ToolProfile(key="codex", name="Codex CLI", vendor="OpenAI",
                    strengths=["coding", "refactoring"], cost_tier="medium", available=True),
        ToolProfile(key="gemini", name="Gemini CLI", vendor="Google",
                    strengths=["multimodal"], cost_tier="medium", available=False),
    ]
    dashboard.data.tools = dashboard.wizard.tools
    dashboard.data.config = dashboard.wizard.load_config()
    dashboard.data.routing = dashboard.data.config.get("routing", {})
    dashboard.data.task_types = [tp[0] for tp in TASK_PATTERNS]
    dashboard.data.health_checks = dashboard._run_health_checks()
    return dashboard


def test_dashboard_collect():
    """Dashboard.collect() populates all data fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config_path.write_text(json.dumps({"version": "1.0.0", "tools": {}, "routing": {}}))
        dashboard = RoleMeshDashboard(config_path=config_path)
        data = dashboard.collect()
        assert isinstance(data, DashboardData)
        assert len(data.tools) > 0  # discover_tools returns all registered
        assert len(data.task_types) == len(TASK_PATTERNS)
    print("  PASS: dashboard_collect")


def test_dashboard_health_checks():
    """Health checks detect config issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        checks = {c.name: c for c in dashboard.data.health_checks}

        assert checks["config_file"].passed is True
        assert checks["tools_available"].passed is True
        assert checks["config_version"].passed is True
        assert checks["no_dead_refs"].passed is True
        # routing_coverage will be False since config only has 2 of 13 task types
        assert checks["routing_coverage"].passed is False
        assert "missing" in checks["routing_coverage"].detail
    print("  PASS: dashboard_health_checks")


def test_dashboard_health_no_config():
    """Health checks handle missing config."""
    dashboard = RoleMeshDashboard(config_path=Path("/nonexistent/config.json"))
    dashboard.data.tools = []
    dashboard.data.config = {}
    dashboard.data.routing = {}
    dashboard.data.task_types = [tp[0] for tp in TASK_PATTERNS]
    dashboard.data.health_checks = dashboard._run_health_checks()

    checks = {c.name: c for c in dashboard.data.health_checks}
    assert checks["config_file"].passed is False
    assert checks["tools_available"].passed is False
    assert checks["routing_coverage"].passed is False
    print("  PASS: dashboard_health_no_config")


def test_dashboard_render_tools():
    """render_tools() shows installed and missing tools."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        output = dashboard.render_tools()
        assert "Claude Code" in output
        assert "Codex CLI" in output
        assert "Not found" in output
        assert "Gemini CLI" in output
    print("  PASS: dashboard_render_tools")


def test_dashboard_render_routing():
    """render_routing() shows routing table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        output = dashboard.render_routing()
        assert "coding" in output
        assert "claude" in output
        assert "codex" in output
    print("  PASS: dashboard_render_routing")


def test_dashboard_render_routing_empty():
    """render_routing() handles no config."""
    dashboard = RoleMeshDashboard(config_path=Path("/nonexistent"))
    dashboard.data.routing = {}
    output = dashboard.render_routing()
    assert "No routing config" in output
    print("  PASS: dashboard_render_routing_empty")


def test_dashboard_render_coverage():
    """render_coverage() shows task/tool matrix."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        output = dashboard.render_coverage()
        assert "coding" in output
        assert "X" in output  # strength marker
        assert "*" in output  # primary route marker
    print("  PASS: dashboard_render_coverage")


def test_dashboard_render_health():
    """render_health() shows pass/fail checks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        output = dashboard.render_health()
        assert "[OK]" in output
        assert "[!!]" in output  # routing_coverage will fail
        assert "Score:" in output
    print("  PASS: dashboard_render_health")


def test_dashboard_render_full():
    """render_full() includes all sections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        output = dashboard.render_full()
        assert "RoleMesh Dashboard" in output
        assert "== Tools ==" in output
        assert "== Routing Table ==" in output
        assert "== Task Coverage Matrix ==" in output
        assert "== Health Check ==" in output
    print("  PASS: dashboard_render_full")


def test_dashboard_to_dict():
    """DashboardData serializes to dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dashboard = _make_dashboard_with_tools(tmpdir)
        d = dashboard.data.to_dict()
        assert "tools" in d
        assert "routing" in d
        assert "health" in d
        assert "task_types" in d
        assert isinstance(d["tools"], list)
        assert isinstance(d["health"], list)
    print("  PASS: dashboard_to_dict")


def test_dashboard_dead_refs():
    """Health check detects dead routing references."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config = {
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude"}},
            "routing": {
                "coding": {"primary": "claude", "fallback": "nonexistent_tool"},
            },
        }
        config_path.write_text(json.dumps(config))
        dashboard = RoleMeshDashboard(config_path=config_path)
        dashboard.data.tools = []
        dashboard.data.config = dashboard.wizard.load_config()
        dashboard.data.routing = dashboard.data.config.get("routing", {})
        dashboard.data.task_types = [tp[0] for tp in TASK_PATTERNS]
        dashboard.data.health_checks = dashboard._run_health_checks()

        checks = {c.name: c for c in dashboard.data.health_checks}
        assert checks["no_dead_refs"].passed is False
        assert "nonexistent_tool" in checks["no_dead_refs"].detail
    print("  PASS: dashboard_dead_refs")


# ===== Run all tests =====

def run_all():
    tests = [
        # Builder
        test_tool_registry_complete,
        test_discover_returns_profiles,
        test_wizard_rank_tools,
        test_wizard_user_preference,
        test_wizard_build_config,
        test_wizard_save_load_config,
        test_wizard_no_tools,
        # Router
        test_classify_coding,
        test_classify_refactoring,
        test_classify_architecture,
        test_classify_frontend,
        test_classify_unknown_defaults_coding,
        test_route_with_config,
        test_route_no_config_defaults,
        test_route_multi,
        test_route_result_to_dict,
        # Dashboard
        test_dashboard_collect,
        test_dashboard_health_checks,
        test_dashboard_health_no_config,
        test_dashboard_render_tools,
        test_dashboard_render_routing,
        test_dashboard_render_routing_empty,
        test_dashboard_render_coverage,
        test_dashboard_render_health,
        test_dashboard_render_full,
        test_dashboard_to_dict,
        test_dashboard_dead_refs,
    ]

    passed = 0
    failed = 0
    errors = []

    print(f"\nRunning {len(tests)} tests...\n")
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  FAIL: {test.__name__}: {e}")

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print()
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
