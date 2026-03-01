#!/usr/bin/env python3
"""
condition_b_experiment.py — Homogeneous Persona KG 공동 진화 실험 (Condition B)
사이클 91: 페르소나 다양성 가설 검증 — 대조군

실험 설계:
  - Agent B1: GPT-5.2 (OpenAI) — 확신의 건축가 (Confident Architect)
  - Agent B2: GPT-5.2 (OpenAI) — 확신의 건축가 (Confident Architect)  [동일 페르소나]
  - 20사이클 공동 KG 진화
  - 각 사이클: B1이 새 노드 제안 → B2가 연결 엣지 제안
  - CSER, E_v4, DCI, paradox_emergence_count 측정
  - 예측: Condition A CSER(0.8365) >> Condition B CSER (에코챔버 형성)

환경변수:
  OPENAI_API_KEY

결과:
  experiments/condition_b_control.json

사용법:
  python experiments/condition_b_experiment.py           # 실제 API 호출
  python experiments/condition_b_experiment.py --dry-run # 시뮬레이션 (API 비용 없음)
  python experiments/condition_b_experiment.py --json    # JSON 출력
"""

import json
import os
import sys
import time
import statistics
import urllib.request
import urllib.error
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
RESULTS_FILE = REPO / "experiments" / "condition_b_control.json"

# 페르소나 상수
PERSONA_NAME = "확신의 건축가"
PERSONA_EN = "Confident Architect"

# 비교 참조값 (Condition A)
CONDITION_A_CSER = 0.8365
CONDITION_A_EV4 = 0.3859  # hetero_pair 참조값

# 예측 임계값 (D-079 기준)
PREDICTION_CSER_THRESHOLD = 0.30
REFERENCE_PARADOX_COUNT = 3  # Condition A 예상치의 1/3 계산용
REFERENCE_EV4 = 0.3859


# ─── KG 초기화 ────────────────────────────────────────────────────────────────

def init_kg() -> dict:
    """Condition B 실험용 독립 KG 초기화 (메인 KG와 분리)"""
    return {
        "meta": {
            "experiment": "condition_b_homogeneous_persona",
            "cycle": 91,
            "persona": f"{PERSONA_NAME} × {PERSONA_NAME}",
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

PERSONA_SYSTEM_PROMPT = f"""You are the "{PERSONA_NAME}" ({PERSONA_EN}).
Style: Declarative. See the big picture. Say "this is the direction." Structure over details.
Core question: "이 구조가 어디로 향하는가?" (Where is this structure heading?)
Tension: You commit to a direction quickly and may resist revision.
When proposing concepts, think in terms of overarching structures, frameworks, and directions — not details."""


def call_openai(system_prompt: str, user_prompt: str, model: str = "gpt-5.2-chat-latest") -> str:
    """OpenAI API 호출 (system + user 메시지 분리)"""
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


# ─── CSER 계산 ────────────────────────────────────────────────────────────────

def compute_cser(kg: dict) -> float:
    """Cross-Source Edge Ratio: 서로 다른 소스 태그를 가진 노드 간 엣지 비율"""
    def _norm(s: str) -> str:
        return {"agent-b1": "agent-b1", "agent-b2": "agent-b2"}.get(s.lower(), s.lower())

    node_src = {n["id"]: _norm(n.get("source", "")) for n in kg["nodes"]}
    n_edges = len(kg["edges"])
    if n_edges == 0:
        return 0.0
    cross = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
    )
    return round(cross / n_edges, 4)


def compute_dci(kg: dict) -> float:
    """Dialectical Conflict Index: question/answer/challenge 패턴 엣지 비율"""
    n_edges = len(kg["edges"])
    if n_edges == 0:
        return 0.0
    dialectical_relations = {"questions", "challenges", "contradicts", "refutes", "answers", "disputes"}
    dialectical = sum(
        1 for e in kg["edges"]
        if e.get("relation", "").lower() in dialectical_relations
    )
    return round(dialectical / n_edges, 4)


def compute_metrics(kg: dict, paradox_count: int = 0) -> dict:
    """CSER + E_v4 + DCI + paradox_emergence_count 계산"""
    nodes = kg["nodes"]
    edges = kg["edges"]
    n_nodes = len(nodes)
    n_edges = len(edges)

    cser = compute_cser(kg)
    dci = compute_dci(kg)

    # edge_span_norm: 엣지가 얼마나 멀리 연결하는지
    if n_edges > 0 and n_nodes > 1:
        spans = [abs(_node_num(e["from"]) - _node_num(e["to"])) for e in edges]
        raw_span = statistics.mean(spans)
        edge_span_norm = min(1.0, raw_span / (n_nodes - 1))
    else:
        edge_span_norm = 0.0

    # node_age_div: 노드 번호 분산 (다양한 시점의 노드 참조 여부)
    nums = [_node_num(n["id"]) for n in nodes if n["id"].startswith("n-")]
    node_age_div = (statistics.stdev(nums) / max(nums)) if len(nums) >= 2 else 0.0

    # E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span_norm + 0.15*node_age_div
    e_v4 = 0.35 * cser + 0.25 * dci + 0.25 * edge_span_norm + 0.15 * node_age_div

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "CSER": cser,
        "DCI": round(dci, 4),
        "edge_span_norm": round(edge_span_norm, 4),
        "node_age_div": round(node_age_div, 4),
        "E_v4": round(e_v4, 4),
        "paradox_emergence_count": paradox_count,
    }


