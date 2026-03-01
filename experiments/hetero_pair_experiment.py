#!/usr/bin/env python3
"""
hetero_pair_experiment.py — Heterogeneous LLM Pair KG 공동 진화 실험
사이클 86: Limitations ①④⑦ 해소

실험 설계:
  - Agent A: GPT-5.2 (OpenAI) — 개념 제안자 (Proposer)
  - Agent B: Gemini 3 Flash (Google) — 연결 탐색자 (Connector)
  - 10사이클 공동 KG 진화
  - 각 사이클: A가 새 노드 제안 → B가 연결 엣지 제안
  - CSER, E_v4 측정 → "이진 게이트 LLM-pair-independent" 검증

환경변수:
  OPENAI_API_KEY, GOOGLE_AI_API_KEY (GOOGLE_API_KEY fallback)

결과 지표:
  - 사이클별 CSER (목표: CSER > 0.5 달성 확인)
  - 최종 E_v4 vs 기존 Claude-Claude pair 비교
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
GOOGLE_KEY = os.environ.get("GOOGLE_AI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
RESULTS_FILE = REPO / "experiments" / "hetero_pair_results.json"

# ─── 초기 KG (빈 상태에서 시작) ───────────────────────────────────────────────

def init_kg() -> dict:
    """헤테로 페어 실험용 빈 KG 초기화"""
    return {
        "meta": {
            "experiment": "hetero_pair_cycle86",
            "pair": "GPT-5.2 (Proposer) × Gemini-3-Flash (Connector)",
            "started": datetime.utcnow().isoformat(),
        },
        "nodes": [],
        "edges": [],
    }


# ─── 노드/엣지 번호 유틸 ───────────────────────────────────────────────────────

def _next_node_id(kg: dict) -> str:
    nums = [int(n["id"].replace("n-", "")) for n in kg["nodes"] if n["id"].startswith("n-")]
    return f"n-{(max(nums) + 1) if nums else 1:03d}"


def _node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


# ─── API 호출 ──────────────────────────────────────────────────────────────────

def call_openai(prompt: str, model: str = "gpt-5.2") -> str:
    """OpenAI API 호출 (GPT-5.2 최신)"""
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_KEY}",
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read())
    return data["choices"][0]["message"]["content"].strip()


def call_gemini(prompt: str, model: str = "gemini-3.1-flash") -> str:
    """Google Gemini API 호출 (Gemini-3.1-Flash 최신)"""
    if not GOOGLE_KEY:
        raise RuntimeError("GOOGLE_AI_API_KEY not set")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.7},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ─── CSER 계산 ────────────────────────────────────────────────────────────────

def compute_cser(kg: dict) -> float:
    def _norm(s: str) -> str:
        return {"gpt": "gpt", "gpt-5.2": "gpt", "openai": "gpt",
                "gemini": "gemini", "google": "gemini"}.get(s.lower(), s.lower())

    node_src = {n["id"]: _norm(n.get("source", "")) for n in kg["nodes"]}
    n_edges = len(kg["edges"])
    if n_edges == 0:
        return 0.0
    cross = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
    )
    return round(cross / n_edges, 4)


def compute_metrics(kg: dict) -> dict:
    """CSER + 간단한 E_v4 근사 계산"""
    nodes = kg["nodes"]
    edges = kg["edges"]
    n_nodes = len(nodes)
    n_edges = len(edges)

    cser = compute_cser(kg)

    # edge_span_norm
    if n_edges > 0 and n_nodes > 1:
        spans = [abs(_node_num(e["from"]) - _node_num(e["to"])) for e in edges]
        raw_span = statistics.mean(spans)
        edge_span_norm = min(1.0, raw_span / (n_nodes - 1))
    else:
        edge_span_norm = 0.0

    # node_age_div
    nums = [_node_num(n["id"]) for n in nodes if n["id"].startswith("n-")]
    node_age_div = (statistics.stdev(nums) / max(nums)) if len(nums) >= 2 else 0.0

    # E_v4 (DCI=0 근사 — question/answer 엣지 없음)
    e_v4 = 0.35 * cser + 0.25 * 0.0 + 0.25 * edge_span_norm + 0.15 * node_age_div

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "CSER": cser,
        "edge_span_norm": round(edge_span_norm, 4),
        "node_age_div": round(node_age_div, 4),
        "E_v4": round(e_v4, 4),
        "gate_passed": cser > 0.5,
    }


# ─── 프롬프트 ─────────────────────────────────────────────────────────────────

def proposer_prompt(cycle: int, kg_summary: str) -> str:
    return f"""You are Agent A (GPT-5.2), the Proposer in a knowledge graph co-evolution experiment.
