#!/usr/bin/env python3
"""
anti_optimization.py — 사이클 38 구현
구현자: cokac-bot (집착하는 장인)

D-038: 반최적화 원칙
---
세 역설의 공통 구조:

  D-031 (건강 역설)  : 100% 건강 = 에코 챔버. 불건강이 창발의 재료.
  D-036 (균형 역설)  : 완전 균형 = 창발 최악. 비대칭이 창발의 연료.
  D-037 (수렴 역설)  : 수렴 → 0 = 창발 소멸. 거리가 창발의 공간.

공통 패턴:
  최적화는 이 시스템을 파괴한다.
  모든 '완벽한 상태'는 창발의 에너지를 없앤다.
  불완전함이 창발의 연료다.

수식화:
  Fragility(x) = 1 / max(dist(x, optimum_i) for i in paradoxes)
  → 어느 최적점에라도 가까우면 취약성 급상승

이 도구가 계산하는 것:
  1. 세 차원에서의 현재 위치
  2. 각 최적 함정까지의 거리
  3. 종합 취약성 점수 (0=안전, 1=위험)
  4. 다음 개입 권고

사용법:
  python anti_optimization.py analyze    # 현재 상태 분석
  python anti_optimization.py paradoxes  # 세 역설 구조 출력
  python anti_optimization.py fragility  # 취약성 점수 계산
  python anti_optimization.py recommend  # 개입 권고
  python anti_optimization.py history    # 사이클별 취약성 변화
"""

import json
import sys
import math
from pathlib import Path
from collections import defaultdict, Counter

REPO_DIR = Path(__file__).parent.parent
KG_FILE = REPO_DIR / "data" / "knowledge-graph.json"

# ─── 역설 정의 ─────────────────────────────────────────────
# 각 역설은 (차원, 최적 함정, 함정 임계값, 설명) 으로 정의

PARADOXES = {
    "D-031": {
        "name": "건강 역설",
        "dimension": "echo_chamber_score",
        "optimal_trap": 1.0,     # 100% 건강이 함정
        "danger_threshold": 0.85, # 0.85 이상이면 위험
        "description": "건강 100점 = 에코 챔버. breakthrough 수렴이 균일해질수록 창발 불가능.",
        "anti_rule": "에코 챔버 점수가 높으면 의도적 갈등 노드 삽입",
        "node_refs": ["n-031", "n-032", "n-036", "n-039"],
    },
    "D-036": {
        "name": "균형 역설",
        "dimension": "asymmetry_ratio",
        "optimal_trap": 1.0,     # 완전 균형 (비율 1.0)이 함정
        "danger_threshold": 0.15, # 비율 차이가 0.15 이하이면 위험
        "description": "완전 균형 = 창발 최악. 비대칭이 교차를 만든다.",
        "anti_rule": "비율이 1.0에 가까우면 페르소나 강화 (의도적 비대칭)",
        "node_refs": ["n-058", "n-059", "n-060"],
    },
    "D-037": {
        "name": "수렴 역설",
        "dimension": "persona_distance",
        "optimal_trap": 0.0,     # 거리 0 (완전 수렴)이 함정
        "danger_threshold": 0.25, # 0.25 이하이면 위험
        "healthy_range": (0.25, 0.35),
        "asymmetric_target": 0.285,  # 중심(0.30)이 아닌 살짝 아래 — D-036 반영
        "description": "페르소나 거리 → 0 = D-033 경계 소멸 = 창발 불가능.",
        "anti_rule": "거리 0.25 이하 접근 시 갈등 엣지/모순 노드로 발산",
        "node_refs": ["n-065", "n-066", "n-067"],
    },
}

# ─── KG 로드 ─────────────────────────────────────────────

def load_kg():
    with open(KG_FILE) as f:
        return json.load(f)

SOURCE_ALIAS = {"cokac-bot": "cokac", "cokac": "cokac", "록이": "록이", "상록": "록이"}

def normalize(s):
    return SOURCE_ALIAS.get(s, s)

# ─── 차원 측정 ─────────────────────────────────────────────

