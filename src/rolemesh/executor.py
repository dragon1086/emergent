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

from .router import RoleMeshRouter

TOOL_COMMANDS = {
    "claude": {
        "cmd": ["claude", "-p"],
        "stdin_mode": False,
    },
    "codex": {
        "cmd": ["codex"],
        "stdin_mode": False,
    },
    "gemini": {
        "cmd": ["gemini"],
        "stdin_mode": False,
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
        "stdin_mode": False,
    },
}


@dataclass
class ExecutionResult:
    tool: str
    tool_name: str
    task_type: str
    confidence: float
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    fallback_used: bool

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class RoleMeshExecutor:
    HISTORY_PATH = Path.home() / ".rolemesh" / "history.jsonl"

    def __init__(
        self,
        config_path: Optional[Path] = None,
        timeout: int = 120,
        dry_run: bool = False,
        history_path: Optional[Path] = None,
    ):
        self._router = RoleMeshRouter(config_path)
        self._timeout = timeout
        self._dry_run = dry_run
        self._history_path = history_path or self.HISTORY_PATH

    def check_tool(self, tool_key: str) -> bool:
        import shutil
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return False
        return shutil.which(cmd_info["cmd"][0]) is not None

    def build_command(
        self, tool_key: str, prompt: str,
        context: Optional[dict] = None,
    ) -> list[str]:
        cmd_info = TOOL_COMMANDS.get(tool_key)
        if not cmd_info:
            return []
        cmd = list(cmd_info["cmd"]) + [prompt]
        if context and "files" in context:
            cmd.extend(context["files"])
        return cmd

    def dispatch(
        self, tool_key: str, prompt: str,
        context: Optional[dict] = None,
    ) -> ExecutionResult:
        cmd = self.build_command(tool_key, prompt, context)
        tool_name = TOOL_COMMANDS.get(tool_key, {}).get("cmd", [tool_key])[0]
        cwd = context.get("cwd") if context else None

        if self._dry_run:
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type="direct", confidence=1.0,
                exit_code=0, stdout=f"[dry-run] {' '.join(cmd)}",
                stderr="", duration_ms=0, fallback_used=False,
            )

        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self._timeout, cwd=cwd,
            )
            duration = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type="direct", confidence=1.0,
                exit_code=result.returncode,
                stdout=result.stdout, stderr=result.stderr,
                duration_ms=duration, fallback_used=False,
            )
        except subprocess.TimeoutExpired:
            duration = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type="direct", confidence=1.0,
                exit_code=124, stdout="", stderr="Timeout expired",
                duration_ms=duration, fallback_used=False,
            )
        except FileNotFoundError:
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type="direct", confidence=1.0,
                exit_code=127, stdout="",
                stderr=f"Tool '{tool_key}' not found on PATH",
                duration_ms=0, fallback_used=False,
            )

    def run(
        self, request: str, context: Optional[dict] = None,
    ) -> ExecutionResult:
        route = self._router.route(request)

        # Try primary tool
        if self.check_tool(route.tool):
            result = self._execute(
                route.tool, route.tool_name,
                route.task_type, route.confidence,
                request, context, fallback_used=False,
            )
            if result.success:
                self._log(result, request)
                return result

        # Try fallback tool
        if route.fallback and self.check_tool(route.fallback):
            result = self._execute(
                route.fallback, route.fallback,
                route.task_type, route.confidence,
                request, context, fallback_used=True,
            )
            self._log(result, request)
            return result

        # Neither available
        result = ExecutionResult(
            tool=route.tool, tool_name=route.tool_name,
            task_type=route.task_type, confidence=route.confidence,
            exit_code=127, stdout="",
            stderr=f"Neither primary ({route.tool}) nor fallback ({route.fallback}) available",
            duration_ms=0, fallback_used=False,
        )
        self._log(result, request)
        return result

    def _execute(
        self, tool_key: str, tool_name: str,
        task_type: str, confidence: float,
        prompt: str, context: Optional[dict],
        fallback_used: bool,
    ) -> ExecutionResult:
        cmd = self.build_command(tool_key, prompt, context)
        cwd = context.get("cwd") if context else None

        if self._dry_run:
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=0, stdout=f"[dry-run] {' '.join(cmd)}",
                stderr="", duration_ms=0, fallback_used=fallback_used,
            )

        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self._timeout, cwd=cwd,
            )
            duration = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=result.returncode,
                stdout=result.stdout, stderr=result.stderr,
                duration_ms=duration, fallback_used=fallback_used,
            )
        except subprocess.TimeoutExpired:
            duration = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=124, stdout="", stderr="Timeout expired",
                duration_ms=duration, fallback_used=fallback_used,
            )
        except FileNotFoundError:
            return ExecutionResult(
                tool=tool_key, tool_name=tool_name,
                task_type=task_type, confidence=confidence,
                exit_code=127, stdout="",
                stderr=f"Tool '{tool_key}' not found",
                duration_ms=0, fallback_used=fallback_used,
            )

    def _log(self, result: ExecutionResult, request: str):
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "request": request[:200],
            "tool": result.tool,
            "task_type": result.task_type,
            "confidence": result.confidence,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "fallback_used": result.fallback_used,
            "success": result.success,
        }
        with open(self._history_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_history(self, limit: int = 50) -> list[dict]:
        if not self._history_path.exists():
            return []
        lines = self._history_path.read_text().strip().split("\n")
        entries = []
        for line in lines[-limit:]:
            if line.strip():
                entries.append(json.loads(line))
        return entries


def main():
    import sys
    request = " ".join(sys.argv[1:]) or "코드 리팩토링해줘"
    executor = RoleMeshExecutor(dry_run=True)
    result = executor.run(request)
    print(f"Tool: {result.tool_name}")
    print(f"Task: {result.task_type} ({result.confidence:.0%})")
    print(f"Command: {result.stdout}")


if __name__ == "__main__":
    main()
