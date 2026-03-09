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

from .builder import SetupWizard, ToolProfile, TOOL_REGISTRY, discover_tools
from .router import RoleMeshRouter, TASK_PATTERNS


class Color:
    """ANSI color helper. Respects NO_COLOR env var and non-TTY detection."""

    _enabled: Optional[bool] = None

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
        if cls._enabled is not None:
            return cls._enabled
        if os.environ.get("NO_COLOR"):
            return False
        return sys.stdout.isatty()

    @classmethod
    def wrap(cls, text: str, *codes: str) -> str:
        if not cls.is_enabled():
            return text
        prefix = "".join(codes)
        return f"{prefix}{text}{cls.RESET}"

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
    tools: list[ToolProfile] = field(default_factory=list)
    config: Optional[dict] = None
    routing: dict = field(default_factory=dict)
    health: list[HealthCheck] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


class RoleMeshDashboard:
    CONFIG_PATH = Path.home() / ".rolemesh" / "config.json"
    HISTORY_PATH = Path.home() / ".rolemesh" / "history.jsonl"

    def __init__(
        self,
        config_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
    ):
        self._config_path = config_path or self.CONFIG_PATH
        self._history_path = history_path or self.HISTORY_PATH
        self._data = DashboardData()

    def collect(self) -> DashboardData:
        # Discover tools
        self._data.tools = discover_tools()

        # Load config
        wizard = SetupWizard()
        self._data.config = wizard.load_config(self._config_path)

        # Extract routing
        if self._data.config and "routing" in self._data.config:
            self._data.routing = self._data.config["routing"]

        # Health checks
        self._data.health = self._run_health_checks()

        # History
        if self._history_path.exists():
            lines = self._history_path.read_text().strip().split("\n")
            for line in lines[-20:]:
                if line.strip():
                    try:
                        self._data.history.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        return self._data

    def _run_health_checks(self) -> list[HealthCheck]:
        checks = []

        # 1. Config file exists
        config_exists = self._config_path.exists()
        checks.append(HealthCheck(
            "config_file",
            config_exists,
            f"{self._config_path}" if config_exists else "Config not found. Run: setup --save",
        ))

        # 2. Tools available
        available = [t for t in self._data.tools if t.available]
        checks.append(HealthCheck(
            "tools_available",
            len(available) > 0,
            f"{len(available)} tool(s) found" if available else "No AI CLI tools installed",
        ))

        # 3. Routing coverage
        all_task_types = {tp[0] for tp in TASK_PATTERNS}
        covered = set(self._data.routing.keys()) if self._data.routing else set()
        missing = all_task_types - covered
        checks.append(HealthCheck(
            "routing_coverage",
            len(missing) == 0,
            f"All {len(all_task_types)} task types covered" if not missing
            else f"Missing: {', '.join(sorted(missing))}",
        ))

        # 4. Config version
        if self._data.config:
            version = self._data.config.get("version", "unknown")
            checks.append(HealthCheck(
                "config_version",
                version == "1.0.0",
                f"v{version}",
            ))
        else:
            checks.append(HealthCheck(
                "config_version", False, "No config loaded",
            ))

        # 5. No dead references
        dead_refs = []
        if self._data.config and "routing" in self._data.config:
            tool_keys = set(self._data.config.get("tools", {}).keys())
            for task_type, rule in self._data.config["routing"].items():
                for role in ("primary", "fallback"):
                    ref = rule.get(role)
                    if ref and ref not in tool_keys:
                        dead_refs.append(f"{task_type}.{role}={ref}")
        checks.append(HealthCheck(
            "no_dead_refs",
            len(dead_refs) == 0,
            "Clean" if not dead_refs else f"Dead: {', '.join(dead_refs)}",
        ))

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
        available = sum(1 for t in self._data.tools if t.available)
        total = len(self._data.tools)
        health_ok = sum(1 for h in self._data.health if h.passed)
        health_total = len(self._data.health)

        title = Color.bold("RoleMesh Dashboard")
        status_color = Color.green if health_ok == health_total else Color.yellow
        status = status_color(f"{health_ok}/{health_total} checks passed")

        lines = [
            f"\n{'=' * 60}",
            f"  {title}",
            f"  Tools: {available}/{total} available | Health: {status}",
            f"{'=' * 60}",
        ]
        return "\n".join(lines)

    def render_tools(self) -> str:
        lines = [f"\n{Color.bold('[ Tools ]')}"]
        lines.append(f"  {'Name':<22} {'Vendor':<12} {'Cost':<8} {'Status':<10} {'Version'}")
        lines.append(f"  {'-' * 22} {'-' * 12} {'-' * 8} {'-' * 10} {'-' * 20}")

        for t in self._data.tools:
            if t.available:
                status = Color.green("OK")
            else:
                status = Color.dim("--")
            ver = t.version or ""
            if len(ver) > 20:
                ver = ver[:17] + "..."
            lines.append(
                f"  {t.name:<22} {t.vendor:<12} {t.cost_tier:<8} {status:<10} {ver}"
            )
        return "\n".join(lines)

    def render_routing(self) -> str:
        lines = [f"\n{Color.bold('[ Routing Table ]')}"]
        lines.append(f"  {'Task Type':<20} {'Primary':<16} {'Fallback':<16}")
        lines.append(f"  {'-' * 20} {'-' * 16} {'-' * 16}")

        if not self._data.routing:
            lines.append(f"  {Color.dim('No routing config. Run: setup --save')}")
            return "\n".join(lines)

        tool_names = {}
        if self._data.config and "tools" in self._data.config:
            for k, v in self._data.config["tools"].items():
                tool_names[k] = v.get("name", k)

        for task_type in sorted(self._data.routing.keys()):
            rule = self._data.routing[task_type]
            primary = rule.get("primary", "--")
            fallback = rule.get("fallback") or "--"
            primary_name = tool_names.get(primary, primary)
            fallback_name = tool_names.get(fallback, fallback) if fallback != "--" else "--"
            lines.append(
                f"  {task_type:<20} {primary_name:<16} {fallback_name:<16}"
            )
        return "\n".join(lines)

    def render_coverage(self) -> str:
        lines = [f"\n{Color.bold('[ Coverage Matrix ]')}"]
        all_task_types = sorted(tp[0] for tp in TASK_PATTERNS)
        available_tools = [t for t in self._data.tools if t.available]

        if not available_tools:
            lines.append(f"  {Color.dim('No tools available.')}")
            return "\n".join(lines)

        # Header row
        header = f"  {'Task Type':<20}"
        for t in available_tools:
            short_name = t.key[:6]
            header += f" {short_name:^8}"
        lines.append(header)
        lines.append(f"  {'-' * 20}" + (" " + "-" * 8) * len(available_tools))

        # Data rows
        for task_type in all_task_types:
            row = f"  {task_type:<20}"
            for t in available_tools:
                if task_type in t.strengths:
                    row += f" {Color.green('*'):^8}"
                else:
                    row += f" {Color.dim('.'):^8}"
            lines.append(row)

        return "\n".join(lines)

    def render_health(self) -> str:
        lines = [f"\n{Color.bold('[ Health ]')}"]
        for check in self._data.health:
            icon = Color.green("PASS") if check.passed else Color.red("FAIL")
            lines.append(f"  [{icon}] {check.name}: {check.detail}")
        return "\n".join(lines)

    def render_history(self) -> str:
        lines = [f"\n{Color.bold('[ Recent History ]')}"]
        lines.append(f"  {'Time':<20} {'Tool':<12} {'Task':<16} {'Status':<8} {'ms':>6}")
        lines.append(f"  {'-' * 20} {'-' * 12} {'-' * 16} {'-' * 8} {'-' * 6}")

        for entry in self._data.history[-10:]:
            ts = entry.get("timestamp", "?")[:19]
            tool = entry.get("tool", "?")
            task = entry.get("task_type", "?")
            ok = Color.green("OK") if entry.get("success") else Color.red("FAIL")
            ms = str(entry.get("duration_ms", 0))
            lines.append(f"  {ts:<20} {tool:<12} {task:<16} {ok:<8} {ms:>6}")

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
            "history": self._data.history[-10:],
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
    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.collect()

    if args.json:
        print(json.dumps(dashboard.to_json(), indent=2, ensure_ascii=False))
        return

    specific = args.tools or args.routing or args.coverage or args.health or args.history
    if not specific:
        print(dashboard.render_full())
    else:
        if args.tools:
            print(dashboard.render_tools())
        if args.routing:
            print(dashboard.render_routing())
        if args.coverage:
            print(dashboard.render_coverage())
        if args.health:
            print(dashboard.render_health())
        if args.history:
            print(dashboard.render_history())


if __name__ == "__main__":
    main()
