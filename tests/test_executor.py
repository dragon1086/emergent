"""Tests for rolemesh/executor.py - Task Executor with fallback."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.rolemesh.executor import RoleMeshExecutor, ExecutionResult, TOOL_COMMANDS


class TestExecutionResult:
    def test_fields(self):
        r = ExecutionResult(
            tool="claude", tool_name="Claude Code", task_type="coding",
            confidence=0.5, exit_code=0, success=True, duration_ms=100,
            fallback_used=False, stdout="ok", stderr="",
        )
        assert r.success is True
        assert r.fallback_used is False


class TestDispatchDryRun:
    def setup_method(self):
        self.executor = RoleMeshExecutor(dry_run=True)

    def test_dry_run_success(self):
        result = self.executor.dispatch("implement a function")
        assert result.success is True
        assert "[dry-run]" in result.stdout

    def test_dry_run_with_tool_override(self):
        result = self.executor.dispatch("test task", tool="claude")
        assert result.tool == "claude"
        assert result.success is True

    def test_unknown_tool(self):
        result = self.executor.dispatch("test", tool="nonexistent_tool")
        assert result.success is False
        assert "Unknown tool" in result.stderr


class TestFallback:
    def test_fallback_on_primary_failure(self):
        config = {
            "version": "1.0.0",
            "tools": {
                "claude": {"name": "Claude Code"},
                "codex": {"name": "Codex CLI"},
            },
            "routing": {
                "coding": {"primary": "codex", "fallback": "claude"},
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_path = Path(f.name)

        executor = RoleMeshExecutor(config_path=config_path, dry_run=False)

        call_count = 0

        def mock_run(tool_key, task, route_result):
            nonlocal call_count
            call_count += 1
            if tool_key == "codex":
                return ExecutionResult(
                    tool="codex", tool_name="Codex CLI", task_type="coding",
                    confidence=0.5, exit_code=1, success=False, duration_ms=50,
                    fallback_used=False, stdout="", stderr="codex failed",
                )
            return ExecutionResult(
                tool="claude", tool_name="Claude Code", task_type="coding",
                confidence=0.5, exit_code=0, success=True, duration_ms=100,
                fallback_used=False, stdout="claude ok", stderr="",
            )

        executor.run = mock_run
        result = executor.dispatch("implement a function")

        assert result.success is True
        assert result.fallback_used is True
        assert result.tool == "claude"
        assert call_count == 2
        config_path.unlink()

    def test_no_fallback_when_tool_forced(self):
        executor = RoleMeshExecutor(dry_run=False)

        def mock_run(tool_key, task, route_result):
            return ExecutionResult(
                tool=tool_key, tool_name="Test", task_type="coding",
                confidence=0.5, exit_code=1, success=False, duration_ms=10,
                fallback_used=False, stdout="", stderr="fail",
            )

        executor.run = mock_run
        result = executor.dispatch("test", tool="claude")
        assert result.success is False
        assert result.fallback_used is False

    def test_no_fallback_when_primary_succeeds(self):
        executor = RoleMeshExecutor(dry_run=True)
        result = executor.dispatch("implement a function")
        assert result.success is True
        assert result.fallback_used is False


class TestHistory:
    def test_history_logged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.jsonl"
            executor = RoleMeshExecutor(dry_run=False)
            executor._history_path = history_path

            # Mock run to avoid actual subprocess and trigger _log_history
            def mock_run(tool_key, task, route_result):
                result = ExecutionResult(
                    tool=tool_key, tool_name="Test", task_type="coding",
                    confidence=0.5, exit_code=0, success=True, duration_ms=10,
                    fallback_used=False, stdout="ok", stderr="",
                )
                executor._log_history(result)
                return result

            executor.run = mock_run
            executor.dispatch("test task")

            assert history_path.exists()
            lines = history_path.read_text().strip().split("\n")
            entry = json.loads(lines[0])
            assert "timestamp" in entry
            assert entry["success"] is True


class TestToolCommands:
    def test_known_tools(self):
        for key in ("claude", "codex", "gemini", "aider"):
            assert key in TOOL_COMMANDS
            assert "cmd" in TOOL_COMMANDS[key]
