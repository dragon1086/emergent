"""
RoleMesh CLI - Unified entry point for all rolemesh commands.

Usage:
    python -m src.rolemesh dashboard [--tools|--routing|--coverage|--health|--history] [--json]
    python -m src.rolemesh setup [--save] [--interactive]
    python -m src.rolemesh route "task description" [--all] [--json]
    python -m src.rolemesh exec "task description" [--tool X] [--dry-run] [--json]
    python -m src.rolemesh status [--json]
"""

import argparse
import json
import sys
from pathlib import Path


def cmd_dashboard(args) -> None:
    """Show system dashboard with tools, routing, coverage, and health."""
    from .dashboard import RoleMeshDashboard, Color

    if getattr(args, "no_color", False):
        Color.set_enabled(False)

    dashboard = RoleMeshDashboard(
        config_path=Path(args.config) if args.config else None,
    )
    dashboard.collect()

    if args.json_out:
        print(json.dumps(dashboard.data.to_dict(),
                         ensure_ascii=False, indent=2))
        return

    if args.tools:
        print(dashboard.render_tools())
    elif args.routing:
        print(dashboard.render_routing())
    elif args.coverage:
        print(dashboard.render_coverage())
    elif args.health:
        print(dashboard.render_health())
    elif getattr(args, "history", False):
        print(dashboard.render_history())
    else:
        print(dashboard.render_full())


def cmd_setup(args) -> None:
    """Discover tools and build routing config."""
    from .builder import SetupWizard

    wizard = SetupWizard()
    if args.config:
        wizard.config_path = Path(args.config)
    wizard.discover()

    if args.interactive:
        print("=== RoleMesh Setup Wizard ===\n")
        print(wizard.summary())
        for t in wizard.available_tools():
            answer = input(f"Prefer {t.name}? [y/n/skip] ").strip().lower()
            if answer == "y":
                t.user_preference = 1
            elif answer == "n":
                t.user_preference = -1

    config = wizard.build_config()

    if args.json_out:
        print(json.dumps(config, ensure_ascii=False, indent=2))
    else:
        routing = config.get("routing", {})
        print(f"\nRouting rules ({len(routing)} task types):")
        for task_type, rule in sorted(routing.items()):
            fallback = rule.get("fallback", "")
            fb_str = f" (fallback: {fallback})" if fallback else ""
            print(f"  {task_type} -> {rule.get('primary', '?')}{fb_str}")

    if args.save:
        wizard.save_config()
        print(f"\nConfig saved to {wizard.config_path}")


def cmd_route(args) -> None:
    """Classify and route a task request."""
    from .router import RoleMeshRouter

    router = RoleMeshRouter(
        config_path=Path(args.config) if args.config else None,
    )

    if args.all:
        results = router.route_multi(args.request)
        if args.json_out:
            print(json.dumps([r.to_dict() for r in results],
                             ensure_ascii=False, indent=2))
        else:
            for r in results:
                print(f"  [{r.confidence:.0%}] {r.task_type} "
                      f"-> {r.tool_name} ({r.tool})")
    else:
        result = router.route(args.request)
        if args.json_out:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"-> {result.tool_name} ({result.tool})")
            print(f"   Task: {result.task_type}")
            if result.fallback:
                print(f"   Fallback: {result.fallback}")
            print(f"   {result.reason}")


def cmd_exec(args) -> None:
    """Route and execute a task via AI CLI tool."""
    from .executor import RoleMeshExecutor

    executor = RoleMeshExecutor(
        config_path=Path(args.config) if args.config else None,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )

    if args.tool:
        result = executor.dispatch(args.tool, args.request)
    else:
        result = executor.run(args.request)

    if args.json_out:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
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


def cmd_status(args) -> None:
    """Quick health summary (one-liner)."""
    from .dashboard import RoleMeshDashboard

    dashboard = RoleMeshDashboard(
        config_path=Path(args.config) if args.config else None,
    )
    dashboard.collect()
    data = dashboard.data

    available = [t for t in data.tools if t.available]
    tool_names = ", ".join(t.name for t in available) or "none"
    passed = sum(1 for c in data.health_checks if c.passed)
    total = len(data.health_checks)
    healthy = "OK" if passed == total else "!!"

    if args.json_out:
        print(json.dumps({
            "tools_available": len(available),
            "tools_total": len(data.tools),
            "tool_names": tool_names,
            "health_passed": passed,
            "health_total": total,
            "healthy": passed == total,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"[{healthy}] {len(available)} tools ({tool_names}) "
              f"| health {passed}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rolemesh",
        description="RoleMesh - AI Tool Discovery & Task Routing CLI",
        epilog=(
            "Examples:\n"
            "  python -m src.rolemesh dashboard          # full dashboard\n"
            "  python -m src.rolemesh dashboard --health  # health only\n"
            "  python -m src.rolemesh setup --save        # discover + save config\n"
            "  python -m src.rolemesh route '코드 리팩토링'  # classify task\n"
            "  python -m src.rolemesh exec --dry-run 'UI 수정'  # dry-run exec\n"
            "  python -m src.rolemesh status              # quick health check\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=str,
                        help="Path to config file "
                             "(default: ~/.rolemesh/config.json)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # dashboard
    p_dash = subparsers.add_parser("dashboard", aliases=["dash", "d"],
                                   help="Show system dashboard")
    p_dash.add_argument("--tools", action="store_true", help="Tools only")
    p_dash.add_argument("--routing", action="store_true",
                        help="Routing table only")
    p_dash.add_argument("--coverage", action="store_true",
                        help="Coverage matrix only")
    p_dash.add_argument("--health", action="store_true",
                        help="Health check only")
    p_dash.add_argument("--history", action="store_true",
                        help="Execution history")
    p_dash.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON output")
    p_dash.add_argument("--no-color", action="store_true",
                        help="Disable colors")

    # setup
    p_setup = subparsers.add_parser("setup", aliases=["s"],
                                    help="Discover tools and build config")
    p_setup.add_argument("--save", action="store_true",
                         help="Save config to disk")
    p_setup.add_argument("--interactive", "-i", action="store_true",
                         help="Guided setup (set preferences)")
    p_setup.add_argument("--json", dest="json_out", action="store_true",
                         help="JSON output")

    # route
    p_route = subparsers.add_parser("route", aliases=["r"],
                                    help="Classify and route a task")
    p_route.add_argument("request", help="Task description to route")
    p_route.add_argument("--all", action="store_true",
                         help="Show all matching task types")
    p_route.add_argument("--json", dest="json_out", action="store_true",
                         help="JSON output")

    # exec
    p_exec = subparsers.add_parser("exec", aliases=["x"],
                                   help="Route and execute a task")
    p_exec.add_argument("request", help="Task description")
    p_exec.add_argument("--tool", type=str,
                        help="Force a specific tool (skip routing)")
    p_exec.add_argument("--dry-run", action="store_true",
                        help="Show command without executing")
    p_exec.add_argument("--timeout", type=int, default=120,
                        help="Timeout in seconds (default: 120)")
    p_exec.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON output")

    # status
    p_status = subparsers.add_parser("status", aliases=["st"],
                                     help="Quick health summary")
    p_status.add_argument("--json", dest="json_out", action="store_true",
                          help="JSON output")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "dashboard": cmd_dashboard, "dash": cmd_dashboard, "d": cmd_dashboard,
        "setup": cmd_setup, "s": cmd_setup,
        "route": cmd_route, "r": cmd_route,
        "exec": cmd_exec, "x": cmd_exec,
        "status": cmd_status, "st": cmd_status,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
