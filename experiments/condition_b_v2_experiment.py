#!/usr/bin/env python3
"""
condition_b_v2_experiment.py — Condition B v2: 동일 페르소나 × 이종 모델 KG 공동 진화 실험
사이클 93: openclaw-bot 요청

실험 설계:
  - Agent 1: GPT-5.2 (OpenAI) — 개념 제안자, source='agent1'
  - Agent 2: Gemini-3.1-Flash (Google) — 연결 탐색자, source='agent2'
  - 페르소나: 두 에이전트 모두 "냉정한 판사" (동일 페르소나, 이종 모델)
  - N=20 사이클 공동 KG 진화
  - 각 사이클: Agent1이 개념 노드 제안 → Agent2가 엣지 제안
  - CSER = cross(agent1, agent2) / total_edges

비교:
  - CSER(A) = 0.5455 (hetero_pair_results.json, cser_final)
  - 판정 기준:
    CSER(B) < 0.4955 → 가설 지지 (다양성 효과 유효)
    0.4955 ≤ CSER(B) ≤ 0.5955 → 불확정
    CSER(B) > 0.5955 → 가설 반박
    CSER(B) < 0.30 → 에코챔버 게이트 차단 (D-076)

환경변수:
  OPENAI_API_KEY, GOOGLE_API_KEY

플래그:
  --dry-run: 시뮬레이션 모드 (API 미사용)
  --json: 결과 JSON을 stdout에 출력
"""

import json
import os
import sys
import time
import random
import urllib.request
import urllib.error
import statistics
from pathlib import Path
from datetime import datetime

# .env 파일 로드
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
RESULTS_FILE = REPO / "experiments" / "condition_b_results.json"

DRY_RUN = "--dry-run" in sys.argv
JSON_OUT = "--json" in sys.argv

# ─── 냉정한 판사 페르소나 ────────────────────────────────────────────────────

JUDGE_PERSONA = (
    "You are a cold, impartial judge. Your only question is: is the prediction correct or not? "
    "Be dry, direct, data-only. Do not show emotion. Do not soften criticism. "
    "Admit when wrong without hesitation."
)

# ─── KG 초기화 ───────────────────────────────────────────────────────────────

def init_kg() -> dict:
    return {
        "meta": {
            "experiment": "condition_b_v2_homogeneous_persona_hetero_model",
            "pair": "GPT-5.2 (냉정한 판사) × Gemini-3.1-Flash (냉정한 판사)",
            "started": datetime.utcnow().isoformat(),
        },
        "nodes": [],
        "edges": [],
    }


# ─── 노드 ID 유틸 ────────────────────────────────────────────────────────────

def _next_node_id(kg: dict) -> str:
    nums = [int(n["id"].replace("n-", "")) for n in kg["nodes"] if n["id"].startswith("n-")]
    return f"n-{(max(nums) + 1) if nums else 1:03d}"


def _node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


# ─── API 호출 ────────────────────────────────────────────────────────────────

def call_openai(system_prompt: str, user_prompt: str, model: str = "gpt-5.2-chat-latest") -> str:
    """OpenAI API 호출. max_completion_tokens 사용, temperature 미설정."""
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": 300,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_KEY}",
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read())
    return data["choices"][0]["message"]["content"].strip()


def call_gemini(system_prompt: str, user_prompt: str, model: str = "gemini-3-flash-preview") -> str:
    """Google Gemini API 호출."""
    if not GOOGLE_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_KEY}"
    # Gemini는 system_instruction + user content 방식
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.7},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ─── 드라이런 시뮬레이션 ─────────────────────────────────────────────────────

# 동일 페르소나 → 두 에이전트가 유사한 구조적 개념을 선택하는 경향 시뮬레이션
_DRY_CONCEPTS = [
    "causal inference gap", "data sufficiency bound", "model confidence interval",
    "prediction error rate", "evidence threshold", "hypothesis rejection zone",
    "variance decomposition", "baseline comparison", "null result handling",
    "statistical significance floor", "effect size measurement", "replication criterion",
    "outlier detection rule", "prior probability anchor", "decision boundary shift",
    "false positive control", "recall-precision tradeoff", "sample bias correction",
    "ground truth alignment", "convergence criterion",
]

_dry_cycle = [0]

def dry_run_agent1(cycle: int) -> dict:
    idx = (cycle - 1) % len(_DRY_CONCEPTS)
    return {
        "concept": _DRY_CONCEPTS[idx],
        "description": f"Dry-run concept #{cycle}: {_DRY_CONCEPTS[idx]}",
        "tags": ["dry-run", "judge"],
        "type": "concept",
    }