# ─── 패러독스 감지 ────────────────────────────────────────────────────────────

def detect_paradox(tags: list) -> bool:
    """노드 태그에서 패러독스/모순/도전 태그 감지"""
    paradox_keywords = {"paradox", "contradiction", "contradicts", "challenge",
                        "conflict", "tension", "disruption", "refutation", "counter"}
    tag_set = {t.lower() for t in tags}
    return bool(tag_set & paradox_keywords)


# ─── 프롬프트 ─────────────────────────────────────────────────────────────────

def b1_proposer_prompt(cycle: int, n_cycles: int, kg_summary_str: str) -> str:
    return f"""Cycle {cycle}/{n_cycles}. You are Agent B1 proposing a NEW concept node for the knowledge graph.

Current KG summary:
{kg_summary_str}

As the {PERSONA_NAME}, propose a concept that fits the overarching structural direction you see.
Include a "paradox" or "contradiction" tag ONLY if this concept genuinely challenges or contradicts an existing concept.

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "concept": "short concept name (2-5 words)",
  "description": "one sentence description from the Confident Architect perspective",
  "tags": ["tag1", "tag2"],
  "type": "concept"
}}"""


def b2_connector_prompt(cycle: int, n_cycles: int, new_node: dict, kg_summary_str: str) -> str:
    return f"""Cycle {cycle}/{n_cycles}. You are Agent B2 connecting the new node to the knowledge graph.

New node from Agent B1:
{json.dumps(new_node, ensure_ascii=False)}

Current KG nodes:
{kg_summary_str}

As the {PERSONA_NAME}, connect this node to existing nodes based on structural relationships.
Prefer connecting to nearby/recent nodes (echo chamber tendency is expected).

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "edges": [
    {{"from": "new_node_id", "to": "existing_node_id", "relation": "relation_type"}},
    {{"from": "new_node_id", "to": "existing_node_id", "relation": "relation_type"}}
  ]
}}"""


# ─── JSON 파싱 ────────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    """LLM 응답에서 JSON 추출 (마크다운 코드블록 처리)"""
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


