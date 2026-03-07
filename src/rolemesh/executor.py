#!/usr/bin/env python3
"""
rolemesh/executor.py - Task Executor

Dispatches tasks to AI CLI tools based on routing decisions.
Completes the pipeline: discover -> route -> execute.

Usage:
    from src.rolemesh.executor import RoleMeshExecutor
    executor = RoleMeshExecutor()
    result = executor.run("이 함수 리팩토링해줘", context={"file": "main.py"})
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .router import RoleMeshRouter, RouteResult


# --- Tool CLI Commands ---

TOOL_COMMANDS: dict[str, dict] = {
    "claude": {
        "cmd": ["claude", "-p"],
        "stdin_mode": False,  # prompt via args
    },
    "codex": {
        "cmd": ["codex"],
        "stdin_mode": True,  # prompt via stdin
    },
    "gemini": {
        "cmd": ["gemini"],
        "stdin_mode": True,
    },
    "aider": {
        "cmd": ["aider", "--message"],
        "stdin_mode": False,
    },
    "copilot": {
        "cmd": ["gh", "copilot", "suggest"],
        "stdin_mode": False,
    },
    "cursor": {
        "cmd": ["cursor"],
        "stdin_mode": True,
    },
}


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
            "confidence": round(self.confidence, 2),
            "exit_code": self.exit_code,
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "fallback_used": self.fallback_used,
        }


class RoleMeshExecutor:
    """
    Executes tasks by routing to the best AI CLI tool.

    Pipeline:
      1. Router classifies the task
      2. Executor checks tool availability
      3. Dispatches via subprocess
      4. Falls back to alternate tool on failure
    """

    def __init__(self, config_path: Optional[Path] = None,
                 timeout: int = 120, dry_run: bool = False):
        self.router = RoleMeshRouter(config_path=config_path)
        self.timeout = timeout
        self.dry_run = dry_run

    def check_tool(self, tool_key: str) -> bool:
        """Check if a tool's CLI binary is available on PATH."""
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return False
        binary = cmd_info["cmd"][0]
        return shutil.which(binary) is not None

    def build_command(self, tool_key: str, prompt: str,
                      context: Optional[dict] = None) -> Optional[list[str]]:
        """Build the CLI command for a given tool and prompt."""
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return None

        cmd = list(cmd_info["cmd"])

        if not cmd_info["stdin_mode"]:
            cmd.append(prompt)

        # Append file context if provided
        if context and context.get("files"):
            for f in context["files"]:
                cmd.append(str(f))

        return cmd

    def dispatch(self, tool_key: str, prompt: str,
                 context: Optional[dict] = None) -> ExecutionResult:
        """
        Dispatch a prompt to a specific tool via subprocess.
        Returns ExecutionResult with stdout/stderr/exit_code.
        """
        route = RouteResult(
            tool=tool_key,
            tool_name=TOOL_COMMANDS.get(tool_key, {}).get("cmd", [tool_key])[0],
            task_type="direct",
            confidence=1.0,
            fallback=None,
            reason="Direct dispatch",
        )

        cmd = self.build_command(tool_key, prompt, context)
        if not cmd:
            return ExecutionResult(
                tool=tool_key, tool_name=tool_key,
                task_type="direct", confidence=1.0,
                exit_code=127, stdout="",
                stderr=f"Unknown tool: {tool_key}",
                duration_ms=0,
            )

        if self.dry_run:
            return ExecutionResult(
                tool=tool_key, tool_name=route.tool_name,
                task_type="direct", confidence=1.0,
                exit_code=0,
                stdout=f"[dry-run] Would execute: {' '.join(cmd)}",
                stderr="", duration_ms=0,
            )

        return self._run_subprocess(cmd, tool_key, route, prompt, context)

    def run(self, request: str, context: Optional[dict] = None) -> ExecutionResult:
        """
        Full pipeline: route the request, then execute.

        1. Classify + route
        2. Check tool availability
        3. Execute (with fallback on failure)
        """
        route = self.router.route(request)

        # Check primary tool
        if not self.check_tool(route.tool):
            # Try fallback
            if route.fallback and self.check_tool(route.fallback):
                route = RouteResult(
                    tool=route.fallback,
                    tool_name=route.fallback,
                    task_type=route.task_type,
                    confidence=route.confidence,
                    fallback=None,
                    reason=f"Primary '{route.tool}' unavailable, using fallback",
                )
                result = self._execute_tool(route, request, context)
                result.fallback_used = True
                return result
            else:
                return ExecutionResult(
                    tool=route.tool, tool_name=route.tool_name,
                    task_type=route.task_type, confidence=route.confidence,
                    exit_code=127, stdout="",
                    stderr=f"Tool '{route.tool}' not found on PATH"
                           + (f" (fallback '{route.fallback}' also unavailable)"
                              if route.fallback else ""),
                    duration_ms=0,
                )

        result = self._execute_tool(route, request, context)

        # On failure, try fallback
        if not result.success and route.fallback and self.check_tool(route.fallback):
            fallback_route = RouteResult(
                tool=route.fallback,
                tool_name=route.fallback,
                task_type=route.task_type,
                confidence=route.confidence,
                fallback=None,
                reason=f"Primary '{route.tool}' failed (exit {result.exit_code}), using fallback",
            )
            fallback_result = self._execute_tool(fallback_route, request, context)
            fallback_result.fallback_used = True
            return fallback_result

        return result

    def _execute_tool(self, route: RouteResult, prompt: str,
                      context: Optional[dict] = None) -> ExecutionResult:
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

        return self._run_subprocess(cmd, route.tool, route, prompt, context)

    def _run_subprocess(self, cmd: list[str], tool_key: str,
                        route: RouteResult, prompt: str,
                        context: Optional[dict] = None) -> ExecutionResult:
        """Run the actual subprocess."""
        cmd_info = TOOL_COMMANDS.get(tool_key, {})
        stdin_data = prompt if cmd_info.get("stdin_mode") else None

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=context.get("cwd") if context else None,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=route.tool, tool_name=route.tool_name,
                task_type=route.task_type, confidence=route.confidence,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=route.tool, tool_name=route.tool_name,
                task_type=route.task_type, confidence=route.confidence,
                exit_code=-1, stdout="",
                stderr=f"Timeout after {self.timeout}s",
                duration_ms=duration_ms,
            )
        except OSError as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=route.tool, tool_name=route.tool_name,
                task_type=route.task_type, confidence=route.confidence,
                exit_code=126, stdout="",
                stderr=f"OS error: {e}",
                duration_ms=duration_ms,
            )


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="RoleMesh Executor - route and execute AI tasks",
        epilog="Examples:\n"
               "  python -m src.rolemesh.executor '이 함수 리팩토링해줘'\n"
               "  python -m src.rolemesh.executor --dry-run 'UI 컴포넌트 수정'\n"
               "  python -m src.rolemesh.executor --tool claude 'explain this code'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("request", help="Task description")
    parser.add_argument("--tool", type=str, default=None,
                        help="Force a specific tool (skip routing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be executed without running")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout in seconds (default: 120)")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON output")
    args = parser.parse_args()

    executor = RoleMeshExecutor(timeout=args.timeout, dry_run=args.dry_run)

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


if __name__ == "__main__":
    main()
