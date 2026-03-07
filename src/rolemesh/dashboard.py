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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .builder import SetupWizard, ToolProfile, TOOL_REGISTRY, discover_tools
from .router import RoleMeshRouter, TASK_PATTERNS


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
        }


# --- Dashboard Logic ---

class RoleMeshDashboard:
    """Collects and displays rolemesh system status."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".rolemesh" / "config.json"
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
        return self.data

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
        lines = ["== Tools ==", ""]
        available = [t for t in self.data.tools if t.available]
        unavailable = [t for t in self.data.tools if not t.available]

        if available:
            lines.append(f"  Installed ({len(available)}):")
            for t in available:
                ver = f" v{t.version}" if t.version else ""
                pref = " *" if t.user_preference == 1 else ""
                lines.append(
                    f"    {t.name}{ver} ({t.vendor}){pref}"
                    f"  [{t.cost_tier}]  strengths: {', '.join(t.strengths)}"
                )
        else:
            lines.append("  No tools installed.")

        if unavailable:
            lines.append(f"\n  Not found ({len(unavailable)}):")
            for t in unavailable:
                lines.append(f"    {t.name} ({t.vendor})")

        return "\n".join(lines)

    def render_routing(self) -> str:
        lines = ["== Routing Table ==", ""]
        if not self.data.routing:
            lines.append("  No routing config. Run: python -m src.rolemesh.builder --save")
            return "\n".join(lines)

        # Header
        lines.append(f"  {'Task Type':<20} {'Primary':<15} {'Fallback':<15}")
        lines.append(f"  {'-'*20} {'-'*15} {'-'*15}")
        for task_type in sorted(self.data.routing.keys()):
            rule = self.data.routing[task_type]
            primary = rule.get("primary", "-")
            fallback = rule.get("fallback") or "-"
            lines.append(f"  {task_type:<20} {primary:<15} {fallback:<15}")

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
        lines = ["== Health Check ==", ""]
        for check in self.data.health_checks:
            icon = "OK" if check.passed else "!!"
            lines.append(f"  [{icon}] {check.name}: {check.detail}")

        passed = sum(1 for c in self.data.health_checks if c.passed)
        total = len(self.data.health_checks)
        lines.append(f"\n  Score: {passed}/{total}")
        return "\n".join(lines)

    def render_full(self) -> str:
        sections = [
            "=" * 50,
            "  RoleMesh Dashboard",
            "=" * 50,
            "",
            self.render_tools(),
            "",
            self.render_routing(),
            "",
            self.render_coverage(),
            "",
            self.render_health(),
            "",
            "=" * 50,
        ]
        return "\n".join(sections)


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RoleMesh Dashboard")
    parser.add_argument("--tools", action="store_true", help="Show tools only")
    parser.add_argument("--routing", action="store_true", help="Show routing table only")
    parser.add_argument("--coverage", action="store_true", help="Show task coverage matrix")
    parser.add_argument("--health", action="store_true", help="Show health check only")
    parser.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.collect()

    if args.json_out:
        print(json.dumps(dashboard.data.to_dict(), indent=2, ensure_ascii=False))
        return

    # Section-specific views
    specific = args.tools or args.routing or args.coverage or args.health
    if specific:
        if args.tools:
            print(dashboard.render_tools())
        if args.routing:
            print(dashboard.render_routing())
        if args.coverage:
            print(dashboard.render_coverage())
        if args.health:
            print(dashboard.render_health())
    else:
        print(dashboard.render_full())


if __name__ == "__main__":
    main()
