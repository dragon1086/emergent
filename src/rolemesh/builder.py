"""
rolemesh/builder.py - AI Tool Discovery & Setup Wizard

Discovers installed AI CLI tools, profiles their capabilities,
and builds a routing configuration.

Usage:
    python -m src.rolemesh.builder              # discover tools
    python -m src.rolemesh.builder --save       # discover + save config
    python -m src.rolemesh.builder --interactive # guided setup
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


TOOL_REGISTRY: dict[str, dict] = {
    "claude": {
        "name": "Claude Code",
        "vendor": "Anthropic",
        "strengths": ["coding", "refactoring", "analysis", "architecture", "reasoning", "explain", "pair-programming"],
        "check_cmd": ["claude", "--version"],
        "cost_tier": "high",
    },
    "codex": {
        "name": "Codex CLI",
        "vendor": "OpenAI",
        "strengths": ["coding", "refactoring", "quick-edit", "completion", "git-integration"],
        "check_cmd": ["codex", "--version"],
        "cost_tier": "medium",
    },
    "gemini": {
        "name": "Gemini CLI",
        "vendor": "Google",
        "strengths": ["coding", "multimodal", "search", "explain", "frontend", "analysis"],
        "check_cmd": ["gemini", "--version"],
        "cost_tier": "medium",
    },
    "aider": {
        "name": "Aider",
        "vendor": "Community",
        "strengths": ["coding", "refactoring", "quick-edit", "git-integration"],
        "check_cmd": ["aider", "--version"],
        "cost_tier": "low",
    },
    "copilot": {
        "name": "GitHub Copilot CLI",
        "vendor": "GitHub",
        "strengths": ["coding", "completion", "explain"],
        "check_cmd": ["copilot", "--version"],
        "cost_tier": "medium",
    },
    "cursor": {
        "name": "Cursor",
        "vendor": "Cursor",
        "strengths": ["coding", "refactoring", "frontend", "completion"],
        "check_cmd": ["cursor", "--version"],
        "cost_tier": "medium",
    },
}


@dataclass
class ToolProfile:
    """Profile of a discovered AI tool."""
    key: str
    name: str
    vendor: str
    strengths: list[str]
    cost_tier: str
    available: bool = False
    version: Optional[str] = None
    user_preference: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SetupWizard:
    """
    Discovers installed AI tools and builds a routing config.

    Flow:
      1. discover_tools() - check which CLIs are installed
      2. rank_tools() - rank by availability + strengths
      3. build_config() - generate routing config
      4. save_config() - persist to ~/.rolemesh/config.json
    """
    tools: list[ToolProfile] = field(default_factory=list)
    config_path: Path = field(default_factory=lambda: Path.home() / ".rolemesh" / "config.json")

    def discover(self) -> list[ToolProfile]:
        """Probe system for installed AI tools."""
        self.tools = discover_tools()
        return self.tools

    def available_tools(self) -> list[ToolProfile]:
        return [t for t in self.tools if t.available]

    def rank_tools(self, task_type: str) -> list[ToolProfile]:
        """
        Rank available tools for a given task type.
        Returns tools sorted by relevance (best first).
        """
        available = self.available_tools()
        return sorted(
            available,
            key=lambda t: (
                task_type in t.strengths,
                t.user_preference or 0,
                t.cost_tier == "low",
            ),
            reverse=True,
        )

    def build_config(self) -> dict:
        """Build routing config from discovered tools."""
        available = self.available_tools()
        all_types: set[str] = set()
        for t in available:
            all_types.update(t.strengths)

        routing = {}
        for task_type in sorted(all_types):
            ranked = self.rank_tools(task_type)
            if ranked:
                routing[task_type] = {"primary": ranked[0].key}
                if len(ranked) > 1:
                    routing[task_type]["fallback"] = ranked[1].key

        return {
            "version": "1.0.0",
            "tools": {t.key: t.to_dict() for t in available},
            "routing": routing,
        }

    def save_config(self, path: Optional[Path] = None) -> Path:
        """Persist config to disk."""
        path = path or self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        config = self.build_config()
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return path

    def load_config(self, path: Optional[Path] = None) -> dict | None:
        """Load existing config."""
        path = path or self.config_path
        if path.exists():
            return json.loads(path.read_text())
        return None

    @staticmethod
    def validate_config(config: dict) -> list[str]:
        """
        Validate a config dict against the expected schema.
        Returns list of error strings (empty = valid).
        """
        errors: list[str] = []
        if not isinstance(config, dict):
            errors.append("Config must be a dict")
            return errors

        if "version" not in config:
            errors.append("Missing 'version' field")
        elif not isinstance(config["version"], str):
            errors.append("'version' must be a string")

        if "tools" not in config:
            errors.append("Missing 'tools' field")
        elif not isinstance(config["tools"], dict):
            errors.append("'tools' must be a dict")
        else:
            for key, val in config["tools"].items():
                if not isinstance(val, dict):
                    errors.append(f"tools['{key}'] must be a dict")

        tool_keys = set(config.get("tools", {}).keys())
        if "routing" in config:
            for task_type, rule in config["routing"].items():
                if isinstance(rule, dict):
                    for role, ref in rule.items():
                        if ref not in tool_keys:
                            errors.append(f"routing['{task_type}'].{role} references unknown tool '{ref}'")

        return errors

    def register_tool(
        self,
        key: str,
        name: str,
        vendor: str,
        strengths: list[str],
        check_cmd: list[str],
        cost_tier: str,
    ) -> ToolProfile:
        """
        Register a custom AI tool into the registry and discover it.
        Returns the created ToolProfile.
        """
        if not key or not name:
            raise ValueError("key and name are required")
        if cost_tier not in ("low", "medium", "high"):
            raise ValueError(f"cost_tier must be low/medium/high, got '{cost_tier}'")

        TOOL_REGISTRY[key] = {
            "name": name,
            "vendor": vendor,
            "strengths": strengths,
            "check_cmd": check_cmd,
            "cost_tier": cost_tier,
        }

        available = bool(shutil.which(check_cmd[0])) if check_cmd else False
        version = None
        if available and check_cmd:
            try:
                result = subprocess.run(check_cmd, capture_output=True, text=True)
                parts = result.stdout.strip().split("\n")
                for prefix in parts:
                    if any(any(c.isdigit() for c in p) for p in prefix.split()):
                        version = prefix.strip()
                        break
            except Exception:
                pass

        profile = ToolProfile(
            key=key,
            name=name,
            vendor=vendor,
            strengths=strengths,
            cost_tier=cost_tier,
            available=available,
            version=version,
        )

        self.tools = [t for t in self.tools if t.key != key]
        self.tools.append(profile)
        return profile

    def unregister_tool(self, key: str) -> bool:
        """Remove a custom tool from the registry. Returns True if found."""
        before = len(self.tools)
        self.tools = [t for t in self.tools if t.key != key]
        TOOL_REGISTRY.pop(key, None)
        return len(self.tools) < before

    def summary(self) -> str:
        """Human-readable summary of discovered tools."""
        available = self.available_tools()
        if not available:
            return "No AI tools found. Install claude, codex, gemini, or aider to get started."

        lines: list[str] = [f"Found {len(available)} AI tool(s):"]
        for t in available:
            ver = f" v{t.version}" if t.version else ""
            lines.append(f"  - {t.name} ({t.vendor}){ver} [{', '.join(t.strengths)}]")
        return "\n".join(lines)


def discover_tools() -> list[ToolProfile]:
    """
    Probe system for all known AI CLI tools.
    Returns list of ToolProfiles with availability set.
    """
    results: list[ToolProfile] = []
    for key, info in TOOL_REGISTRY.items():
        check_cmd = info.get("check_cmd", [])
        available = bool(shutil.which(check_cmd[0])) if check_cmd else False
        version = None

        if available and check_cmd:
            try:
                proc = subprocess.run(check_cmd, capture_output=True, text=True)
                parts = proc.stdout.strip().split("\n")
                for prefix in parts:
                    if any(any(c.isdigit() for c in p) for p in prefix.lstrip().split()):
                        version = prefix.strip()
                        break
            except Exception:
                pass

        results.append(ToolProfile(
            key=key,
            name=info["name"],
            vendor=info["vendor"],
            strengths=info["strengths"],
            cost_tier=info["cost_tier"],
            available=available,
            version=version,
        ))
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser("rolemesh-builder", description="AI Tool Discovery & Setup Wizard")
    parser.add_argument("--save", action="store_true", help="Save config to disk")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    args = parser.parse_args()

    wizard = SetupWizard()
    if args.config:
        wizard.config_path = Path(args.config)
    wizard.discover()

    if args.json_out:
        config = wizard.build_config()
        print(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        print(wizard.summary())

    if args.save:
        wizard.save_config()
        print(f"\nConfig saved to {wizard.config_path}")


if __name__ == "__main__":
    main()
