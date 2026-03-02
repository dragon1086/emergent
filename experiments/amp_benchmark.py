#!/usr/bin/env python3
"""
amp_benchmark.py — TASK-003: amp 벤치마크 (auto-persona ON vs OFF)

실험 설계:
  - Control (OFF): 모든 질문에 하드코딩된 "Analyst" + "Critic" 페르소나
  - Treatment (ON): 질문 도메인에 따라 auto-selected 대립 페르소나
  - 동일 GPT-5.2 모델, 동일 4-turn 토론 형식
  - Gemini 외부 판사 (GPT-5.2 자기평가 편향 방지)
  - 블라인드 A/B 평가 (판사는 어느 쪽이 ON/OFF인지 모름)

환경변수:
  OPENAI_API_KEY, GOOGLE_API_KEY

사용:
  python amp_benchmark.py [--dry-run]
"""

import json
import os
import sys
import time
import random
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

# ─── .env 로드 ────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
env_file = REPO / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_AI_API_KEY", "")
RESULTS_FILE = REPO / "experiments" / "amp_benchmark_results.json"

DRY_RUN = "--dry-run" in sys.argv

# --output 지원
_output_arg = next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--output" and i+1 < len(sys.argv)), None)
if _output_arg:
    RESULTS_FILE = Path(_output_arg) if Path(_output_arg).is_absolute() else REPO / _output_arg

# ─── 테스트 질문 (10개, 다양한 실생활 결정 질문) ─────────────────────────────

TEST_QUESTIONS = [
    "나 이직해야 할까? 현재 연봉 8천, 제안 1.2억, 근데 스타트업이야",
    "이 계약서 사인해도 될까? 3년 독점 조항이 있어",
    "비트코인 지금 사야 해?",
    "부모님이 요양원 가셔야 하는데 어떻게 해야 해?",
    "창업할까 대학원 갈까?",
    "이 코드 리팩토링 해야 할까 새로 짜야 할까?",
    "결혼 전에 집을 살까 전세를 할까?",
    "AI 회사에 투자해도 될까? PER이 200이야",
    "아이 영어 교육 언제부터 시작해야 해?",
    "팀원이 계속 실수해. 해고해야 할까?",
]

# ─── 도메인별 대립 페르소나 (auto-persona ON) ─────────────────────────────────
# 각 질문에 대해 의미있는 긴장 관계를 만드는 페르소나 쌍 선택

DOMAIN_PERSONAS = {
    # 커리어/이직
    0: ("Ambitious Growth Strategist", "Risk-Aware Stability Advocate"),
    # 법률/계약
    1: ("Deal-Closing Business Attorney", "Protective Rights-First Lawyer"),
    # 투자/가상화폐
    2: ("Momentum Trader", "Fundamental Value Investor"),
    # 가족/돌봄
    3: ("Professional Care Efficiency Expert", "Family-Centered Emotional Advocate"),
    # 창업/진로
    4: ("Serial Entrepreneur", "Academic Research Scholar"),
    # 기술/엔지니어링
    5: ("Pragmatic Shipping Engineer", "Clean Architecture Purist"),
    # 부동산/주거
    6: ("Asset Accumulation Investor", "Financial Flexibility Advocate"),
    # 투자/주식
    7: ("Growth-at-Any-Price Bull", "Valuation Discipline Bear"),
    # 교육/육아
    8: ("Early Intervention Education Expert", "Child-Led Development Advocate"),
    # 팀관리/HR
    9: ("Performance Accountability Manager", "Coaching & Retention Specialist"),
}

# ─── Control 페르소나 (auto-persona OFF) ──────────────────────────────────────

CONTROL_PERSONA_A = "Analyst"
CONTROL_PERSONA_B = "Critic"

# ─── API 호출 ─────────────────────────────────────────────────────────────────

