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
    strengths: list
    cost_tier: str
    available: bool = False
    version: Optional[str] = None
    user_preference: Optional[int] = None


def discover_tools() -> list[ToolProfile]:
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
                    check_cmd, capture_output=True, timeout=5,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                version = result.stdout.decode().strip().split("\n")[0][:80]
                profile.version = version if version else None
            except Exception:
                pass
        tools.append(profile)
    return tools


class SetupWizard:
    CONFIG_DIR = Path.home() / ".rolemesh"
    CONFIG_PATH = CONFIG_DIR / "config.json"

    def __init__(self):
        self._tools: list[ToolProfile] = []
        self._custom_tools: dict = {}

    def discover(self):
        self._tools = discover_tools()

    def available_tools(self) -> list[ToolProfile]:
        return [t for t in self._tools if t.available]

    def rank_tools(self, task_type: str) -> list[ToolProfile]:
        def score(t: ToolProfile) -> tuple:
            return (
                0 if task_type in t.strengths else 1,
                t.user_preference or 999,
                {"low": 0, "medium": 1, "high": 2}.get(t.cost_tier, 1),
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

        return {"version": "1.0.0", "tools": tools_dict, "routing": routing}

    def save_config(self, path: Optional[Path] = None):
        path = path or self.CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        config = self.build_config()
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

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

        tool_keys = set(config.get("tools", {}).keys())
        for task_type, rule in config.get("routing", {}).items():
            primary = rule.get("primary")
            fallback = rule.get("fallback")
            if primary and primary not in tool_keys:
                errors.append(f"routing[{task_type}].primary '{primary}' not in tools")
            if fallback and fallback not in tool_keys:
                errors.append(f"routing[{task_type}].fallback '{fallback}' not in tools")
        return errors

    def register_tool(self, key: str, name: str, vendor: str,
                      strengths: list, check_cmd: list,
                      cost_tier: str = "medium") -> ToolProfile:
        profile = ToolProfile(
            key=key, name=name, vendor=vendor,
            strengths=strengths, cost_tier=cost_tier,
        )
        if shutil.which(check_cmd[0]):
            profile.available = True
            try:
                result = subprocess.run(
                    check_cmd, capture_output=True, timeout=5,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                version = result.stdout.decode().strip().split("\n")[0][:80]
                profile.version = version if version else None
            except Exception:
                pass
        self._tools.append(profile)
        self._custom_tools[key] = True
        TOOL_REGISTRY[key] = {
            "name": name, "vendor": vendor,
            "strengths": strengths, "check_cmd": check_cmd,
            "cost_tier": cost_tier,
        }
        return profile

    def unregister_tool(self, key: str) -> bool:
        self._tools = [t for t in self._tools if t.key != key]
        self._custom_tools.pop(key, None)
        TOOL_REGISTRY.pop(key, None)
        return True

    def interactive_setup(self) -> dict:
        self.discover()
        available = self.available_tools()
        print(self.summary())

        for tool in available:
            prompt = f"\n  Rank for {tool.name} ({tool.vendor})? [1-{len(available)}, Enter=skip]: "
            try:
                val = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if val and val.isdigit():
                tool.user_preference = int(val)

        config = self.build_config()
        errors = self.validate_config(config)
        if errors:
            print(f"  Warnings: {errors}")

        save_prompt = input("\n  Save config? [y/N]: ").strip().lower()
        if save_prompt == "y":
            path = self.save_config()
            print(f"  Saved to {self.CONFIG_PATH}")

        return config

    def summary(self) -> str:
        available = self.available_tools()
        lines = [f"RoleMesh: {len(available)}/{len(self._tools)} tools available"]
        for t in self._tools:
            status = "[OK]" if t.available else "[--]"
            ver = f" ({t.version})" if t.version else ""
            lines.append(f"  {status} {t.name}{ver} — {t.vendor}, {t.cost_tier}")
        return "\n".join(lines)


def main():
    wizard = SetupWizard()
    wizard.discover()
    print(wizard.summary())


if __name__ == "__main__":
    main()