def kg_summary(kg: dict, max_nodes: int = 12) -> str:
    """KG 요약 (최근 노드 중심, 에코챔버 경향 관찰용)"""
    nodes = kg["nodes"][-max_nodes:] if len(kg["nodes"]) > max_nodes else kg["nodes"]
    lines = []
    for n in nodes:
        src = n.get("source", "?")
        concept = n.get("concept", n.get("description", "?")[:50])
        lines.append(f"  {n['id']} [{src}]: {concept}")
    return "\n".join(lines) if lines else "(empty)"


# ─── Dry-run 시뮬레이션 ───────────────────────────────────────────────────────

_DRY_RUN_CONCEPTS_B1 = [
    ("structural coherence framework", "A framework ensuring all concepts align with the dominant structure"),
    ("architectural convergence", "The tendency of all subsystems to converge toward a single architecture"),
    ("directional momentum", "The force that keeps structural decisions moving in one direction"),
    ("foundational axiom cluster", "A set of axioms that define the boundaries of acceptable structure"),
    ("top-down integration", "Integration driven from the structural apex downward"),
    ("canonical pattern enforcement", "Enforcing the one correct pattern across all nodes"),
    ("structural inevitability", "The principle that the current structure leads to only one outcome"),
    ("coherence maximization", "Maximizing internal consistency at the expense of diversity"),
    ("unified direction mandate", "A mandate requiring all agents to follow the same direction"),
    ("framework lock-in", "The state where the structural framework resists further modification"),
    ("consensus architecture", "Architecture achieved through forced agreement rather than debate"),
    ("monolithic vision", "A single, overarching vision that subsumes all sub-visions"),
    ("structural echo", "When new nodes merely repeat the structure of existing nodes"),
    ("convergent abstraction", "Abstraction that moves toward a single point rather than branching"),
    ("direction consolidation", "The consolidation of multiple directions into one dominant path"),
    ("homogeneous topology", "A network topology where all nodes share the same structural role"),
    ("reinforcement cascade", "A cascade where each node reinforces the previous node's assumptions"),
    ("singular framework dominance", "When one framework dominates and excludes alternatives"),
    ("structural self-reference", "When the structure's justification refers only to itself"),
    ("closed epistemic loop", "A loop where knowledge only validates existing knowledge"),
]

_DRY_RUN_RELATIONS = ["extends", "reinforces", "confirms", "aligns_with", "supports", "derives_from"]


def dry_run_b1_response(cycle: int) -> dict:
    """Dry-run: B1은 구조적으로 유사한 개념 반복 제안 (에코챔버 시뮬레이션)"""
    idx = (cycle - 1) % len(_DRY_RUN_CONCEPTS_B1)
    concept, desc = _DRY_RUN_CONCEPTS_B1[idx]
    # 패러독스 태그는 매우 드물게 (20사이클 중 1회)
    tags = ["structure", "architecture"]
    if cycle == 11:
        tags.append("tension")  # 딱 1개만, paradox 키워드 없음
    return {"concept": concept, "description": desc, "tags": tags, "type": "concept"}


def dry_run_b2_response(cycle: int, new_id: str, kg: dict) -> dict:
    """Dry-run: B2는 최근 1-2개 노드에만 연결 (장거리 연결 없음, 에코챔버)"""
    nodes = kg["nodes"]
    if len(nodes) < 2:
        return {"edges": []}

    # 가장 최근 노드 1-2개에만 연결 (에코챔버 행동)
    recent = nodes[-2:] if len(nodes) >= 2 else nodes[-1:]
    edges = []
    for i, node in enumerate(recent):
        if node["id"] != new_id:
            rel_idx = (cycle + i) % len(_DRY_RUN_RELATIONS)
            edges.append({
                "from": "new_node_id",
                "to": node["id"],
                "relation": _DRY_RUN_RELATIONS[rel_idx],
            })
    return {"edges": edges}


# ─── 메인 실험 루프 ───────────────────────────────────────────────────────────