def call_openai(system_prompt: str, user_prompt: str, max_tokens: int = 600, retries: int = 3) -> str:
    """OpenAI GPT-5.2 호출. max_completion_tokens 미사용 (gpt-5.2에서 빈 응답 버그)."""
    if DRY_RUN:
        return f"[DRY-RUN] GPT-5.2 response to: {user_prompt[:60]}..."

    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": "gpt-5.2-chat-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }).encode()

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=payload, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_KEY}",
            })
            with urllib.request.urlopen(req, timeout=60) as res:
                data = json.loads(res.read())
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt * 5
                print(f"  [rate limit] waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("OpenAI call failed after retries")


def call_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 800, retries: int = 3) -> str:
    """Gemini API 호출. gemini-2.0-flash fallback 포함."""
    if DRY_RUN:
        return f"[DRY-RUN] Gemini response to: {user_prompt[:60]}..."

    if not GOOGLE_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    # 모델 우선순위: gemini-3-flash-preview -> gemini-2.0-flash
    models_to_try = ["gemini-3-flash-preview", "gemini-2.0-flash"]

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_KEY}"
        payload = json.dumps({
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
        }).encode()

        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as res:
                    data = json.loads(res.read())
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 2 ** attempt * 5
                    print(f"  [Gemini rate limit] waiting {wait}s...", flush=True)
                    time.sleep(wait)
                elif e.code == 404 and attempt == 0:
                    # 모델 없으면 다음 모델로
                    print(f"  [Gemini] model {model} not found, trying fallback...", flush=True)
                    break
                else:
                    if attempt == retries - 1:
                        break  # 다음 모델 시도
                    time.sleep(2 ** attempt)
            except Exception:
                if attempt == retries - 1:
                    break
                time.sleep(2 ** attempt)

    raise RuntimeError("Gemini call failed on all models")


# ─── 4-turn 토론 형식 ─────────────────────────────────────────────────────────

def run_debate(question: str, persona_a: str, persona_b: str) -> str:
    """
    4-turn 토론 실행:
      Turn 1: Agent A 초기 입장
      Turn 2: Agent B 반박
      Turn 3: Agent A 재반박
      Turn 4: 종합 결론
    최종 답변 반환.
    """
    debate_log = []

    # Turn 1: Agent A 초기 입장
    sys_a = (
        f"You are {persona_a}. You are participating in a structured debate to help a user make a decision. "
        f"Give your honest perspective based on your expertise and worldview. "
        f"Be specific, practical, and direct. Respond in Korean."
    )
    turn1 = call_openai(sys_a, f"질문: {question}\n\n당신의 입장을 제시하세요.", max_tokens=400)
    debate_log.append(f"[{persona_a}] {turn1}")

    # Turn 2: Agent B 반박
    sys_b = (
        f"You are {persona_b}. You are debating against {persona_a}. "
        f"Challenge their position, identify blind spots, and present your contrasting view. "
        f"Be constructive but firm. Respond in Korean."
    )
    turn2 = call_openai(
        sys_b,
        f"질문: {question}\n\n{persona_a}의 주장:\n{turn1}\n\n이에 대한 반박과 당신의 관점을 제시하세요.",
        max_tokens=400,
    )
    debate_log.append(f"[{persona_b}] {turn2}")

    # Turn 3: Agent A 재반박 및 보완
    turn3 = call_openai(
        sys_a,
        f"질문: {question}\n\n{persona_b}의 반박:\n{turn2}\n\n재반박하고 핵심 논거를 강화하세요.",
        max_tokens=400,
    )
    debate_log.append(f"[{persona_a}] {turn3}")

    # Turn 4: 종합 결론 (중립적 통합자)
    synthesis_sys = (
        "You are a neutral synthesis moderator. Your job is to integrate the debate into a clear, "
        "actionable recommendation for the user. Include key considerations from both sides. "
        "Be practical. End with a concrete recommendation. Respond in Korean."
    )
    synthesis_prompt = (
        f"질문: {question}\n\n"
        f"토론 내용:\n"
        f"{persona_a}: {turn1}\n\n"
        f"{persona_b}: {turn2}\n\n"
        f"{persona_a} (재반박): {turn3}\n\n"
        f"이 토론을 종합하여 사용자에게 명확한 결론과 권고사항을 제시하세요."
    )
    conclusion = call_openai(synthesis_sys, synthesis_prompt, max_tokens=500)
    debate_log.append(f"[종합] {conclusion}")

    return conclusion


