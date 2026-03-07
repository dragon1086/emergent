"""Tests for rolemesh/router.py - Task-to-Tool Router."""

import json
import tempfile
from pathlib import Path

import pytest

from src.rolemesh.router import RoleMeshRouter, RouteResult, TASK_PATTERNS


class TestClassifyTask:
    def setup_method(self):
        self.router = RoleMeshRouter(config_path=Path("/nonexistent"))

    def test_coding_korean(self):
        matches = self.router.classify_task("코드 작성해줘")
        types = [m[0] for m in matches]
        assert "coding" in types

    def test_coding_english(self):
        matches = self.router.classify_task("implement a new function")
        types = [m[0] for m in matches]
        assert "coding" in types

    def test_refactoring(self):
        matches = self.router.classify_task("리팩토링 해줘")
        types = [m[0] for m in matches]
        assert "refactoring" in types

    def test_analysis(self):
        matches = self.router.classify_task("이 버그 원인 분석해줘")
        types = [m[0] for m in matches]
        assert "analysis" in types

    def test_no_match(self):
        matches = self.router.classify_task("xyzzy foobarbaz")
        assert matches == []

    def test_multiple_matches(self):
        matches = self.router.classify_task("코드 분석하고 리팩토링해줘")
        assert len(matches) >= 2

    def test_confidence_range(self):
        matches = self.router.classify_task("코드 작성해줘")
        for _, conf in matches:
            assert 0.0 < conf <= 1.0


class TestRoute:
    def test_default_fallback_no_config(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        result = router.route("xyzzy")
        assert result.tool == "claude"
        assert result.confidence == 0.0
        assert "defaulting" in result.reason.lower()

    def test_route_with_config(self):
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

        router = RoleMeshRouter(config_path=config_path)
        result = router.route("implement a function")
        assert result.tool == "codex"
        assert result.fallback == "claude"
        config_path.unlink()

    def test_route_returns_route_result(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        result = router.route("코드 작성")
        assert isinstance(result, RouteResult)
        assert result.tool_name is not None


class TestRouteMulti:
    def test_returns_list(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        results = router.route_multi("코드 분석하고 리팩토링해줘")
        assert isinstance(results, list)
        assert len(results) >= 2

    def test_each_result_is_route_result(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        results = router.route_multi("코드 작성해줘")
        for r in results:
            assert isinstance(r, RouteResult)


class TestTaskPatterns:
    def test_all_patterns_have_two_elements(self):
        for name, patterns in TASK_PATTERNS:
            assert isinstance(name, str)
            assert isinstance(patterns, tuple)
            assert len(patterns) >= 1