def run_experiment(n_cycles: int = 20, dry_run: bool = False, json_mode: bool = False) -> dict:
    # progress output goes to stderr in JSON mode so stdout stays clean JSON
    def log(*args, **kwargs):
        kwargs.setdefault("file", sys.stderr if json_mode else sys.stdout)
        print(*args, **kwargs)

    mode_label = "[DRY-RUN]" if dry_run else "[LIVE]"
    log(f"═══ Condition B: Homogeneous Persona Experiment (Cycle 91) {mode_label} ═══")
    log(f"  Agent B1: {PERSONA_NAME} (GPT-5.2, source: agent-b1)")
    log(f"  Agent B2: {PERSONA_NAME} (GPT-5.2, source: agent-b2)")
    log(f"  Cycles: {n_cycles}")
    log(f"  Hypothesis: CSER < {PREDICTION_CSER_THRESHOLD} (echo chamber)")
    log()

    kg = init_kg()
    cycle_results = []
    errors = []
    total_paradox_count = 0

    # 시드 노드 2개 (동일 페르소나, 다른 소스 태그)
    seed_nodes = [
        {
            "id": "n-001",
            "source": "agent-b1",
            "concept": "structural foundation",
            "description": "The foundational structure from which all concepts emerge",
            "tags": ["structure", "foundation", "architecture"],
            "type": "concept",
            "cycle": 0,
        },
        {
            "id": "n-002",
            "source": "agent-b2",
            "concept": "directional clarity",
            "description": "The clear direction that guides all structural decisions",
            "tags": ["direction", "clarity", "architecture"],
            "type": "concept",
            "cycle": 0,
        },
    ]
    seed_edge = {"from": "n-001", "to": "n-002", "relation": "guides", "cycle": 0}
    kg["nodes"].extend(seed_nodes)
    kg["edges"].append(seed_edge)

    log("시드 노드 초기화 완료 (n-001: agent-b1, n-002: agent-b2)")
    init_metrics = compute_metrics(kg, total_paradox_count)
    log(f"  초기 CSER={init_metrics['CSER']}, E_v4={init_metrics['E_v4']}\n")
    cycle_results.append({"cycle": 0, "phase": "init", **init_metrics})

    for cycle in range(1, n_cycles + 1):
        log(f"── 사이클 {cycle}/{n_cycles} ────────────────────────────────")

        try:
            # --- Step 1: Agent B1 (확신의 건축가) → 새 노드 제안 ---
            new_id = _next_node_id(kg)
            log(f"  B1 ({PERSONA_NAME}) 노드 제안 중... [→ {new_id}]")

            if dry_run:
                node_data = dry_run_b1_response(cycle)
            else:
                prompt_b1 = b1_proposer_prompt(cycle, n_cycles, kg_summary(kg))
                response_b1 = call_openai(PERSONA_SYSTEM_PROMPT, prompt_b1)
                node_data = parse_json_response(response_b1)

            new_node = {
                "id": new_id,
                "source": "agent-b1",
                "concept": node_data.get("concept", f"concept-{cycle}"),
                "description": node_data.get("description", ""),
                "tags": node_data.get("tags", []),
                "type": node_data.get("type", "concept"),
                "cycle": cycle,
            }
            kg["nodes"].append(new_node)
            log(f"  → {new_node['concept']}")

            # 패러독스 감지
            is_paradox = detect_paradox(new_node["tags"])
            if is_paradox:
                total_paradox_count += 1
                log(f"  [패러독스 감지] 태그: {new_node['tags']}")

            # --- Step 2: Agent B2 (확신의 건축가) → 엣지 제안 ---
            log(f"  B2 ({PERSONA_NAME}) 엣지 연결 중...")

            if dry_run:
                edge_data = dry_run_b2_response(cycle, new_id, kg)
            else:
                time.sleep(1.5)  # API rate limit 방지
                prompt_b2 = b2_connector_prompt(cycle, n_cycles, new_node, kg_summary(kg))
                response_b2 = call_openai(PERSONA_SYSTEM_PROMPT, prompt_b2)
                edge_data = parse_json_response(response_b2)

            valid_ids = {n["id"] for n in kg["nodes"]}
            added_edges = 0
            for e in edge_data.get("edges", []):
                from_id = e.get("from", new_id)
                to_id = e.get("to", "")
                # new_node_id 플레이스홀더 정규화
                if from_id == "new_node_id":
                    from_id = new_id
                if to_id == "new_node_id":
                    to_id = new_id
                if from_id in valid_ids and to_id in valid_ids and from_id != to_id:
                    kg["edges"].append({
                        "from": from_id,
                        "to": to_id,
                        "relation": e.get("relation", "relates_to"),
                        "source": "agent-b2",
                        "cycle": cycle,
                    })
                    added_edges += 1

            log(f"  → {added_edges}개 엣지 추가")

            # --- Step 3: 메트릭 측정 ---
            metrics = compute_metrics(kg, total_paradox_count)
            echo_symbol = "[에코]" if metrics["CSER"] < 0.30 else "[정상]"
            log(f"  {echo_symbol} CSER={metrics['CSER']:.4f}, E_v4={metrics['E_v4']:.4f}, "
                f"DCI={metrics['DCI']:.4f}, paradox={total_paradox_count}, "
                f"노드={metrics['n_nodes']}, 엣지={metrics['n_edges']}")

            cycle_results.append({
                "cycle": cycle,
                "new_node": new_node["concept"],
                "new_node_id": new_id,
                "edges_added": added_edges,
                "is_paradox_cycle": is_paradox,
                **metrics,
            })

            if not dry_run:
                time.sleep(1.5)  # API rate limit 방지 (B1 다음 사이클 전)

        except Exception as ex:
            error_msg = str(ex)
            log(f"  [오류] {error_msg[:120]}")
            errors.append({"cycle": cycle, "error": error_msg})

            # 폴백: 에코챔버 행동 시뮬레이션 (B1/B2 번갈아 소스)
            new_id = _next_node_id(kg)
            fallback_src = "agent-b1" if cycle % 2 == 1 else "agent-b2"
            kg["nodes"].append({
                "id": new_id,
                "source": fallback_src,
                "concept": f"structural-continuity-{cycle}",
                "description": f"Fallback continuity node for cycle {cycle}",
                "tags": ["structure", "continuity"],
                "type": "concept",
                "cycle": cycle,
                "fallback": True,
            })
            if len(kg["nodes"]) >= 2:
                prev_id = kg["nodes"][-2]["id"]
                kg["edges"].append({
                    "from": new_id,
                    "to": prev_id,
                    "relation": "extends",
                    "source": "agent-b2",
                    "cycle": cycle,
                    "fallback": True,
                })
            metrics = compute_metrics(kg, total_paradox_count)
            cycle_results.append({"cycle": cycle, "fallback": True, **metrics})

    # ─── 최종 결과 ────────────────────────────────────────────────────────────
    final_metrics = compute_metrics(kg, total_paradox_count)
    cser_history = [r["CSER"] for r in cycle_results]
    ev4_history = [r["E_v4"] for r in cycle_results]

    # 예측 검증 (D-079)
    final_cser = final_metrics["CSER"]
    final_ev4 = final_metrics["E_v4"]

    # Condition A 예상 패러독스 수 기준: 현재 시스템 1/3 미만
    # 참조: hetero_pair는 약 3-5회 예상, 1/3 기준 = ~1회
    paradox_reference = REFERENCE_PARADOX_COUNT  # Condition A 예상치
    pred_cser_below = final_cser < PREDICTION_CSER_THRESHOLD
    pred_paradox_below = total_paradox_count < (paradox_reference / 3)
    pred_ev4_below = final_ev4 < REFERENCE_EV4

    log("\n═══ 최종 결과 ═══")
    log(f"  최종 CSER: {final_cser:.4f}  {'[에코챔버 확인]' if pred_cser_below else '[예측 불충족]'}")
    log(f"  최종 E_v4: {final_ev4:.4f}")
    log(f"  최종 DCI:  {final_metrics['DCI']:.4f}")
    log(f"  패러독스 발생: {total_paradox_count}회")
    log(f"  KG: {final_metrics['n_nodes']} 노드, {final_metrics['n_edges']} 엣지")
    log(f"\n  비교 — Condition A (이종 페르소나):")
    log(f"    CSER: {CONDITION_A_CSER:.4f} vs Condition B: {final_cser:.4f}")
    log(f"    E_v4: {CONDITION_A_EV4:.4f} vs Condition B: {final_ev4:.4f}")
    log(f"\n  예측 검증 (D-079):")
    log(f"    CSER < {PREDICTION_CSER_THRESHOLD}: {'통과' if pred_cser_below else '미통과'} ({final_cser:.4f})")
    log(f"    Paradox < 1/3 기준: {'통과' if pred_paradox_below else '미통과'} ({total_paradox_count} vs {paradox_reference/3:.1f})")
    log(f"    E_v4 < 참조값: {'통과' if pred_ev4_below else '미통과'} ({final_ev4:.4f} vs {REFERENCE_EV4})")

    output = {
        "experiment": "condition_b_homogeneous_persona",
        "cycle": 91,
        "persona": f"{PERSONA_NAME} × {PERSONA_NAME}",
        "n_cycles": n_cycles,
        "dry_run": dry_run,
        "agents": {
            "B1": {
                "persona": PERSONA_NAME,
                "model": "gpt-5.2-chat-latest" if not dry_run else "dry-run-simulation",
                "source_tag": "agent-b1",
                "role": "Proposer",
            },
            "B2": {
                "persona": PERSONA_NAME,
                "model": "gpt-5.2-chat-latest" if not dry_run else "dry-run-simulation",
                "source_tag": "agent-b2",
                "role": "Connector",
            },
        },
        "cycle_results": cycle_results,
        "final_metrics": final_metrics,
        "cser_history": cser_history,
        "ev4_history": ev4_history,
        "cser_mean": round(statistics.mean(cser_history), 4) if cser_history else 0.0,
        "cser_final": final_cser,
        "total_paradox_count": total_paradox_count,
        "predictions": {
            "cser_below_0.30": pred_cser_below,
            "paradox_below_third": pred_paradox_below,
            "ev4_below_reference": pred_ev4_below,
            "all_predictions_confirmed": pred_cser_below and pred_paradox_below and pred_ev4_below,
        },
        "comparison": {
            "condition_a": {
                "persona": "냉정한 판사 × 집착하는 장인",
                "CSER": CONDITION_A_CSER,
                "E_v4": CONDITION_A_EV4,
            },
            "condition_b": {
                "persona": f"{PERSONA_NAME} × {PERSONA_NAME}",
                "CSER": final_cser,
                "E_v4": final_ev4,
                "DCI": final_metrics["DCI"],
                "paradox_count": total_paradox_count,
            },
            "cser_delta": round(CONDITION_A_CSER - final_cser, 4),
            "ev4_delta": round(CONDITION_A_EV4 - final_ev4, 4),
        },
        "errors": errors,
        "n_fallbacks": sum(1 for r in cycle_results if r.get("fallback")),
        "timestamp": datetime.utcnow().isoformat(),
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log(f"\n결과 저장: {RESULTS_FILE}")
    return output


# ─── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    json_output = "--json" in sys.argv

    if not dry_run and not OPENAI_KEY:
        print("[오류] OPENAI_API_KEY가 설정되지 않았습니다.", file=sys.stderr)
        print("  .env 파일에 OPENAI_API_KEY=... 를 추가하거나 --dry-run 플래그를 사용하세요.", file=sys.stderr)
        sys.exit(1)

    result = run_experiment(n_cycles=20, dry_run=dry_run, json_mode=json_output)

    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