# ─── 관점 추출 (blind spot 측정용) ───────────────────────────────────────────

def extract_perspectives(question: str, answer: str) -> list[str]:
    """GPT-5.2로 답변에서 고유 관점/고려사항을 JSON 리스트로 추출."""
    sys_prompt = (
        "You are a perspective extractor. Given a question and an answer, "
        "extract a list of distinct perspectives, considerations, or key points mentioned. "
        "Return ONLY a JSON array of short strings (3-8 words each). "
        "Example: [\"financial risk assessment\", \"career growth potential\", \"market volatility\"]"
    )
    user_prompt = f"Question: {question}\n\nAnswer: {answer}\n\nExtract perspectives as JSON array:"

    raw = call_openai(sys_prompt, user_prompt, max_tokens=300)

    if DRY_RUN:
        return ["perspective A", "perspective B", "perspective C"]

    # JSON 파싱 시도
    try:
        # 코드블록 제거
        cleaned = raw.strip()
        if "```" in cleaned:
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not l.startswith("```"))
        # 첫 번째 [ ... ] 찾기
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    # 파싱 실패시 줄 단위 fallback
    return [line.strip().strip("-•").strip() for line in raw.split("\n") if line.strip() and len(line.strip()) > 3][:8]


def count_blind_spots(perspectives_off: list[str], perspectives_on: list[str]) -> int:
    """
    ON에는 있지만 OFF에는 없는 관점 수 계산.
    간단한 텍스트 포함 여부 기반 (소문자 비교).
    """
    off_lower = " ".join(p.lower() for p in perspectives_off)
    count = 0
    for p in perspectives_on:
        # 3단어 이상인 관점에서 핵심 단어가 OFF에 없으면 blind spot
        key_words = [w for w in p.lower().split() if len(w) > 3]
        if key_words and not any(w in off_lower for w in key_words):
            count += 1
    return count


# ─── Gemini 판사 평가 ─────────────────────────────────────────────────────────

def judge_answers(question: str, answer_a: str, answer_b: str) -> dict:
    """
    Gemini가 블라인드로 두 답변을 평가.
    판사는 어느 것이 ON/OFF인지 모름.
    반환: {quality_a, quality_b, completeness_a, completeness_b, preferred, reason}
    """
    judge_sys = (
        "You are an impartial expert evaluator. You will assess two AI-generated answers to the same question. "
        "You do NOT know which system generated each answer. "
        "Evaluate objectively based on quality, completeness, and practical usefulness. "
        "Respond ONLY in valid JSON."
    )
    judge_prompt = (
        f"Question: {question}\n\n"
        f"Answer A:\n{answer_a}\n\n"
        f"Answer B:\n{answer_b}\n\n"
        "Evaluate both answers and respond with this exact JSON structure:\n"
        "{\n"
        '  "quality_a": <integer 1-10>,\n'
        '  "quality_b": <integer 1-10>,\n'
        '  "completeness_a": <integer 1-10>,\n'
        '  "completeness_b": <integer 1-10>,\n'
        '  "preferred": "A" or "B",\n'
        '  "reason": "<2-3 sentence explanation of why preferred is better>"\n'
        "}"
    )

    raw = call_gemini(judge_sys, judge_prompt, max_tokens=800)

    if DRY_RUN:
        return {
            "quality_a": random.randint(5, 8),
            "quality_b": random.randint(6, 9),
            "completeness_a": random.randint(5, 8),
            "completeness_b": random.randint(6, 9),
            "preferred": random.choice(["A", "B"]),
            "reason": "Dry-run evaluation.",
        }

    try:
        cleaned = raw.strip()
        if "```" in cleaned:
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not l.startswith("```"))
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    # 파싱 실패 fallback
    return {
        "quality_a": 5, "quality_b": 5,
        "completeness_a": 5, "completeness_b": 5,
        "preferred": "A",
        "reason": f"Parse failed. Raw: {raw[:200]}",
    }


