#!/usr/bin/env python3
"""
novel_ops 확장 3-Way: Solo vs Pipeline vs Emergent
GPT-5.2 동일 모델, N=10 trials
새로운 연산 규칙 문제 3개
"""
import json, os, urllib.request, time, re, sys, math
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)

K = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()
if not K:
    print("ERROR: OPENAI_API_KEY not found"); sys.exit(1)

PROBLEMS = [
    {
        "id": "vex",
        "rules": "a⊕b = a*b - a - b + 1\na⊗b = a + b - floor(a*b/2)",
        "question": "(3⊕4)⊗(2⊕5)",
        "answer": -2,
        "hint": "3⊕4=6, 2⊕5=4, then 6⊗4=6+4-floor(24/2)=-2"
    },
    {
        "id": "zork",
        "rules": "a◆b = 2*a + b - 1\na◇b = a*b - a + 1",
        "question": "(4◆3)◇2",
        "answer": 18,
        "hint": ""
    },
    {
        "id": "recursive",
        "rules": "f(1)=1, f(2)=2\n홀수 n: f(n) = f(n-1) + f(n-2)\n짝수 n: f(n) = f(n-1) * f(n-2) - 1",
        "question": "f(8)",
        "answer": 1832,
        "hint": "f(3)=3,f(4)=5,f(5)=8,f(6)=39,f(7)=47,f(8)=47*39-1=1832"
    }
]


def call(prompt, temp=0.4):
    body = json.dumps({
        "model": "gpt-5.2",
        "input": prompt,
        "temperature": temp
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=body,
        headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        r = json.loads(resp.read())
    for item in r.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c["text"]
    return ""


def extract_number(text):
    """마지막 정수 추출 (음수 포함)"""
    nums = re.findall(r'-?\d+', text)
    if not nums:
        return None
    # 마지막 숫자 시도
    return int(nums[-1])


def grade(response, expected_answer):
    """정답 판별: 숫자 추출 후 비교"""
    n = extract_number(response)
    return n is not None and n == expected_answer


def make_base_prompt(p):
    return (
        f"새로운 연산 규칙:\n{p['rules']}\n\n"
        f"문제: {p['question']}\n\n"
        "위 규칙에 따라 단계별로 계산하고, 마지막 줄에 최종 답(정수)만 적으시오.\n"
        "최종 답: "
    )


# ─── SOLO ───────────────────────────────────────────────
def solo(p):
    return call(make_base_prompt(p), temp=0.4)


# ─── PIPELINE (Plan → Check → Review) ────────────────────
def pipeline(p):
    rules, q = p['rules'], p['question']

    # Step 1: Plan — 규칙 이해
    s1 = call(
        f"새로운 연산 규칙을 분석하시오:\n{rules}\n\n"
        "각 연산자의 정의를 자신의 말로 설명하고, 계산 순서를 명시하시오.",
        temp=0.3
    )
    time.sleep(0.3)

    # Step 2: Check — 단계별 계산
    s2 = call(
        f"규칙:\n{rules}\n\n문제: {q}\n\n"
        f"규칙 분석:\n{s1[:500]}\n\n"
        "위 분석을 바탕으로 각 연산을 순서대로 계산하시오. 중간값을 모두 표시하시오.",
        temp=0.4
    )
    time.sleep(0.3)

    # Step 3: Review — 검증 및 최종 답
    s3 = call(
        f"규칙:\n{rules}\n\n문제: {q}\n\n"
        f"이전 계산:\n{s2[:500]}\n\n"
        "계산이 맞는지 검증하고, 마지막 줄에 최종 답(정수만)을 제시하시오.\n"
        "최종 답: ",
        temp=0.2
    )
    return s3


# ─── EMERGENT (A독립풀기→B독립풀기→크로스체크→합성) ─────────
def emergent(p):
    rules, q = p['rules'], p['question']

    # Agent A: 독립 계산
    a = call(
        f"[Agent A] 새로운 연산 규칙:\n{rules}\n\n문제: {q}\n\n"
        "독립적으로 단계별 계산 후 최종 답(정수)을 제시하시오.\n최종 답: ",
        temp=0.5
    )
    time.sleep(0.3)

    # Agent B: 독립 계산 (A 참고 금지)
    b = call(
        f"[Agent B] 새로운 연산 규칙:\n{rules}\n\n문제: {q}\n\n"
        "Agent A와 독립적으로 계산하시오. Agent A 답을 신뢰하지 마시오.\n"
        "단계별 계산 후 최종 답(정수)을 제시하시오.\n최종 답: ",
        temp=0.5
    )
    time.sleep(0.3)

    # 크로스체크: 불일치 해소
    cross = call(
        f"두 에이전트가 독립 계산했습니다:\n\n"
        f"규칙:\n{rules}\n\n문제: {q}\n\n"
        f"Agent A: {a[:400]}\n\nAgent B: {b[:400]}\n\n"
        "두 결과를 비교하시오. 불일치가 있으면 어느 쪽이 옳은지 판단하시오. "
        "정확한 최종 답을 밝히시오.\n최종 답: ",
        temp=0.3
    )
    time.sleep(0.3)

    # 합성: 최종 확정
    final = call(
        f"최종 검증:\n규칙:\n{rules}\n\n문제: {q}\n\n"
        f"크로스체크 결과:\n{cross[:400]}\n\n"
        "최종 답(정수만)을 확정하시오.\n최종 답: ",
        temp=0.2
    )
    return final


# ─── RUN ─────────────────────────────────────────────────
N = 10
results = []

for method_name, method_fn in [("solo", solo), ("pipeline", pipeline), ("emergent", emergent)]:
    print(f"\n{'='*55}")
    print(f"  METHOD: {method_name.upper()}")
    print(f"{'='*55}")

    for p in PROBLEMS:
        pid = p["id"]
        expected = p["answer"]
        scores = []
        print(f"\n  Problem: {pid} | expected={expected}")

        for t in range(N):
            try:
                resp = method_fn(p)
                ok = grade(resp, expected)
                got = extract_number(resp)
                scores.append(1 if ok else 0)
                print(f"    t{t+1:02d}: {'✅' if ok else '❌'} (got={got})")
                time.sleep(0.5)
            except Exception as e:
                print(f"    t{t+1:02d}: ⚠️  {e}")
                scores.append(0)
                time.sleep(2)

        acc = sum(scores) / N
        print(f"  ─ {method_name} | {pid}: {acc:.0%}  ({sum(scores)}/{N})")

        results.append({
            "method": method_name,
            "problem": pid,
            "accuracy": round(acc, 2),
            "trials": N,
            "raw_scores": scores
        })

# ─── SUMMARY ─────────────────────────────────────────────
print(f"\n{'='*55}")
print("  FINAL: Novel Ops 3-Way (N=10)")
print(f"{'='*55}")
for method in ["solo", "pipeline", "emergent"]:
    mr = [r for r in results if r["method"] == method]
    avg = sum(r["accuracy"] for r in mr) / len(mr)
    detail = {r["problem"]: f"{r['accuracy']:.0%}" for r in mr}
    print(f"  {method.capitalize():10s}: avg={avg:.0%}  |  {detail}")

# Save
out_path = Path("/Users/rocky/emergent/experiments/novel_ops_expanded.json")
out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
print(f"\nSaved: {out_path}")