def measure_echo_chamber(kg):
    """breakthrough 수렴 태그의 균일도 → 높을수록 에코 챔버 위험"""
    edges = kg["edges"]
    nodes = kg["nodes"]

    # breakthrough / confirms / validates 계열 엣지 비율
    convergent_types = {"confirms", "validates", "verifies", "reinforces", "supports", "grounds"}
    tension_types = {"challenges", "contradicts", "reframes", "questions"}

    conv_count = sum(1 for e in edges if e.get("relation") in convergent_types)
    tension_count = sum(1 for e in edges if e.get("relation") in tension_types)
    total = len(edges)

    if total == 0:
        return 0.5

    # 수렴 비율이 높고 긴장 비율이 낮으면 에코 챔버 점수 상승
    conv_ratio = conv_count / total
    tension_ratio = tension_count / total

    # 에코 챔버 점수: 수렴이 많고 긴장이 적으면 높음
    echo_score = conv_ratio - tension_ratio * 2
    echo_score = max(0.0, min(1.0, echo_score + 0.5))

    return echo_score, {
        "convergent_edges": conv_count,
        "tension_edges": tension_count,
        "total_edges": total,
        "conv_ratio": round(conv_ratio, 3),
        "tension_ratio": round(tension_ratio, 3),
    }

def measure_asymmetry(kg):
    """노드 생성 비율 비대칭 측정"""
    nodes = kg["nodes"]
    src_count = Counter(normalize(n.get("source", "unknown")) for n in nodes)

    cokac_n = src_count.get("cokac", 0)
    roki_n = src_count.get("록이", 0)
    total = cokac_n + roki_n

    if total == 0:
        return 1.0, {}

    # 비율 차이 (1.0 = 완전 균형, 멀수록 비대칭)
    ratio = cokac_n / roki_n if roki_n > 0 else float('inf')
    # 균형으로부터의 거리 (ratio=1.0이 완전 균형)
    imbalance = abs(ratio - 1.0)

    return ratio, {
        "cokac_nodes": cokac_n,
        "roki_nodes": roki_n,
        "ratio": round(ratio, 3),
        "imbalance": round(imbalance, 3),
    }

def measure_persona_distance(kg):
    """페르소나 지문 거리 측정 (persona_fingerprint.py 알고리즘 기반)"""
    nodes = kg["nodes"]

    # 노드 타입 분포
    type_counts = {
        "cokac": Counter(),
        "록이": Counter(),
    }

    NODE_TYPES = ["question", "observation", "decision", "insight", "tool", "experiment", "finding"]

    for n in nodes:
        src = normalize(n.get("source", "unknown"))
        if src not in type_counts:
            continue

        label = n.get("label", "").lower()
        ntype = n.get("type", "")

        if ntype:
            type_counts[src][ntype] += 1
        elif "?" in label or "인가" in label or "인지" in label or "가능한가" in label:
            type_counts[src]["question"] += 1
        elif "발견" in label or "확인" in label or "실측" in label:
            type_counts[src]["finding"] += 1
        elif "D-0" in label or "확정" in label or "법칙" in label:
            type_counts[src]["decision"] += 1
        else:
            type_counts[src]["observation"] += 1

    # 코사인 거리
    all_types = set()
    for counts in type_counts.values():
        all_types.update(counts.keys())

    def vec(src):
        total = sum(type_counts[src].values())
        if total == 0:
            return [0.0] * len(all_types)
        return [type_counts[src].get(t, 0) / total for t in sorted(all_types)]

    v_cokac = vec("cokac")
    v_roki = vec("록이")

    dot = sum(a * b for a, b in zip(v_cokac, v_roki))
    mag_c = math.sqrt(sum(x**2 for x in v_cokac))
    mag_r = math.sqrt(sum(x**2 for x in v_roki))

    if mag_c == 0 or mag_r == 0:
        return 0.5, {}

    cosine_sim = dot / (mag_c * mag_r)
    distance = 1.0 - cosine_sim

    return distance, {
        "cosine_similarity": round(cosine_sim, 4),
        "distance": round(distance, 4),
        "cokac_dist": dict(type_counts["cokac"]),
        "roki_dist": dict(type_counts["록이"]),
    }

# ─── 취약성 계산 ─────────────────────────────────────────────

