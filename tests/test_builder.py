"""Tests for rolemesh/builder.py - Tool Discovery & Setup Wizard."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.rolemesh.builder import (
    TOOL_REGISTRY,
    ToolProfile,
    discover_tools,
    SetupWizard,
)


class TestToolProfile:
    def test_defaults(self):
        tp = ToolProfile(key="test", name="Test", vendor="V", strengths=["coding"], cost_tier="low")
        assert tp.available is False
        assert tp.version is None
        assert tp.user_preference is None

    def test_all_fields(self):
        tp = ToolProfile(
            key="x", name="X", vendor="V", strengths=["a", "b"],
            cost_tier="high", available=True, version="1.0", user_preference=1,
        )
        assert tp.available is True
        assert tp.version == "1.0"
        assert tp.user_preference == 1


class TestDiscoverTools:
    def test_returns_list(self):
        tools = discover_tools()
        assert isinstance(tools, list)
        assert len(tools) == len(TOOL_REGISTRY)

    def test_all_registry_keys_present(self):
        tools = discover_tools()
        keys = {t.key for t in tools}
        assert keys == set(TOOL_REGISTRY.keys())

    @patch("shutil.which", return_value=None)
    def test_no_tools_available(self, mock_which):
        tools = discover_tools()
        assert all(not t.available for t in tools)

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_tool_detected(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(stdout=b"claude 1.2.3\n", stderr=b"")
        tools = discover_tools()
        assert all(t.available for t in tools)


class TestSetupWizard:
    def setup_method(self):
        self.wizard = SetupWizard()

    @patch("shutil.which", return_value=None)
    def test_discover_returns_tools(self, mock_which):
        tools = self.wizard.discover()
        assert len(tools) == len(TOOL_REGISTRY)

    @patch("shutil.which", return_value=None)
    def test_available_tools_empty(self, mock_which):
        self.wizard.discover()
        assert self.wizard.available_tools() == []

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_available_tools_found(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(stdout=b"v1\n", stderr=b"")
        self.wizard.discover()
        avail = self.wizard.available_tools()
        assert len(avail) == len(TOOL_REGISTRY)

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_rank_tools_by_task(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(stdout=b"v1\n", stderr=b"")
        self.wizard.discover()
        ranked = self.wizard.rank_tools("coding")
        assert len(ranked) > 0
        assert "coding" in ranked[0].strengths

    def test_build_config_structure(self):
        self.wizard._tools = [
            ToolProfile(key="t1", name="T1", vendor="V", strengths=["coding"], cost_tier="low", available=True),
            ToolProfile(key="t2", name="T2", vendor="V", strengths=["analysis"], cost_tier="high", available=True),
        ]
        config = self.wizard.build_config()
        assert "version" in config
        assert "tools" in config
        assert "routing" in config
        assert config["version"] == "1.0.0"
        assert "t1" in config["tools"]
        assert "t2" in config["tools"]

    def test_save_and_load_config(self):
        self.wizard._tools = [
            ToolProfile(key="t1", name="T1", vendor="V", strengths=["coding"], cost_tier="low", available=True),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            self.wizard.save_config(path)
            assert path.exists()

            loaded = self.wizard.load_config(path)
            assert loaded is not None
            assert loaded["version"] == "1.0.0"

    def test_load_config_missing_file(self):
        result = self.wizard.load_config(Path("/nonexistent/config.json"))
        assert result is None

    def test_validate_config_valid(self):
        config = {
            "version": "1.0.0",
            "tools": {"t1": {"name": "T1"}},
            "routing": {"coding": {"primary": "t1", "fallback": None}},
        }
        errors = self.wizard.validate_config(config)
        assert errors == []

    def test_validate_config_missing_fields(self):
        errors = self.wizard.validate_config({})
        assert len(errors) == 3

    def test_validate_config_dead_ref(self):
        config = {
            "version": "1.0.0",
            "tools": {"t1": {"name": "T1"}},
            "routing": {"coding": {"primary": "nonexistent", "fallback": None}},
        }
        errors = self.wizard.validate_config(config)
        assert any("nonexistent" in e for e in errors)

    @patch("shutil.which", return_value="/usr/bin/custom")
    @patch("subprocess.run")
    def test_register_tool(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(stdout=b"custom 2.0\n", stderr=b"")
        profile = self.wizard.register_tool(
            key="custom", name="Custom", vendor="Test",
            strengths=["coding"], check_cmd=["custom", "--version"], cost_tier="low",
        )
        assert profile.available is True
        assert profile.key == "custom"
        assert "custom" in TOOL_REGISTRY
        # cleanup
        self.wizard.unregister_tool("custom")

    def test_unregister_tool(self):
        self.wizard._tools = [
            ToolProfile(key="x", name="X", vendor="V", strengths=[], cost_tier="low"),
        ]
        self.wizard._custom_tools = ["x"]
        result = self.wizard.unregister_tool("x")
        assert result is True
        assert len(self.wizard._tools) == 0

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_summary_format(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(stdout=b"claude 1.0\n", stderr=b"")
        self.wizard.discover()
        summary = self.wizard.summary()
        assert "RoleMesh:" in summary
        assert "tools available" in summary
