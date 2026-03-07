"""
rolemesh/builder.py - AI Tool Discovery & Setup Wizard

Discovers installed AI CLI tools, profiles their capabilities,
and builds a routing configuration.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

TOOL_REGISTRY = {
    "claude": {
        "name": "Claude Code",
        "vendor": "Anthropic",
        "strengths": [
            "coding", "refactoring", "analysis", "architecture",
            "reasoning", "explain", "pair-programming",
        ],
        "check_cmd": ["claude", "--version"],
        "cost_tier": "high",
    },
    "codex": {
        "name": "Codex CLI",
        "vendor": "OpenAI",
        "strengths": [
            "coding", "refactoring", "quick-edit", "completion",
            "git-integration",
        ],
        "check_cmd": ["codex", "--version"],
        "cost_tier": "medium",
    },
    "gemini": {
        "name": "Gemini CLI",
        "vendor": "Google",
        "strengths": [
            "coding", "multimodal", "search", "explain",
            "frontend", "analysis",
        ],
        "check_cmd": ["gemini", "--version"],
        "cost_tier": "medium",
    },
    "aider": {
        "name": "Aider",
        "vendor": "Community",
        "strengths": [
            "coding", "refactoring", "quick-edit", "git-integration",
        ],
        "check_cmd": ["aider", "--version"],
        "cost_tier": "low",
    },
    "copilot": {
        "name": "GitHub Copilot CLI",
        "vendor": "GitHub",
        "strengths": ["coding", "completion", "explain"],
        "check_cmd": ["gh", "copilot", "--version"],
        "cost_tier": "medium",
    },
    "cursor": {
        "name": "Cursor",
        "vendor": "Cursor",
        "strengths": [
            "coding", "refactoring", "frontend", "completion",
        ],
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
    profiles = []
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
                    check_cmd,
                    capture_output=True, text=True, timeout=10,
                )
                version_text = (result.stdout or result.stderr).strip()
                if version_text:
                    profile.version = version_text.split("\n")[0][:80]
            except Exception:
                pass
        profiles.append(profile)
    return profiles


class SetupWizard:
    CONFIG_DIR = Path.home() / ".rolemesh"
    CONFIG_PATH = CONFIG_DIR / "config.json"

    def __init__(self):
        self._tools: list[ToolProfile] = []
        self._custom_tools: dict[str, ToolProfile] = {}

    def discover(self) -> list[ToolProfile]:
        self._tools = discover_tools()
        return self._tools

    def available_tools(self) -> list[ToolProfile]:
        return [t for t in self._tools if t.available]

    def rank_tools(self, task_type: str) -> list[ToolProfile]:
        available = self.available_tools()
        cost_order = {"low": 0, "medium": 1, "high": 2}

        def score(t: ToolProfile) -> tuple:
            has_strength = task_type in t.strengths
            pref = t.user_preference if t.user_preference is not None else 999
            cost = cost_order.get(t.cost_tier, 1)
            return (not has_strength, pref, cost)

        return sorted(available, key=score)

    def build_config(self) -> dict:
        all_task_types = set()
        for t in self._tools:
            all_task_types.update(t.strengths)

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
        for task_type in sorted(all_task_types):
            ranked = self.rank_tools(task_type)
            if ranked:
                primary = ranked[0].key
                fallback = ranked[1].key if len(ranked) > 1 else None
                routing[task_type] = {"primary": primary, "fallback": fallback}

        return {
            "version": "1.0.0",
            "tools": tools_dict,
            "routing": routing,
        }

    def save_config(self, path: Optional[Path] = None) -> Path:
        config_path = path or self.CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = self.build_config()
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return config_path

    def load_config(self, path: Optional[Path] = None) -> Optional[dict]:
        config_path = path or self.CONFIG_PATH
        if config_path.exists():
            return json.loads(config_path.read_text())
        return None

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if "version" not in config:
            errors.append("missing 'version' field")
        if "tools" not in config:
            errors.append("missing 'tools' field")
        if "routing" not in config:
            errors.append("missing 'routing' field")
        if errors:
            return errors

        tool_keys = set(config["tools"].keys())
        for task_type, rule in config.get("routing", {}).items():
            primary = rule.get("primary")
            fallback = rule.get("fallback")
            if primary and primary not in tool_keys:
                errors.append(f"routing[{task_type}].primary '{primary}' not in tools")
            if fallback and fallback not in tool_keys:
                errors.append(f"routing[{task_type}].fallback '{fallback}' not in tools")
        return errors

    def register_tool(
        self, key: str, name: str, vendor: str,
        strengths: list[str], check_cmd: list[str], cost_tier: str,
    ) -> ToolProfile:
        profile = ToolProfile(
            key=key, name=name, vendor=vendor,
            strengths=strengths, cost_tier=cost_tier,
        )
        if shutil.which(check_cmd[0]):
            profile.available = True
            try:
                result = subprocess.run(
                    check_cmd, capture_output=True, text=True, timeout=10,
                )
                ver = (result.stdout or result.stderr).strip()
                if ver:
                    profile.version = ver.split("\n")[0][:80]
            except Exception:
                pass
        self._tools.append(profile)
        self._custom_tools[key] = profile
        TOOL_REGISTRY[key] = {
            "name": name, "vendor": vendor, "strengths": strengths,
            "check_cmd": check_cmd, "cost_tier": cost_tier,
        }
        return profile

    def unregister_tool(self, key: str) -> bool:
        self._tools = [t for t in self._tools if t.key != key]
        removed = key in self._custom_tools or key in TOOL_REGISTRY
        self._custom_tools.pop(key, None)
        TOOL_REGISTRY.pop(key, None)
        return removed

    def summary(self) -> str:
        available = self.available_tools()
        total = len(self._tools)
        lines = [f"RoleMesh: {len(available)}/{total} tools available"]
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
