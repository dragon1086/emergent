"""
rolemesh/builder.py - AI Tool Discovery & Setup Wizard

Discovers installed AI CLI tools, profiles their capabilities,
and builds a routing configuration.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


TOOL_REGISTRY = {
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
        "strengths": ["coding", "refactoring", "quick-edit", "analysis", "completion"],
        "check_cmd": ["codex", "--version"],
        "cost_tier": "medium",
    },
    "gemini": {
        "name": "Gemini CLI",
        "vendor": "Google",
        "strengths": ["coding", "analysis", "reasoning", "multimodal", "search", "explain"],
        "check_cmd": ["gemini", "--version"],
        "cost_tier": "medium",
    },
    "aider": {
        "name": "Aider",
        "vendor": "Community",
        "strengths": ["coding", "refactoring", "quick-edit", "git-integration", "pair-programming"],
        "check_cmd": ["aider", "--version"],
        "cost_tier": "low",
    },
    "copilot": {
        "name": "GitHub Copilot CLI",
        "vendor": "GitHub",
        "strengths": ["coding", "completion", "explain", "quick-edit"],
        "check_cmd": ["gh", "copilot", "--version"],
        "cost_tier": "medium",
    },
    "cursor": {
        "name": "Cursor",
        "vendor": "Cursor",
        "strengths": ["coding", "refactoring", "frontend", "completion", "pair-programming"],
        "check_cmd": ["cursor", "--version"],
        "cost_tier": "medium",
    },
}


@dataclass
class ToolProfile:
    key: str
    name: str
    vendor: str
    strengths: list[str]
    cost_tier: str
    available: bool = False
    version: Optional[str] = None
    user_preference: Optional[int] = None


def discover_tools() -> list[ToolProfile]:
    """Probe the system for all known AI CLI tools."""
    tools = []
    for key, info in TOOL_REGISTRY.items():
        profile = ToolProfile(
            key=key,
            name=info["name"],
            vendor=info["vendor"],
            strengths=list(info["strengths"]),
            cost_tier=info["cost_tier"],
        )
        check_cmd = info["check_cmd"]
        if shutil.which(check_cmd[0]):
            profile.available = True
            try:
                result = subprocess.run(
                    check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                version = result.stdout.strip().split(b"\n")[0].decode()
                profile.version = version[:80] if version else None
            except Exception:
                pass
        tools.append(profile)
    return tools


class SetupWizard:
    CONFIG_DIR = Path.home() / ".rolemesh"
    CONFIG_PATH = Path.home() / ".rolemesh" / "config.json"

    def __init__(self):
        self._tools: list[ToolProfile] = []
        self._custom_tools: list[str] = []

    def discover(self) -> list[ToolProfile]:
        self._tools = discover_tools()
        return self._tools

    def available_tools(self) -> list[ToolProfile]:
        return [t for t in self._tools if t.available]

    def rank_tools(self, task_type: str) -> list[ToolProfile]:
        cost_order = {"low": 0, "medium": 1, "high": 2}

        def score(t: ToolProfile) -> tuple:
            return (
                0 if task_type in t.strengths else 1,
                t.user_preference if t.user_preference is not None else 999,
                cost_order.get(t.cost_tier, 1),
            )

        return sorted(self.available_tools(), key=score)

    def build_config(self) -> dict:
        all_types = set()
        for t in self._tools:
            all_types.update(t.strengths)

        tools_dict = {}
        for t in self._tools:
            tools_dict[t.key] = {
                "key": t.key,
                "name": t.name,
                "vendor": t.vendor,
                "strengths": t.strengths,
                "cost_tier": t.cost_tier,
                "available": t.available,
                "version": t.version,
            }

        routing = {}
        for task_type in sorted(all_types):
            ranked = self.rank_tools(task_type)
            routing[task_type] = {
                "primary": ranked[0].key if len(ranked) > 0 else None,
                "fallback": ranked[1].key if len(ranked) > 1 else None,
            }

        return {
            "version": "1.0.0",
            "tools": tools_dict,
            "routing": routing,
        }

    def save_config(self, path: Optional[Path] = None) -> Path:
        path = path or self.CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        config = self.build_config()
        path.write_text(json.dumps(config, indent=2))
        return path

    def load_config(self, path: Optional[Path] = None) -> Optional[dict]:
        path = path or self.CONFIG_PATH
        if path.exists():
            return json.loads(path.read_text())
        return None

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if "version" not in config:
            errors.append("missing 'version' field")
        if "tools" not in config:
            errors.append("missing 'tools' field")
        if "routing" not in config:
            errors.append("missing 'routing' field")

        if "routing" in config and "tools" in config:
            tool_keys = set(config["tools"].keys())
            for task_type, rule in config["routing"].items():
                primary = rule.get("primary")
                fallback = rule.get("fallback")
                if primary and primary not in tool_keys:
                    errors.append(f"routing[{task_type}].primary '{primary}' not in tools")
                if fallback and fallback not in tool_keys:
                    errors.append(f"routing[{task_type}].fallback '{fallback}' not in tools")

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
        profile = ToolProfile(
            key=key, name=name, vendor=vendor,
            strengths=strengths, cost_tier=cost_tier,
        )
        if shutil.which(check_cmd[0]):
            profile.available = True
            try:
                result = subprocess.run(
                    check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                version = result.stdout.strip().split(b"\n")[0].decode()
                profile.version = version[:80] if version else None
            except Exception:
                pass
        self._tools.append(profile)
        self._custom_tools.append(key)
        TOOL_REGISTRY[key] = {
            "name": name, "vendor": vendor,
            "strengths": strengths, "check_cmd": check_cmd,
            "cost_tier": cost_tier,
        }
        return profile

    def unregister_tool(self, key: str) -> bool:
        self._tools = [t for t in self._tools if t.key != key]
        self._custom_tools = [k for k in self._custom_tools if k != key]
        TOOL_REGISTRY.pop(key, None)
        return True

    def interactive_setup(self) -> dict:
        """Run interactive setup: discover tools, let user set preferences, save config."""
        self.discover()
        available = self.available_tools()

        print("\n=== RoleMesh Interactive Setup ===\n")
        print(self.summary())

        if not available:
            print("\nNo AI CLI tools found. Install at least one tool and re-run.")
            return self.build_config()

        print(f"\nFound {len(available)} tool(s). Set preference order (1=highest).")
        print("Press Enter to skip (auto-rank by capability match).\n")

        for tool in available:
            prompt = f"  Preference for {tool.name} [{tool.vendor}] (1-{len(available)}, Enter=auto): "
            try:
                val = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSkipping preferences.")
                break
            if val.isdigit():
                tool.user_preference = int(val)

        config = self.build_config()
        errors = self.validate_config(config)
        if errors:
            print(f"\nWarnings: {errors}")

        try:
            save_prompt = input("\nSave config? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            save_prompt = "n"

        if save_prompt in ("", "y", "yes"):
            path = self.save_config()
            print(f"Config saved to: {path}")
        else:
            print("Config not saved.")

        return config

    def summary(self) -> str:
        available = self.available_tools()
        lines = [f"RoleMesh: {len(available)}/{len(self._tools)} tools available"]
        for t in self._tools:
            status = "OK" if t.available else "--"
            ver = f" ({t.version})" if t.version else ""
            lines.append(f"  [{status}] {t.name}{ver} — {t.vendor}, {t.cost_tier}")
        return "\n".join(lines)


def main():
    wizard = SetupWizard()
    wizard.discover()
    print(wizard.summary())


if __name__ == "__main__":
    main()
