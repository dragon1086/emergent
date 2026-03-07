"""Tests for rolemesh/router.py - Task-to-Tool Router."""

import json
from pathlib import Path

import pytest

from src.rolemesh.router import RoleMeshRouter, RouteResult, TASK_PATTERNS


class TestRouteResult:
    def test_to_dict(self):
        r = RouteResult(tool="claude", tool_name="Claude Code", task_type="coding",
                        confidence=0.8, fallback="codex", reason="test")
        d = r.to_dict()
        assert d["tool"] == "claude"
        assert d["confidence"] == 0.8
        assert d["fallback"] == "codex"


class TestClassifyTask:
    def setup_method(self):
        self.router = RoleMeshRouter(config_path=Path("/nonexistent"))

    def test_coding_korean(self):
        results = self.router.classify_task("코드 작성해줘")
        types = [t for t, _ in results]
        assert "coding" in types

    def test_coding_english(self):
        results = self.router.classify_task("implement a function")
        types = [t for t, _ in results]
        assert "coding" in types

    def test_refactoring(self):
        results = self.router.classify_task("리팩토링 해줘")
        types = [t for t, _ in results]
        assert "refactoring" in types

    def test_analysis(self):
        results = self.router.classify_task("이 버그 분석해줘")
        types = [t for t, _ in results]
        assert "analysis" in types

    def test_frontend(self):
        results = self.router.classify_task("UI 컴포넌트 수정")
        types = [t for t, _ in results]
        assert "frontend" in types

    def test_git_integration(self):
        results = self.router.classify_task("커밋 해줘")
        types = [t for t, _ in results]
        assert "git-integration" in types

    def test_no_match(self):
        results = self.router.classify_task("xyz 123 ???")
        assert results == []

    def test_multi_match(self):
        results = self.router.classify_task("코드 리팩토링하고 UI도 수정해줘")
        types = [t for t, _ in results]
        assert len(types) >= 2

    def test_confidence_sorted(self):
        results = self.router.classify_task("코드 작성하고 구현해줘")
        if len(results) > 1:
            assert results[0][1] >= results[1][1]


class TestRoute:
    def test_route_with_no_config(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        result = router.route("코드 작성")
        assert isinstance(result, RouteResult)
        assert result.tool == "claude"  # default

    def test_route_no_match_defaults(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        result = router.route("xyz 123 ???")
        assert result.tool == "claude"
        assert result.confidence == 0.0
        assert "default" in result.reason.lower()

    def test_route_with_config(self, tmp_path):
        config = {
            "version": "1.0.0",
            "tools": {
                "codex": {"name": "Codex CLI"},
                "claude": {"name": "Claude Code"},
            },
            "routing": {
                "coding": {"primary": "codex", "fallback": "claude"},
            },
        }
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps(config))

        router = RoleMeshRouter(config_path=cfg_path)
        result = router.route("코드 작성해줘")
        assert result.tool == "codex"
        assert result.fallback == "claude"

    def test_route_reason_strong(self, tmp_path):
        config = {"version": "1.0.0", "tools": {}, "routing": {}}
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps(config))
        router = RoleMeshRouter(config_path=cfg_path)
        result = router.route("코드 작성하고 구현 만들어")
        assert result.confidence > 0


class TestRouteMulti:
    def test_returns_multiple(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        results = router.route_multi("코드 리팩토링하고 UI도 수정해줘")
        assert len(results) >= 2
        assert all(isinstance(r, RouteResult) for r in results)

    def test_empty_on_no_match(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        results = router.route_multi("xyz 123")
        assert results == []


class TestBuildReason:
    def test_strong_match(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        reason = router._build_reason("coding", 1.0, [("coding", 1.0)])
        assert "Strong" in reason

    def test_good_match(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        reason = router._build_reason("coding", 0.5, [("coding", 0.5)])
        assert "Good" in reason

    def test_weak_match(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        reason = router._build_reason("coding", 0.3, [("coding", 0.3)])
        assert "Weak" in reason

    def test_also_considered(self):
        router = RoleMeshRouter(config_path=Path("/nonexistent"))
        reason = router._build_reason("coding", 0.8, [("coding", 0.8), ("refactoring", 0.5)])
        assert "refactoring" in reason
