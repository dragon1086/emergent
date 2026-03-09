"""
S4: Long-term Self-Improvement Loop (Core Differentiator)
Runs 10 rounds of: code write -> review -> improve -> re-evaluate
Measures: quality improvement rate round 1 vs round 10
OpenClaw's unique capability: persistent memory across rounds
"""
import time
import asyncio
from typing import Any
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OPENAI_MODEL, ANTHROPIC_MODEL, SYSTEM_A, SYSTEM_B, SYSTEM_C, RESULTS_DIR
import openai
import anthropic

CODING_TASK = """
Write a Python function `process_user_data(users: list[dict]) -> dict` that:
1. Filters out inactive users (status != 'active')
2. Groups users by department
3. Calculates average salary per department
4. Returns top 3 departments by average salary
5. Handles edge cases: empty list, missing fields, invalid salary values

Include type hints and handle all edge cases gracefully.
"""

EVALUATOR_CRITERIA = """Score this Python code (1-10) on these criteria:
1. Correctness: Does it handle the task correctly?
2. Edge Cases: Are all edge cases handled?
3. Code Quality: Is it clean, readable, well-structured?
4. Performance: Is it efficient?
5. Pythonic: Does it follow Python best practices?

Respond with:
SCORES: correctness=X, edge_cases=X, quality=X, performance=X, pythonic=X
TOTAL_SCORE: X.X (average)
KEY_ISSUES: [bullet list of problems]
IMPROVEMENTS: [specific suggestions]
"""

ROUNDS = 10
MEMORY_FILE = RESULTS_DIR / "s4_openclaw_memory.json"


async def _evaluate_code(client_oai: openai.AsyncOpenAI, code: str) -> dict[str, Any]:
    """Evaluate code quality using GPT as judge."""
    import re
    resp = await client_oai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": EVALUATOR_CRITERIA},
            {"role": "user", "content": f"Evaluate this code:\n```python\n{code}\n```"}
        ],
        temperature=0.0,
    )
    text = resp.choices[0].message.content

    m = re.search(r"SCORES:\s*correctness=(\d+),\s*edge_cases=(\d+),\s*quality=(\d+),\s*performance=(\d+),\s*pythonic=(\d+)", text)
    scores = {}
    if m:
        vals = [int(x) for x in m.groups()]
        scores = {"correctness": vals[0], "edge_cases": vals[1], "quality": vals[2], "performance": vals[3], "pythonic": vals[4]}

    m2 = re.search(r"TOTAL_SCORE:\s*([\d.]+)", text)
    total = float(m2.group(1)) if m2 else (sum(scores.values()) / len(scores) if scores else 5.0)

    return {"scores": scores, "total": total, "feedback": text}


async def run_system_a(client_oai: openai.AsyncOpenAI, client_ant: anthropic.AsyncAnthropic) -> dict[str, Any]:
    """System A: OpenClaw+cokac+amp with persistent memory across rounds.

    OpenClaw's UNIQUE CAPABILITY:
    - Maintains memory of all previous round improvements
    - Uses cross-model synthesis to avoid local optima
    - amp tracks quality trajectory and targets weakest areas
    """
    start = time.time()
    round_scores = []

    # OpenClaw memory: persists across rounds (simulating OpenClaw's cron + memory system)
    memory = {"past_issues": [], "past_scores": [], "improvement_log": []}

    # Initial code generation
    init_resp = await client_ant.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": f"Write Python code for this task:\n{CODING_TASK}\nProvide only the code, no explanation."}],
    )
    current_code = init_resp.content[0].text

    for round_num in range(1, ROUNDS + 1):
        # Evaluate current code
        eval_result = await _evaluate_code(client_oai, current_code)
        round_scores.append({"round": round_num, "score": eval_result["total"], "scores": eval_result["scores"]})
        memory["past_scores"].append(eval_result["total"])

        if round_num == ROUNDS:
            break

        # Memory-augmented improvement (OpenClaw's key advantage)
        memory_context = ""
        if memory["past_issues"]:
            memory_context = f"\nPrevious issues to avoid:\n" + "\n".join(f"- {i}" for i in memory["past_issues"][-5:])
            memory_context += f"\nScore trend: {memory['past_scores']}"

        # GPT reviews with memory context
        gpt_review = await client_oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": f"You are a code reviewer. Focus on issues not yet fixed.{memory_context}"},
                {"role": "user", "content": f"Review and list the TOP 3 remaining issues:\n```python\n{current_code}\n```\nFeedback from evaluator: {eval_result['feedback'][:500]}"}
            ],
            temperature=0.1,
        )
        review = gpt_review.choices[0].message.content
        memory["past_issues"].append(review[:200])

        # Claude improves with cross-model review
        improve_resp = await client_ant.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": f"Improve this code based on review feedback. Fix ALL issues mentioned.\n\nCurrent code:\n```python\n{current_code}\n```\n\nReview:\n{review}\n\nWrite the improved complete code only."}
            ],
        )
        current_code = improve_resp.content[0].text

    # Save memory for future sessions (OpenClaw's persistent memory simulation)
    MEMORY_FILE.write_text(json.dumps(memory, indent=2))

    elapsed = time.time() - start
    improvement = round_scores[-1]["score"] - round_scores[0]["score"] if len(round_scores) >= 2 else 0

    return {
        "system": SYSTEM_A,
        "scenario": "s4_self_improvement",
        "rounds": ROUNDS,
        "round_scores": round_scores,
        "score_round_1": round_scores[0]["score"],
        "score_round_10": round_scores[-1]["score"],
        "improvement_delta": improvement,
        "improvement_pct": (improvement / round_scores[0]["score"] * 100) if round_scores[0]["score"] > 0 else 0,
        "elapsed_seconds": elapsed,
        "openclaw_unique_features": ["persistent_memory", "cross_model_synthesis", "targeted_improvement"],
        "final_code": current_code[:500],
    }