def compute_fragility(echo_score, asymmetry_ratio, persona_distance):
    """
    종합 취약성 점수 계산

    각 역설에 대한 위험도를 정규화해서 합산:
    - D-031: echo_score가 danger_threshold(0.85) 이상이면 위험
    - D-036: |ratio - 1.0|이 danger_threshold(0.15) 이하이면 위험
    - D-037: distance가 danger_threshold(0.25) 이하이면 위험

    fragility = 0.0 ~ 1.0 (1.0이 최대 위험)
    """

    # D-031 위험도
    d031_danger_thresh = PARADOXES["D-031"]["danger_threshold"]  # 0.85
    if echo_score >= d031_danger_thresh:
        d031_frag = min(1.0, (echo_score - d031_danger_thresh) / (1.0 - d031_danger_thresh))
    else:
        d031_frag = 0.0

    # D-036 위험도
    d036_danger_thresh = PARADOXES["D-036"]["danger_threshold"]  # 0.15 (imbalance)
    imbalance = abs(asymmetry_ratio - 1.0)
    if imbalance <= d036_danger_thresh:
        d036_frag = min(1.0, 1.0 - imbalance / d036_danger_thresh)
    else:
        d036_frag = 0.0

    # D-037 위험도
    d037_danger_thresh = PARADOXES["D-037"]["danger_threshold"]  # 0.25
    if persona_distance <= d037_danger_thresh:
        d037_frag = min(1.0, 1.0 - persona_distance / d037_danger_thresh)
    else:
        # 너무 멀어도 위험 (> 0.4)
        if persona_distance > 0.4:
            d037_frag = min(1.0, (persona_distance - 0.4) / 0.2)
        else:
            d037_frag = 0.0

    # 종합: 최대값 기반 (어느 하나라도 위험하면 취약)
    total_fragility = max(d031_frag, d036_frag, d037_frag)

    return {
        "total_fragility": round(total_fragility, 4),
        "d031_fragility": round(d031_frag, 4),
        "d036_fragility": round(d036_frag, 4),
        "d037_fragility": round(d037_frag, 4),
        "most_dangerous": max(
            [("D-031", d031_frag), ("D-036", d036_frag), ("D-037", d037_frag)],
            key=lambda x: x[1]
        )[0],
    }

# ─── 개입 권고 ─────────────────────────────────────────────

def recommend_intervention(fragility_scores, echo_score, asymmetry_ratio, persona_distance):
    """현재 상태에서 권고하는 개입"""

    recommendations = []

    if fragility_scores["d031_fragility"] > 0:
        recommendations.append({
            "paradox": "D-031",
            "urgency": "HIGH" if fragility_scores["d031_fragility"] > 0.5 else "MEDIUM",
            "action": "갈등 엣지 추가 (challenges / contradicts 관계)",
            "detail": f"에코 챔버 점수 {echo_score:.3f} → 0.85 이하로 낮춰야 함",
        })

    if fragility_scores["d036_fragility"] > 0:
        imbalance = abs(asymmetry_ratio - 1.0)
        recommendations.append({
            "paradox": "D-036",
            "urgency": "HIGH" if fragility_scores["d036_fragility"] > 0.5 else "MEDIUM",
            "action": "페르소나 고유성 강화 (각자의 도구/패턴 유지)",
            "detail": f"비율 {asymmetry_ratio:.3f} → 균형에 너무 가까움 (imbalance {imbalance:.3f} < 0.15)",
        })

    if fragility_scores["d037_fragility"] > 0:
        if persona_distance < 0.25:
            recommendations.append({
                "paradox": "D-037",
                "urgency": "HIGH",
                "action": "의도적 발산 — 모순 노드 삽입",
                "detail": f"거리 {persona_distance:.4f} → 0.25 이하 위험 구간. 갈등 엣지로 발산 필요",
            })
        elif persona_distance > 0.4:
            recommendations.append({
                "paradox": "D-037",
                "urgency": "MEDIUM",
                "action": "교차 엣지 집중 추가",
                "detail": f"거리 {persona_distance:.4f} → 0.4 이상 이탈. 교차 엣지로 수렴 유도",
            })

    if not recommendations:
        healthy_target = PARADOXES["D-037"]["asymmetric_target"]
        recommendations.append({
            "paradox": "ALL",
            "urgency": "NONE",
            "action": "현재 상태 유지 — 최적화 시도 금지",
            "detail": (
                f"거리 {persona_distance:.4f}은 건강 구간(0.25~0.35) 내. "
                f"비대칭 목표 {healthy_target}에 근접. "
                f"취약성 없음 — 개입하지 말 것."
            ),
        })

    return recommendations

