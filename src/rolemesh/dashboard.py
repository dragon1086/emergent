#!/usr/bin/env python3
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


# --- ANSI Colors ---

class Color:
    """ANSI color codes for terminal output. Disabled when NO_COLOR is set or not a TTY."""

    _enabled: Optional[bool] = None

    @classmethod
    def enabled(cls) -> bool:
        if cls._enabled is not None:
            return cls._enabled
        return (
            os.environ.get("NO_COLOR") is None
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )

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


# --- Data Models ---

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
                    "available": t.available,
                    "version": t.version,
                    "strengths": t.strengths,
                    "cost_tier": t.cost_tier,
                }
                for t in self.tools
            ],
            "config_loaded": bool(self.config),
            "routing": self.routing,
            "task_types": self.task_types,
            "health": [
                {"name": h.name, "passed": h.passed, "detail": h.detail}
                for h in self.health_checks
            ],
            "history": self.history,
        }


# --- Dashboard Logic ---

class RoleMeshDashboard:
    """Collects and displays rolemesh system status."""

    def __init__(self, config_path: Optional[Path] = None,
                 history_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".rolemesh" / "config.json"
        self.history_path = history_path or Path.home() / ".rolemesh" / "history.jsonl"
        self.wizard = SetupWizard(config_path=self.config_path)
        self.data = DashboardData()

    def collect(self) -> DashboardData:
        """Gather all dashboard data."""
        self.wizard.discover()
        self.data.tools = self.wizard.tools
        self.data.config = self.wizard.load_config()
        self.data.routing = self.data.config.get("routing", {})
        self.data.task_types = [tp[0] for tp in TASK_PATTERNS]
        self.data.health_checks = self._run_health_checks()
        self.data.history = self._load_history()
        return self.data

    def _load_history(self, limit: int = 20) -> list[dict]:
        """Load recent execution history from JSONL file."""
        if not self.history_path.exists():
            return []
        entries = []
        try:
            with open(self.history_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            pass
        return entries[-limit:]

    def _run_health_checks(self) -> list[HealthCheck]:
        checks = []

        # 1. Config file exists
        exists = self.config_path.exists()
        checks.append(HealthCheck(
            name="config_file",
            passed=exists,
            detail=str(self.config_path) if exists else f"Not found: {self.config_path}",
        ))

        # 2. At least one tool available
        available = [t for t in self.data.tools if t.available]
        checks.append(HealthCheck(
            name="tools_available",
            passed=len(available) > 0,
            detail=f"{len(available)}/{len(self.data.tools)} tools installed",
        ))

        # 3. All task types have routing rules
        if self.data.routing:
            covered = [t for t in self.data.task_types if t in self.data.routing]
            uncovered = [t for t in self.data.task_types if t not in self.data.routing]
            checks.append(HealthCheck(
                name="routing_coverage",
                passed=len(uncovered) == 0,
                detail=f"{len(covered)}/{len(self.data.task_types)} task types routed"
                       + (f" (missing: {', '.join(uncovered)})" if uncovered else ""),
            ))
        else:
            checks.append(HealthCheck(
                name="routing_coverage",
                passed=False,
                detail="No routing rules (run: python -m src.rolemesh.builder --save)",
            ))

        # 4. Config version check
        version = self.data.config.get("version")
        checks.append(HealthCheck(
            name="config_version",
            passed=version == "1.0.0",
            detail=f"v{version}" if version else "No version found",
        ))

        # 5. No dead references in routing
        config_tools = set(self.data.config.get("tools", {}).keys())
        dead_refs = []
        for task_type, rule in self.data.routing.items():
            if rule.get("primary") and rule["primary"] not in config_tools:
                dead_refs.append(f"{task_type}->{rule['primary']}")
            if rule.get("fallback") and rule["fallback"] not in config_tools:
                dead_refs.append(f"{task_type}->{rule['fallback']}(fb)")
        checks.append(HealthCheck(
            name="no_dead_refs",
            passed=len(dead_refs) == 0,
            detail="All references valid" if not dead_refs else f"Dead refs: {', '.join(dead_refs)}",
        ))

        return checks

    # --- Renderers ---

    def render_tools(self) -> str:
        lines = [Color.bold("== Tools =="), ""]
        available = [t for t in self.data.tools if t.available]
        unavailable = [t for t in self.data.tools if not t.available]

        if available:
            lines.append(f"  Installed ({len(available)}):")
            for t in available:
                ver = f" v{t.version}" if t.version else ""
                pref = Color.yellow(" *") if t.user_preference == 1 else ""
                name_str = Color.green(f"{t.name}{ver}")
                lines.append(
                    f"    {name_str} ({t.vendor}){pref}"
                    f"  [{t.cost_tier}]  strengths: {', '.join(t.strengths)}"
                )
        else:
            lines.append(Color.yellow("  No tools installed."))

        if unavailable:
            lines.append(f"\n  Not found ({len(unavailable)}):")
            for t in unavailable:
                lines.append(f"    {Color.dim(t.name)} ({t.vendor})")

        return "\n".join(lines)

    def render_routing(self) -> str:
        lines = [Color.bold("== Routing Table =="), ""]
        if not self.data.routing:
            lines.append(Color.yellow("  No routing config. Run: python -m src.rolemesh.builder --save"))
            return "\n".join(lines)

        # Header
        lines.append(f"  {Color.bold('Task Type'):<20} {Color.bold('Primary'):<15} {Color.bold('Fallback'):<15}")
        lines.append(f"  {'-'*20} {'-'*15} {'-'*15}")
        for task_type in sorted(self.data.routing.keys()):
            rule = self.data.routing[task_type]
            primary = rule.get("primary", "-")
            fallback = rule.get("fallback") or "-"
            lines.append(f"  {task_type:<20} {Color.cyan(primary):<15} {Color.dim(fallback):<15}")

        return "\n".join(lines)

    def render_coverage(self) -> str:
        lines = ["== Task Coverage Matrix ==", ""]
        available = [t for t in self.data.tools if t.available]
        if not available:
            lines.append("  No tools available.")
            return "\n".join(lines)

        # Build header
        tool_keys = [t.key for t in available]
        header = f"  {'Task Type':<20}" + "".join(f" {k:<8}" for k in tool_keys)
        lines.append(header)
        lines.append(f"  {'-'*20}" + "".join(f" {'-'*8}" for _ in tool_keys))

        tool_map = {t.key: t for t in available}
        for task_type in self.data.task_types:
            row = f"  {task_type:<20}"
            for key in tool_keys:
                has = "X" if task_type in tool_map[key].strengths else "."
                routed = ""
                if self.data.routing.get(task_type, {}).get("primary") == key:
                    routed = "*"
                row += f" {has + routed:<8}"
            lines.append(row)

        lines.append("")
        lines.append("  X = strength, * = primary route, . = not supported")
        return "\n".join(lines)

    def render_health(self) -> str:
        lines = [Color.bold("== Health Check =="), ""]
        for check in self.data.health_checks:
            if check.passed:
                icon = Color.green("OK")
            else:
                icon = Color.red("!!")
            lines.append(f"  [{icon}] {check.name}: {check.detail}")

        passed = sum(1 for c in self.data.health_checks if c.passed)
        total = len(self.data.health_checks)
        score_color = Color.green if passed == total else Color.yellow
        lines.append(f"\n  Score: {score_color(f'{passed}/{total}')}")
        return "\n".join(lines)

    def render_history(self) -> str:
        lines = [Color.bold("== Execution History =="), ""]
        if not self.data.history:
            lines.append(Color.dim("  No execution history."))
            return "\n".join(lines)

        # Header
        lines.append(
            f"  {'Time':<20} {'Tool':<10} {'Task':<15} "
            f"{'Status':<8} {'Duration':<10} {'Request'}"
        )
        lines.append(
            f"  {'-'*20} {'-'*10} {'-'*15} "
            f"{'-'*8} {'-'*10} {'-'*20}"
        )

        for entry in reversed(self.data.history):
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            tool = entry.get("tool", "-")
            task = entry.get("task_type", "-")
            success = entry.get("success", False)
            duration = entry.get("duration_ms", 0)
            request = entry.get("request", "")[:40]
            fallback = " (fb)" if entry.get("fallback_used") else ""

            status = Color.green("OK") if success else Color.red("FAIL")
            dur_str = f"{duration}ms"

            lines.append(
                f"  {ts:<20} {tool:<10} {task:<15} "
                f"{status:<8} {dur_str:<10} {request}{fallback}"
            )

        # Summary stats
        total = len(self.data.history)
        ok = sum(1 for e in self.data.history if e.get("success"))
        fail = total - ok
        avg_ms = (
            sum(e.get("duration_ms", 0) for e in self.data.history) // total
            if total else 0
        )
        lines.append("")
        lines.append(
            f"  Total: {total} | "
            f"{Color.green(f'OK: {ok}')} | "
            f"{Color.red(f'Fail: {fail}')} | "
            f"Avg: {avg_ms}ms"
        )
        return "\n".join(lines)

    def render_full(self) -> str:
        sections = [
            Color.bold("=" * 50),
            Color.bold("  RoleMesh Dashboard"),
            Color.bold("=" * 50),
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
        sections.extend(["", Color.bold("=" * 50)])
        return "\n".join(sections)


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RoleMesh Dashboard")
    parser.add_argument("--tools", action="store_true", help="Show tools only")
    parser.add_argument("--routing", action="store_true", help="Show routing table only")
    parser.add_argument("--coverage", action="store_true", help="Show task coverage matrix")
    parser.add_argument("--health", action="store_true", help="Show health check only")
    parser.add_argument("--history", action="store_true", help="Show execution history")
    parser.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    parser.add_argument("--no-color", dest="no_color", action="store_true", help="Disable color output")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    args = parser.parse_args()

    if args.no_color:
        Color.set_enabled(False)

    config_path = Path(args.config) if args.config else None
    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.collect()

    if args.json_out:
        print(json.dumps(dashboard.data.to_dict(), indent=2, ensure_ascii=False))
        return

    # Section-specific views
    specific = args.tools or args.routing or args.coverage or args.health or args.history
    if specific:
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
    else:
        print(dashboard.render_full())


if __name__ == "__main__":
    main()
