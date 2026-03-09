"""Tests for rolemesh/dashboard.py"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.rolemesh.dashboard import (
    Color,
    DashboardData,
    HealthCheck,
    RoleMeshDashboard,
)
from src.rolemesh.builder import ToolProfile


# --- Color ---

class TestColor:
    def test_wrap_with_colors_enabled(self):
        Color.set_enabled(True)
        # Force TTY detection bypass by checking is_enabled logic
        with patch.object(Color, "is_enabled", return_value=True):
            result = Color.green("ok")
            assert "\033[32m" in result
            assert "ok" in result
            assert result.endswith(Color.RESET)

    def test_wrap_with_colors_disabled(self):
        with patch.object(Color, "is_enabled", return_value=False):
            assert Color.green("ok") == "ok"
            assert Color.red("fail") == "fail"
            assert Color.bold("title") == "title"
            assert Color.dim("dim") == "dim"
            assert Color.cyan("cyan") == "cyan"
            assert Color.yellow("warn") == "warn"

    def test_no_color_env(self):
        Color.set_enabled(True)
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert Color.is_enabled() is False

    def test_is_enabled_default(self):
        Color.set_enabled(True)
        # In test environment stdout is not a TTY, so should be False
        with patch.dict(os.environ, {}, clear=True):
            # Non-TTY → disabled
            assert Color.is_enabled() is False


# --- HealthCheck ---

class TestHealthCheck:
    def test_dataclass_fields(self):
        hc = HealthCheck(name="test", passed=True, detail="all good")
        assert hc.name == "test"
        assert hc.passed is True
        assert hc.detail == "all good"


# --- DashboardData ---

class TestDashboardData:
    def test_defaults(self):
        data = DashboardData()
        assert data.tools == []
        assert data.config is None
        assert data.routing == {}
        assert data.health == []
        assert data.history == []


# --- RoleMeshDashboard ---

def _make_tool(key="claude", name="Claude Code", available=True,
               version="4.1.0", strengths=None):
    return ToolProfile(
        key=key, name=name, vendor="Anthropic",
        strengths=strengths or ["coding", "analysis"],
        cost_tier="high", available=available, version=version,
    )


class TestRoleMeshDashboard:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "config.json"
        self.history_path = Path(self.tmpdir) / "history.jsonl"

    def _write_config(self, config=None):
        config = config or {
            "version": "1.0.0",
            "tools": {
                "claude": {
                    "key": "claude", "name": "Claude Code",
                    "vendor": "Anthropic",
                    "strengths": ["coding", "analysis"],
                    "cost_tier": "high", "available": True,
                    "version": "4.1.0",
                }
            },
            "routing": {
                "coding": {"primary": "claude", "fallback": None},
                "analysis": {"primary": "claude", "fallback": None},
            },
        }
        self.config_path.write_text(json.dumps(config))
        return config

    def _write_history(self, entries=None):
        entries = entries or [
            {"timestamp": "2026-03-07T10:00:00", "tool": "claude",
             "task_type": "coding", "success": True, "duration_ms": 1200},
        ]
        with open(self.history_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_collect_no_config(self):
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools", return_value=[]):
            data = dash.collect()
        assert data.config is None
        assert data.tools == []
        assert data.history == []

    def test_collect_with_config(self):
        self._write_config()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            data = dash.collect()
        assert data.config is not None
        assert data.config["version"] == "1.0.0"
        assert len(data.tools) == 1
        assert "coding" in data.routing

    def test_collect_with_history(self):
        self._write_config()
        self._write_history()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            data = dash.collect()
        assert len(data.history) == 1
        assert data.history[0]["tool"] == "claude"

    def test_collect_bad_history_lines(self):
        self._write_config()
        with open(self.history_path, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"tool": "claude"}) + "\n")
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            data = dash.collect()
        assert len(data.history) == 1

    def test_health_checks_all_pass(self):
        self._write_config()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        passed = [h for h in dash._data.health if h.passed]
        assert len(passed) >= 3  # config_file, tools_available, config_version

    def test_health_no_tools(self):
        self._write_config()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool(available=False)]):
            dash.collect()
        tools_check = [h for h in dash._data.health if h.name == "tools_available"]
        assert len(tools_check) == 1
        assert tools_check[0].passed is False

    def test_health_dead_refs(self):
        config = self._write_config({
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude Code"}},
            "routing": {
                "coding": {"primary": "nonexistent", "fallback": None},
            },
        })
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        dead_check = [h for h in dash._data.health if h.name == "no_dead_refs"]
        assert len(dead_check) == 1
        assert dead_check[0].passed is False
        assert "nonexistent" in dead_check[0].detail

    # --- Render tests ---

    def test_render_tools(self):
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool(), _make_tool(key="codex", name="Codex", available=False, version=None)]):
            dash.collect()
        output = dash.render_tools()
        assert "Claude Code" in output
        assert "Codex" in output

    def test_render_routing_no_config(self):
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools", return_value=[]):
            dash.collect()
        output = dash.render_routing()
        assert "No config loaded" in output

    def test_render_routing_with_config(self):
        self._write_config()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        output = dash.render_routing()
        assert "Routing Table" in output
        assert "coding" in output

    def test_render_coverage_no_tools(self):
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools", return_value=[]):
            dash.collect()
        output = dash.render_coverage()
        assert "No tools available" in output

    def test_render_coverage_with_tools(self):
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        tool = _make_tool(strengths=["coding", "analysis"])
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[tool]):
            dash.collect()
        output = dash.render_coverage()
        assert "Task Coverage Matrix" in output
        assert "claude" in output

    def test_render_health(self):
        self._write_config()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        output = dash.render_health()
        assert "Health Checks" in output
        assert "config_file" in output

    def test_render_history(self):
        self._write_config()
        self._write_history()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        output = dash.render_history()
        assert "Recent Executions" in output
        assert "claude" in output

    def test_render_full(self):
        self._write_config()
        self._write_history()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        output = dash.render_full()
        assert "RoleMesh Dashboard" in output
        assert "Tools" in output
        assert "Routing Table" in output
        assert "Health Checks" in output

    def test_to_json(self):
        self._write_config()
        self._write_history()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        result = dash.to_json()
        assert "tools" in result
        assert "routing" in result
        assert "health" in result
        assert "history" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["key"] == "claude"

    def test_to_json_serializable(self):
        self._write_config()
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        # Should not raise
        serialized = json.dumps(dash.to_json(), ensure_ascii=False)
        assert isinstance(serialized, str)

    def test_history_limit_10(self):
        self._write_config()
        entries = [
            {"timestamp": f"2026-03-07T{i:02d}:00:00", "tool": "claude",
             "task_type": "coding", "success": True, "duration_ms": 100}
            for i in range(15)
        ]
        self._write_history(entries)
        dash = RoleMeshDashboard(
            config_path=self.config_path,
            history_path=self.history_path,
        )
        with patch("src.rolemesh.dashboard.discover_tools",
                    return_value=[_make_tool()]):
            dash.collect()
        output = dash.render_history()
        # render_history shows last 10
        lines = [l for l in output.split("\n") if "claude" in l]
        assert len(lines) == 10