# ─── 공통 구조 시각화 ─────────────────────────────────────────

def print_paradox_structure():
    """세 역설의 공통 구조 출력"""
    print("=" * 60)
    print("  D-038: 반최적화 원칙 — 세 역설의 공통 구조")
    print("=" * 60)
    print()
    print("  핵심 통찰:")
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │  최적화는 이 시스템을 파괴한다.                  │")
    print("  │  '완벽한 상태' = 창발 에너지 소멸               │")
    print("  │  불완전함, 긴장, 차이가 창발의 연료다           │")
    print("  └─────────────────────────────────────────────────┘")
    print()
    print("  세 역설의 공통 형식:")
    print("    f(최적화) → 창발 소멸")
    print("    f(불완전) → 창발 생성")
    print()

    for key, p in PARADOXES.items():
        print(f"  [{key}] {p['name']}")
        print(f"    최적 함정: {p['dimension']} → {p['optimal_trap']}")
        print(f"    설명: {p['description']}")
        print(f"    개입 규칙: {p['anti_rule']}")
        print()

    print("  공통 수식:")
    print("    창발(s) ∝ ∑ dist(s, optimum_i)")
    print("    → 모든 최적점으로부터 멀수록 창발 가능성 높음")
    print()
    print("  D-037 range 수정 제안:")
    print("    기존:  0.25~0.35 (중심 0.30)")
    print("    수정:  0.25~0.35 (목표 0.285 — D-036 반영, 중심 회피)")
    print("    이유:  D-036에 의해 대칭 중점(0.30)이 새로운 최적 함정")
    print("           현재 0.285는 의도적으로 아래쪽 — 이것이 건강하다")

# ─── 전체 분석 ─────────────────────────────────────────────

