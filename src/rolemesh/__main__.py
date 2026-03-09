#!/usr/bin/env python3
"""
RoleMesh CLI - Unified entry point for all rolemesh commands.

Usage:
    python -m src.rolemesh dashboard [--tools|--routing|--coverage|--health|--history] [--json] [--no-color]
    python -m src.rolemesh setup     [--save] [--interactive] [--json]
    python -m src.rolemesh route     <request> [--all] [--json]
    python -m src.rolemesh exec      <request> [--tool TOOL] [--dry-run] [--json]
    python -m src.rolemesh history   [--json] [--no-color]
    python -m src.rolemesh status    [--no-color]         # quick health summary
    python -m src.rolemesh --help
"""

import argparse
import json
import sys
from pathlib import Path


def cmd_dashboard(args):
    """Show system dashboard with tools, routing, coverage, and health."""
    from .dashboard import RoleMeshDashboard, Color

    if getattr(args, "no_color", False):
        Color.set_enabled(False)

    config_path = Path(args.config) if args.config else None
    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.collect()

    if args.json_out:
        print(json.dumps(dashboard.data.to_dict(), indent=2, ensure_ascii=False))
        return

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


def cmd_setup(args):
    """Discover tools and build routing config."""
    from .builder import SetupWizard

    config_path = Path(args.config) if args.config else None
    wizard = SetupWizard(config_path=config_path) if config_path else SetupWizard()
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


def cmd_route(args):
    """Classify and route a task request."""
    from .router import RoleMeshRouter

    config_path = Path(args.config) if args.config else None
    router = RoleMeshRouter(config_path=config_path)

    if args.all:
        results = router.route_multi(args.request)
        if args.json_out:
            print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        else:
            for r in results:
                print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool_name} ({r.tool})")
    else:
        result = router.route(args.request)
        if args.json_out:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"-> {result.tool_name} ({result.tool})")
            print(f"   Task: {result.task_type} ({result.confidence:.0%})")
            if result.fallback:
                print(f"   Fallback: {result.fallback}")
            print(f"   {result.reason}")


def cmd_exec(args):
    """Route and execute a task via AI CLI tool."""
    from .executor import RoleMeshExecutor

    config_path = Path(args.config) if args.config else None
    executor = RoleMeshExecutor(
        config_path=config_path,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )

    if args.tool:
        result = executor.dispatch(args.tool, args.request)
    else:
        result = executor.run(args.request)

    if args.json_out:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        status = "OK" if result.success else "FAIL"
        print(f"[{status}] {result.tool_name} ({result.tool})")
        print(f"  Task: {result.task_type} ({result.confidence:.0%})")
        print(f"  Duration: {result.duration_ms}ms")
        if result.fallback_used:
            print("  (fallback tool used)")
        if result.stdout:
            print(f"\n{result.stdout}")
        if result.stderr:
            print(f"\nSTDERR: {result.stderr}")


def cmd_history(args):
    """Show execution history."""
    from .dashboard import RoleMeshDashboard, Color

    if getattr(args, "no_color", False):
        Color.set_enabled(False)

    config_path = Path(args.config) if args.config else None
    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.collect()

    if args.json_out:
        print(json.dumps(dashboard.data.history, indent=2, ensure_ascii=False))
    else:
        print(dashboard.render_history())


def cmd_status(args):
    """Quick health summary (one-liner)."""
    from .dashboard import RoleMeshDashboard, Color

    if getattr(args, "no_color", False):
        Color.set_enabled(False)

    config_path = Path(args.config) if args.config else None
    dashboard = RoleMeshDashboard(config_path=config_path)
    dashboard.collect()

    available = [t for t in dashboard.data.tools if t.available]
    passed = sum(1 for c in dashboard.data.health_checks if c.passed)
    total = len(dashboard.data.health_checks)
    tool_names = ", ".join(t.name for t in available) if available else "none"

    if args.json_out:
        print(json.dumps({
            "tools_available": len(available),
            "tools_total": len(dashboard.data.tools),
            "tool_names": [t.name for t in available],
            "health_passed": passed,
            "health_total": total,
            "healthy": passed == total,
        }, indent=2, ensure_ascii=False))
    else:
        health_icon = Color.green("OK") if passed == total else Color.red("!!")
        print(f"[{health_icon}] {len(available)} tools ({tool_names}) | health {passed}/{total}")


