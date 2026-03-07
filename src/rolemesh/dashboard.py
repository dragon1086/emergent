"""
rolemesh/dashboard.py - Dashboard CLI

Displays a unified view of discovered tools, routing config,
task type coverage, and config health.

Usage:
    python -m src.rolemesh dashboard              # full dashboard
    python -m src.rolemesh dashboard --tools       # tools only
    python -m src.rolemesh dashboard --routing     # routing table only
    python -m src.rolemesh dashboard --coverage    # task coverage matrix
    python -m src.rolemesh dashboard --health      # config health check
    python -m src.rolemesh dashboard --history     # execution history
    python -m src.rolemesh dashboard --json        # JSON output
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import builder as builder
from .builder import SetupWizard, ToolProfile, TOOL_REGISTRY, discover_tools
from . import router as router
from .router import RoleMeshRouter, TASK_PATTERNS


class Color:
    """ANSI color helper. Respects NO_COLOR env var and non-TTY detection."""
    _enabled: bool = True
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    @classmethod
    def set_enabled(cls, enabled: bool):
        cls._enabled = enabled

    @classmethod
    def is_enabled(cls) -> bool:
        if cls._enabled is False:
            return False
        if os.environ.get("NO_COLOR"):
            return False
        return sys.stdout.isatty()

    @classmethod
    def wrap(cls, text: str, *codes: str) -> str:
        if not cls.is_enabled():
            return text
        return "".join(codes) + text + cls.RESET

    @classmethod
    def bold(cls, text: str) -> str:
        return cls.wrap(text, cls.BOLD)

    @classmethod
    def green(cls, text: str) -> str:
        return cls.wrap(text, cls.GREEN)

    @classmethod
    def red(cls, text: str) -> str:
        return cls.wrap(text, cls.RED)

    @classmethod
    def yellow(cls, text: str) -> str:
        return cls.wrap(text, cls.YELLOW)

    @classmethod
    def cyan(cls, text: str) -> str:
        return cls.wrap(text, cls.CYAN)

    @classmethod
    def dim(cls, text: str) -> str:
        return cls.wrap(text, cls.DIM)


@dataclass
class HealthCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class DashboardData:
    tools: list = field(default_factory=list)
    config: Optional[dict] = None
    routing: dict = field(default_factory=dict)
    health: list = field(default_factory=list)
    history: list = field(default_factory=list)


class RoleMeshDashboard:
    CONFIG_PATH = Path.home() / ".rolemesh" / "config.json"
    HISTORY_PATH = Path.home() / ".rolemesh" / "history.jsonl"

    def __init__(self, config_path: Optional[Path] = None, history_path: Optional[Path] = None):
        self._config_path = config_path or self.CONFIG_PATH
        self._history_path = history_path or self.HISTORY_PATH
        self._data = DashboardData()

    def collect(self) -> DashboardData:
        self._data.tools = discover_tools()

        wizard = SetupWizard()
        self._data.config = wizard.load_config(self._config_path)

        if self._data.config:
            self._data.routing = self._data.config.get("routing", {})

        self._data.health = self._run_health_checks()

        if self._history_path.exists():
            lines = self._history_path.read_text().strip().split("\n")
            self._data.history = []
            for line in lines:
                try:
                    self._data.history.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return self._data

    def _run_health_checks(self) -> list[HealthCheck]:
        checks = []

        # 1. config_file
        if self._config_path.exists():
            checks.append(HealthCheck("config_file", True, str(self._config_path)))
        else:
            checks.append(HealthCheck("config_file", False, "Config not found. Run: setup --save"))

        # 2. tools_available
        available = [t for t in self._data.tools if t.available]
        if available:
            checks.append(HealthCheck("tools_available", True, f"{len(available)} tool(s) found"))
        else:
            checks.append(HealthCheck("tools_available", False, "No AI CLI tools installed"))

        # 3. routing_coverage
        all_types = set(tp[0] for tp in TASK_PATTERNS)
        if self._data.routing:
            covered = set(self._data.routing.keys())
            missing = all_types - covered
            if not missing:
                checks.append(HealthCheck("routing_coverage", True, f"All {len(all_types)} task types covered"))
            else:
                checks.append(HealthCheck("routing_coverage", False, "Missing: " + ", ".join(sorted(missing))))
        else:
            checks.append(HealthCheck("routing_coverage", False, "Missing: " + ", ".join(sorted(all_types))))

        # 4. config_version
        if self._data.config:
            version = self._data.config.get("version", "unknown")
            checks.append(HealthCheck("config_version", version == "1.0.0", f"v{version}"))
        else:
            checks.append(HealthCheck("config_version", False, "No config loaded"))

        # 5. no_dead_refs
        if self._data.config:
            tool_keys = set(self._data.config.get("tools", {}).keys())
            dead = set()
            for task_type, rule in self._data.config.get("routing", {}).items():
                for ref_key in ("primary", "fallback"):
                    ref = rule.get(ref_key)
                    if ref and ref not in tool_keys:
                        dead.add(f"{task_type}.{ref_key}={ref}")
            if not dead:
                checks.append(HealthCheck("no_dead_refs", True, "Clean"))
            else:
                checks.append(HealthCheck("no_dead_refs", False, "Dead: " + ", ".join(sorted(dead))))
        else:
            checks.append(HealthCheck("no_dead_refs", False, "No config loaded"))

        return checks

    def render_full(self) -> str:
        sections = [
            self._header(),
            self.render_tools(),
            self.render_routing(),
            self.render_coverage(),
            self.render_health(),
        ]
        if self._data.history:
            sections.append(self.render_history())
        return "\n".join(sections)

    def _header(self) -> str:
        avail = sum(1 for t in self._data.tools if t.available)
        total = len(self._data.tools)
        passed = sum(1 for h in self._data.health if h.passed)
        total_checks = len(self._data.health)

        return "\n".join([
            "  " + Color.bold("RoleMesh Dashboard"),
            f"  Tools: {avail}/{total} available | Health: "
            + (Color.green if passed == total_checks else Color.yellow)(f"{passed}/{total_checks} checks passed"),
            "  " + "=" * 60,
        ])

    def render_tools(self) -> str:
        lines = ["\n", Color.bold("[ Tools ]")]
        lines.append(
            f"  {Color.bold(f'{'Name':<22}')} "
            f"{Color.bold(f'{'Vendor':<12}')} "
            f"{Color.bold(f'{'Cost':<8}')} "
            f"{Color.bold(f'{'Status':<10}')} "
            f"{Color.bold('Version')}"
        )
        lines.append(f"  {'─' * 22} {'─' * 12} {'─' * 8} {'─' * 10} {'─' * 20}")

        for t in self._data.tools:
            status = Color.green("OK") if t.available else Color.dim("--")
            ver = t.version if t.version else ""
            if len(ver) > 20:
                ver = ver[:17] + "..."
            lines.append(
                f"  {t.name:<22} {t.vendor:<12} {t.cost_tier:<8} {status:<10} {ver}"
            )

        return "\n".join(lines)

    def render_routing(self) -> str:
        lines = ["\n", Color.bold("[ Routing Table ]")]

        if not self._data.config:
            lines.append(Color.dim("  No routing config. Run: setup --save"))
            return "\n".join(lines)

        lines.append(
            f"  {Color.bold(f'{'Task Type':<20}')} "
            f"{Color.bold(f'{'Primary':<16}')} "
            f"{Color.bold('Fallback')}"
        )
        lines.append(f"  {'─' * 20} {'─' * 16} {'─' * 16}")

        tools_map = self._data.config.get("tools", {})
        for task_type in sorted(self._data.routing.keys()):
            rule = self._data.routing[task_type]
            primary_key = rule.get("primary", "--")
            fallback_key = rule.get("fallback")
            primary_name = tools_map.get(primary_key, {}).get("name", primary_key) if primary_key else "--"
            fallback_name = tools_map.get(fallback_key, {}).get("name", fallback_key) if fallback_key else "--"
            lines.append(f"  {task_type:<20} {primary_name:<16} {fallback_name}")

        return "\n".join(lines)

    def render_coverage(self) -> str:
        lines = ["\n", Color.bold("[ Coverage Matrix ]")]

        avail_tools = [t for t in self._data.tools if t.available]
        if not avail_tools:
            lines.append(Color.dim("  No tools available."))
            return "\n".join(lines)

        # Header
        header = f"  {'Task Type':<20}"
        for t in avail_tools:
            header += f" {t.key:^8}"
        lines.append(header)
        lines.append(f"  {'─' * 20}" + " ────────" * len(avail_tools))

        for task_type, _ in sorted(TASK_PATTERNS):
            row = f"  {task_type:<20}"
            for t in avail_tools:
                if task_type in t.strengths:
                    row += f" {Color.green('*'):^8}"
                else:
                    row += f" {Color.dim('.'):^8}"
            lines.append(row)

        return "\n".join(lines)

    def render_health(self) -> str:
        lines = ["\n", Color.bold("[ Health ]")]

        for check in self._data.health:
            status = Color.green("PASS") if check.passed else Color.red("FAIL")
            lines.append(f"  [{status}] {check.name}: {check.detail}")

        return "\n".join(lines)

    def render_history(self) -> str:
        lines = ["\n", Color.bold("[ Recent History ]")]
        lines.append(
            f"  {Color.bold(f'{'Time':<20}')} "
            f"{Color.bold(f'{'Tool':<12}')} "
            f"{Color.bold(f'{'Task':<16}')} "
            f"{Color.bold(f'{'Status':<8}')} "
            f"{Color.bold(f'{'ms':>6}')}"
        )
        lines.append(f"  {'─' * 20} {'─' * 12} {'─' * 16} {'─' * 8} {'─' * 6}")

        for entry in self._data.history[-10:]:
            ts = entry.get("timestamp", "?")
            tool = entry.get("tool", "?")
            task = entry.get("task_type", "?")
            success = entry.get("success", False)
            status = Color.green("OK") if success else Color.red("FAIL")
            ms = str(entry.get("duration_ms", "?"))
            lines.append(f"  {ts:<20} {tool:<12} {task:<16} {status:<8} {ms:>6}")

        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "tools": [
                {
                    "key": t.key, "name": t.name, "vendor": t.vendor,
                    "strengths": t.strengths, "cost_tier": t.cost_tier,
                    "available": t.available, "version": t.version,
                }
                for t in self._data.tools
            ],
            "routing": self._data.routing,
            "health": [
                {"name": h.name, "passed": h.passed, "detail": h.detail}
                for h in self._data.health
            ],
            "history": self._data.history,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RoleMesh Dashboard")
    parser.add_argument("--tools", action="store_true", help="Show tools only")
    parser.add_argument("--routing", action="store_true", help="Show routing table")
    parser.add_argument("--coverage", action="store_true", help="Show coverage matrix")
    parser.add_argument("--health", action="store_true", help="Show health checks")
    parser.add_argument("--history", action="store_true", help="Show execution history")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--config", type=str, help="Config path override")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    dash = RoleMeshDashboard(config_path=config_path)
    dash.collect()

    if args.json:
        print(json.dumps(dash.to_json(), indent=2))
    elif args.tools:
        print(dash.render_tools())
    elif args.routing:
        print(dash.render_routing())
    elif args.coverage:
        print(dash.render_coverage())
    elif args.health:
        print(dash.render_health())
    elif args.history:
        print(dash.render_history())
    else:
        print(dash.render_full())


if __name__ == "__main__":
    main()