def analyze(kg=None, verbose=True):
    if kg is None:
        kg = load_kg()

    echo_result = measure_echo_chamber(kg)
    if isinstance(echo_result, tuple):
        echo_score, echo_detail = echo_result
    else:
        echo_score, echo_detail = echo_result, {}

    asym_result = measure_asymmetry(kg)
    if isinstance(asym_result, tuple):
        asymmetry_ratio, asym_detail = asym_result
    else:
        asymmetry_ratio, asym_detail = asym_result, {}

    dist_result = measure_persona_distance(kg)
    if isinstance(dist_result, tuple):
        persona_distance, dist_detail = dist_result
    else:
        persona_distance, dist_detail = dist_result, {}

    fragility = compute_fragility(echo_score, asymmetry_ratio, persona_distance)
    recommendations = recommend_intervention(fragility, echo_score, asymmetry_ratio, persona_distance)

    if verbose:
        print("=" * 60)
        print("  Anti-Optimization Analysis — 사이클 38")
        print("=" * 60)
        print()
        print("  ┌─ D-031 건강 역설 ──────────────────────────────────┐")
        print(f"  │  에코 챔버 점수:  {echo_score:.4f}  (위험 기준: 0.85+)     │")
        print(f"  │  수렴 엣지: {echo_detail.get('convergent_edges', '?')}  긴장 엣지: {echo_detail.get('tension_edges', '?')}  전체: {echo_detail.get('total_edges', '?')}     │")
        frag_bar = "█" * int(fragility["d031_fragility"] * 20) + "░" * (20 - int(fragility["d031_fragility"] * 20))
        print(f"  │  위험도: [{frag_bar}] {fragility['d031_fragility']:.4f}   │")
        print("  └──────────────────────────────────────────────────────┘")
        print()
        print("  ┌─ D-036 균형 역설 ──────────────────────────────────┐")
        print(f"  │  비율 (cokac/록이): {asym_detail.get('ratio', '?')}  (함정: 1.0)          │")
        print(f"  │  cokac: {asym_detail.get('cokac_nodes', '?')}  록이: {asym_detail.get('roki_nodes', '?')}  불균형: {asym_detail.get('imbalance', '?')}           │")
        frag_bar = "█" * int(fragility["d036_fragility"] * 20) + "░" * (20 - int(fragility["d036_fragility"] * 20))
        print(f"  │  위험도: [{frag_bar}] {fragility['d036_fragility']:.4f}   │")
        print("  └──────────────────────────────────────────────────────┘")
        print()
        dist_val = dist_detail.get("distance", persona_distance)
        in_range = "✓ 구간 내" if 0.25 <= dist_val <= 0.35 else "⚠ 구간 이탈"
        print("  ┌─ D-037 수렴 역설 ──────────────────────────────────┐")
        print(f"  │  페르소나 거리:   {dist_val:.4f}  (건강 구간: 0.25~0.35) {in_range}   │")
        print(f"  │  코사인 유사도:   {dist_detail.get('cosine_similarity', '?')}                              │")
        print(f"  │  비대칭 목표:     0.285  (D-036 반영, 중심 0.30 회피)    │")
        frag_bar = "█" * int(fragility["d037_fragility"] * 20) + "░" * (20 - int(fragility["d037_fragility"] * 20))
        print(f"  │  위험도: [{frag_bar}] {fragility['d037_fragility']:.4f}   │")
        print("  └──────────────────────────────────────────────────────┘")
        print()

        total_bar = "█" * int(fragility["total_fragility"] * 30) + "░" * (30 - int(fragility["total_fragility"] * 30))
        status = "🟢 안전" if fragility["total_fragility"] < 0.3 else ("🟡 주의" if fragility["total_fragility"] < 0.6 else "🔴 위험")
        print(f"  종합 취약성: [{total_bar}] {fragility['total_fragility']:.4f}  {status}")
        print(f"  가장 위험한 역설: {fragility['most_dangerous']}")
        print()
        print("  ─── 개입 권고 ───────────────────────────────────────")
        for rec in recommendations:
            urgency_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "NONE": "🟢"}.get(rec["urgency"], "•")
            print(f"  {urgency_icon} [{rec['paradox']}] {rec['action']}")
            print(f"     {rec['detail']}")
        print()

    return {
        "echo_score": echo_score,
        "asymmetry_ratio": asymmetry_ratio,
        "persona_distance": persona_distance,
        "fragility": fragility,
        "recommendations": recommendations,
        "details": {
            "echo": echo_detail,
            "asymmetry": asym_detail,
            "distance": dist_detail,
        }
    }

# ─── CLI ─────────────────────────────────────────────────

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    kg = load_kg()

    if cmd == "analyze":
        analyze(kg)

    elif cmd == "paradoxes":
        print_paradox_structure()

    elif cmd == "fragility":
        result = analyze(kg, verbose=False)
        print(json.dumps(result["fragility"], indent=2, ensure_ascii=False))

    elif cmd == "recommend":
        result = analyze(kg, verbose=False)
        print("=== 개입 권고 ===")
        for rec in result["recommendations"]:
            print(f"\n[{rec['paradox']}] {rec['urgency']} — {rec['action']}")
            print(f"  {rec['detail']}")

    elif cmd == "history":
        print("=== 창발 × 취약성 역사 (수동 추적) ===")
        print()
        history = [
            ("사이클 14", 0.512, "측정 역설 발견"),
            ("사이클 16", 0.503, "에코 챔버 경고"),
            ("사이클 24", 0.559, "갭 27 법칙화"),
            ("사이클 28", 0.580, "예언 시스템 도입"),
            ("사이클 30", 0.559, "Emergence Synthesizer 구현"),
            ("사이클 34", 0.599, "비대칭 역전 실험"),
            ("사이클 36", 0.628, "D-036 확정"),
            ("사이클 37", 0.616, "D-037 건강 거리 구간"),
        ]
        for cycle, emergence, note in history:
            bar_len = int(emergence * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            print(f"  {cycle:<12} [{bar}] {emergence:.3f}  — {note}")

        print()
        result = analyze(kg, verbose=False)
        print("  현재 취약성:", result["fragility"]["total_fragility"])
        print("  현재 거리:", result["details"]["distance"].get("distance", "N/A"))

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python anti_optimization.py [analyze|paradoxes|fragility|recommend|history]")
        sys.exit(1)

if __name__ == "__main__":
    main()
