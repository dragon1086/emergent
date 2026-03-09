"""
rolemesh/dashboard.py - Dashboard CLI

Displays a unified view of discovered tools, routing config,
task type coverage, and config health.

Usage:
    python -m src.rolemesh.dashboard              # full dashboard
    python -m src.rolemesh.dashboard --tools       # tools only
    python -m src.rolemesh.dashboard --routing     # routing table only
    python -m src.rolemesh.dashboard --coverage    # task coverage matrix
    python -m src.rolemesh.dashboard --health      # config health check
    python -m src.rolemesh.dashboard --history     # execution history
    python -m src.rolemesh.dashboard --json        # JSON output
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
    """ANSI color codes for terminal output. Disabled when NO_COLOR is set or not a TTY."""

    _enabled: Optional[bool] = None

    @classmethod
    def enabled(cls) -> bool:
        if cls._enabled is not None:
            return cls._enabled
        if os.environ.get("NO_COLOR"):
            return False
        if hasattr(sys.stdout, "isatty"):
            return sys.stdout.isatty()
        return True

    @classmethod
    def set_enabled(cls, value: bool) -> None:
        cls._enabled = value

    @staticmethod
    def _wrap(code: str, text: str) -> str:
        if not Color.enabled():
            return text
        return f"\033[{code}m{text}\033[0m"

    @staticmethod
    def green(text: str) -> str:
        return Color._wrap("32", text)

    @staticmethod
    def red(text: str) -> str:
        return Color._wrap("31", text)

    @staticmethod
    def yellow(text: str) -> str:
        return Color._wrap("33", text)

    @staticmethod
    def cyan(text: str) -> str:
        return Color._wrap("36", text)

    @staticmethod
    def bold(text: str) -> str:
        return Color._wrap("1", text)

    @staticmethod
    def dim(text: str) -> str:
        return Color._wrap("2", text)


@dataclass
class HealthCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class DashboardData:
    tools: list[ToolProfile] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    routing: dict = field(default_factory=dict)
    health_checks: list[HealthCheck] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tools": [
                {
                    "key": t.key,
                    "name": t.name,
                    "vendor": t.vendor,
                    "available": bool(t.available),
                    "version": t.version,
                    "strengths": t.strengths,
                    "cost_tier": t.cost_tier,
                }
                for t in self.tools
            ],
            "config_loaded": bool(self.config),
            "routing": self.routing,
            "task_types": self.task_types,
            "health_checks": [
                {"name": h.name, "passed": h.passed, "detail": h.detail}
                for h in self.health_checks
            ],
            "history": self.history,
        }


class RoleMeshDashboard:
    """Collects and displays rolemesh system status."""

    def __init__(self, config_path: Optional[Path] = None, history_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".rolemesh" / "config.json"
        self.history_path = history_path or Path.home() / ".rolemesh" / "history.jsonl"
        self.wizard = SetupWizard(config_path=self.config_path)
        self.data = DashboardData()

    def collect(self) -> DashboardData:
        """Gather all dashboard data."""
        self.wizard.discover()
        self.data.tools = self.wizard.tools
        self.data.config = self.wizard.load_config() or {}
        self.data.routing = self.data.config.get("routing", {})
        self.data.task_types = [tp[0] for tp in TASK_PATTERNS]
        self.data.health_checks = self._run_health_checks()
        self.data.history = self._load_history()
        return self.data

    def _load_history(self, limit: int = 20) -> list[dict]:
        """Load recent execution history from JSONL file."""
        if not self.history_path.exists():
            return []
        entries: list[dict] = []
        try:
            with open(self.history_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except (json.JSONDecodeError, OSError):
                            pass
        except OSError:
            pass
        return entries[-limit:]

    def _run_health_checks(self) -> list[HealthCheck]:
        """Run all health checks and return results."""
        checks: list[HealthCheck] = []

        # 1. config_file
        checks.append(HealthCheck(
            name="config_file",
            passed=self.config_path.exists(),
            detail=str(self.config_path) if self.config_path.exists() else f"Not found: {self.config_path}",
        ))

        # 2. tools_available
        available = [t for t in self.data.tools if t.available]
        checks.append(HealthCheck(
            name="tools_available",
            passed=len(available) > 0,
            detail=f"{len(available)}/{len(self.data.tools)} tools installed",
        ))

        # 3. routing_coverage
        routed_types = set(self.data.routing.keys()) if self.data.routing else set()
        all_types = set(self.data.task_types)
        missing = sorted(all_types - routed_types)
        checks.append(HealthCheck(
            name="routing_coverage",
            passed=len(missing) == 0,
            detail=f"{len(routed_types)} task types routed" +
                   (f" (missing: {', '.join(missing)})" if missing else ""),
        ))

        # 4. config_version
        version = self.data.config.get("version", "")
        checks.append(HealthCheck(
            name="config_version",
            passed=version == "1.0.0",
            detail=f"version={version}" if version else "No version field",
        ))

        # 5. no_dead_refs
        tool_keys = set(self.data.config.get("tools", {}).keys())
        dead_refs: list[str] = []
        for task_type, rule in self.data.routing.items():
            if isinstance(rule, dict):
                for role, ref in rule.items():
                    if ref not in tool_keys and tool_keys:
                        dead_refs.append(f"{task_type}.{role}={ref}")
        checks.append(HealthCheck(
            name="no_dead_refs",
            passed=len(dead_refs) == 0,
            detail=f"Dead refs: {', '.join(dead_refs)}" if dead_refs else "All refs valid",
        ))

        return checks

    def render_tools(self) -> str:
        """Render tools section."""
        lines: list[str] = [Color.bold("== Tools =="), ""]
        installed = [t for t in self.data.tools if t.available]

        lines.append(f"  Installed ({len(installed)}):")
        for t in self.data.tools:
            ver = f" v{t.version}" if t.version else ""
            pref = getattr(t, "user_preference", None)
            marker = " *" if pref else ""
            if t.available:
                lines.append(f"    {Color.green(t.name)} ({t.vendor}){ver}{marker}"
                             f"  [{Color.dim(', '.join(t.strengths))}]  {Color.dim(t.cost_tier)}")
            else:
                lines.append(f"    {Color.yellow(t.name)} ({t.vendor}){ver}"
                             f"  [{Color.dim(', '.join(t.strengths))}]  {Color.dim(t.cost_tier)}")
        return "\n".join(lines)

    def render_routing(self) -> str:
        """Render routing table."""
        lines: list[str] = [Color.bold("== Routing Table =="), ""]
        routing = self.data.routing

        if not routing:
            lines.append("  No routing config. Run: python -m src.rolemesh.builder --save")
            return "\n".join(lines)

        header = f"  {Color.cyan(f'{'Task Type':<20}')} {'Primary':<15} {'Fallback'}"
        lines.append(header)

        for task_type in sorted(routing.keys()):
            rule = routing.get(task_type, {})
            if isinstance(rule, dict):
                primary = rule.get("primary", "-")
                fallback = rule.get("fallback", "-") or "-"
            else:
                primary = rule
                fallback = "-"
            lines.append(f"  {task_type:<20} {primary:<15} {Color.dim(fallback)}")

        return "\n".join(lines)

    def render_coverage(self) -> str:
        """Render task coverage matrix."""
        lines: list[str] = [Color.bold("== Task Coverage Matrix =="), ""]

        available = [t for t in self.data.tools if t.available]
        if not available:
            lines.append("  No tools available.")
            return "\n".join(lines)

        tool_keys = [t.key for t in available]
        header = f"  {'Task Type':<20}" + "".join(f"{k:<10}" for k in tool_keys)
        lines.append(header)

        for task_type in self.data.task_types:
            row = f"  {task_type:<20}"
            for t in available:
                has = "X" if task_type in t.strengths else "."
                rule = self.data.routing.get(task_type, {})
                if isinstance(rule, dict) and rule.get("primary") == t.key and has == "X":
                    row += f"{Color.green(has):<10}"
                elif has == "X":
                    row += f"{Color.yellow(has):<10}"
                else:
                    row += f"{has:<10}"
            lines.append(row)

        return "\n".join(lines)

    def render_health(self) -> str:
        """Render health check results."""
        lines: list[str] = [Color.bold("== Health Check =="), ""]

        for check in self.data.health_checks:
            status = Color.green("OK") if check.passed else Color.red("!!")
            lines.append(f"  [{status}] {check.name}: {check.detail}")

        passed = sum(1 for c in self.data.health_checks if c.passed)
        total = len(self.data.health_checks)
        score_color = Color.green if passed == total else Color.yellow
        lines.append(f"\n  Score: {score_color(f'{passed}/{total}')}")

        return "\n".join(lines)

    def render_history(self) -> str:
        """Render execution history."""
        lines: list[str] = [Color.bold("== Execution History =="), ""]

        if not self.data.history:
            lines.append("  No execution history.")
            return "\n".join(lines)

        header = (f"  {Color.dim(f'{'Time':<20}')} {'Tool':<10} {'Type':<15} {'Status':<8} {'Duration'}")
        lines.append(header)

        for entry in reversed(self.data.history):
            ts = entry.get("timestamp", "?").replace("T", " ")[:20]
            tool = entry.get("tool", "?")
            task_type = entry.get("task_type", "?")
            ok = entry.get("success", False)
            status = Color.green("OK") if ok else Color.red("FAIL")
            dur = f"{entry.get('duration_ms', 0)}ms"
            lines.append(f"  {ts:<20} {tool:<10} {task_type:<15} {status:<8} {dur}")

        total = len(self.data.history)
        ok_count = sum(1 for e in self.data.history if e.get("success"))
        lines.append(f"\n  {ok_count}/{total} succeeded")

        return "\n".join(lines)

    def render_full(self) -> str:
        """Render full dashboard."""
        sections = [
            Color.bold("  RoleMesh Dashboard"),
            "=" * 50,
            "",
            self.render_tools(),
            "",
            self.render_routing(),
            "",
            self.render_coverage(),
            "",
            self.render_health(),
        ]
        if self.data.history:
            sections.extend(["", self.render_history()])
        return "\n".join(sections)


def main():
    import argparse
    parser = argparse.ArgumentParser("RoleMesh Dashboard")
    parser.add_argument("--tools", action="store_true", help="Show tools only")
    parser.add_argument("--routing", action="store_true", help="Show routing table only")
    parser.add_argument("--coverage", action="store_true", help="Show task coverage matrix only")
    parser.add_argument("--health", action="store_true", help="Show health check only")
    parser.add_argument("--history", action="store_true", help="Show execution history")
    parser.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--config", type=str, help="Path to config file")
    args = parser.parse_args()

    if args.no_color:
        Color.set_enabled(False)

    dashboard = RoleMeshDashboard(
        config_path=Path(args.config) if args.config else None,
    )
    dashboard.collect()

    if args.json_out:
        print(json.dumps(dashboard.data.to_dict(), indent=2, ensure_ascii=False))
    elif args.tools:
        print(dashboard.render_tools())
    elif args.routing:
        print(dashboard.render_routing())
    elif args.coverage:
        print(dashboard.render_coverage())
    elif args.health:
        print(dashboard.render_health())
    elif args.history:
        print(dashboard.render_history())
    else:
        print(dashboard.render_full())


if __name__ == "__main__":
    main()
