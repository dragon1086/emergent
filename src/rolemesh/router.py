#!/usr/bin/env python3
"""
rolemesh/router.py - Task-to-Tool Router

Given a user request, classifies the task type and routes it
to the best available AI tool based on the RoleMesh config.

Usage:
    from src.rolemesh.router import RoleMeshRouter
    router = RoleMeshRouter()
    result = router.route("이 함수 리팩토링해줘")
    # -> {"tool": "claude", "task_type": "refactoring", ...}
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# --- Task Classification ---

TASK_PATTERNS: list[tuple[str, list[str]]] = [
    # (task_type, keyword patterns)
    ("coding", [
        r"코드|code|구현|implement|함수|function|class|클래스",
        r"작성|write|만들어|build|생성|create|추가|add",
    ]),
    ("refactoring", [
        r"리팩토링|refactor|정리|cleanup|개선|improve",
        r"분리|split|추출|extract|단순화|simplify",
    ]),
    ("quick-edit", [
        r"오타|typo|수정|fix|바꿔|change|rename|이름",
        r"삭제|delete|remove|제거",
    ]),
    ("analysis", [
        r"분석|analy[sz]|조사|investigat|원인|cause|왜|why",
        r"디버그|debug|에러|error|버그|bug",
    ]),
    ("architecture", [
        r"아키텍처|architect|설계|design|구조|structur",
        r"마이그레이션|migrat|전략|strateg|시스템|system",
    ]),
    ("reasoning", [
        r"추론|reason|논리|logic|판단|judg|평가|evaluat",
        r"비교|compar|선택|choose|결정|decid",
    ]),
    ("frontend", [
        r"ui|ux|화면|screen|레이아웃|layout|스타일|style|css",
        r"컴포넌트|component|디자인|design|반응형|responsive",
    ]),
    ("multimodal", [
        r"이미지|image|사진|photo|스크린샷|screenshot",
        r"그래프|graph|차트|chart|시각|visual",
    ]),
    ("search", [
        r"검색|search|찾아|find|조회|lookup|문서|doc",
        r"최신|latest|뉴스|news|정보|info",
    ]),
    ("explain", [
        r"설명|explain|이해|understand|알려|tell",
        r"의미|mean|뭐야|what is|어떻게|how",
    ]),
    ("git-integration", [
        r"커밋|commit|브랜치|branch|merge|pr|pull request",
        r"git|깃|리베이스|rebase|체리픽|cherry",
    ]),
    ("completion", [
        r"자동완성|complet|채워|fill|이어서|continu",
        r"다음|next|마저|rest",
    ]),
    ("pair-programming", [
        r"같이|together|페어|pair|도와|help|봐줘|review",
        r"코드리뷰|code review|검토|check",
    ]),
]


@dataclass
class RouteResult:
    tool: str
    tool_name: str
    task_type: str
    confidence: float  # 0.0 ~ 1.0
    fallback: Optional[str]
    reason: str

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "tool_name": self.tool_name,
            "task_type": self.task_type,
            "confidence": round(self.confidence, 2),
            "fallback": self.fallback,
            "reason": self.reason,
        }


class RoleMeshRouter:
    """
    Routes tasks to the best AI tool based on config.

    Loads config from ~/.rolemesh/config.json (built by SetupWizard).
    Falls back to sensible defaults if no config exists.
    """

    DEFAULT_TOOL = "claude"

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".rolemesh" / "config.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {}

    def classify_task(self, request: str) -> list[tuple[str, float]]:
        """
        Classify request into task types with confidence scores.
        Returns sorted list of (task_type, confidence).
        """
        text = request.lower()
        scores: dict[str, float] = {}

        for task_type, patterns in TASK_PATTERNS:
            match_count = 0
            total_patterns = len(patterns)
            for pattern in patterns:
                if re.search(pattern, text):
                    match_count += 1
            if match_count > 0:
                scores[task_type] = match_count / total_patterns

        if not scores:
            return [("coding", 0.3)]  # default: assume coding

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def route(self, request: str) -> RouteResult:
        """
        Route a task to the best available AI tool.

        1. Classify the task type
        2. Look up routing config
        3. Return tool + fallback
        """
        classifications = self.classify_task(request)
        best_type, confidence = classifications[0]

        routing = self.config.get("routing", {})
        tools = self.config.get("tools", {})

        if best_type in routing:
            rule = routing[best_type]
            primary = rule["primary"]
            fallback = rule.get("fallback")
            tool_info = tools.get(primary, {})
            tool_name = tool_info.get("name", primary)
        else:
            primary = self.DEFAULT_TOOL
            fallback = None
            tool_name = "Claude Code"

        return RouteResult(
            tool=primary,
            tool_name=tool_name,
            task_type=best_type,
            confidence=confidence,
            fallback=fallback,
            reason=self._build_reason(best_type, confidence, classifications),
        )

    def route_multi(self, request: str) -> list[RouteResult]:
        """
        Return routing suggestions for all matched task types.
        Useful for complex requests that span multiple categories.
        """
        classifications = self.classify_task(request)
        results = []
        for task_type, confidence in classifications:
            routing = self.config.get("routing", {})
            tools = self.config.get("tools", {})
            if task_type in routing:
                rule = routing[task_type]
                primary = rule["primary"]
                fallback = rule.get("fallback")
                tool_info = tools.get(primary, {})
                tool_name = tool_info.get("name", primary)
            else:
                primary = self.DEFAULT_TOOL
                fallback = None
                tool_name = "Claude Code"
            results.append(RouteResult(
                tool=primary,
                tool_name=tool_name,
                task_type=task_type,
                confidence=confidence,
                fallback=fallback,
                reason=f"Task type '{task_type}' matched with {confidence:.0%} confidence",
            ))
        return results

    def _build_reason(self, task_type: str, confidence: float,
                      all_types: list[tuple[str, float]]) -> str:
        if confidence >= 0.8:
            return f"Strong match for '{task_type}'"
        elif confidence >= 0.5:
            alts = [t for t, _ in all_types[1:3]]
            alt_str = f" (also considered: {', '.join(alts)})" if alts else ""
            return f"Good match for '{task_type}'{alt_str}"
        else:
            return f"Weak match for '{task_type}' - consider specifying task type"


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RoleMesh Task Router")
    parser.add_argument("request", help="Task description to route")
    parser.add_argument("--json", dest="json_out", action="store_true")
    parser.add_argument("--all", action="store_true",
                        help="Show all matching task types")
    args = parser.parse_args()

    router = RoleMeshRouter()

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


if __name__ == "__main__":
    main()
