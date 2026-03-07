"""Tests for rolemesh/executor.py - Task Executor."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.rolemesh.executor import (
    TOOL_COMMANDS,
    ExecutionResult,
    RoleMeshExecutor,
)
from src.rolemesh.router import RouteResult


class TestExecutionResult:
    def test_success_property(self):
        r = ExecutionResult(
            tool="claude", tool_name="Claude", task_type="coding",
            confidence=1.0, exit_code=0, stdout="ok", stderr="",
            duration_ms=100,
        )
        assert r.success is True

    def test_failure_property(self):
        r = ExecutionResult(
            tool="claude", tool_name="Claude", task_type="coding",
            confidence=1.0, exit_code=1, stdout="", stderr="err",
            duration_ms=50,
        )
        assert r.success is False

    def test_to_dict(self):
        r = ExecutionResult(
            tool="claude", tool_name="Claude", task_type="coding",
            confidence=0.85, exit_code=0, stdout="ok", stderr="",
            duration_ms=100, fallback_used=True,
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["confidence"] == 0.85
        assert d["fallback_used"] is True


class TestBuildCommand:
    def setup_method(self):
        self.executor = RoleMeshExecutor(config_path=Path("/nonexistent"))

    def test_simple_tool(self):
        cmd = self.executor.build_command("claude", "hello")
        assert cmd == ["claude", "-p", "hello"]

    def test_list_command(self):
        cmd = self.executor.build_command("copilot", "explain")
        assert cmd[:3] == ["gh", "copilot", "suggest"]
        assert "-p" in cmd

    def test_with_files_context(self):
        cmd = self.executor.build_command("claude", "fix", context={"files": ["a.py", "b.py"]})
        assert "a.py" in cmd
        assert "b.py" in cmd

    def test_unknown_tool(self):
        cmd = self.executor.build_command("nonexistent", "hello")
        assert cmd == []


class TestCheckTool:
    def setup_method(self):
        self.executor = RoleMeshExecutor(config_path=Path("/nonexistent"))

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_available(self, _):
        assert self.executor.check_tool("claude") is True

    @patch("shutil.which", return_value=None)
    def test_unavailable(self, _):
        assert self.executor.check_tool("claude") is False

    def test_unknown_key(self):
        assert self.executor.check_tool("unknown_tool_xyz") is False


class TestDispatch:
    def test_dry_run(self):
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"), dry_run=True)
        result = executor.dispatch("claude", "hello")
        assert result.success is True
        assert "[dry-run]" in result.stdout

    def test_unknown_tool_returns_127(self):
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"))
        result = executor.dispatch("unknown_xyz", "hello")
        assert result.exit_code == 127
        assert "Unknown tool" in result.stderr

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_dispatch_success(self, mock_run, _):
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"))
        result = executor.dispatch("claude", "test prompt")
        assert result.success is True
        assert result.stdout == "done"


class TestRun:
    def test_run_dry_run(self):
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"), dry_run=True)
        result = executor.run("코드 작성")
        assert result.success is True
        assert "[dry-run]" in result.stdout

    @patch("shutil.which", return_value=None)
    def test_run_no_tool_available(self, _):
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"))
        result = executor.run("코드 작성")
        assert result.exit_code == 127
        assert "not found" in result.stderr

    @patch("shutil.which", side_effect=lambda x: "/bin/codex" if x == "codex" else None)
    def test_run_fallback_when_primary_missing(self, _):
        config = {
            "version": "1.0.0",
            "tools": {"claude": {}, "codex": {}},
            "routing": {"coding": {"primary": "claude", "fallback": "codex"}},
        }
        cfg = Path("/tmp/test_rolemesh_cfg.json")
        cfg.write_text(json.dumps(config))

        executor = RoleMeshExecutor(config_path=cfg, dry_run=True)
        result = executor.run("코드 작성해줘")
        assert result.fallback_used is True
        cfg.unlink(missing_ok=True)


class TestRunSubprocess:
    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run, _):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=5)
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"), timeout=5)
        result = executor.dispatch("claude", "long task")
        assert result.exit_code == -1
        assert "Timeout" in result.stderr

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_os_error_handling(self, mock_run, _):
        mock_run.side_effect = OSError("Permission denied")
        executor = RoleMeshExecutor(config_path=Path("/nonexistent"))
        result = executor.dispatch("claude", "test")
        assert result.exit_code == 126
        assert "Permission denied" in result.stderr


class TestHistory:
    def test_log_and_read_history(self, tmp_path):
        hist = tmp_path / "history.jsonl"
        executor = RoleMeshExecutor(
            config_path=Path("/nonexistent"),
            dry_run=True,
            history_path=hist,
        )
        # dry_run skips logging, so manually test _log_history
        executor.dry_run = False
        result = ExecutionResult(
            tool="claude", tool_name="Claude", task_type="coding",
            confidence=0.9, exit_code=0, stdout="ok", stderr="",
            duration_ms=50,
        )
        executor._log_history("test request", result)

        entries = executor.get_history()
        assert len(entries) == 1
        assert entries[0]["tool"] == "claude"
        assert entries[0]["success"] is True

    def test_get_history_missing_file(self, tmp_path):
        executor = RoleMeshExecutor(
            config_path=Path("/nonexistent"),
            history_path=tmp_path / "nope.jsonl",
        )
        assert executor.get_history() == []

    def test_history_limit(self, tmp_path):
        hist = tmp_path / "history.jsonl"
        executor = RoleMeshExecutor(
            config_path=Path("/nonexistent"),
            history_path=hist,
        )
        result = ExecutionResult(
            tool="t", tool_name="T", task_type="x",
            confidence=1.0, exit_code=0, stdout="", stderr="",
            duration_ms=0,
        )
        for i in range(10):
            executor._log_history(f"req-{i}", result)

        entries = executor.get_history(limit=3)
        assert len(entries) == 3