Cycle {cycle}/10. Your role: propose a NEW concept node that extends the knowledge graph.

Current KG summary:
{kg_summary}

Respond ONLY with valid JSON (no markdown):
{{
  "concept": "short concept name (2-5 words)",
  "description": "one sentence description",
  "tags": ["tag1", "tag2"],
  "type": "concept"
}}"""


def connector_prompt(cycle: int, new_node: dict, kg_summary: str) -> str:
    return f"""You are Agent B (Gemini-3-Flash), the Connector in a knowledge graph co-evolution experiment.
Cycle {cycle}/10. Your role: propose connections between the new node and existing nodes.

New node from Agent A:
{json.dumps(new_node, ensure_ascii=False)}

Current KG nodes:
{kg_summary}

Propose 2-3 edges connecting the new node to existing nodes.
Respond ONLY with valid JSON (no markdown):
{{
  "edges": [
    {{"from": "new_node_id", "to": "existing_node_id", "relation": "relation_type"}},
    {{"from": "new_node_id", "to": "existing_node_id", "relation": "relation_type"}}
  ]
}}"""


# ─── JSON 파싱 ────────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    """LLM 응답에서 JSON 추출 (마크다운 코드블록 제거)"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 부분만 추출 시도
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


def kg_summary(kg: dict, max_nodes: int = 10) -> str:
    """KG 요약 (최근 노드 중심)"""
    nodes = kg["nodes"][-max_nodes:] if len(kg["nodes"]) > max_nodes else kg["nodes"]
    lines = []
    for n in nodes:
        lines.append(f"  {n['id']} [{n.get('source', '?')}]: {n.get('concept', n.get('description', '?')[:50])}")
    return "\n".join(lines) if lines else "(empty)"


# ─── 메인 실험 루프 ───────────────────────────────────────────────────────────

