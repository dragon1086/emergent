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

from .builder import SetupWizard
from .router import RoleMeshRouter
from .executor import RoleMeshExecutor
from .dashboard import RoleMeshDashboard, Color


def cmd_dashboard(args):
    from pathlib import Path
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


def cmd_setup(args):
    wizard = SetupWizard()
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
    task = " ".join(args.task) if args.task else ""
    if not task:
        print("Error: provide a task description", file=sys.stderr)
        sys.exit(1)

    router = RoleMeshRouter()

    if args.all:
        results = router.route_multi(task)
        if args.json:
            print(json.dumps([
                {"tool": r.tool, "tool_name": r.tool_name,
                 "task_type": r.task_type, "confidence": r.confidence,
                 "fallback": r.fallback, "reason": r.reason}
                for r in results
            ], indent=2, ensure_ascii=False))
        else:
            for r in results:
                conf_str = f"{r.confidence:.0%}"
                print(f"  {r.task_type:<20} -> {r.tool_name:<20} ({conf_str})")
    else:
        result = router.route(task)
        if args.json:
            print(json.dumps({
                "tool": result.tool, "tool_name": result.tool_name,
                "task_type": result.task_type, "confidence": result.confidence,
                "fallback": result.fallback, "reason": result.reason,
            }, indent=2, ensure_ascii=False))
        else:
            print(f"Task:       {task}")
            print(f"Type:       {result.task_type} ({result.confidence:.0%})")
            print(f"Tool:       {result.tool_name}")
            if result.fallback:
                print(f"Fallback:   {result.fallback}")
            print(f"Reason:     {result.reason}")


def cmd_exec(args):
    task = " ".join(args.task) if args.task else ""
    if not task:
        print("Error: provide a task description", file=sys.stderr)
        sys.exit(1)

    executor = RoleMeshExecutor(dry_run=args.dry_run)

    if args.tool:
        result = executor.dispatch(args.tool, task)
    else:
        result = executor.run(task)

    if args.json:
        print(json.dumps({
            "tool": result.tool, "tool_name": result.tool_name,
            "task_type": result.task_type, "confidence": result.confidence,
            "exit_code": result.exit_code, "success": result.success,
            "duration_ms": result.duration_ms,
            "fallback_used": result.fallback_used,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:500],
        }, indent=2, ensure_ascii=False))
    else:
        status = Color.green("OK") if result.success else Color.red("FAIL")
        print(f"Tool:       {result.tool_name}")
        print(f"Task:       {result.task_type} ({result.confidence:.0%})")
        print(f"Status:     {status} (exit {result.exit_code})")
        print(f"Duration:   {result.duration_ms}ms")
        if result.fallback_used:
            print(f"Fallback:   used")
        if result.stdout.strip():
            print(f"\n--- stdout ---\n{result.stdout.strip()[:1000]}")
        if result.stderr.strip():
            print(f"\n--- stderr ---\n{result.stderr.strip()[:500]}")


def cmd_status(args):
    wizard = SetupWizard()
    wizard.discover()
    available = wizard.available_tools()
    total = len(wizard._tools)

    config = wizard.load_config()
    config_ok = config is not None

    if args.json:
        print(json.dumps({
            "tools_available": len(available),
            "tools_total": total,
            "config_loaded": config_ok,
            "tools": [{"key": t.key, "name": t.name} for t in available],
        }, indent=2, ensure_ascii=False))
    else:
        status_icon = Color.green("OK") if available and config_ok else Color.yellow("!!")
        tools_str = ", ".join(t.name for t in available) or "none"
        config_str = "loaded" if config_ok else "missing (run: setup --save)"
        print(f"[{status_icon}] RoleMesh: {len(available)}/{total} tools ({tools_str}) | config: {config_str}")


def main():
    parser = argparse.ArgumentParser(
        prog="rolemesh",
        description="RoleMesh - AI tool discovery, routing, and execution",
    )
    parser.add_argument("--config", type=str, help="Config path override")
    parser.add_argument("--json", action="store_true", help="JSON output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Visual system dashboard")
    p_dash.add_argument("--tools", action="store_true")
    p_dash.add_argument("--routing", action="store_true")
    p_dash.add_argument("--coverage", action="store_true")
    p_dash.add_argument("--health", action="store_true")
    p_dash.add_argument("--history", action="store_true")
    p_dash.add_argument("--json", action="store_true", dest="json")
    p_dash.add_argument("--config", type=str)

    # setup
    p_setup = subparsers.add_parser("setup", help="Discover tools, build config")
    p_setup.add_argument("--save", action="store_true", help="Save config to disk")
    p_setup.add_argument("--interactive", action="store_true")

    # route
    p_route = subparsers.add_parser("route", help="Classify and route a task")
    p_route.add_argument("task", nargs="*")
    p_route.add_argument("--all", action="store_true", help="Show all matches")
    p_route.add_argument("--json", action="store_true", dest="json")

    # exec
    p_exec = subparsers.add_parser("exec", help="Route and execute a task")
    p_exec.add_argument("task", nargs="*")
    p_exec.add_argument("--tool", type=str, help="Force specific tool")
    p_exec.add_argument("--dry-run", action="store_true")
    p_exec.add_argument("--json", action="store_true", dest="json")

    # status
    p_status = subparsers.add_parser("status", help="One-line health summary")
    p_status.add_argument("--json", action="store_true", dest="json")

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
