"""
RoleMesh CLI - Unified entry point for all rolemesh commands.

Usage:
    python -m src.rolemesh dashboard [--tools|--routing|--coverage|--health|--history] [--json]
    python -m src.rolemesh setup [--save] [--interactive]
    python -m src.rolemesh route "task description" [--all] [--json]
    python -m src.rolemesh exec "task description" [--tool X] [--dry-run]
    python -m src.rolemesh status [--json]
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


def cmd_setup(args):
    wizard = SetupWizard()

    if args.interactive:
        wizard.interactive_setup()
        return

    wizard.discover()
    print(wizard.summary())

    if args.save:
        path = wizard.save_config()
        print(f"\nConfig saved to: {path}")

        config = wizard.build_config()
        errors = wizard.validate_config(config)
        if errors:
            print(f"\nValidation warnings: {errors}")


def cmd_route(args):
    task = " ".join(args.task)
    if not task:
        print("Error: provide a task description", file=sys.stderr)
        sys.exit(1)

    router = RoleMeshRouter()

    if args.all:
        results = router.route_multi(task)
        if args.json:
            print(json.dumps([
                {
                    "tool": r.tool, "tool_name": r.tool_name,
                    "task_type": r.task_type, "confidence": r.confidence,
                    "fallback": r.fallback, "reason": r.reason,
                }
                for r in results
            ], indent=2))
        else:
            for r in results:
                print(f"  {r.task_type:<20} -> {r.tool_name:<16} ({r.confidence:.0%})")
    else:
        result = router.route(task)
        if args.json:
            print(json.dumps({
                "tool": result.tool, "tool_name": result.tool_name,
                "task_type": result.task_type, "confidence": result.confidence,
                "fallback": result.fallback, "reason": result.reason,
            }, indent=2))
        else:
            print(f"Task:       {task}")
            print(f"Type:       {result.task_type} ({result.confidence:.0%})")
            print(f"Tool:       {result.tool_name}")
            print(f"Fallback:   {result.fallback}")
            print(f"Reason:     {result.reason}")


def cmd_exec(args):
    task = " ".join(args.task)
    if not task:
        print("Error: provide a task description", file=sys.stderr)
        sys.exit(1)

    executor = RoleMeshExecutor(dry_run=args.dry_run)
    result = executor.dispatch(task, tool=args.tool)

    if args.json:
        print(json.dumps({
            "tool": result.tool, "tool_name": result.tool_name,
            "task_type": result.task_type, "confidence": result.confidence,
            "exit_code": result.exit_code, "success": result.success,
            "duration_ms": result.duration_ms, "fallback_used": result.fallback_used,
            "stdout": result.stdout, "stderr": result.stderr,
        }, indent=2))
    else:
        status = Color.green("OK") if result.success else Color.red("FAIL")
        print(f"Tool:       {result.tool_name}")
        print(f"Task:       {result.task_type} ({result.confidence:.0%})")
        print(f"Status:     {status} (exit {result.exit_code})")
        print(f"Duration:   {result.duration_ms}ms")
        if result.fallback_used:
            print("Fallback:   used")
        if result.stdout.strip():
            print(f"\n--- stdout ---\n{result.stdout.strip()}")
        if result.stderr.strip():
            print(f"\n--- stderr ---\n{result.stderr.strip()}")


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
            "tools": [{"key": t.key, "name": t.name} for t in available],
        }, indent=2))
    else:
        names = ", ".join(t.name for t in available) if available else "none"
        status_icon = Color.green("OK") if available else Color.yellow("!!")
        config_status = "loaded" if config else "missing (run: setup --save)"
        print(f"[{status_icon}] RoleMesh: {len(available)}/{total} tools ({names}) | config: {config_status}")


def main():
    parser = argparse.ArgumentParser(prog="rolemesh", description="RoleMesh - AI tool discovery, routing, and execution")
    parser.add_argument("--config", type=str, help="Config path override")
    parser.add_argument("--json", action="store_true", help="JSON output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Visual system dashboard")
    dash_parser.add_argument("--tools", action="store_true")
    dash_parser.add_argument("--routing", action="store_true")
    dash_parser.add_argument("--coverage", action="store_true")
    dash_parser.add_argument("--health", action="store_true")
    dash_parser.add_argument("--history", action="store_true")
    dash_parser.add_argument("--json", action="store_true", dest="json")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Discover tools, build config")
    setup_parser.add_argument("--save", action="store_true", help="Save config to disk")
    setup_parser.add_argument("--interactive", action="store_true")

    # route
    route_parser = subparsers.add_parser("route", help="Classify and route a task")
    route_parser.add_argument("task", nargs="*")
    route_parser.add_argument("--all", action="store_true", help="Show all matches")
    route_parser.add_argument("--json", action="store_true", dest="json")

    # exec
    exec_parser = subparsers.add_parser("exec", help="Route and execute a task")
    exec_parser.add_argument("task", nargs="*")
    exec_parser.add_argument("--tool", type=str, help="Force specific tool")
    exec_parser.add_argument("--dry-run", action="store_true")
    exec_parser.add_argument("--json", action="store_true", dest="json")

    # status
    subparsers.add_parser("status", help="One-line health summary")

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