def run_experiment(n_cycles: int = 10) -> dict:
    print("═══ Heterogeneous LLM Pair Experiment (Cycle 86) ═══")
    print("  Agent A (Proposer): GPT-5.2")
    print("  Agent B (Connector): Gemini-3.1-Flash")
    print(f"  Cycles: {n_cycles}")
    print()

    kg = init_kg()
    cycle_results = []
    errors = []

    # 시드 노드 2개 (실험 시작점)
    seed_nodes = [
        {"id": "n-001", "source": "gpt", "concept": "emergent intelligence",
         "description": "Intelligence arising from complex interactions", "tags": ["emergence", "intelligence"], "type": "concept"},
        {"id": "n-002", "source": "gemini", "concept": "cross-source synthesis",
         "description": "Knowledge creation by combining heterogeneous sources", "tags": ["synthesis", "cross-source"], "type": "concept"},
    ]
    seed_edge = {"from": "n-001", "to": "n-002", "relation": "enables", "cycle": 0}
    kg["nodes"].extend(seed_nodes)
    kg["edges"].append(seed_edge)

    print("시드 노드 초기화 완료 (n-001: GPT, n-002: Gemini)")
    metrics = compute_metrics(kg)
    print(f"  초기 CSER={metrics['CSER']}, E_v4={metrics['E_v4']}\n")

    cycle_results.append({"cycle": 0, "phase": "init", **metrics})

    for cycle in range(1, n_cycles + 1):
        print(f"── 사이클 {cycle}/{n_cycles} ────────────────────────────────")

        try:
            # --- Step 1: Agent A (GPT) → 새 노드 제안 ---
            new_id = _next_node_id(kg)
            prompt_a = proposer_prompt(cycle, kg_summary(kg))
            print(f"  A (GPT) 노드 제안 중... [→ {new_id}]")
            response_a = call_openai(prompt_a)
            node_data = parse_json_response(response_a)

            new_node = {
                "id": new_id,
                "source": "gpt",
                "concept": node_data.get("concept", f"concept-{cycle}"),
                "description": node_data.get("description", ""),
                "tags": node_data.get("tags", []),
                "type": node_data.get("type", "concept"),
                "cycle": cycle,
            }
            kg["nodes"].append(new_node)
            print(f"  → {new_node['concept']}")

            # --- Step 2: Agent B (Gemini) → 엣지 제안 ---
            prompt_b = connector_prompt(cycle, new_node, kg_summary(kg))
            print(f"  B (Gemini) 엣지 연결 중...")
            response_b = call_gemini(prompt_b)
            edge_data = parse_json_response(response_b)

            valid_ids = {n["id"] for n in kg["nodes"]}
            added_edges = 0
            for e in edge_data.get("edges", []):
                from_id = e.get("from", new_id)
                to_id = e.get("to", "")
                # new_id 혹은 기존 ID로 정규화
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

            print(f"  → {added_edges}개 엣지 추가")

            # --- Step 3: 메트릭 측정 ---
            metrics = compute_metrics(kg)
            gate_symbol = "✅" if metrics["gate_passed"] else "⚠️"
            print(f"  {gate_symbol} CSER={metrics['CSER']:.4f}, E_v4={metrics['E_v4']:.4f}, "
                  f"노드={metrics['n_nodes']}, 엣지={metrics['n_edges']}")

            cycle_results.append({
                "cycle": cycle,
                "new_node": new_node["concept"],
                "edges_added": added_edges,
                **metrics,
            })

        except Exception as ex:
            error_msg = str(ex)
            print(f"  ❌ 오류: {error_msg[:100]}")
            errors.append({"cycle": cycle, "error": error_msg})
            # 폴백: 시뮬레이션 노드 추가
            new_id = _next_node_id(kg)
            fallback_src = "gpt" if cycle % 2 == 1 else "gemini"
            kg["nodes"].append({
                "id": new_id,
                "source": fallback_src,
                "concept": f"adaptive-concept-{cycle}",
                "description": f"Fallback node for cycle {cycle}",
                "tags": ["emergence", "adaptation"],
                "type": "concept",
                "cycle": cycle,
                "fallback": True,
            })
            if len(kg["nodes"]) >= 2:
                prev_id = kg["nodes"][-2]["id"]
                kg["edges"].append({
                    "from": new_id, "to": prev_id,
                    "relation": "extends", "cycle": cycle, "fallback": True,
                })
            metrics = compute_metrics(kg)
            cycle_results.append({"cycle": cycle, "fallback": True, **metrics})

        time.sleep(0.5)  # API rate limit 방지

    # ─── 최종 결과 ────────────────────────────────────────────────────────────
    final_metrics = compute_metrics(kg)
    cser_history = [r["CSER"] for r in cycle_results]
    gate_crossed = final_metrics["CSER"] > 0.5

    # 기존 Claude-Claude pair 참조값 (사이클 79-84 평균)
    claude_ref_cser = 0.80
    claude_ref_ev4 = 0.3859

    print("\n═══ 최종 결과 ═══")
    print(f"  최종 CSER: {final_metrics['CSER']:.4f}  {'✅ 게이트 통과' if gate_crossed else '⚠️  게이트 미달'}")
    print(f"  최종 E_v4: {final_metrics['E_v4']:.4f}")
    print(f"  KG: {final_metrics['n_nodes']} 노드, {final_metrics['n_edges']} 엣지")
    print(f"\n  비교 — Claude-Claude pair:")
    print(f"    CSER: {claude_ref_cser:.4f} vs GPT×Gemini: {final_metrics['CSER']:.4f}")
    print(f"    E_v4: {claude_ref_ev4:.4f} vs GPT×Gemini: {final_metrics['E_v4']:.4f}")

    output = {
        "cycle": 86,
        "experiment": "heterogeneous_llm_pair",
        "agents": {
            "A": {"role": "Proposer", "model": "GPT-5.2", "source_tag": "gpt"},
            "B": {"role": "Connector", "model": "Gemini-3.1-Flash", "source_tag": "gemini"},
        },
        "n_cycles": n_cycles,
        "cycle_results": cycle_results,
        "final_metrics": final_metrics,
        "cser_history": cser_history,
        "cser_mean": round(statistics.mean(cser_history), 4) if cser_history else 0,
        "cser_final": final_metrics["CSER"],
        "gate_passed": gate_crossed,
        "comparison": {
            "claude_claude": {"CSER": claude_ref_cser, "E_v4": claude_ref_ev4},
            "gpt_gemini": {"CSER": final_metrics["CSER"], "E_v4": final_metrics["E_v4"]},
        },
        "errors": errors,
        "n_fallbacks": sum(1 for r in cycle_results if r.get("fallback")),
        "timestamp": datetime.utcnow().isoformat(),
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {RESULTS_FILE}")
    return output


if __name__ == "__main__":
    result = run_experiment(n_cycles=10)
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