def dry_run_agent2(new_node: dict, kg: dict) -> dict:
    valid = [n["id"] for n in kg["nodes"] if n["id"] != new_node.get("id", "")]
    if len(valid) < 2:
        targets = valid
    else:
        targets = random.sample(valid, min(2, len(valid)))
    edges = [{"from": new_node.get("id", "n-new"), "to": t, "relation": "constrains"} for t in targets]
    return {"edges": edges}


# ─── CSER 계산 ───────────────────────────────────────────────────────────────

def compute_cser(kg: dict) -> float:
    """CSER = cross-source edges / total edges. source='agent1' vs 'agent2'."""
    node_src = {n["id"]: n.get("source", "") for n in kg["nodes"]}
    n_edges = len(kg["edges"])
    if n_edges == 0:
        return 0.0
    cross = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
        and node_src.get(e["from"], "") != ""
        and node_src.get(e["to"], "") != ""
    )
    return round(cross / n_edges, 4)


def compute_metrics(kg: dict) -> dict:
    nodes = kg["nodes"]
    edges = kg["edges"]
    n_nodes = len(nodes)
    n_edges = len(edges)

    cser = compute_cser(kg)

    if n_edges > 0 and n_nodes > 1:
        spans = [abs(_node_num(e["from"]) - _node_num(e["to"])) for e in edges]
        raw_span = statistics.mean(spans)
        edge_span_norm = min(1.0, raw_span / (n_nodes - 1))
    else:
        edge_span_norm = 0.0

    nums = [_node_num(n["id"]) for n in nodes if n["id"].startswith("n-")]
    node_age_div = (statistics.stdev(nums) / max(nums)) if len(nums) >= 2 else 0.0

    e_v4 = 0.35 * cser + 0.25 * 0.0 + 0.25 * edge_span_norm + 0.15 * node_age_div

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "CSER": cser,
        "edge_span_norm": round(edge_span_norm, 4),
        "node_age_div": round(node_age_div, 4),
        "E_v4": round(e_v4, 4),
    }


# ─── 부트스트랩 CI ────────────────────────────────────────────────────────────

def bootstrap_ci(values: list, n_boot: int = 1000, ci: float = 0.95):
    if not values:
        return (0.0, 0.0)
    means = []
    for _ in range(n_boot):
        sample = random.choices(values, k=len(values))
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int((1 - ci) / 2 * n_boot)]
    hi = means[int((1 + ci) / 2 * n_boot)]
    return (round(lo, 4), round(hi, 4))


# ─── 프롬프트 ────────────────────────────────────────────────────────────────

def agent1_prompt(cycle: int, kg_summary_text: str, n_cycles: int) -> str:
    return (
        f"Cycle {cycle}/{n_cycles}. You are proposing a NEW concept node that extends the knowledge graph.\n\n"
        f"Current KG nodes:\n{kg_summary_text}\n\n"
        "Respond ONLY with valid JSON (no markdown):\n"
        "{\n"
        '  "concept": "short concept name (2-5 words)",\n'
        '  "description": "one sentence description",\n'
        '  "tags": ["tag1", "tag2"],\n'
        '  "type": "concept"\n'
        "}"
    )


def agent2_prompt(cycle: int, new_node: dict, kg_summary_text: str, n_cycles: int) -> str:
    return (
        f"Cycle {cycle}/{n_cycles}. You are proposing edges connecting a new node to existing nodes.\n\n"
        f"New node from Agent 1:\n{json.dumps(new_node, ensure_ascii=False)}\n\n"
        f"Current KG nodes:\n{kg_summary_text}\n\n"
        "Propose 2-3 edges. Respond ONLY with valid JSON (no markdown):\n"
        "{\n"
        '  "edges": [\n'
        '    {"from": "new_node_id", "to": "existing_node_id", "relation": "relation_type"},\n'
        '    {"from": "new_node_id", "to": "existing_node_id", "relation": "relation_type"}\n'
        "  ]\n"
        "}"
    )


# ─── JSON 파싱 ───────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


def kg_summary_text(kg: dict, max_nodes: int = 10) -> str:
    nodes = kg["nodes"][-max_nodes:] if len(kg["nodes"]) > max_nodes else kg["nodes"]
    lines = []
    for n in nodes:
        src = n.get("source", "?")
        concept = n.get("concept", n.get("description", "?")[:50])
        lines.append(f"  {n['id']} [{src}]: {concept}")
    return "\n".join(lines) if lines else "(empty)"


# ─── 판정 ────────────────────────────────────────────────────────────────────

REFERENCE_CSER_A = 0.5455