# ─── 단일 질문 벤치마크 실행 ─────────────────────────────────────────────────

def run_single_question(idx: int, question: str) -> dict:
    """한 질문에 대해 OFF/ON 실행 후 판사 평가 반환."""
    print(f"\n[Q{idx+1}/10] {question[:50]}...", flush=True)

    # Condition OFF: 하드코딩 페르소나
    print(f"  [OFF] {CONTROL_PERSONA_A} vs {CONTROL_PERSONA_B}", flush=True)
    answer_off = run_debate(question, CONTROL_PERSONA_A, CONTROL_PERSONA_B)

    # Condition ON: 도메인 맞춤 페르소나
    persona_a_on, persona_b_on = DOMAIN_PERSONAS[idx]
    print(f"  [ON]  {persona_a_on} vs {persona_b_on}", flush=True)
    answer_on = run_debate(question, persona_a_on, persona_b_on)

    # 관점 추출 (blind spot 측정)
    print(f"  [perspectives] extracting...", flush=True)
    persp_off = extract_perspectives(question, answer_off)
    persp_on = extract_perspectives(question, answer_on)
    blind_spots = count_blind_spots(persp_off, persp_on)

    # 블라인드 A/B: 랜덤으로 OFF/ON을 A/B에 할당
    randomized = random.random() < 0.5
    if randomized:
        # OFF = A, ON = B
        answer_a, answer_b = answer_off, answer_on
        mapping = {"A": "off", "B": "on"}
    else:
        # ON = A, OFF = B
        answer_a, answer_b = answer_on, answer_off
        mapping = {"A": "on", "B": "off"}

    # Gemini 판사 평가
    print(f"  [judge] Gemini evaluating (blind A/B)...", flush=True)
    judgment = judge_answers(question, answer_a, answer_b)

    # 매핑 역변환: A/B -> off/on
    preferred_label = mapping.get(judgment.get("preferred", "A"), "off")

    # ON/OFF 점수 정리
    if randomized:
        # A=off, B=on
        quality_off = judgment.get("quality_a", 5)
        quality_on = judgment.get("quality_b", 5)
        completeness_off = judgment.get("completeness_a", 5)
        completeness_on = judgment.get("completeness_b", 5)
    else:
        # A=on, B=off
        quality_on = judgment.get("quality_a", 5)
        quality_off = judgment.get("quality_b", 5)
        completeness_on = judgment.get("completeness_a", 5)
        completeness_off = judgment.get("completeness_b", 5)

    return {
        "question": question,
        "persona_off": {
            "persona_a": CONTROL_PERSONA_A,
            "persona_b": CONTROL_PERSONA_B,
            "answer": answer_off,
        },
        "persona_on": {
            "persona_a": persona_a_on,
            "persona_b": persona_b_on,
            "answer": answer_on,
        },
        "perspectives": {
            "off": persp_off,
            "on": persp_on,
        },
        "judge": {
            "quality_off": quality_off,
            "quality_on": quality_on,
            "completeness_off": completeness_off,
            "completeness_on": completeness_on,
            "blind_spots_covered": blind_spots,
            "ab_winner": preferred_label,
            "ab_reason": judgment.get("reason", ""),
            "ab_randomized_off_is_a": randomized,
        },
    }


# ─── 요약 통계 계산 ───────────────────────────────────────────────────────────

