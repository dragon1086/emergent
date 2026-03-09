#!/usr/bin/env python3
"""
rolemesh/builder.py - AI Tool Discovery & Setup Wizard

Discovers installed AI CLI tools, profiles their capabilities,
and builds a routing config so tasks go to the right tool.

Usage:
    python -m src.rolemesh.builder              # auto-discover
    python -m src.rolemesh.builder --interactive # guided setup
    python -m src.rolemesh.builder --json        # JSON output
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# --- Tool Registry (known AI CLIs and their strengths) ---

TOOL_REGISTRY: dict[str, dict] = {
    "claude": {
        "name": "Claude Code",
        "vendor": "Anthropic",
        "strengths": ["coding", "analysis", "reasoning", "architecture"],
        "check_cmd": ["claude", "--version"],
        "cost_tier": "high",
    },
    "codex": {
        "name": "Codex CLI",
        "vendor": "OpenAI",
        "strengths": ["coding", "refactoring", "quick-edit"],
        "check_cmd": ["codex", "--version"],
        "cost_tier": "medium",
    },
    "gemini": {
        "name": "Gemini CLI",
        "vendor": "Google",
        "strengths": ["multimodal", "search", "ui-design", "frontend"],
        "check_cmd": ["gemini", "--version"],
        "cost_tier": "medium",
    },
    "aider": {
        "name": "Aider",
        "vendor": "Community",
        "strengths": ["coding", "git-integration", "pair-programming"],
        "check_cmd": ["aider", "--version"],
        "cost_tier": "low",
    },
    "copilot": {
        "name": "GitHub Copilot CLI",
        "vendor": "GitHub",
        "strengths": ["completion", "quick-edit", "explain"],
        "check_cmd": ["gh", "copilot", "--version"],
        "cost_tier": "low",
    },
    "cursor": {
        "name": "Cursor",
        "vendor": "Cursor",
        "strengths": ["coding", "ui", "inline-edit"],
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
    cost_tier: str  # low, medium, high
    available: bool = False
    version: Optional[str] = None
    user_preference: int = 0  # 0=neutral, 1=preferred, -1=avoid

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
        if not available:
            return []

        def relevance(tool: ToolProfile) -> float:
            score = 0.0
            if task_type in tool.strengths:
                score += 10.0
            # prefer user-preferred tools
            score += tool.user_preference * 5.0
            # prefer cheaper tools for simple tasks
            cost_map = {"low": 2.0, "medium": 1.0, "high": 0.0}
            score += cost_map.get(tool.cost_tier, 0.0)
            return score

        return sorted(available, key=relevance, reverse=True)

    def build_config(self) -> dict:
        """Build routing config from discovered tools."""
        available = self.available_tools()
        task_types = set()
        for t in available:
            task_types.update(t.strengths)

        routing = {}
        for task_type in sorted(task_types):
            ranked = self.rank_tools(task_type)
            if ranked:
                routing[task_type] = {
                    "primary": ranked[0].key,
                    "fallback": ranked[1].key if len(ranked) > 1 else None,
                }

        return {
            "version": "1.0.0",
            "tools": {t.key: t.to_dict() for t in available},
            "routing": routing,
        }

    def save_config(self, path: Optional[Path] = None) -> Path:
        """Persist config to disk."""
        target = path or self.config_path
        target.parent.mkdir(parents=True, exist_ok=True)
        config = self.build_config()
        target.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return target

    def load_config(self, path: Optional[Path] = None) -> dict:
        """Load existing config."""
        target = path or self.config_path
        if target.exists():
            return json.loads(target.read_text())
        return {}

    @staticmethod
    def validate_config(config: dict) -> list[str]:
        """
        Validate a config dict against the expected schema.
        Returns list of error strings (empty = valid).
        """
        errors: list[str] = []

        if not isinstance(config, dict):
            return ["Config must be a dict"]

        # version
        if "version" not in config:
            errors.append("Missing 'version' field")
        elif not isinstance(config["version"], str):
            errors.append("'version' must be a string")

        # tools
        if "tools" not in config:
            errors.append("Missing 'tools' field")
        elif not isinstance(config["tools"], dict):
            errors.append("'tools' must be a dict")
        else:
            for key, tool in config["tools"].items():
                if not isinstance(tool, dict):
                    errors.append(f"tools['{key}'] must be a dict")

        # routing
        if "routing" not in config:
            errors.append("Missing 'routing' field")
        elif not isinstance(config["routing"], dict):
            errors.append("'routing' must be a dict")
        else:
            tool_keys = set(config.get("tools", {}).keys())
            for task_type, rule in config["routing"].items():
                if not isinstance(rule, dict):
                    errors.append(f"routing['{task_type}'] must be a dict")
                    continue
                if "primary" not in rule:
                    errors.append(f"routing['{task_type}'] missing 'primary'")
                elif rule["primary"] and rule["primary"] not in tool_keys:
                    errors.append(
                        f"routing['{task_type}'].primary '{rule['primary']}' "
                        f"not found in tools"
                    )
                fb = rule.get("fallback")
                if fb and fb not in tool_keys:
                    errors.append(
                        f"routing['{task_type}'].fallback '{fb}' "
                        f"not found in tools"
                    )

        return errors

    def register_tool(self, key: str, name: str, vendor: str,
                       strengths: list[str], check_cmd: list[str],
                       cost_tier: str = "medium") -> ToolProfile:
        """
        Register a custom AI tool into the registry and discover it.
        Returns the created ToolProfile.
        """
        if cost_tier not in ("low", "medium", "high"):
            raise ValueError(f"cost_tier must be low/medium/high, got '{cost_tier}'")
        if not key or not name:
            raise ValueError("key and name are required")

        TOOL_REGISTRY[key] = {
            "name": name,
            "vendor": vendor,
            "strengths": strengths,
            "check_cmd": check_cmd,
            "cost_tier": cost_tier,
        }

        profile = ToolProfile(
            key=key, name=name, vendor=vendor,
            strengths=strengths, cost_tier=cost_tier,
        )
        # Probe availability
        binary = check_cmd[0] if check_cmd else ""
        if binary and shutil.which(binary):
            profile.available = True
            try:
                result = subprocess.run(
                    check_cmd, capture_output=True, text=True, timeout=5,
                )
                version_line = result.stdout.strip().split("\n")[0]
                for part in version_line.split():
                    if any(c.isdigit() for c in part):
                        profile.version = part.strip("v").strip(",")
                        break
            except Exception:
                pass

        # Replace existing or append
        self.tools = [t for t in self.tools if t.key != key]
        self.tools.append(profile)
        return profile

    def unregister_tool(self, key: str) -> bool:
        """Remove a custom tool from the registry. Returns True if found."""
        if key not in TOOL_REGISTRY:
            return False
        del TOOL_REGISTRY[key]
        before = len(self.tools)
        self.tools = [t for t in self.tools if t.key != key]
        return len(self.tools) < before or True

    def summary(self) -> str:
        """Human-readable summary of discovered tools."""
        available = self.available_tools()
        if not available:
            return "No AI tools found. Install claude, codex, gemini, or aider to get started."

        lines = [f"Found {len(available)} AI tool(s):"]
        for t in available:
            ver = f" v{t.version}" if t.version else ""
            lines.append(f"  - {t.name}{ver} ({t.vendor}) [{', '.join(t.strengths)}]")
        return "\n".join(lines)


def discover_tools() -> list[ToolProfile]:
    """
    Probe system for all known AI CLI tools.
    Returns list of ToolProfiles with availability set.
    """
    profiles = []
    for key, info in TOOL_REGISTRY.items():
        profile = ToolProfile(
            key=key,
            name=info["name"],
            vendor=info["vendor"],
            strengths=info["strengths"],
            cost_tier=info["cost_tier"],
        )

        # Check if binary exists on PATH
        binary = info["check_cmd"][0]
        if shutil.which(binary):
            profile.available = True
            # Try to get version
            try:
                result = subprocess.run(
                    info["check_cmd"],
                    capture_output=True, text=True, timeout=5,
                )
                version_line = result.stdout.strip().split("\n")[0]
                # Extract version-like string
                for part in version_line.split():
                    if any(c.isdigit() for c in part):
                        profile.version = part.strip("v").strip(",")
                        break
            except Exception:
                pass

        profiles.append(profile)
    return profiles


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RoleMesh AI Tool Setup Wizard")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Output config as JSON")
    parser.add_argument("--save", action="store_true",
                        help="Save config to ~/.rolemesh/config.json")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Guided setup (set preferences)")
    args = parser.parse_args()

    wizard = SetupWizard()
    wizard.discover()

    if args.interactive:
        print("=== RoleMesh Setup Wizard ===\n")
        print(wizard.summary())
        print()
        for tool in wizard.available_tools():
            resp = input(f"Prefer {tool.name}? [y/n/skip] ").strip().lower()
            if resp == "y":
                tool.user_preference = 1
            elif resp == "n":
                tool.user_preference = -1

    config = wizard.build_config()

    if args.json_out:
        print(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        print(wizard.summary())
        if config.get("routing"):
            print(f"\nRouting rules ({len(config['routing'])} task types):")
            for task, rule in config["routing"].items():
                fb = f" (fallback: {rule['fallback']})" if rule["fallback"] else ""
                print(f"  {task} -> {rule['primary']}{fb}")

    if args.save:
        path = wizard.save_config()
        print(f"\nConfig saved to {path}")


if __name__ == "__main__":
    main()