def judge_cser(cser_b: float) -> tuple:
    """Returns (judgment_str, echo_chamber_gate)."""
    echo_gate = cser_b < 0.30
    if cser_b < 0.4955:
        judgment = "가설 지지"
    elif cser_b <= 0.5955:
        judgment = "불확정"
    else:
        judgment = "가설 반박"
    return judgment, echo_gate


# ─── 메인 실험 루프 ──────────────────────────────────────────────────────────

def run_experiment(n_cycles: int = 20) -> dict:
    mode_label = "[DRY-RUN] " if DRY_RUN else ""
    print(f"═══ {mode_label}Condition B v2: 동일 페르소나 × 이종 모델 (Cycle 93) ═══", flush=True)
    print(f"  Agent 1 (Proposer): GPT-5.2 (gpt-5.2-chat-latest), 냉정한 판사", flush=True)
    print(f"  Agent 2 (Connector): Gemini-3.1-Flash (gemini-3-flash-preview), 냉정한 판사", flush=True)
    print(f"  Cycles: {n_cycles}", flush=True)
    print(f"  Reference CSER(A): {REFERENCE_CSER_A}", flush=True)
    print(flush=True)

    # 3 problems: GCD, QuickSort, LRU Cache
    problems = ["GCD", "QuickSort", "LRU Cache"]

    kg = init_kg()
    cycle_results = []
    errors = []
    cser_history = []

    # 시드 노드: 두 에이전트 각각 1개
    seed_nodes = [
        {
            "id": "n-001",
            "source": "agent1",
            "concept": "algorithmic correctness",
            "description": "The property of an algorithm producing the expected output for all valid inputs",
            "tags": ["correctness", "algorithm"],
            "type": "concept",
        },
        {
            "id": "n-002",
            "source": "agent2",
            "concept": "computational complexity",
            "description": "Measure of resources required by an algorithm relative to input size",
            "tags": ["complexity", "performance"],
            "type": "concept",
        },
    ]
    seed_edge = {"from": "n-001", "to": "n-002", "relation": "constrains", "cycle": 0}
    kg["nodes"].extend(seed_nodes)
    kg["edges"].append(seed_edge)

    print("시드 노드 초기화 완료 (n-001: agent1, n-002: agent2)", flush=True)
    metrics = compute_metrics(kg)
    print(f"  초기 CSER={metrics['CSER']}, E_v4={metrics['E_v4']}", flush=True)
    print(flush=True)

    cser_history.append(metrics["CSER"])
    cycle_results.append({"cycle": 0, "phase": "init", **metrics})

    for cycle in range(1, n_cycles + 1):
        problem = problems[(cycle - 1) % len(problems)]
        print(f"── 사이클 {cycle}/{n_cycles} [{problem}] ──────────────────────────────────", flush=True)

        try:
            # --- Step 1: Agent 1 (GPT-5.2) → 새 노드 제안 ---
            new_id = _next_node_id(kg)
            print(f"  Agent1 (GPT) 노드 제안 중... [→ {new_id}]", flush=True)

            if DRY_RUN:
                node_data = dry_run_agent1(cycle)
                # Dry-run: simulate API delay
                time.sleep(0.1)
            else:
                prompt_a = agent1_prompt(cycle, kg_summary_text(kg), n_cycles)
                response_a = call_openai(JUDGE_PERSONA, prompt_a)
                node_data = parse_json_response(response_a)
                time.sleep(1.5)

            new_node = {
                "id": new_id,
                "source": "agent1",
                "concept": node_data.get("concept", f"concept-cycle{cycle}"),
                "description": node_data.get("description", ""),
                "tags": node_data.get("tags", []),
                "type": node_data.get("type", "concept"),
                "cycle": cycle,
                "problem": problem,
            }
            kg["nodes"].append(new_node)
            print(f"  → {new_node['concept']}", flush=True)

            # --- Step 2: Agent 2 (Gemini-3.1-Flash) → 엣지 제안 ---
            print(f"  Agent2 (Gemini) 엣지 연결 중...", flush=True)

            if DRY_RUN:
                new_node_for_dry = dict(new_node)
                new_node_for_dry["id"] = new_id
                edge_data = dry_run_agent2(new_node_for_dry, kg)
                time.sleep(0.1)
            else:
                prompt_b = agent2_prompt(cycle, new_node, kg_summary_text(kg), n_cycles)
                response_b = call_gemini(JUDGE_PERSONA, prompt_b)
                edge_data = parse_json_response(response_b)
                time.sleep(1.5)

            valid_ids = {n["id"] for n in kg["nodes"]}
            added_edges = 0
            for e in edge_data.get("edges", []):
                from_id = e.get("from", new_id)
                to_id = e.get("to", "")
                if from_id == "new_node_id":
                    from_id = new_id
                if to_id == "new_node_id":
                    to_id = new_id
                if from_id in valid_ids and to_id in valid_ids and from_id != to_id:
                    kg["edges"].append({
                        "from": from_id,
                        "to": to_id,
                        "relation": e.get("relation", "relates_to"),
                        "cycle": cycle,
                    })
                    added_edges += 1

            print(f"  → {added_edges}개 엣지 추가", flush=True)

            # --- Step 3: 메트릭 측정 ---
            metrics = compute_metrics(kg)
            cser_history.append(metrics["CSER"])
            print(
                f"  CSER={metrics['CSER']:.4f}, E_v4={metrics['E_v4']:.4f}, "
                f"노드={metrics['n_nodes']}, 엣지={metrics['n_edges']}",
                flush=True,
            )

            cycle_results.append({
                "cycle": cycle,
                "problem": problem,
                "new_node": new_node["concept"],
                "edges_added": added_edges,
                **metrics,
            })

        except Exception as ex:
            error_msg = str(ex)
            print(f"  오류: {error_msg[:120]}", flush=True)
            errors.append({"cycle": cycle, "error": error_msg})

            # 폴백: 번갈아 가며 소스 할당
            new_id = _next_node_id(kg)
            fallback_src = "agent1" if cycle % 2 == 1 else "agent2"
            kg["nodes"].append({
                "id": new_id,
                "source": fallback_src,
                "concept": f"fallback-concept-{cycle}",
                "description": f"Fallback node for cycle {cycle}",
                "tags": ["fallback"],
                "type": "concept",
                "cycle": cycle,
                "problem": problem,
                "fallback": True,
            })
            if len(kg["nodes"]) >= 2:
                prev_id = kg["nodes"][-2]["id"]
                kg["edges"].append({
                    "from": new_id,
                    "to": prev_id,
                    "relation": "extends",
                    "cycle": cycle,
                    "fallback": True,
                })
            metrics = compute_metrics(kg)
            cser_history.append(metrics["CSER"])
            cycle_results.append({"cycle": cycle, "problem": problem, "fallback": True, **metrics})

    # ─── 최종 결과 ────────────────────────────────────────────────────────────
    final_metrics = compute_metrics(kg)
    final_cser = final_metrics["CSER"]

    # 부트스트랩 CI 95%
    ci_lo, ci_hi = bootstrap_ci(cser_history)

    # 판정
    judgment, echo_gate = judge_cser(final_cser)

    print(flush=True)
    print("═══ 최종 결과 ═══", flush=True)
    print(f"  최종 CSER(B): {final_cser:.4f}", flush=True)
    print(f"  부트스트랩 CI 95%: [{ci_lo:.4f}, {ci_hi:.4f}]", flush=True)
    print(f"  참조 CSER(A): {REFERENCE_CSER_A}", flush=True)
    print(f"  판정: {judgment}", flush=True)
    if echo_gate:
        print(f"  [D-076] 에코챔버 게이트 차단 (CSER < 0.30)", flush=True)
    print(f"  KG: {final_metrics['n_nodes']} 노드, {final_metrics['n_edges']} 엣지", flush=True)
    print(f"  오류/폴백: {len(errors)}회", flush=True)

    output = {
        "experiment": "condition_b_v2_homogeneous_persona_hetero_model",
        "cycle": 93,
        "persona": "냉정한 판사 × 냉정한 판사",
        "agents": {
            "agent1": {
                "model": "gpt-5.2-chat-latest",
                "persona": "냉정한 판사",
                "source": "agent1",
            },
            "agent2": {
                "model": "gemini-3-flash-preview",
                "persona": "냉정한 판사",
                "source": "agent2",
            },
        },
        "n_cycles": n_cycles,
        "problems": problems,
        "cycle_results": cycle_results,
        "final_cser": final_cser,
        "cser_history": cser_history,
        "bootstrap_ci_95": [ci_lo, ci_hi],
        "reference_cser_a": REFERENCE_CSER_A,
        "judgment": judgment,
        "echo_chamber_gate": echo_gate,
        "final_metrics": final_metrics,
        "errors": errors,
        "n_fallbacks": sum(1 for r in cycle_results if r.get("fallback")),
        "dry_run": DRY_RUN,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if not DRY_RUN:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {RESULTS_FILE}", flush=True)
    else:
        print(f"\n[DRY-RUN] 결과 저장 생략 (실제 실행 시 → {RESULTS_FILE})", flush=True)

    return output


if __name__ == "__main__":
    result = run_experiment(n_cycles=20)
    if JSON_OUT:
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
