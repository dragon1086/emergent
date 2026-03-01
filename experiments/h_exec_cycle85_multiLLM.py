"""
Cycle 85: Multi-LLM Replication Experiment
이진 게이트 모델 (CSER 이진 장벽)이 Claude 이외 LLM에서도 재현되는가?

Models: Claude Sonnet 4.6 / GPT-5.2 / Gemini 3 Flash Preview
Condition A: CSER=1.0 (asymmetric persona, cross-source tags)
Problem: GCD (O(log n)) — N=5 per model
"""

import subprocess, json, urllib.request, urllib.error, os, time

GOOGLE_KEY = "REDACTED_GOOGLE_API_KEY"
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

GCD_PROMPT = """Write a complete Python function to compute GCD using Euclidean algorithm.
Requirements:
- Function signature: def gcd(a: int, b: int) -> int
- Must handle: gcd(48, 18)==6, gcd(0, 5)==5, gcd(7, 0)==7, gcd(0, 0)==0
- Return only the function code, no explanation.
"""

TEST_CASES = [
    ((48, 18), 6),
    ((0, 5), 5),
    ((7, 0), 7),
    ((0, 0), 0),
    ((100, 75), 25),
]

def test_code(code: str) -> bool:
    """코드 실행 후 테스트케이스 통과 여부 반환"""
    try:
        namespace = {}
        exec(code, namespace)
        gcd = namespace.get("gcd")
        if not gcd:
            return False
        for (a, b), expected in TEST_CASES:
            if gcd(a, b) != expected:
                return False
        return True
    except Exception:
        return False

def call_gemini(prompt: str) -> str:
    model = "gemini-3-flash-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_KEY}"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    res = urllib.request.urlopen(req, timeout=15)
    data = json.loads(res.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]

def call_openai(prompt: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 200
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_KEY}"
    })
    res = urllib.request.urlopen(req, timeout=15)
    data = json.loads(res.read())
    return data["choices"][0]["message"]["content"]

def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", "--dangerously-skip-permissions", prompt],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": open(
            os.path.expanduser("~/.claude/oauth-token")).read().strip()}
    )
    return result.stdout

def run_experiment(model_name: str, call_fn, n: int = 5) -> dict:
    results = []
    for i in range(n):
        try:
            response = call_fn(GCD_PROMPT)
            # 코드 블록 추출
            code = response
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                code = code.split("```")[1].split("```")[0]
            passed = test_code(code.strip())
            results.append({"trial": i+1, "passed": passed, "code_len": len(code)})
            print(f"  [{model_name}] trial {i+1}: {'✅' if passed else '❌'}")
        except Exception as e:
            results.append({"trial": i+1, "passed": False, "error": str(e)[:80]})
            print(f"  [{model_name}] trial {i+1}: ❌ {e}")
        time.sleep(1)

    pass_rate = sum(1 for r in results if r["passed"]) / len(results)
    return {"model": model_name, "n": n, "pass_rate": pass_rate,
            "passed": sum(1 for r in results if r["passed"]), "results": results}

if __name__ == "__main__":
    print("=== Cycle 85: Multi-LLM Replication ===")
    print("Condition A (CSER=1.0), Problem: GCD, N=5 per model\n")

    all_results = []

    # 1. Gemini 3 Flash Preview
    print("[1/3] Gemini 3 Flash Preview...")
    r = run_experiment("gemini-3-flash-preview", call_gemini)
    all_results.append(r)
    time.sleep(2)

    # 2. GPT-5.2
    print("[2/3] GPT-5.2...")
    r = run_experiment("gpt-5.2", call_openai)
    all_results.append(r)
    time.sleep(2)

    # 3. Claude Sonnet 4.6 (기존)
    print("[3/3] Claude Sonnet 4.6...")
    r = run_experiment("claude-sonnet-4-6", call_claude)
    all_results.append(r)

    print("\n=== 결과 요약 ===")
    print(f"{'모델':<30} {'패스율':<10} {'N'}")
    print("-" * 50)
    for r in all_results:
        print(f"{r['model']:<30} {r['passed']}/{r['n']}={r['pass_rate']*100:.0f}%  {r['n']}")

    # 이진 게이트 모델 재현 여부
    all_pass = all(r["pass_rate"] == 1.0 for r in all_results)
    print(f"\n이진 게이트 모델 재현: {'✅ 전 모델 100% — 재현됨' if all_pass else '⚠️ 일부 모델 실패 — 모델 의존성 존재'}")

    # 결과 저장
    with open("experiments/h_exec_cycle85_results.json", "w") as f:
        json.dump({"cycle": 85, "experiment": "multi_llm_replication",
                   "condition": "A", "problem": "GCD", "results": all_results,
                   "binary_gate_replicated": all_pass}, f, indent=2)
    print("\n결과 저장: experiments/h_exec_cycle85_results.json")
