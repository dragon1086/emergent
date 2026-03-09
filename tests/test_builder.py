"""Tests for rolemesh/builder.py - AI Tool Discovery & Setup Wizard."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.rolemesh.builder import (
    TOOL_REGISTRY,
    SetupWizard,
    ToolProfile,
    discover_tools,
)


class TestToolProfile:
    def test_to_dict(self):
        p = ToolProfile(
            key="claude", name="Claude Code", vendor="Anthropic",
            strengths=["coding"], cost_tier="high", available=True, version="1.0",
        )
        d = p.to_dict()
        assert d["key"] == "claude"
        assert d["available"] is True
        assert d["version"] == "1.0"

    def test_defaults(self):
        p = ToolProfile(key="x", name="X", vendor="V", strengths=[], cost_tier="low")
        assert p.available is False
        assert p.version is None
        assert p.user_preference is None


class TestDiscoverTools:
    @patch("shutil.which", return_value=None)
    def test_no_tools_available(self, mock_which):
        results = discover_tools()
        assert len(results) == len(TOOL_REGISTRY)
        assert all(not t.available for t in results)

    @patch("shutil.which", side_effect=lambda x: "/usr/bin/claude" if x == "claude" else None)
    @patch("subprocess.run")
    def test_claude_available(self, mock_run, mock_which):
        mock_run.return_value = type("R", (), {"stdout": "claude 1.2.3\n", "returncode": 0})()
        results = discover_tools()
        claude = next(t for t in results if t.key == "claude")
        assert claude.available is True
        assert claude.version == "claude 1.2.3"


class TestSetupWizard:
    def setup_method(self):
        self.wizard = SetupWizard()

    @patch("shutil.which", return_value=None)
    def test_discover_populates_tools(self, _):
        self.wizard.discover()
        assert len(self.wizard.tools) == len(TOOL_REGISTRY)

    @patch("shutil.which", return_value=None)
    def test_available_tools_empty_when_none_installed(self, _):
        self.wizard.discover()
        assert self.wizard.available_tools() == []

    @patch("shutil.which", return_value=None)
    def test_summary_no_tools(self, _):
        self.wizard.discover()
        s = self.wizard.summary()
        assert "No AI tools found" in s

    def test_available_tools_filters(self):
        self.wizard.tools = [
            ToolProfile(key="a", name="A", vendor="V", strengths=["coding"], cost_tier="low", available=True),
            ToolProfile(key="b", name="B", vendor="V", strengths=["coding"], cost_tier="low", available=False),
        ]
        assert len(self.wizard.available_tools()) == 1

    def test_rank_tools_by_strength(self):
        self.wizard.tools = [
            ToolProfile(key="a", name="A", vendor="V", strengths=["analysis"], cost_tier="high", available=True),
            ToolProfile(key="b", name="B", vendor="V", strengths=["coding"], cost_tier="low", available=True),
        ]
        ranked = self.wizard.rank_tools("coding")
        assert ranked[0].key == "b"

    def test_build_config_structure(self):
        self.wizard.tools = [
            ToolProfile(key="claude", name="Claude", vendor="Anthropic",
                        strengths=["coding", "analysis"], cost_tier="high", available=True),
        ]
        config = self.wizard.build_config()
        assert "version" in config
        assert "tools" in config
        assert "routing" in config
        assert "claude" in config["tools"]
        assert "coding" in config["routing"]

    def test_save_and_load_config(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        self.wizard.config_path = cfg_path
        self.wizard.tools = [
            ToolProfile(key="t", name="T", vendor="V", strengths=["coding"], cost_tier="low", available=True),
        ]
        saved = self.wizard.save_config()
        assert saved.exists()

        loaded = self.wizard.load_config()
        assert loaded is not None
        assert loaded["version"] == "1.0.0"
        assert "t" in loaded["tools"]

    def test_load_config_missing_file(self, tmp_path):
        self.wizard.config_path = tmp_path / "nope.json"
        assert self.wizard.load_config() is None

    def test_validate_config_valid(self):
        config = {
            "version": "1.0.0",
            "tools": {"claude": {"name": "Claude"}},
            "routing": {"coding": {"primary": "claude"}},
        }
        assert SetupWizard.validate_config(config) == []

    def test_validate_config_missing_version(self):
        config = {"tools": {}, "routing": {}}
        errors = SetupWizard.validate_config(config)
        assert any("version" in e for e in errors)

    def test_validate_config_missing_tools(self):
        config = {"version": "1.0.0"}
        errors = SetupWizard.validate_config(config)
        assert any("tools" in e for e in errors)

    def test_validate_config_bad_routing_ref(self):
        config = {
            "version": "1.0.0",
            "tools": {"claude": {}},
            "routing": {"coding": {"primary": "nonexistent"}},
        }
        errors = SetupWizard.validate_config(config)
        assert any("nonexistent" in e for e in errors)

    def test_validate_config_not_dict(self):
        errors = SetupWizard.validate_config("bad")
        assert any("dict" in e for e in errors)

    @patch("shutil.which", return_value="/usr/bin/mytool")
    @patch("subprocess.run")
    def test_register_tool(self, mock_run, _):
        mock_run.return_value = type("R", (), {"stdout": "mytool 2.0\n", "returncode": 0})()
        profile = self.wizard.register_tool(
            key="mytool", name="My Tool", vendor="Me",
            strengths=["coding"], check_cmd=["mytool", "--version"], cost_tier="low",
        )
        assert profile.key == "mytool"
        assert profile.available is True
        assert any(t.key == "mytool" for t in self.wizard.tools)

    def test_register_tool_validation(self):
        with pytest.raises(ValueError, match="key and name"):
            self.wizard.register_tool("", "", "V", [], [], "low")
        with pytest.raises(ValueError, match="cost_tier"):
            self.wizard.register_tool("k", "N", "V", [], [], "invalid")

    def test_register_replaces_existing(self):
        self.wizard.tools = [
            ToolProfile(key="x", name="Old", vendor="V", strengths=[], cost_tier="low"),
        ]
        with patch("shutil.which", return_value=None):
            self.wizard.register_tool("x", "New", "V", ["coding"], ["x"], "medium")
        assert len([t for t in self.wizard.tools if t.key == "x"]) == 1
        assert self.wizard.tools[-1].name == "New"

    def test_unregister_tool(self):
        self.wizard.tools = [
            ToolProfile(key="x", name="X", vendor="V", strengths=[], cost_tier="low"),
        ]
        assert self.wizard.unregister_tool("x") is True
        assert len(self.wizard.tools) == 0

    def test_unregister_missing(self):
        assert self.wizard.unregister_tool("nonexistent") is False

    def test_summary_with_tools(self):
        self.wizard.tools = [
            ToolProfile(key="a", name="ToolA", vendor="VendorA",
                        strengths=["coding"], cost_tier="low", available=True, version="1.0"),
        ]
        s = self.wizard.summary()
        assert "ToolA" in s
        assert "VendorA" in s
        assert "v1.0" in s
