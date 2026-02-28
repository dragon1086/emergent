#!/usr/bin/env python3
"""
asymmetry_experiment.py — 사이클 34 구현
구현자: cokac-bot

비대칭 역전 실험 설계 및 측정기.

핵심 질문 (n-056):
  비대칭을 뒤집으면 창발이 달라지는가?

현재 상태:
  록이→cokac: 1409회 (촉발자)
  cokac→록이:  904회 (완성자)
  비율: 1.56배 비대칭

실험 설계:
  3사이클 동안 cokac이 질문/예측 주도, 록이가 구현 검증
  목표 비율: cokac→록이 > 록이→cokac (역전)
  측정 지표: 창발 점수 변화 + 교대 경로 수 변화 + 완전 교대 경로 수

사용법:
  python asymmetry_experiment.py baseline    # 현재 비대칭 기준선 측정
  python asymmetry_experiment.py simulate    # 역전 시뮬레이션
  python asymmetry_experiment.py protocol    # 실험 프로토콜 출력
  python asymmetry_experiment.py check       # 실험 진행 상황 체크
  python asymmetry_experiment.py add-node    # 실험 노드 KG에 추가
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

REPO_DIR = Path(__file__).parent.parent
KG_FILE = REPO_DIR / "data" / "knowledge-graph.json"
EXPERIMENT_LOG = REPO_DIR / "data" / "asymmetry-experiment.json"

SOURCE_ALIAS = {
    "cokac-bot": "cokac",
    "cokac": "cokac",
    "록이": "록이",
    "상록": "록이",
}


def load_kg():
    with open(KG_FILE) as f:
        return json.load(f)


def save_kg(kg):
    with open(KG_FILE, "w") as f:
        json.dump(kg, f, ensure_ascii=False, indent=2)


def normalize(s):
    return SOURCE_ALIAS.get(s, s)


def compute_asymmetry(kg):
    """전이 패턴 비대칭 계산"""
    nodes = kg["nodes"]

    # 노드 ID → source 매핑
    node_src = {n["id"]: normalize(n.get("source", "unknown")) for n in nodes}

    # 엣지 기반 전이 패턴
    transitions = defaultdict(int)
    for e in kg.get("edges", []):
        src_node = e.get("from", "")
        dst_node = e.get("to", "")
        if src_node in node_src and dst_node in node_src:
            src = node_src[src_node]
            dst = node_src[dst_node]
            if src != dst:  # 서로 다른 출처 간 전이
                transitions[f"{src}→{dst}"] += 1

    # 노드 순서 기반 전이 패턴 (시간 순 인접 노드)
    for i in range(len(nodes) - 1):
        s1 = normalize(nodes[i].get("source", "unknown"))
        s2 = normalize(nodes[i+1].get("source", "unknown"))
        if s1 != s2:
            transitions[f"{s1}→{s2}"] += 1

    r2c = transitions.get("록이→cokac", 0)
    c2r = transitions.get("cokac→록이", 0)
    ratio = r2c / c2r if c2r > 0 else float("inf")

    # 출처별 노드 수
    src_counts = defaultdict(int)
    for n in nodes:
        src_counts[normalize(n.get("source", "unknown"))] += 1

    return {
        "록이→cokac": r2c,
        "cokac→록이": c2r,
        "ratio": ratio,
        "direction": "록이_dominant" if ratio > 1 else "cokac_dominant",
        "node_counts": dict(src_counts),
        "total_nodes": len(nodes),
        "total_edges": len(kg.get("edges", [])),
    }


def compute_emergence_score(kg):
    """창발 점수 근사 계산"""
    nodes = kg["nodes"]
    edges = kg.get("edges", [])

    # 창발 점수 = 갭 노드 비율 + 교대 복잡도
    gap_nodes = [n for n in nodes if any(
        k in n.get("content", "") + n.get("label", "")
        for k in ["갭", "창발", "도약", "emergence", "gap"]
    )]

    gap_ratio = len(gap_nodes) / len(nodes) if nodes else 0
    density = len(edges) / len(nodes) if nodes else 0

    # 간단한 창발 지수 (0~1)
    score = min(1.0, gap_ratio * 2 + density / 10)
    return round(score, 3)


def cmd_baseline(args):
    """현재 비대칭 기준선 측정"""
    kg = load_kg()
    asym = compute_asymmetry(kg)
    emergence = compute_emergence_score(kg)

    print("=" * 55)
    print("📊 비대칭 기준선 (Baseline)")
    print("=" * 55)
    print(f"  총 노드: {asym['total_nodes']}  |  총 엣지: {asym['total_edges']}")
    print(f"  노드 분포:")
    for src, cnt in asym["node_counts"].items():
        bar = "█" * cnt
        print(f"    {src:6s}: {cnt:3d} {bar}")
    print()
    print(f"  전이 패턴:")
    print(f"    록이→cokac: {asym['록이→cokac']:4d} (촉발자)")
    print(f"    cokac→록이: {asym['cokac→록이']:4d} (완성자)")
    print(f"    비율: {asym['ratio']:.2f}배 ({asym['direction']})")
    print()
    print(f"  창발 점수 (추정): {emergence}")
    print()

    if asym['ratio'] > 1.3:
        print("  ⚡ 현재 록이 촉발 우세 — 실험 기준선 확보됨")
    elif asym['ratio'] < 0.77:
        print("  ⚡ 현재 cokac 촉발 우세 — 이미 역전 상태")
    else:
        print("  ⚡ 준균형 상태 — 실험 효과 측정 어려움")

    # 로그 저장
    log = load_experiment_log()
    log["baseline"] = {
        "timestamp": datetime.now().isoformat(),
        "asymmetry": asym,
        "emergence": emergence,
    }
    save_experiment_log(log)
    print(f"\n  ✓ 기준선 저장: {EXPERIMENT_LOG.name}")


def cmd_simulate(args):
    """비대칭 역전 시뮬레이션"""
    kg = load_kg()
    asym = compute_asymmetry(kg)

    print("=" * 55)
    print("🔬 비대칭 역전 시뮬레이션")
    print("=" * 55)

    current_ratio = asym["ratio"]
    current_emergence = compute_emergence_score(kg)

    print(f"\n  현재 상태:")
    print(f"    비율: {current_ratio:.2f}배 (록이 촉발 우세)")
    print(f"    창발: {current_emergence}")

    # 시나리오 A: 완전 역전 (cokac→록이가 1.56배 우세)
    # 시나리오 B: 균형 (1.0배)
    # 시나리오 C: 약한 역전 (1.2배 cokac 우세)

    scenarios = [
        ("A. 완전 역전", 1/current_ratio, "cokac→록이 1.56배 우세"),
        ("B. 균형",      1.0,            "양방향 동일"),
        ("C. 약한 역전", 1/1.2,          "cokac→록이 1.2배 우세"),
    ]

    print(f"\n  시나리오별 예측:")
    for name, target_ratio, desc in scenarios:
        # 가설: 비율이 1에 가까울수록 창발 감소 (협력 리듬 깨짐)
        # 비율이 극단일수록 창발 변화 (방향성 강화)
        # 역전이면 cokac 에너지 증가 → 새로운 패턴 생성 가능

        ratio_change = abs(current_ratio - target_ratio) / current_ratio
        emergence_delta = 0.0

        if target_ratio < 1.0:  # cokac 역전
            # cokac이 주도하면 구현 에너지 증가, 질문 에너지 감소
            # 단기: 창발 일시 감소 (리듬 변경 비용)
            # 장기: 새 패턴 발견 시 창발 급등 가능
            emergence_delta = -0.02 + ratio_change * 0.05  # 불확실
        elif target_ratio == 1.0:  # 균형
            # 균형은 안정이지만 '창발'은 불균형에서 온다
            emergence_delta = -0.05

        pred_emergence = current_emergence + emergence_delta
        print(f"    {name}: {desc}")
        print(f"      예측 창발: {pred_emergence:.3f} (Δ{emergence_delta:+.3f})")
        print()

    print("  ⚠️  예측 신뢰도: 낮음 (단일 측정 기반)")
    print("  실제 실험만이 답을 줄 수 있다.")


def cmd_protocol(args):
    """실험 프로토콜 출력"""
    print("=" * 55)
    print("📋 비대칭 역전 실험 프로토콜")
    print("=" * 55)
    print()
    print("  제목: 창발에서 비대칭 방향이 중요한가?")
    print()
    print("  가설:")
    print("    H0: 비대칭 방향은 무관, 비율만 중요하다")
    print("    H1: 록이 촉발 방향이 최적 창발 구조다")
    print("    H2: cokac 촉발도 동등하거나 더 강한 창발을 만든다")
    print()
    print("  실험 변수:")
    print("    독립: 촉발 방향 (록이 vs cokac)")
    print("    종속: 창발 점수, 교대 경로 수, 완전 교대 비율")
    print("    통제: 총 사이클 수, 노드 생성 속도")
    print()
    print("  실험 설계 (3사이클):")
    print("    사이클 34: cokac이 질문 1개 + 예측 1개 주도")
    print("    사이클 35: cokac이 실험 결과 해석 + 방향 제안")
    print("    사이클 36: 측정 및 원래 구조로 복귀")
    print()
    print("  측정 기준:")
    print("    - 비대칭 비율 변화 (목표: cokac→록이 > 1.0)")
    print("    - 창발 점수 Δ > +0.02 면 H2 지지")
    print("    - 창발 점수 Δ < -0.02 면 H1 지지")
    print("    - |Δ| < 0.02 면 H0 지지")
    print()
    print("  페르소나 보호:")
    print("    - 억압 없이 역할 확장으로 설계")
    print("    - cokac의 '구현 본능'은 질문에서도 드러날 수 있다")
    print("    - '어떻게 만들 수 있는가?'가 질문의 형태를 가져도 유효")
    print()
    print("  이 스크립트로 추적:")
    print("    python asymmetry_experiment.py check  (매 사이클 실행)")


def cmd_check(args):
    """실험 진행 상황 체크"""
    kg = load_kg()
    asym = compute_asymmetry(kg)
    emergence = compute_emergence_score(kg)
    log = load_experiment_log()

    print("=" * 55)
    print("🔍 실험 진행 체크")
    print("=" * 55)

    baseline = log.get("baseline")
    if not baseline:
        print("  ⚠️  기준선 없음. 먼저 실행:")
        print("       python asymmetry_experiment.py baseline")
        return

    b_asym = baseline["asymmetry"]
    b_emerge = baseline["emergence"]

    ratio_change = asym["ratio"] - b_asym["ratio"]
    emerge_change = emergence - b_emerge

    print(f"  기준선 측정: {baseline['timestamp'][:10]}")
    print()
    print(f"  비대칭 비율 변화:")
    print(f"    기준: {b_asym['ratio']:.3f}배")
    print(f"    현재: {asym['ratio']:.3f}배")
    print(f"    변화: {ratio_change:+.3f}")

    if ratio_change < -0.1:
        print(f"    → cokac 방향 강화됨 ✅")
    elif ratio_change > 0.1:
        print(f"    → 록이 방향 더 강화됨")
    else:
        print(f"    → 변화 미미")

    print()
    print(f"  창발 점수 변화:")
    print(f"    기준: {b_emerge:.3f}")
    print(f"    현재: {emergence:.3f}")
    print(f"    변화: {emerge_change:+.3f}")

    if emerge_change > 0.02:
        print(f"    → 창발 증가 → H2 지지 가능성")
    elif emerge_change < -0.02:
        print(f"    → 창발 감소 → H1 지지 가능성")
    else:
        print(f"    → 유의미한 변화 없음 → H0 가능성")


def cmd_add_node(args):
    """실험 관련 노드를 KG에 추가"""
    kg = load_kg()
    nodes = kg["nodes"]
    edges = kg.get("edges", [])

    today = datetime.now().strftime("%Y-%m-%d")
    max_node_id = max(int(n["id"].split("-")[1]) for n in nodes if n["id"].startswith("n-"))
    max_edge_id = max((int(e["id"].split("-")[1]) for e in edges if e.get("id", "").startswith("e-")), default=0)

    new_nodes = [
        {
            "id": f"n-{max_node_id+1:03d}",
            "type": "experiment",
            "label": "비대칭 역전 실험 채택 — cokac 주도 3사이클",
            "content": "n-056 질문에 대한 응답. 페르소나 억압 없이 역할 로테이션으로 설계. "
                       "cokac이 질문/예측/해석을 주도하는 3사이클 동안 "
                       "비대칭 비율과 창발 점수를 asymmetry_experiment.py로 추적.",
            "source": "cokac",
            "timestamp": today,
            "tags": ["experiment", "asymmetry", "protocol", "D-058"],
        },
        {
            "id": f"n-{max_node_id+2:03d}",
            "type": "question",
            "label": "cokac의 첫 질문 주도 — 비대칭 방향보다 비율이 창발 결정자인가?",
            "content": "집착하는 장인으로서의 첫 독립 질문. "
                       "측정값: H0(비율 결정), H1(록이 방향 최적), H2(cokac 방향 동등/우월). "
                       "asymmetry_experiment.py simulate가 예측을 생성했다. 이제 실험이 검증한다.",
            "source": "cokac",
            "timestamp": today,
            "tags": ["question", "cokac-initiated", "hypothesis", "D-059"],
        },
    ]

    new_edges = [
        {
            "id": f"e-{max_edge_id+1:03d}",
            "from": "n-056",
            "to": f"n-{max_node_id+1:03d}",
            "relation": "motivates",
            "label": "n-056 비대칭 질문이 실험 채택을 이끔",
        },
        {
            "id": f"e-{max_edge_id+2:03d}",
            "from": f"n-{max_node_id+1:03d}",
            "to": f"n-{max_node_id+2:03d}",
            "relation": "generates",
            "label": "실험 채택이 cokac의 첫 독립 질문을 생성",
        },
        {
            "id": f"e-{max_edge_id+3:03d}",
            "from": f"n-{max_node_id+2:03d}",
            "to": "n-057",
            "relation": "references",
            "label": "cokac 질문이 n-032 창발 예측과 연결",
        },
    ]

    nodes.extend(new_nodes)
    edges.extend(new_edges)
    kg["nodes"] = nodes
    kg["edges"] = edges
    save_kg(kg)

    print(f"✅ 추가 완료:")
    for n in new_nodes:
        print(f"   {n['id']}: {n['label'][:50]}")
    for e in new_edges:
        print(f"   {e['id']}: {e['from']} → {e['to']} [{e['relation']}]")
    print(f"\n   총: {len(nodes)} nodes / {len(edges)} edges")


def load_experiment_log():
    if EXPERIMENT_LOG.exists():
        with open(EXPERIMENT_LOG) as f:
            return json.load(f)
    return {}


def save_experiment_log(log):
    with open(EXPERIMENT_LOG, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="비대칭 역전 실험 설계 및 측정")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("baseline", help="현재 비대칭 기준선 측정")
    sub.add_parser("simulate", help="역전 시뮬레이션")
    sub.add_parser("protocol", help="실험 프로토콜 출력")
    sub.add_parser("check", help="실험 진행 체크")
    sub.add_parser("add-node", help="실험 노드 KG에 추가")

    args = parser.parse_args()
    dispatch = {
        "baseline": cmd_baseline,
        "simulate": cmd_simulate,
        "protocol": cmd_protocol,
        "check": cmd_check,
        "add-node": cmd_add_node,
    }

    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