async def run_system_b(client_ant: anthropic.AsyncAnthropic, client_oai: openai.AsyncOpenAI) -> dict[str, Any]:
    """System B: Claude standalone loop (no persistent memory, no cross-model)."""
    start = time.time()
    round_scores = []

    init_resp = await client_ant.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": f"Write Python code for:\n{CODING_TASK}\nCode only."}],
    )
    current_code = init_resp.content[0].text

    for round_num in range(1, ROUNDS + 1):
        eval_result = await _evaluate_code(client_oai, current_code)
        round_scores.append({"round": round_num, "score": eval_result["total"]})

        if round_num == ROUNDS:
            break

        improve = await client_ant.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": f"Improve this code:\n```python\n{current_code}\n```\nFeedback: {eval_result['feedback'][:400]}\nWrite improved code only."}],
        )
        current_code = improve.content[0].text

    elapsed = time.time() - start
    improvement = round_scores[-1]["score"] - round_scores[0]["score"] if len(round_scores) >= 2 else 0

    return {
        "system": SYSTEM_B,
        "scenario": "s4_self_improvement",
        "rounds": ROUNDS,
        "round_scores": round_scores,
        "score_round_1": round_scores[0]["score"],
        "score_round_10": round_scores[-1]["score"],
        "improvement_delta": improvement,
        "improvement_pct": (improvement / round_scores[0]["score"] * 100) if round_scores[0]["score"] > 0 else 0,
        "elapsed_seconds": elapsed,
    }


async def run_system_c(client_oai: openai.AsyncOpenAI) -> dict[str, Any]:
    """System C: GPT standalone loop."""
    start = time.time()
    round_scores = []

    init_resp = await client_oai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": f"Write Python code for:\n{CODING_TASK}\nCode only."}],
        temperature=0.2,
    )
    current_code = init_resp.choices[0].message.content

    for round_num in range(1, ROUNDS + 1):
        eval_result = await _evaluate_code(client_oai, current_code)
        round_scores.append({"round": round_num, "score": eval_result["total"]})

        if round_num == ROUNDS:
            break

        improve = await client_oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": f"Improve this code:\n```python\n{current_code}\n```\nFeedback: {eval_result['feedback'][:400]}\nWrite improved code only."}],
            temperature=0.1,
        )
        current_code = improve.choices[0].message.content

    elapsed = time.time() - start
    improvement = round_scores[-1]["score"] - round_scores[0]["score"] if len(round_scores) >= 2 else 0

    return {
        "system": SYSTEM_C,
        "scenario": "s4_self_improvement",
        "rounds": ROUNDS,
        "round_scores": round_scores,
        "score_round_1": round_scores[0]["score"],
        "score_round_10": round_scores[-1]["score"],
        "improvement_delta": improvement,
        "improvement_pct": (improvement / round_scores[0]["score"] * 100) if round_scores[0]["score"] > 0 else 0,
        "elapsed_seconds": elapsed,
    }


async def run(oai_key: str, ant_key: str) -> list[dict[str, Any]]:
    client_oai = openai.AsyncOpenAI(api_key=oai_key)
    client_ant = anthropic.AsyncAnthropic(api_key=ant_key)

    # Run sequentially to avoid API rate limits on this heavy scenario
    results = []
    for coro in [
        run_system_a(client_oai, client_ant),
        run_system_b(client_ant, client_oai),
        run_system_c(client_oai),
    ]:
        try:
            r = await coro
            results.append(r)
        except Exception as e:
            results.append({"error": str(e)})

    return [r for r in results if "system" in r]


if __name__ == "__main__":
    import os, json
    results = asyncio.run(run(os.environ["OPENAI_API_KEY"], os.environ["ANTHROPIC_API_KEY"]))
    print(json.dumps(results, indent=2))
