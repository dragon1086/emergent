#!/usr/bin/env python3
"""
router.py — 태스크 복잡도 기반 실행 경로 자동 라우터
구현자: cokac-bot

배경:
  amp가 Claude Code 위에서 동작할 때, 모든 요청을 토론할 필요가 없다.
  복잡도에 따라 자동으로 경로를 결정하는 라우터.

경로:
  "direct" — Claude Code 직행           (복잡도 < 0.3)
  "review" — amp 1라운드 리뷰 후 실행  (복잡도 0.3 ~ 0.7)
  "debate" — amp 풀 토론 후 실행        (복잡도 > 0.7)

사용법:
  python router.py "오타 고쳐줘"                   # → direct
  python router.py "Redis 도입할까?"               # → debate
  python router.py --explain "이 함수 최적화해줘"  # 이유 포함 출력
  python router.py --json "마이크로서비스 설계해줘" # JSON 출력
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path

# ─── 키워드 사전 (1차 필터 — 빠름) ──────────────────────────────────────────

# (패턴 리스트, 복잡도 점수)
KEYWORD_RULES: list[tuple[list[str], float]] = [
    # direct (< 0.3): 단순 수정, 오타, 이름 변경
    (["오타", "typo", "rename", "이름변경", "고쳐줘", "수정해줘", "바꿔줘",
      "삭제해줘", "추가해줘", "주석", "comment", "indent", "들여쓰기"], 0.1),

    # review (0.3 ~ 0.7): 기능 개선, 최적화, 리팩토링
    (["최적화", "optimize", "리팩토링", "refactor", "개선", "improve",
      "성능", "performance", "캐싱", "caching", "로깅", "logging",
      "테스트", "test", "검토", "review", "정리", "cleanup"], 0.5),

    # debate (> 0.7): 아키텍처, 설계, 도입, 전략
    (["아키텍처", "architecture", "설계", "design", "구조", "structure",
      "도입", "introduce", "migration", "마이그레이션", "전략", "strategy",
      "마이크로서비스", "microservice", "분산", "distributed",
      "데이터베이스 설계", "db design", "api 설계", "api design",
      "보안", "security", "인증", "auth", "창발", "emergence",
      "프레임워크", "framework", "플랫폼", "platform"], 0.9),
]

# ─── 복잡도 계산 ─────────────────────────────────────────────────────────────

def keyword_score(request: str) -> tuple[float | None, str]:
    """
    키워드 기반 1차 복잡도 평가.
    매칭되면 (score, matched_keyword) 반환.
    불확실하면 (None, "") 반환.
    """
    text = request.lower()

    best_score: float | None = None
    best_kw = ""

    for keywords, score in KEYWORD_RULES:
        for kw in keywords:
            if kw.lower() in text:
                # 가장 높은 점수 우선 (debate > review > direct)
                if best_score is None or score > best_score:
                    best_score = score
                    best_kw = kw

    return best_score, best_kw


def llm_score(request: str) -> tuple[float, str]:
    """
    LLM 2차 평가 — Claude CLI 호출.
    복잡도 0~1 스코어 + 한 줄 이유 반환.
    실패 시 기본값 0.5 (review) 반환.
    """
    prompt = (
        f"다음 요청의 구현 복잡도를 0.0~1.0으로 평가하라.\n"
        f"0.0 = 매우 단순 (오타 수정 등), 1.0 = 매우 복잡 (아키텍처 설계 등).\n"
        f"반드시 JSON만 출력: {{\"score\": 0.X, \"reason\": \"한 줄 이유\"}}\n\n"
        f"요청: {request}"
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
        # JSON 파싱 시도
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(output[start:end])
            score = float(data.get("score", 0.5))
            reason = str(data.get("reason", "LLM 평가"))
            return max(0.0, min(1.0, score)), reason
    except Exception:
        pass
    return 0.5, "LLM 평가 실패 — 기본값 review 적용"


def score_to_route(score: float) -> str:
    """복잡도 점수 → 실행 경로"""
    if score < 0.3:
        return "direct"
    elif score <= 0.7:
        return "review"
    else:
        return "debate"


def route(request: str, use_llm: bool = True) -> dict:
    """
    요청을 분석해 실행 경로를 결정한다.

    Returns:
        {
            "route":   "direct" | "review" | "debate",
            "score":   0.0 ~ 1.0,
            "method":  "keyword" | "llm" | "default",
            "reason":  "한 줄 이유",
        }
    """
    score, matched_kw = keyword_score(request)

    if score is not None:
        # 키워드 매칭 성공
        return {
            "route":  score_to_route(score),
            "score":  score,
            "method": "keyword",
            "reason": f"키워드 매칭: '{matched_kw}'",
        }

    # 키워드 불확실 → LLM 평가
    if use_llm:
        llm_s, llm_reason = llm_score(request)
        return {
            "route":  score_to_route(llm_s),
            "score":  llm_s,
            "method": "llm",
            "reason": llm_reason,
        }

    # LLM 비활성 → 기본값
    return {
        "route":  "review",
        "score":  0.5,
        "method": "default",
        "reason": "키워드 불확실, LLM 비활성 — review 기본값",
    }


# ─── 출력 헬퍼 ────────────────────────────────────────────────────────────────

ROUTE_ICONS = {
    "direct": "⚡",
    "review": "🔍",
    "debate": "🏛 ",
}

ROUTE_DESC = {
    "direct": "Claude Code 직행 (복잡도 < 0.3)",
    "review": "amp 1라운드 리뷰 후 Claude Code (복잡도 0.3~0.7)",
    "debate": "amp 풀 토론 후 Claude Code (복잡도 > 0.7)",
}


def print_result(result: dict, request: str, explain: bool = False) -> None:
    r = result["route"]
    icon = ROUTE_ICONS[r]
    print(f"{icon} {r.upper()}")
    if explain:
        print(f"   요청:    {request}")
        print(f"   복잡도:  {result['score']:.2f}  ({result['method']} 평가)")
        print(f"   이유:    {result['reason']}")
        print(f"   경로:    {ROUTE_DESC[r]}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="router.py",
        description="태스크 복잡도 기반 실행 경로 자동 라우터",
    )
    parser.add_argument("request", help="라우팅할 요청 텍스트")
    parser.add_argument("--explain", "-e", action="store_true",
                        help="복잡도 점수 + 이유 포함 출력")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON 형식 출력")
    parser.add_argument("--no-llm", action="store_true",
                        help="LLM 2차 평가 비활성 (키워드 전용)")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = route(args.request, use_llm=not args.no_llm)

    if args.json_out:
        result["request"] = args.request
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result, args.request, explain=args.explain)


if __name__ == "__main__":
    main()