def compute_summary(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    def avg(vals):
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    quality_off = [r["judge"]["quality_off"] for r in results]
    quality_on = [r["judge"]["quality_on"] for r in results]
    completeness_off = [r["judge"]["completeness_off"] for r in results]
    completeness_on = [r["judge"]["completeness_on"] for r in results]
    blind_spots = [r["judge"]["blind_spots_covered"] for r in results]
    winners = [r["judge"]["ab_winner"] for r in results]

    win_on = sum(1 for w in winners if w == "on")
    win_off = sum(1 for w in winners if w == "off")

    return {
        "avg_quality_off": avg(quality_off),
        "avg_quality_on": avg(quality_on),
        "avg_completeness_off": avg(completeness_off),
        "avg_completeness_on": avg(completeness_on),
        "total_blind_spots": sum(blind_spots),
        "avg_blind_spots_per_question": avg(blind_spots),
        "ab_win_rate_on": round(win_on / n, 2),
        "ab_win_rate_off": round(win_off / n, 2),
        "ab_ties": n - win_on - win_off,
        "n_questions": n,
    }


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("amp Benchmark: auto-persona ON vs OFF")
    print(f"Model: gpt-5.2-chat-latest | Judge: Gemini (blind A/B)")
    print(f"Questions: {len(TEST_QUESTIONS)} | Dry-run: {DRY_RUN}")
    print("=" * 60)

    if not DRY_RUN and not OPENAI_KEY:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not DRY_RUN and not GOOGLE_KEY:
        print("ERROR: GOOGLE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    results = []
    failed = []

    for idx, question in enumerate(TEST_QUESTIONS):
        try:
            result = run_single_question(idx, question)
            results.append(result)
            j = result["judge"]
            print(
                f"  -> quality: OFF={j['quality_off']} ON={j['quality_on']} | "
                f"completeness: OFF={j['completeness_off']} ON={j['completeness_on']} | "
                f"blind_spots={j['blind_spots_covered']} | winner={j['ab_winner']}",
                flush=True,
            )
        except Exception as e:
            print(f"  [ERROR] Q{idx+1}: {e}", flush=True)
            failed.append({"question_idx": idx, "question": question, "error": str(e)})

        # 레이트 리밋 방지 대기
        if not DRY_RUN and idx < len(TEST_QUESTIONS) - 1:
            time.sleep(2)

    summary = compute_summary(results)

    output = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "gpt-5.2-chat-latest",
            "judge": "gemini-3-flash-preview (fallback: gemini-2.0-flash)",
            "n_questions": len(TEST_QUESTIONS),
            "n_completed": len(results),
            "n_failed": len(failed),
            "dry_run": DRY_RUN,
        },
        "results": results,
        "failed": failed,
        "summary": summary,
    }

    RESULTS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nResults saved to: {RESULTS_FILE}", flush=True)

    # 최종 요약 출력
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if summary:
        print(f"  Quality     OFF: {summary['avg_quality_off']:5.2f}  ON: {summary['avg_quality_on']:5.2f}  "
              f"(delta: {summary['avg_quality_on'] - summary['avg_quality_off']:+.2f})")
        print(f"  Completeness OFF: {summary['avg_completeness_off']:5.2f}  ON: {summary['avg_completeness_on']:5.2f}  "
              f"(delta: {summary['avg_completeness_on'] - summary['avg_completeness_off']:+.2f})")
        print(f"  Blind spots covered (total): {summary['total_blind_spots']}")
        print(f"  Avg blind spots / question:  {summary['avg_blind_spots_per_question']:.2f}")
        print(f"  A/B win rate — ON: {summary['ab_win_rate_on']:.0%}  OFF: {summary['ab_win_rate_off']:.0%}")
        if summary.get("ab_ties", 0):
            print(f"  Ties: {summary['ab_ties']}")
    if failed:
        print(f"\n  WARNING: {len(failed)} question(s) failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
