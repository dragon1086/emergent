"""Tests for rolemesh/dashboard.py"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.rolemesh.builder import ToolProfile
from src.rolemesh.dashboard import (
    Color,
    DashboardData,
    HealthCheck,
    RoleMeshDashboard,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config file with routing."""
    config = {
        "version": "1.0.0",
        "tools": {
            "claude": {
                "key": "claude",
                "name": "Claude Code",
                "vendor": "Anthropic",
                "strengths": ["coding", "refactoring", "analysis"],
                "cost_tier": "high",
                "available": True,
                "version": "2.0.0",
            },
            "codex": {
                "key": "codex",
                "name": "Codex CLI",
                "vendor": "OpenAI",
                "strengths": ["coding", "quick-edit"],
                "cost_tier": "medium",
                "available": True,
                "version": "1.0.0",
            },
        },
        "routing": {
            "coding": {"primary": "claude", "fallback": "codex"},
            "refactoring": {"primary": "claude"},
            "quick-edit": {"primary": "codex"},
            "analysis": {"primary": "claude"},
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return config_path


@pytest.fixture
def tmp_history(tmp_path):
    """Create a temporary history JSONL file."""
    history_path = tmp_path / "history.jsonl"
    entries = [
        {"timestamp": "2026-03-07T10:00:00", "tool": "claude", "task_type": "coding", "success": True, "duration_ms": 1200},
        {"timestamp": "2026-03-07T10:05:00", "tool": "codex", "task_type": "quick-edit", "success": False, "duration_ms": 800},
        {"timestamp": "2026-03-07T10:10:00", "tool": "claude", "task_type": "analysis", "success": True, "duration_ms": 3000},
    ]
    history_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return history_path


MOCK_TOOLS = [
    ToolProfile(key="claude", name="Claude Code", vendor="Anthropic",
                strengths=["coding", "refactoring", "analysis"],
                cost_tier="high", available=True, version="2.0.0"),
    ToolProfile(key="codex", name="Codex CLI", vendor="OpenAI",
                strengths=["coding", "quick-edit"],
                cost_tier="medium", available=True, version="1.0.0"),
    ToolProfile(key="aider", name="Aider", vendor="Community",
                strengths=["coding"], cost_tier="low",
                available=False, version=None),
]


@pytest.fixture
def dashboard(tmp_config, tmp_history):
    """Dashboard with mock config and history."""
    with patch("src.rolemesh.builder.discover_tools", return_value=MOCK_TOOLS):
        d = RoleMeshDashboard(config_path=tmp_config, history_path=tmp_history)
        d.collect()
        return d


# ─── Color Tests ─────────────────────────────────────────────────────────────


class TestColor:
    def test_disabled_returns_plain_text(self):
        Color.set_enabled(False)
        assert Color.green("hello") == "hello"
        assert Color.red("err") == "err"
        assert Color.bold("b") == "b"
        Color.set_enabled(None)

    def test_enabled_wraps_ansi(self):
        Color.set_enabled(True)
        result = Color.green("ok")
        assert "\x1b[32m" in result
        assert "ok" in result
        assert "\x1b[0m" in result
        Color.set_enabled(None)

    def test_all_colors(self):
        Color.set_enabled(True)
        assert "\x1b[31m" in Color.red("r")
        assert "\x1b[33m" in Color.yellow("y")
        assert "\x1b[36m" in Color.cyan("c")
        assert "\x1b[1m" in Color.bold("b")
        assert "\x1b[2m" in Color.dim("d")
        Color.set_enabled(None)


# ─── DashboardData Tests ────────────────────────────────────────────────────


class TestDashboardData:
    def test_to_dict_empty(self):
        data = DashboardData()
        d = data.to_dict()
        assert d["tools"] == []
        assert d["config_loaded"] is False
        assert d["routing"] == {}
        assert d["task_types"] == []
        assert d["health_checks"] == []
        assert d["history"] == []

    def test_to_dict_with_tools(self):
        data = DashboardData(tools=MOCK_TOOLS[:1])
        d = data.to_dict()
        assert len(d["tools"]) == 1
        assert d["tools"][0]["key"] == "claude"
        assert d["tools"][0]["available"] is True

    def test_to_dict_with_health_checks(self):
        data = DashboardData(
            health_checks=[HealthCheck("test", True, "ok")]
        )
        d = data.to_dict()
        assert d["health_checks"][0]["name"] == "test"
        assert d["health_checks"][0]["passed"] is True


# ─── HealthCheck Tests ──────────────────────────────────────────────────────


class TestHealthCheck:
    def test_fields(self):
        h = HealthCheck(name="config_file", passed=True, detail="/path")
        assert h.name == "config_file"
        assert h.passed is True
        assert h.detail == "/path"


# ─── RoleMeshDashboard Tests ───────────────────────────────────────────────


class TestDashboard:
    def test_collect_populates_data(self, dashboard):
        assert len(dashboard.data.tools) == 3
        assert len(dashboard.data.health_checks) > 0
        assert len(dashboard.data.task_types) > 0

    def test_collect_loads_config(self, dashboard):
        assert dashboard.data.config.get("version") == "1.0.0"

    def test_collect_loads_routing(self, dashboard):
        assert "coding" in dashboard.data.routing
        assert dashboard.data.routing["coding"]["primary"] == "claude"

    def test_collect_loads_history(self, dashboard):
        assert len(dashboard.data.history) == 3
        assert dashboard.data.history[0]["tool"] == "claude"

    def test_health_config_file_passes(self, dashboard):
        checks = {c.name: c for c in dashboard.data.health_checks}
        assert checks["config_file"].passed is True

    def test_health_tools_available(self, dashboard):
        checks = {c.name: c for c in dashboard.data.health_checks}
        assert checks["tools_available"].passed is True
        available = [t for t in dashboard.data.tools if t.available]
        assert f"{len(available)}/{len(dashboard.data.tools)}" in checks["tools_available"].detail

    def test_health_config_version(self, dashboard):
        checks = {c.name: c for c in dashboard.data.health_checks}
        assert checks["config_version"].passed is True

    def test_health_no_dead_refs(self, dashboard):
        checks = {c.name: c for c in dashboard.data.health_checks}
        assert checks["no_dead_refs"].passed is True

    def test_health_dead_ref_detected(self, tmp_path):
        config = {
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude"}},
            "routing": {"coding": {"primary": "nonexistent"}},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        with patch("src.rolemesh.builder.discover_tools", return_value=MOCK_TOOLS):
            d = RoleMeshDashboard(config_path=config_path)
            d.collect()
        checks = {c.name: c for c in d.data.health_checks}
        assert checks["no_dead_refs"].passed is False
        assert "nonexistent" in checks["no_dead_refs"].detail


class TestDashboardRenderers:
    def test_render_tools(self, dashboard):
        Color.set_enabled(False)
        output = dashboard.render_tools()
        assert "Tools" in output
        assert "Claude Code" in output
        assert "Codex CLI" in output
        assert "Aider" in output
        Color.set_enabled(None)

    def test_render_routing(self, dashboard):
        Color.set_enabled(False)
        output = dashboard.render_routing()
        assert "Routing Table" in output
        assert "coding" in output
        assert "claude" in output
        Color.set_enabled(None)

    def test_render_routing_empty(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        with patch("src.rolemesh.builder.discover_tools", return_value=[]):
            d = RoleMeshDashboard(config_path=config_path)
            d.collect()
        Color.set_enabled(False)
        output = d.render_routing()
        assert "No routing config" in output
        Color.set_enabled(None)

    def test_render_coverage(self, dashboard):
        Color.set_enabled(False)
        output = dashboard.render_coverage()
        assert "Task Coverage Matrix" in output
        assert "claude" in output
        Color.set_enabled(None)

    def test_render_coverage_no_tools(self, tmp_path):
        no_tools = [
            ToolProfile(key="x", name="X", vendor="V",
                        strengths=[], cost_tier="low",
                        available=False, version=None),
        ]
        config_path = tmp_path / "empty.json"
        config_path.write_text("{}")
        with patch("src.rolemesh.builder.discover_tools", return_value=no_tools):
            d = RoleMeshDashboard(config_path=config_path)
            d.collect()
        Color.set_enabled(False)
        output = d.render_coverage()
        assert "No tools available" in output
        Color.set_enabled(None)

    def test_render_health(self, dashboard):
        Color.set_enabled(False)
        output = dashboard.render_health()
        assert "Health Check" in output
        assert "Score:" in output
        Color.set_enabled(None)

    def test_render_history(self, dashboard):
        Color.set_enabled(False)
        output = dashboard.render_history()
        assert "Execution History" in output
        assert "claude" in output
        assert "3" in output  # total count
        Color.set_enabled(None)

    def test_render_history_empty(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        with patch("src.rolemesh.builder.discover_tools", return_value=[]):
            d = RoleMeshDashboard(config_path=config_path)
            d.collect()
        Color.set_enabled(False)
        output = d.render_history()
        assert "No execution history" in output
        Color.set_enabled(None)

    def test_render_full(self, dashboard):
        Color.set_enabled(False)
        output = dashboard.render_full()
        assert "RoleMesh Dashboard" in output
        assert "Tools" in output
        assert "Routing Table" in output
        assert "Task Coverage Matrix" in output
        assert "Health Check" in output
        assert "Execution History" in output
        Color.set_enabled(None)

    def test_render_full_no_history(self, tmp_config):
        with patch("src.rolemesh.builder.discover_tools", return_value=MOCK_TOOLS):
            d = RoleMeshDashboard(config_path=tmp_config)
            d.collect()
        Color.set_enabled(False)
        output = d.render_full()
        assert "Execution History" not in output
        Color.set_enabled(None)


class TestDashboardHistory:
    def test_load_history_missing_file(self, tmp_path):
        with patch("src.rolemesh.builder.discover_tools", return_value=[]):
            d = RoleMeshDashboard(
                config_path=tmp_path / "c.json",
                history_path=tmp_path / "nope.jsonl",
            )
            d.collect()
        assert d.data.history == []

    def test_load_history_malformed_lines(self, tmp_path):
        history_path = tmp_path / "bad.jsonl"
        history_path.write_text('{"ok": true}\nnot json\n{"ok": false}\n')
        with patch("src.rolemesh.builder.discover_tools", return_value=[]):
            d = RoleMeshDashboard(
                config_path=tmp_path / "c.json",
                history_path=history_path,
            )
            d.collect()
        assert len(d.data.history) == 2

    def test_load_history_limit(self, tmp_path):
        history_path = tmp_path / "big.jsonl"
        lines = [json.dumps({"i": i}) for i in range(50)]
        history_path.write_text("\n".join(lines))
        with patch("src.rolemesh.builder.discover_tools", return_value=[]):
            d = RoleMeshDashboard(
                config_path=tmp_path / "c.json",
                history_path=history_path,
            )
            d.collect()
        assert len(d.data.history) == 20  # default limit


class TestDashboardJSON:
    def test_to_dict_roundtrip(self, dashboard):
        d = dashboard.data.to_dict()
        serialized = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(serialized)
        assert len(parsed["tools"]) == len(dashboard.data.tools)
        assert parsed["config_loaded"] is True
        assert len(parsed["health_checks"]) == len(dashboard.data.health_checks)
        assert len(parsed["history"]) == 3
