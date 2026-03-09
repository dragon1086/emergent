"""
rolemesh/executor.py - Task Executor

Dispatches tasks to AI CLI tools based on routing decisions.
Completes the pipeline: classify -> route -> execute.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import router
from .router import RoleMeshRouter


TOOL_COMMANDS = {
    "claude": {"cmd": ["claude", "-p"], "stdin_mode": False},
    "codex": {"cmd": ["codex", "-p"], "stdin_mode": False},
    "gemini": {"cmd": ["gemini", "-p"], "stdin_mode": False},
    "aider": {"cmd": ["aider", "--message"], "stdin_mode": False},
    "copilot": {"cmd": ["gh", "copilot", "-p"], "stdin_mode": False},
    "cursor": {"cmd": ["cursor", "-p"], "stdin_mode": False},
}


@dataclass
class ExecutionResult:
    tool_name: str
    task_type: str
    confidence: float
    success: bool
    exit_code: int
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    fallback_used: bool = False


class RoleMeshExecutor:
    def __init__(self, config_path: Optional[Path] = None, dry_run: bool = False):
        self._router = RoleMeshRouter(config_path)
        self._dry_run = dry_run
        self._history_path = Path.home() / ".rolemesh" / "history.jsonl"

    def dispatch(self, task: str, tool: Optional[str] = None) -> ExecutionResult:
        route_result = self._router.route(task)

        tool_key = tool or route_result.tool_name
        if tool_key not in TOOL_COMMANDS:
            return ExecutionResult(
                tool_name=tool_key, task_type=route_result.task_type,
                confidence=route_result.confidence,
                success=False, exit_code=-1, duration_ms=0,
                stderr=f"Unknown tool: {tool_key}",
            )

        result = self.run(tool_key, task, route_result)
        if not result.success and route_result.fallback:
            fallback_key = route_result.fallback
            if fallback_key in TOOL_COMMANDS:
                fallback_result = self.run(fallback_key, task, route_result)
                fallback_result.fallback_used = True
                return fallback_result

        return result

    def run(self, tool_key: str, task: str, route_result=None) -> ExecutionResult:
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return ExecutionResult(
                tool_name=tool_key, task_type="unknown",
                confidence=0.0, success=False, exit_code=-1,
                duration_ms=0, stderr=f"No command for {tool_key}",
            )

        cmd = cmd_info["cmd"] + [task]

        if self._dry_run:
            return ExecutionResult(
                tool_name=tool_key,
                task_type=route_result.task_type if route_result else "unknown",
                confidence=route_result.confidence if route_result else 0.0,
                success=True, exit_code=0, duration_ms=0,
                stdout=f"[dry-run] would execute: {' '.join(cmd)}",
            )

        start = time.time()
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=300,
            )
            duration_ms = int((time.time() - start) * 1000)
            result = ExecutionResult(
                tool_name=tool_key,
                task_type=route_result.task_type if route_result else "unknown",
                confidence=route_result.confidence if route_result else 0.0,
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=proc.stdout.decode(),
                stderr=proc.stderr.decode(),
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            result = ExecutionResult(
                tool_name=tool_key,
                task_type=route_result.task_type if route_result else "unknown",
                confidence=route_result.confidence if route_result else 0.0,
                success=False, exit_code=-1,
                duration_ms=duration_ms, stderr=str(e),
            )

        self._log_history(result)
        return result

    def _log_history(self, result: ExecutionResult):
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "tool": result.tool_name,
                "task_type": result.task_type,
                "success": result.success,
                "duration_ms": result.duration_ms,
            }
            with open(self._history_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


def main():
    import sys
    if len(sys.argv) < 2:
        return
    task = " ".join(sys.argv[1:])
    executor = RoleMeshExecutor()
    result = executor.dispatch(task)
    print(f"Tool: {result.tool_name} | Type: {result.task_type} | Conf: {result.confidence:.2f}")
    print(f"Success: {result.success} | Exit: {result.exit_code} | Time: {result.duration_ms}ms")
    if result.stdout:
        print(result.stdout)


if __name__ == "__main__":
    main()
