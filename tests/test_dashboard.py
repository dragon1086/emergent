"""Tests for rolemesh/dashboard.py - Terminal Dashboard & Health Checks."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.rolemesh.dashboard import (
    Color,
    HealthCheck,
    DashboardData,
    RoleMeshDashboard,
)
from src.rolemesh.builder import ToolProfile


def _make_tools():
    return [
        ToolProfile(
            key="claude", name="Claude Code", vendor="Anthropic",
            strengths=["coding", "refactoring", "analysis"],
            cost_tier="high", available=True, version="1.2.3",
        ),
        ToolProfile(
            key="codex", name="Codex CLI", vendor="OpenAI",
            strengths=["coding", "quick-edit"],
            cost_tier="medium", available=False,
        ),
    ]


def _make_config():
    return {
        "version": "1.0.0",
        "tools": {
            "claude": {"name": "Claude Code"},
            "codex": {"name": "Codex CLI"},
        },
        "routing": {
            "coding": {"primary": "claude", "fallback": "codex"},
            "analysis": {"primary": "claude", "fallback": None},
        },
    }


class TestColor:
    def test_wrap_enabled(self):
        Color.set_enabled(True)
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            with patch.dict("os.environ", {}, clear=True):
                result = Color.wrap("hi", Color.RED)
                assert "\033[31m" in result
                assert "hi" in result

    def test_wrap_disabled(self):
        Color.set_enabled(False)
        result = Color.wrap("hi", Color.RED)
        assert result == "hi"
        Color.set_enabled(True)

    def test_no_color_env(self):
        Color.set_enabled(True)
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            result = Color.wrap("hi", Color.RED)
            assert result == "hi"

    def test_bold(self):
        Color.set_enabled(False)
        assert Color.bold("x") == "x"
        Color.set_enabled(True)

    def test_green(self):
        Color.set_enabled(False)
        assert Color.green("ok") == "ok"
        Color.set_enabled(True)

    def test_red(self):
        Color.set_enabled(False)
        assert Color.red("err") == "err"
        Color.set_enabled(True)

    def test_yellow(self):
        Color.set_enabled(False)
        assert Color.yellow("warn") == "warn"
        Color.set_enabled(True)

    def test_cyan(self):
        Color.set_enabled(False)
        assert Color.cyan("info") == "info"
        Color.set_enabled(True)

    def test_dim(self):
        Color.set_enabled(False)
        assert Color.dim("muted") == "muted"
        Color.set_enabled(True)


class TestHealthCheck:
    def test_fields(self):
        hc = HealthCheck(name="test_check", passed=True, detail="all good")
        assert hc.name == "test_check"
        assert hc.passed is True
        assert hc.detail == "all good"


class TestDashboardData:
    def test_defaults(self):
        d = DashboardData()
        assert d.tools == []
        assert d.config is None
        assert d.routing == {}
        assert d.health == []
        assert d.history == []


class TestRoleMeshDashboard:
    def _make_dashboard(self, config=None, history_entries=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"

            if config:
                config_path.write_text(json.dumps(config))

            if history_entries:
                lines = [json.dumps(e) for e in history_entries]
                history_path.write_text("\n".join(lines))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            return dash, tmpdir

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_collect_no_config(self, mock_discover):
        mock_discover.return_value = _make_tools()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            data = dash.collect()

            assert len(data.tools) == 2
            assert data.config is None
            assert data.routing == {}

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_collect_with_config(self, mock_discover):
        mock_discover.return_value = _make_tools()
        config = _make_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            config_path.write_text(json.dumps(config))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            data = dash.collect()

            assert data.config is not None
            assert "coding" in data.routing
            assert data.routing["coding"]["primary"] == "claude"

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_collect_with_history(self, mock_discover):
        mock_discover.return_value = _make_tools()
        entries = [
            {"timestamp": "2026-03-07 10:00:00", "tool": "claude", "task_type": "coding", "success": True, "duration_ms": 500},
            {"timestamp": "2026-03-07 10:01:00", "tool": "codex", "task_type": "analysis", "success": False, "duration_ms": 200},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            history_path.write_text("\n".join(json.dumps(e) for e in entries))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            data = dash.collect()

            assert len(data.history) == 2
            assert data.history[0]["tool"] == "claude"

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_health_checks_no_config(self, mock_discover):
        mock_discover.return_value = _make_tools()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            dash.collect()

            checks = {h.name: h for h in dash._data.health}
            assert checks["config_file"].passed is False
            assert checks["tools_available"].passed is True
            assert checks["routing_coverage"].passed is False
            assert checks["config_version"].passed is False
            assert checks["no_dead_refs"].passed is False

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_health_checks_with_valid_config(self, mock_discover):
        mock_discover.return_value = _make_tools()
        from src.rolemesh.router import TASK_PATTERNS
        routing = {tp[0]: {"primary": "claude", "fallback": None} for tp in TASK_PATTERNS}
        config = {"version": "1.0.0", "tools": {"claude": {"name": "Claude Code"}}, "routing": routing}

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            config_path.write_text(json.dumps(config))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            dash.collect()

            checks = {h.name: h for h in dash._data.health}
            assert checks["config_file"].passed is True
            assert checks["routing_coverage"].passed is True
            assert checks["config_version"].passed is True
            assert checks["no_dead_refs"].passed is True

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_health_dead_refs(self, mock_discover):
        mock_discover.return_value = _make_tools()
        config = {
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude Code"}},
            "routing": {"coding": {"primary": "nonexistent", "fallback": None}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            config_path.write_text(json.dumps(config))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            dash.collect()

            checks = {h.name: h for h in dash._data.health}
            assert checks["no_dead_refs"].passed is False
            assert "nonexistent" in checks["no_dead_refs"].detail

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_health_no_tools_available(self, mock_discover):
        tools = _make_tools()
        for t in tools:
            t.available = False
        mock_discover.return_value = tools

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            dash.collect()

            checks = {h.name: h for h in dash._data.health}
            assert checks["tools_available"].passed is False


class TestRender:
    @patch("src.rolemesh.dashboard.discover_tools")
    def _setup_dashboard(self, mock_discover, config=None, history=None):
        Color.set_enabled(False)
        mock_discover.return_value = _make_tools()

        tmpdir = tempfile.mkdtemp()
        config_path = Path(tmpdir) / "config.json"
        history_path = Path(tmpdir) / "history.jsonl"

        if config:
            config_path.write_text(json.dumps(config))
        if history:
            history_path.write_text("\n".join(json.dumps(e) for e in history))

        dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
        dash.collect()
        return dash

    def test_render_tools(self):
        dash = self._setup_dashboard()
        output = dash.render_tools()
        assert "Claude Code" in output
        assert "Codex CLI" in output
        assert "Anthropic" in output

    def test_render_routing_no_config(self):
        dash = self._setup_dashboard()
        output = dash.render_routing()
        assert "No routing config" in output

    def test_render_routing_with_config(self):
        dash = self._setup_dashboard(config=_make_config())
        output = dash.render_routing()
        assert "coding" in output
        assert "analysis" in output

    def test_render_coverage(self):
        dash = self._setup_dashboard()
        output = dash.render_coverage()
        assert "Coverage" in output or "Task Type" in output

    def test_render_coverage_no_tools(self):
        Color.set_enabled(False)
        tools = _make_tools()
        for t in tools:
            t.available = False

        with patch("src.rolemesh.dashboard.discover_tools", return_value=tools):
            with tempfile.TemporaryDirectory() as tmpdir:
                dash = RoleMeshDashboard(
                    config_path=Path(tmpdir) / "c.json",
                    history_path=Path(tmpdir) / "h.jsonl",
                )
                dash.collect()
                output = dash.render_coverage()
                assert "No tools available" in output

    def test_render_health(self):
        dash = self._setup_dashboard()
        output = dash.render_health()
        assert "PASS" in output or "FAIL" in output

    def test_render_history(self):
        entries = [
            {"timestamp": "2026-03-07 10:00:00", "tool": "claude", "task_type": "coding", "success": True, "duration_ms": 500},
        ]
        dash = self._setup_dashboard(history=entries)
        output = dash.render_history()
        assert "claude" in output
        assert "coding" in output

    def test_render_full(self):
        dash = self._setup_dashboard(config=_make_config())
        output = dash.render_full()
        assert "RoleMesh Dashboard" in output
        assert "Tools" in output
        assert "Routing" in output
        assert "Health" in output

    def test_render_full_with_history(self):
        entries = [
            {"timestamp": "2026-03-07 10:00:00", "tool": "claude", "task_type": "coding", "success": True, "duration_ms": 100},
        ]
        dash = self._setup_dashboard(config=_make_config(), history=entries)
        output = dash.render_full()
        assert "History" in output


class TestToJson:
    @patch("src.rolemesh.dashboard.discover_tools")
    def test_json_structure(self, mock_discover):
        mock_discover.return_value = _make_tools()
        config = _make_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            config_path.write_text(json.dumps(config))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            dash.collect()
            data = dash.to_json()

            assert "tools" in data
            assert "routing" in data
            assert "health" in data
            assert "history" in data

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_json_tools_fields(self, mock_discover):
        mock_discover.return_value = _make_tools()

        with tempfile.TemporaryDirectory() as tmpdir:
            dash = RoleMeshDashboard(
                config_path=Path(tmpdir) / "c.json",
                history_path=Path(tmpdir) / "h.jsonl",
            )
            dash.collect()
            data = dash.to_json()

            tool = data["tools"][0]
            assert "key" in tool
            assert "name" in tool
            assert "vendor" in tool
            assert "strengths" in tool
            assert "cost_tier" in tool
            assert "available" in tool

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_json_serializable(self, mock_discover):
        mock_discover.return_value = _make_tools()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            history_path = Path(tmpdir) / "history.jsonl"
            config_path.write_text(json.dumps(_make_config()))

            dash = RoleMeshDashboard(config_path=config_path, history_path=history_path)
            dash.collect()
            serialized = json.dumps(dash.to_json())
            assert isinstance(serialized, str)


class TestDashboardMain:
    @patch("src.rolemesh.dashboard.discover_tools")
    def test_main_json(self, mock_discover, capsys):
        mock_discover.return_value = _make_tools()
        from src.rolemesh.dashboard import main
        with patch("sys.argv", ["dashboard", "--json"]):
            main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "tools" in data

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_main_tools(self, mock_discover, capsys):
        mock_discover.return_value = _make_tools()
        from src.rolemesh.dashboard import main
        with patch("sys.argv", ["dashboard", "--tools"]):
            main()
        captured = capsys.readouterr()
        assert "Claude Code" in captured.out

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_main_health(self, mock_discover, capsys):
        mock_discover.return_value = _make_tools()
        from src.rolemesh.dashboard import main
        with patch("sys.argv", ["dashboard", "--health"]):
            main()
        captured = capsys.readouterr()
        assert "PASS" in captured.out or "FAIL" in captured.out

    @patch("src.rolemesh.dashboard.discover_tools")
    def test_main_full(self, mock_discover, capsys):
        mock_discover.return_value = _make_tools()
        from src.rolemesh.dashboard import main
        with patch("sys.argv", ["dashboard"]):
            main()
        captured = capsys.readouterr()
        assert "RoleMesh" in captured.out
