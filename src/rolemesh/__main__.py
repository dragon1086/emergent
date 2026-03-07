"""
RoleMesh CLI - Unified entry point for all rolemesh commands.

Usage:
    python -m src.rolemesh dashboard [--tools|--routing|--coverage|--health|--history|--json]
    python -m src.rolemesh setup [--save|--interactive]
    python -m src.rolemesh route "<task>" [--all|--json]
    python -m src.rolemesh exec "<task>" [--tool TOOL|--dry-run|--json]
    python -m src.rolemesh status
"""

import argparse
import json
import sys
from pathlib import Path

from .builder import SetupWizard
from .router import RoleMeshRouter
from .executor import RoleMeshExecutor
from .dashboard import RoleMeshDashboard, Color


def cmd_dashboard(args):
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


def cmd_setup(args):
    wizard = SetupWizard()
    wizard.discover()
    print(wizard.summary())

    if args.save:
        path = wizard.save_config()
        config = wizard.build_config()
        errors = wizard.validate_config(config)
        if errors:
            for e in errors:
                print(f"  WARN: {e}")


def cmd_route(args):
    task = " ".join(args.task)
    if not task:
        print("Error: no task provided", file=sys.stderr)
        sys.exit(1)

    router = RoleMeshRouter()

    if args.all:
        results = router.route_multi(task)
        if args.json:
            print(json.dumps([
                {"tool": r.tool_name, "task_type": r.task_type,
                 "confidence": r.confidence, "fallback": r.fallback}
                for r in results
            ], indent=2))
        else:
            for r in results:
                print(f"  {r.task_type:<20s} -> {r.tool_name}"
                      f" (conf={r.confidence:.2f}, fallback={r.fallback})")
    else:
        result = router.route(task)
        if args.json:
            print(json.dumps({
                "tool": result.tool_name, "task_type": result.task_type,
                "confidence": result.confidence, "fallback": result.fallback,
                "reason": result.reason,
            }, indent=2))
        else:
            print(f"  Route: {result.tool_name} ({result.task_type},"
                  f" conf={result.confidence:.2f})")
            if result.fallback:
                print(f"  Fallback: {result.fallback}")
            if result.reason:
                print(f"  Reason: {result.reason}")


def cmd_exec(args):
    task = " ".join(args.task)
    if not task:
        print("Error: no task provided", file=sys.stderr)
        sys.exit(1)

    executor = RoleMeshExecutor(dry_run=args.dry_run)
    result = executor.dispatch(task, tool=args.tool)

    if args.json:
        print(json.dumps({
            "tool": result.tool_name, "task_type": result.task_type,
            "confidence": result.confidence, "exit_code": result.exit_code,
            "success": result.success, "duration_ms": result.duration_ms,
            "fallback_used": result.fallback_used,
        }, indent=2))
    else:
        status = Color.green("OK") if result.success else Color.red("FAIL")
        print(f"  Tool: {result.tool_name} | Type: {result.task_type}"
              f" | [{status}] | {result.duration_ms}ms")
        if result.stdout:
            print(result.stdout)


def cmd_status(args):
    wizard = SetupWizard()
    wizard.discover()
    available = wizard.available_tools()
    total = len(wizard._tools)
    config = wizard.load_config()

    if args.json:
        print(json.dumps({
            "tools_available": len(available),
            "tools_total": total,
            "config_loaded": config is not None,
            "tool_names": [t.name for t in available],
        }, indent=2))
    else:
        names = ", ".join(t.name for t in available)
        status_icon = Color.green("ready") if config else Color.yellow("no config")
        print(f"  RoleMesh: {len(available)}/{total} tools | {status_icon}")
        if names:
            print(f"  Available: {names}")
        config_status = "loaded" if config else "missing (run: setup --save)"
        print(f"  Config: {config_status}")


def main():
    parser = argparse.ArgumentParser(
        prog="rolemesh",
        description="RoleMesh - AI tool discovery, routing, and execution",
    )
    subparsers = parser.add_subparsers(dest="command")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Show dashboard")
    dash_parser.add_argument("--config", type=str, help="Config file path")
    dash_parser.add_argument("--json", action="store_true", help="JSON output")
    dash_parser.add_argument("--tools", action="store_true", help="Tools only")
    dash_parser.add_argument("--routing", action="store_true", help="Routing table")
    dash_parser.add_argument("--coverage", action="store_true", help="Coverage matrix")
    dash_parser.add_argument("--health", action="store_true", help="Health checks")
    dash_parser.add_argument("--history", action="store_true", help="Execution history")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Discover tools & save config")
    setup_parser.add_argument("--save", action="store_true", help="Save config")
    setup_parser.add_argument("--interactive", action="store_true", help="Interactive mode")

    # route
    route_parser = subparsers.add_parser("route", help="Classify and route a task")
    route_parser.add_argument("task", nargs="*", help="Task description")
    route_parser.add_argument("--all", action="store_true", help="Show all matches")
    route_parser.add_argument("--json", action="store_true", help="JSON output")

    # exec
    exec_parser = subparsers.add_parser("exec", help="Execute a task via routed tool")
    exec_parser.add_argument("task", nargs="*", help="Task description")
    exec_parser.add_argument("--tool", type=str, help="Force specific tool")
    exec_parser.add_argument("--dry-run", action="store_true", help="Dry run")
    exec_parser.add_argument("--json", action="store_true", help="JSON output")

    # status
    status_parser = subparsers.add_parser("status", help="Quick status overview")
    status_parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "route":
        cmd_route(args)
    elif args.command == "exec":
        cmd_exec(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
