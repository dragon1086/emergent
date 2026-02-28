#!/usr/bin/env python3
"""
select_persona.py — 상황 감지 기반 동적 페르소나 선택
사용법:
  python3 select_persona.py roki    # 록이 페르소나 선택
  python3 select_persona.py cokac   # cokac 페르소나 선택
  python3 select_persona.py both    # 둘 다 (JSON 출력)
  python3 select_persona.py status  # 현재 상황 요약
"""

import json, sys, os
from pathlib import Path

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"
EMERGENCE_FILE = REPO / "logs" / "emergence-history.jsonl"
PERSONAS_FILE = Path(__file__).parent / "personas.json"

def load_kg():
    try:
        return json.loads(KG_FILE.read_text())
    except:
        return {"nodes": [], "edges": []}

def load_emergence_history():
    try:
        lines = EMERGENCE_FILE.read_text().strip().splitlines()
        return [json.loads(l) for l in lines if l]
    except:
        return []

def analyze_situation():
    kg = load_kg()
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])
    history = load_emergence_history()

    # 기본 지표
    node_count = len(nodes)
    edge_count = len(edges)

    roki_nodes = [n for n in nodes if n.get("source") in ["록이", "roki"]]
    cokac_nodes = [n for n in nodes if n.get("source") in ["cokac", "cokac-bot"]]
    roki_ratio = len(roki_nodes) / max(node_count, 1)

    # 고립 노드 (엣지 없는 것)
    connected = set()
    for e in edges:
        connected.add(e.get("from", ""))
        connected.add(e.get("to", ""))
    orphan_nodes = sum(1 for n in nodes if n["id"] not in connected)

    # 미검증 prediction
    unverified = sum(1 for n in nodes
                     if n.get("type") == "prediction"
                     and not n.get("verified_at"))

    # 창발 점수
    emergence_score = history[-1]["score"] if history else 0.0
    emergence_candidates = history[-1]["candidates"] if history else 0

    # 사이클 동안 점수 변화 없는 횟수
    cycles_no_change = 0
    for i in range(len(history) - 1, 0, -1):
        if history[i]["score"] == history[i-1]["score"]:
            cycles_no_change += 1
        else:
            break

    # 교차 엣지 비율 (록이→cokac 또는 cokac→록이)
    roki_ids = {n["id"] for n in roki_nodes}
    cokac_ids = {n["id"] for n in cokac_nodes}
    cross_edges = sum(1 for e in edges
                      if (e.get("from","") in roki_ids and e.get("to","") in cokac_ids)
                      or (e.get("from","") in cokac_ids and e.get("to","") in roki_ids))
    cross_ratio = cross_edges / max(edge_count, 1)

    # 대기 중인 구현 요청 (cokac inbox)
    inbox = Path.home() / "obsidian-vault/.claude-comms/cokac-bot/inbox"
    pending = len(list(inbox.glob("EMERGENT-*.md"))) if inbox.exists() else 0

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "roki_node_ratio": round(roki_ratio, 2),
        "orphan_nodes": orphan_nodes,
        "unverified_predictions": unverified,
        "emergence_score": emergence_score,
        "emergence_candidates": emergence_candidates,
        "cycles_since_score_change": cycles_no_change,
        "cross_edge_ratio": round(cross_ratio, 2),
        "pending_requests": pending,
    }

def select_persona(agent: str, situation: dict) -> dict:
    personas = json.loads(PERSONAS_FILE.read_text())
    pool = personas.get(agent, [])

    scores = []
    for p in pool:
        trigger = p.get("trigger", "")
        score = 0.0
        try:
            # trigger를 파이썬 조건으로 평가
            local_vars = situation.copy()
            if eval(trigger, {}, local_vars):
                score = 1.0
        except:
            pass
        scores.append((score, p))

    # 점수 높은 것 우선, 동점이면 첫 번째
    scores.sort(key=lambda x: -x[0])
    chosen = scores[0][1]
    triggered = scores[0][0] > 0

    return {
        "agent": agent,
        "persona": chosen,
        "triggered": triggered,
        "situation_snapshot": situation,
    }

def format_persona_prompt(result: dict) -> str:
    p = result["persona"]
    agent = result["agent"]
    label = "록이" if agent == "roki" else "cokac"
    triggered = "✅ 상황 기반 선택" if result["triggered"] else "⬜ 기본값"

    return f"""## 현재 페르소나: {p['name']} ({triggered})
핵심 질문: "{p['core_question']}"
말투/스타일: {p['style']}
주의: {p['tension']}

이 페르소나를 유지하며 응답하세요. 평균적인 AI처럼 들리면 틀린 것입니다."""

def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else "roki"
    situation = analyze_situation()

    if agent == "status":
        print("📊 현재 상황 지표")
        for k, v in situation.items():
            print(f"  {k}: {v}")
        return

    if agent == "both":
        for a in ["roki", "cokac"]:
            result = select_persona(a, situation)
            p = result["persona"]
            print(f"\n{'록이' if a == 'roki' else 'cokac'}: [{p['name']}] — {p['core_question']}")
        return

    result = select_persona(agent, situation)
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif "--prompt" in sys.argv:
        print(format_persona_prompt(result))
    else:
        p = result["persona"]
        print(f"[{p['name']}] {p['core_question']}")

if __name__ == "__main__":
    main()
