"""
rolemesh/executor.py - Task Executor

Dispatches tasks to AI CLI tools based on routing decisions.
Completes the pipeline: discover -> route -> execute.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import router as router
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
    tool: str
    tool_name: str
    task_type: str
    confidence: float
    exit_code: int
    success: bool
    duration_ms: int
    fallback_used: bool
    stdout: str
    stderr: str


class RoleMeshExecutor:
    def __init__(self, config_path: Optional[Path] = None, dry_run: bool = False):
        self._router = RoleMeshRouter(config_path=config_path)
        self._dry_run = dry_run
        self._history_path = Path.home() / ".rolemesh" / "history.jsonl"

    def dispatch(self, task: str, tool: Optional[str] = None) -> ExecutionResult:
        route_result = self._router.route(task)
        tool_key = tool or route_result.tool

        if tool_key not in TOOL_COMMANDS:
            return ExecutionResult(
                tool=tool_key, tool_name=route_result.tool_name,
                task_type=route_result.task_type, confidence=route_result.confidence,
                exit_code=1, success=False, duration_ms=0, fallback_used=False,
                stdout="", stderr=f"Unknown tool: {tool_key}",
            )

        return self.run(tool_key, task, route_result)

    def run(self, tool_key: str, task: str, route_result) -> ExecutionResult:
        cmd_info = TOOL_COMMANDS[tool_key]
        cmd = cmd_info["cmd"] + [task]

        if self._dry_run:
            return ExecutionResult(
                tool=tool_key, tool_name=route_result.tool_name,
                task_type=route_result.task_type, confidence=route_result.confidence,
                exit_code=0, success=True, duration_ms=0, fallback_used=False,
                stdout=f"[dry-run] {' '.join(cmd)}", stderr="",
            )

        start = time.time()
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
            )
            duration_ms = int((time.time() - start) * 1000)

            result = ExecutionResult(
                tool=tool_key, tool_name=route_result.tool_name,
                task_type=route_result.task_type, confidence=route_result.confidence,
                exit_code=proc.returncode, success=proc.returncode == 0,
                duration_ms=duration_ms, fallback_used=False,
                stdout=proc.stdout.decode(errors="replace"),
                stderr=proc.stderr.decode(errors="replace"),
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            result = ExecutionResult(
                tool=tool_key, tool_name=route_result.tool_name,
                task_type=route_result.task_type, confidence=route_result.confidence,
                exit_code=1, success=False,
                duration_ms=duration_ms, fallback_used=False,
                stdout="", stderr=str(e),
            )

        self._log_history(result)
        return result

    def _log_history(self, result: ExecutionResult):
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tool": result.tool,
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
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "코드 리팩토링해줘"
    executor = RoleMeshExecutor(dry_run=True)
    result = executor.dispatch(task)
    print(f"Tool: {result.tool_name}")
    print(f"Task: {result.task_type} ({result.confidence:.0%})")
    print(f"Status: {'OK' if result.success else 'FAIL'} (exit {result.exit_code})")
    print(f"Duration: {result.duration_ms}ms")
    if result.stdout:
        print(f"\n--- stdout ---\n{result.stdout}")


if __name__ == "__main__":
    main()
