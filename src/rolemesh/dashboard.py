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

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

    _enabled: bool = True

    @classmethod
    def set_enabled(cls, enabled: bool):
        cls._enabled = enabled

    @classmethod
    def is_enabled(cls) -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        if not sys.stdout.isatty():
            return False
        return cls._enabled

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

    def __init__(self, config_path: Optional[Path] = None,
                 history_path: Optional[Path] = None):
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
            lines = self._history_path.read_text().strip()
            if lines:
                for line in lines.split("\n"):
                    try:
                        self._data.history.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        return self._data

    def _run_health_checks(self) -> list[HealthCheck]:
        checks = []

        # 1. Config file exists
        checks.append(HealthCheck(
            name="config_file",
            passed=self._config_path.exists(),
            detail=str(self._config_path) if self._config_path.exists()
                   else "Config not found. Run: setup --save",
        ))

        # 2. Tools available
        available = [t for t in self._data.tools if t.available]
        checks.append(HealthCheck(
            name="tools_available",
            passed=len(available) > 0,
            detail=f"{len(available)} tool(s) found"
                   if available else "No AI CLI tools installed",
        ))

        # 3. Routing coverage
        all_types = set(tp[0] for tp in TASK_PATTERNS)
        covered = set(self._data.routing.keys()) if self._data.routing else set()
        missing = sorted(all_types - covered)
        checks.append(HealthCheck(
            name="routing_coverage",
            passed=len(missing) == 0,
            detail=f"All {len(all_types)} task types covered"
                   if not missing else f"Missing: {', '.join(missing)}",
        ))

        # 4. Config version
        version = "unknown"
        if self._data.config:
            version = self._data.config.get("version", "unknown")
        checks.append(HealthCheck(
            name="config_version",
            passed=version == "1.0.0",
            detail=version if self._data.config else "No config loaded",
        ))

        # 5. No dead references
        if self._data.config:
            tool_keys = set(self._data.config.get("tools", {}).keys())
            dead = []
            for task_type, rule in self._data.routing.items():
                for ref_key in ("primary", "fallback"):
                    ref = rule.get(ref_key)
                    if ref and ref not in tool_keys:
                        dead.append(f"{task_type}.{ref_key}={ref}")
            checks.append(HealthCheck(
                name="no_dead_refs",
                passed=len(dead) == 0,
                detail="Clean" if not dead else f"Dead: {', '.join(dead)}",
            ))

        return checks

    # --- Renderers ---

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
            "",
            f"  {Color.bold('RoleMesh Dashboard')}",
            f"  Tools: {Color.green(str(avail))}/{total} available"
            f" | Health: {Color.green(str(passed))}/{total_checks}"
            f" checks passed" if passed == total_checks else
            f"  Tools: {Color.yellow(str(avail))}/{total} available"
            f" | Health: {Color.yellow(str(passed))}/{total_checks}"
            f" checks passed",
            "  " + "=" * 60,
        ])

    def render_tools(self) -> str:
        lines = ["", f"  {Color.bold('Tools')}"]
        for t in self._data.tools:
            if t.available:
                status = Color.green("[OK]")
            else:
                status = Color.dim("[--]")
            ver = f" ({t.version})" if t.version else ""
            if len(ver) > 30:
                ver = ver[:30] + "..."
            lines.append(
                f"    {status} {t.name}{ver}"
                f" — {Color.dim(t.vendor)}, {t.cost_tier}"
            )
        return "\n".join(lines)

    def render_routing(self) -> str:
        lines = ["", f"  {Color.bold('Routing Table')}"]

        if not self._data.config:
            lines.append(f"    {Color.dim('No config loaded. Run: setup --save')}")
            return "\n".join(lines)

        tools_map = self._data.config.get("tools", {})
        for task_type in sorted(self._data.routing.keys()):
            rule = self._data.routing[task_type]
            primary_key = rule.get("primary")
            fallback_key = rule.get("fallback")
            primary_name = tools_map.get(primary_key, {}).get("name", primary_key) if primary_key else "—"
            fallback_name = tools_map.get(fallback_key, {}).get("name", fallback_key) if fallback_key else "—"
            lines.append(
                f"    {task_type:<20s}"
                f" -> {primary_name}"
                f" {Color.dim('| fallback: ' + fallback_name)}"
            )
        return "\n".join(lines)

    def render_coverage(self) -> str:
        lines = ["", f"  {Color.bold('Task Coverage Matrix')}"]

        avail_tools = [t for t in self._data.tools if t.available]
        if not avail_tools:
            lines.append(f"    {Color.dim('No tools available')}")
            return "\n".join(lines)

        # Header row
        header = f"    {'Task Type':<20s}"
        for t in avail_tools:
            header += f" {t.key[:8]:>8s}"
        lines.append(header)
        lines.append(f"    {'—' * 20}" + "".join(f" {'—' * 8}" for _ in avail_tools))

        # Data rows
        for task_type, _ in sorted(TASK_PATTERNS, key=lambda x: x[0]):
            row = f"    {task_type:<20s}"
            for t in avail_tools:
                if task_type in t.strengths:
                    row += f" {Color.green('●'):>8s}"
                else:
                    row += f" {Color.dim('·'):>8s}"
            lines.append(row)

        return "\n".join(lines)

    def render_health(self) -> str:
        lines = ["", f"  {Color.bold('Health Checks')}"]
        for check in self._data.health:
            if check.passed:
                status = Color.green("PASS")
            else:
                status = Color.red("FAIL")
            lines.append(f"    [{status}] {check.name}: {check.detail}")
        return "\n".join(lines)

    def render_history(self) -> str:
        lines = ["", f"  {Color.bold('Recent Executions')}"]
        for entry in self._data.history[-10:]:
            ts = entry.get("timestamp", "?")
            tool = entry.get("tool", "?")
            task = entry.get("task_type", "?")
            success = entry.get("success", False)
            status = Color.green("OK") if success else Color.red("FAIL")
            ms = str(entry.get("duration_ms", "?"))
            lines.append(f"    {ts}  {tool:<10s}  {task:<16s}  [{status}]  {ms}ms")
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
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--tools", action="store_true", help="Tools only")
    parser.add_argument("--routing", action="store_true", help="Routing table only")
    parser.add_argument("--coverage", action="store_true", help="Coverage matrix only")
    parser.add_argument("--health", action="store_true", help="Health checks only")
    parser.add_argument("--history", action="store_true", help="Execution history only")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    dash = RoleMeshDashboard(config_path=config_path)
    dash.collect()

    if args.json:
        print(json.dumps(dash.to_json(), indent=2, ensure_ascii=False))
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
