"""
rolemesh/executor.py - Task Executor

Dispatches tasks to AI CLI tools based on routing decisions.
Completes the pipeline: classify -> route -> execute.

Usage:
    python -m src.rolemesh.executor "이 함수 리팩토링해줘"
    python -m src.rolemesh.executor --dry-run "UI 컴포넌트 수정"
    python -m src.rolemesh.executor --tool claude "explain this code"
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import router as router_mod
from .router import RoleMeshRouter, RouteResult


# ─── Tool Commands ───────────────────────────────────────────────────────────

TOOL_COMMANDS: dict[str, dict] = {
    "claude": {"cmd": "claude", "stdin_mode": False},
    "codex": {"cmd": "codex", "stdin_mode": False},
    "gemini": {"cmd": "gemini", "stdin_mode": False},
    "aider": {"cmd": "aider", "stdin_mode": False},
    "copilot": {"cmd": "copilot", "stdin_mode": False},
    "cursor": {"cmd": "cursor", "stdin_mode": False},
}


# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """Result of dispatching a task to an AI tool."""
    tool: str
    tool_name: str
    task_type: str
    confidence: float
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    fallback_used: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "tool_name": self.tool_name,
            "task_type": self.task_type,
            "confidence": self.confidence,
            "exit_code": self.exit_code,
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "fallback_used": self.fallback_used,
        }


# ─── Executor ────────────────────────────────────────────────────────────────

class RoleMeshExecutor:
    """
    Executes tasks by routing to the best AI CLI tool.

    Pipeline:
      1. Router classifies the task
      2. Executor checks tool availability
      3. Dispatches via subprocess
      4. Falls back to alternate tool on failure
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        timeout: int = 120,
        dry_run: bool = False,
        history_path: Optional[Path] = None,
    ):
        self.router = RoleMeshRouter(config_path=config_path)
        self.timeout = timeout
        self.dry_run = dry_run
        self.history_path = history_path or (
            Path.home() / ".rolemesh" / "history.jsonl"
        )

    def _log_history(
        self, request: str, result: "ExecutionResult"
    ) -> None:
        """Append execution record to history JSONL file."""
        if self.dry_run:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request": request[:200],
            "tool": result.tool,
            "task_type": result.task_type,
            "confidence": result.confidence,
            "success": result.success,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "fallback_used": result.fallback_used,
        }
        with open(self.history_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_history(self, limit: int = 50) -> list[dict]:
        """Read recent execution history entries."""
        if not self.history_path.exists():
            return []
        entries: list[dict] = []
        with open(self.history_path) as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except (json.JSONDecodeError, OSError):
                        pass
        return entries[-limit:]

    def check_tool(self, tool_key: str) -> bool:
        """Check if a tool's CLI binary is available on PATH."""
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return False
        return bool(shutil.which(cmd_info["cmd"]))

    def build_command(
        self,
        tool_key: str,
        prompt: str,
        context: Optional[dict] = None,
    ) -> list[str]:
        """Build the CLI command for a given tool and prompt."""
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return []
        cmd = [cmd_info["cmd"]]
        if cmd_info.get("stdin_mode"):
            pass  # stdin tools get prompt via stdin
        else:
            cmd.append("-p")
            cmd.append(prompt)
        if context and context.get("files"):
            for f in context["files"]:
                cmd.append(str(f))
        return cmd

    def dispatch(
        self,
        tool_key: str,
        prompt: str,
        context: Optional[dict] = None,
    ) -> ExecutionResult:
        """
        Dispatch a prompt to a specific tool via subprocess.
        Returns ExecutionResult with stdout/stderr/exit_code.
        """
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return ExecutionResult(
                tool=tool_key, tool_name=f"Unknown tool: {tool_key}",
                task_type="direct", confidence=1.0,
                exit_code=127, stdout="", stderr=f"Unknown tool: {tool_key}",
                duration_ms=0,
            )

        cmd = self.build_command(tool_key, prompt, context)

        if self.dry_run:
            return ExecutionResult(
                tool=tool_key, tool_name=cmd_info["cmd"],
                task_type="direct", confidence=1.0,
                exit_code=0,
                stdout=f"[dry-run] Would execute: {' '.join(cmd)}",
                stderr="", duration_ms=0,
            )

        return self._run_subprocess(cmd, tool_key, prompt)

    def run(
        self,
        request: str,
        context: Optional[dict] = None,
    ) -> ExecutionResult:
        """
        Full pipeline: route the request, then execute.

        1. Classify + route
        2. Check tool availability
        3. Execute (with fallback on failure)
        """
        route = self.router.route(request)

        # Check primary tool availability
        if not self.check_tool(route.tool):
            if route.fallback and self.check_tool(route.fallback):
                print(f"Primary '{route.tool}' unavailable, using fallback")
                route = RouteResult(
                    tool=route.fallback,
                    tool_name=route.fallback,
                    task_type=route.task_type,
                    confidence=route.confidence,
                    fallback=None,
                    reason=route.reason,
                )
            else:
                msg = f"Tool '{route.tool}' not found on PATH"
                if route.fallback:
                    msg += f" (fallback '{route.fallback}' also unavailable)"
                return ExecutionResult(
                    tool=route.tool, tool_name=route.tool_name,
                    task_type=route.task_type, confidence=route.confidence,
                    exit_code=127, stdout="", stderr=msg, duration_ms=0,
                )

        result = self._execute_tool(route, request, context)

        # Try fallback on failure
        if not result.success and route.fallback and self.check_tool(route.fallback):
            print(f"Tool '{route.tool}' failed (exit {result.exit_code}), "
                  f"using fallback")
            fallback_route = RouteResult(
                tool=route.fallback,
                tool_name=route.fallback,
                task_type=route.task_type,
                confidence=route.confidence,
            )
            result = self._execute_tool(fallback_route, request, context)
            result.fallback_used = True

        self._log_history(request, result)
        return result

    def _execute_tool(
        self,
        route: RouteResult,
        prompt: str,
        context: Optional[dict] = None,
    ) -> ExecutionResult:
        """Execute a routed task."""
        cmd = self.build_command(route.tool, prompt, context)
        if not cmd:
            return ExecutionResult(
                tool=route.tool, tool_name=route.tool_name,
                task_type=route.task_type, confidence=route.confidence,
                exit_code=127, stdout="",
                stderr=f"No command config for tool: {route.tool}",
                duration_ms=0,
            )

        if self.dry_run:
            return ExecutionResult(
                tool=route.tool, tool_name=route.tool_name,
                task_type=route.task_type, confidence=route.confidence,
                exit_code=0,
                stdout=f"[dry-run] Would execute: {' '.join(cmd)}",
                stderr="", duration_ms=0,
            )

        return self._run_subprocess(cmd, route.tool, prompt, route)

    def _run_subprocess(
        self,
        cmd: list[str],
        tool_key: str,
        prompt: str,
        route: Optional[RouteResult] = None,
    ) -> ExecutionResult:
        """Run the actual subprocess."""
        cmd_info = TOOL_COMMANDS.get(tool_key, {})
        task_type = route.task_type if route else "direct"
        confidence = route.confidence if route else 1.0
        tool_name = route.tool_name if route else tool_key

        start = time.monotonic()
        try:
            stdin_data = prompt if cmd_info.get("stdin_mode") else None
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input=stdin_data,
                cwd=cmd_info.get("cwd"),
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=proc.returncode,
                stdout=proc.stdout, stderr=proc.stderr,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=-1, stdout="",
                stderr=f"Timeout after {self.timeout}s",
                duration_ms=duration_ms,
            )
        except OSError as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=126, stdout="",
                stderr=f"OS error: {e}",
                duration_ms=duration_ms,
            )


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rolemesh-executor",
        description="RoleMesh Executor - route and execute AI tasks",
        epilog=(
            "Examples:\n"
            "  python -m src.rolemesh.executor '이 함수 리팩토링해줘'\n"
            "  python -m src.rolemesh.executor --dry-run 'UI 컴포넌트 수정'\n"
            "  python -m src.rolemesh.executor --tool claude 'explain this code'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("request", help="Task description")
    parser.add_argument("--tool", type=str,
                        help="Force a specific tool (skip routing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be executed without running")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout in seconds (default: 120)")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON output")
    args = parser.parse_args()

    executor = RoleMeshExecutor(
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


if __name__ == "__main__":
    main()
