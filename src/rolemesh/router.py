"""
rolemesh/router.py - Task-to-Tool Router

Given a user request, classifies the task type and routes it
to the best AI CLI tool based on config.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

TASK_PATTERNS: list[tuple[str, tuple[str, str]]] = [
    ("coding", (
        r"코드|code|구현|implement|함수|function|class|클래스",
        r"작성|write|만들어|build|생성|create|추가|add",
    )),
    ("refactoring", (
        r"리팩토링|refactor|정리|cleanup|개선|improve",
        r"분리|split|추출|extract|단순화|simplify",
    )),
    ("quick-edit", (
        r"오타|typo|수정|fix|바꿔|change|rename|이름",
        r"삭제|delete|remove|제거",
    )),
    ("analysis", (
        r"분석|analy[sz]|조사|investigat|원인|cause|왜|why",
        r"디버그|debug|에러|error|버그|bug",
    )),
    ("architecture", (
        r"아키텍처|architect|설계|design|구조|structur",
        r"마이그레이션|migrat|전략|strateg|시스템|system",
    )),
    ("reasoning", (
        r"추론|reason|논리|logic|판단|judg|평가|evaluat",
        r"비교|compar|선택|choose|결정|decid",
    )),
    ("frontend", (
        r"ui|ux|화면|screen|레이아웃|layout|스타일|style|css",
        r"컴포넌트|component|디자인|design|반응형|responsive",
    )),
    ("multimodal", (
        r"이미지|image|사진|photo|스크린샷|screenshot",
        r"그래프|graph|차트|chart|시각|visual",
    )),
    ("search", (
        r"검색|search|찾아|find|조회|lookup|문서|doc",
        r"최신|latest|뉴스|news|정보|info",
    )),
    ("explain", (
        r"설명|explain|이해|understand|알려|tell",
        r"의미|mean|뭐야|what is|어떻게|how",
    )),
    ("git-integration", (
        r"커밋|commit|브랜치|branch|merge|pr|pull request",
        r"git|깃|리베이스|rebase|체리픽|cherry",
    )),
    ("completion", (
        r"자동완성|complet|채워|fill|이어서|continu",
        r"다음|next|마저|rest",
    )),
    ("pair-programming", (
        r"같이|together|페어|pair|도와|help|봐줘|review",
        r"코드리뷰|code review|검토|check",
    )),
]


@dataclass
class RouteResult:
    tool: str
    tool_name: str
    task_type: str
    confidence: float
    fallback: Optional[str]
    reason: str


class RoleMeshRouter:
    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or Path.home() / ".rolemesh" / "config.json"
        self._config: Optional[dict] = None
        if self._config_path.exists():
            self._config = json.loads(self._config_path.read_text())

    def classify_task(self, request: str) -> list[tuple[str, float]]:
        results = []
        text = request.lower()
        for task_type, patterns in TASK_PATTERNS:
            matched = 0
            total = len(patterns)
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched += 1
            if matched > 0:
                confidence = matched / total
                results.append((task_type, confidence))
        results.sort(key=lambda x: -x[1])
        return results

    def route(self, request: str) -> RouteResult:
        classifications = self.classify_task(request)
        if not classifications:
            return RouteResult(
                tool="claude", tool_name="Claude Code",
                task_type="coding", confidence=0.0,
                fallback=None, reason="No pattern match; defaulting to Claude Code",
            )

        task_type, confidence = classifications[0]

        if self._config and "routing" in self._config:
            routing = self._config["routing"]
            if task_type in routing:
                rule = routing[task_type]
                primary = rule["primary"]
                fallback = rule.get("fallback")
                tool_name = primary
                if self._config and "tools" in self._config:
                    tool_info = self._config["tools"].get(primary, {})
                    tool_name = tool_info.get("name", primary)
                return RouteResult(
                    tool=primary, tool_name=tool_name,
                    task_type=task_type, confidence=confidence,
                    fallback=fallback,
                    reason=f"Matched '{task_type}' (confidence={confidence:.1%}), routed to {tool_name}",
                )

        return RouteResult(
            tool="claude", tool_name="Claude Code",
            task_type=task_type, confidence=confidence,
            fallback=None,
            reason=f"Matched '{task_type}' (confidence={confidence:.1%}), no config; defaulting to Claude Code",
        )

    def route_multi(self, request: str) -> list[RouteResult]:
        classifications = self.classify_task(request)
        results = []
        for task_type, confidence in classifications:
            if self._config and "routing" in self._config:
                routing = self._config["routing"]
                if task_type in routing:
                    rule = routing[task_type]
                    primary = rule["primary"]
                    fallback = rule.get("fallback")
                    tool_name = primary
                    if "tools" in self._config:
                        tool_info = self._config["tools"].get(primary, {})
                        tool_name = tool_info.get("name", primary)
                    results.append(RouteResult(
                        tool=primary, tool_name=tool_name,
                        task_type=task_type, confidence=confidence,
                        fallback=fallback,
                        reason=f"Matched '{task_type}' ({confidence:.1%})",
                    ))
                    continue
            results.append(RouteResult(
                tool="claude", tool_name="Claude Code",
                task_type=task_type, confidence=confidence,
                fallback=None,
                reason=f"Matched '{task_type}' ({confidence:.1%}), no routing config",
            ))
        return results


def main():
    import sys
    request = " ".join(sys.argv[1:]) or "코드 리팩토링해줘"
    router = RoleMeshRouter()
    classifications = router.classify_task(request)
    print(f"Request: {request}")
    print(f"Classifications: {classifications}")
    result = router.route(request)
    print(f"Route: {result.tool_name} ({result.task_type}, {result.confidence:.0%})")
    print(f"Reason: {result.reason}")


if __name__ == "__main__":
    main()