def main():
    parser = argparse.ArgumentParser(
        prog="rolemesh",
        description="RoleMesh - AI Tool Discovery & Task Routing CLI",
        epilog=(
            "Examples:\n"
            "  python -m src.rolemesh dashboard           # full dashboard\n"
            "  python -m src.rolemesh dashboard --health   # health only\n"
            "  python -m src.rolemesh dashboard --history  # execution history\n"
            "  python -m src.rolemesh setup --save         # discover + save config\n"
            "  python -m src.rolemesh route '코드 리팩토링'   # classify task\n"
            "  python -m src.rolemesh exec --dry-run 'UI 수정'  # dry-run exec\n"
            "  python -m src.rolemesh history              # execution history\n"
            "  python -m src.rolemesh status               # quick health check\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=str, default=None,
                        help="Path to config file (default: ~/.rolemesh/config.json)")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # dashboard
    p_dash = sub.add_parser("dashboard", aliases=["dash", "d"],
                            help="Show system dashboard")
    p_dash.add_argument("--tools", action="store_true", help="Tools only")
    p_dash.add_argument("--routing", action="store_true", help="Routing table only")
    p_dash.add_argument("--coverage", action="store_true", help="Coverage matrix only")
    p_dash.add_argument("--health", action="store_true", help="Health check only")
    p_dash.add_argument("--history", action="store_true", help="Execution history only")
    p_dash.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    p_dash.add_argument("--no-color", dest="no_color", action="store_true", help="Disable colors")

    # setup
    p_setup = sub.add_parser("setup", aliases=["s"],
                             help="Discover tools and build config")
    p_setup.add_argument("--save", action="store_true", help="Save config to disk")
    p_setup.add_argument("--interactive", "-i", action="store_true",
                         help="Guided setup (set preferences)")
    p_setup.add_argument("--json", dest="json_out", action="store_true", help="JSON output")

    # route
    p_route = sub.add_parser("route", aliases=["r"],
                             help="Classify and route a task")
    p_route.add_argument("request", help="Task description to route")
    p_route.add_argument("--all", action="store_true",
                         help="Show all matching task types")
    p_route.add_argument("--json", dest="json_out", action="store_true", help="JSON output")

    # exec
    p_exec = sub.add_parser("exec", aliases=["x"],
                            help="Route and execute a task")
    p_exec.add_argument("request", help="Task description")
    p_exec.add_argument("--tool", type=str, default=None,
                        help="Force a specific tool (skip routing)")
    p_exec.add_argument("--dry-run", action="store_true",
                        help="Show command without executing")
    p_exec.add_argument("--timeout", type=int, default=120,
                        help="Timeout in seconds (default: 120)")
    p_exec.add_argument("--json", dest="json_out", action="store_true", help="JSON output")

    # history
    p_history = sub.add_parser("history", aliases=["hist", "h"],
                               help="Show execution history")
    p_history.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    p_history.add_argument("--no-color", dest="no_color", action="store_true", help="Disable colors")

    # status
    p_status = sub.add_parser("status", aliases=["st"],
                              help="Quick health summary")
    p_status.add_argument("--json", dest="json_out", action="store_true", help="JSON output")
    p_status.add_argument("--no-color", dest="no_color", action="store_true", help="Disable colors")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Normalize aliases
    cmd_map = {
        "dashboard": cmd_dashboard, "dash": cmd_dashboard, "d": cmd_dashboard,
        "setup": cmd_setup, "s": cmd_setup,
        "route": cmd_route, "r": cmd_route,
        "exec": cmd_exec, "x": cmd_exec,
        "history": cmd_history, "hist": cmd_history, "h": cmd_history,
        "status": cmd_status, "st": cmd_status,
    }

    handler = cmd_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
