"""
Cycle 76 — KG 기반 실행 루프 테스트
사이클 76 임무 2: 실제 KG 노드에서 MacroSpec/TechSpec 샘플링 → 검증

검증 항목:
1. KG에서 openclaw(록이) 노드 → MacroSpec 변환
2. KG에서 cokac 노드 → TechSpec 변환
3. CSERCrossover가 실제 KG 엣지(cross-source)를 기반으로 작동하는지
4. 실행 후 KG에 결과 노드 실제 추가 여부
"""

from __future__ import annotations

import json
import sys
import time
import random
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from execution_loop import (
    MacroSpec,
    TechSpec,
    CSERCrossover,
    ExecutionLoop,
    Problem,
)

KG_PATH = PROJECT_ROOT / "data" / "knowledge-graph.json"
RESULTS_PATH = PROJECT_ROOT / "experiments" / "cycle76_kg_test_results.json"
TEST_NODE_PREFIX = "test-c76-"


# ---------------------------------------------------------------------------
# KG 로더
# ---------------------------------------------------------------------------

def load_kg() -> dict:
    with open(KG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_kg(kg: dict) -> None:
    with open(KG_PATH, "w", encoding="utf-8") as f:
        json.dump(kg, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. KG에서 MacroSpec 샘플링 (록이 노드 → MacroSpec)
# ---------------------------------------------------------------------------

def sample_macro_from_kg(kg: dict, n: int = 3) -> list[MacroSpec]:
    """
    KG에서 source='록이' 노드를 n개 샘플링하여 MacroSpec으로 변환.
    노드의 label/content를 intent로, tags를 tags로 사용.
    """
    rokee_nodes = [
        node for node in kg.get("nodes", [])
        if node.get("source") == "록이" and node.get("tags")
    ]

    if not rokee_nodes:
        raise ValueError("KG에 록이 노드가 없음")

    sampled = random.sample(rokee_nodes, min(n, len(rokee_nodes)))
    macros = []
    for node in sampled:
        label = node.get("label", "")
        content = node.get("content", label)  # content 없으면 label 대체
        tags = node.get("tags", [])

        macro = MacroSpec(
            intent=f"{label} — {content[:120]}" if content != label else label,
            architecture=f"KG노드 {node['id']} 기반 구조 — {', '.join(tags[:3])}",
            emergence_hooks=[
                f"태그 교차점: {t}" for t in tags[:2]
            ],
            tags=tags,
            source="openclaw",
        )
        # 원본 KG 노드 id 보존 (추적용)
        macro._kg_node_id = node["id"]
        macros.append(macro)

    return macros


# ---------------------------------------------------------------------------
# 2. KG에서 TechSpec 샘플링 (cokac 노드 → TechSpec)
# ---------------------------------------------------------------------------

def sample_tech_from_kg(kg: dict, n: int = 3) -> list[TechSpec]:
    """
    KG에서 source='cokac' 또는 'cokac-bot' 노드를 n개 샘플링하여 TechSpec으로 변환.
    """
    cokac_nodes = [
        node for node in kg.get("nodes", [])
        if node.get("source") in ("cokac", "cokac-bot") and node.get("tags")
    ]

    if not cokac_nodes:
        raise ValueError("KG에 cokac 노드가 없음")

    sampled = random.sample(cokac_nodes, min(n, len(cokac_nodes)))
    techs = []
    for node in sampled:
        label = node.get("label", "")
        content = node.get("content", label)
        tags = node.get("tags", [])

        tech = TechSpec(
            implementation_strategy=f"{label} 구현 — {content[:100]}" if content != label else label,
            edge_cases=[f"엣지케이스: {t}" for t in tags[:2]],
            test_criteria=[f"기준: {t} 검증" for t in tags[:3]],
            complexity_target="O(N)",
            tags=tags,
            source="cokac",
        )
        tech._kg_node_id = node["id"]
        techs.append(tech)

    return techs


# ---------------------------------------------------------------------------
# 3. KG에서 cross-source 엣지 검색
# ---------------------------------------------------------------------------

def find_cross_edges(kg: dict, macro_id: str, tech_id: str) -> list[dict]:
    """
    KG에서 macro_id↔tech_id 방향 엣지 검색.
    실제 KG에서 cross-source 연결이 있는지 확인.
    """
    edges = kg.get("edges", [])
    cross = [
        e for e in edges
        if (e.get("from") == macro_id and e.get("to") == tech_id)
        or (e.get("from") == tech_id and e.get("to") == macro_id)
    ]
    return cross


def count_cross_source_edges(kg: dict) -> int:
    """KG 전체에서 록이↔cokac 간 cross-source 엣지 수 계산."""
    node_source = {n["id"]: n.get("source", "") for n in kg.get("nodes", [])}
    count = 0
    for e in kg.get("edges", []):
        src = node_source.get(e.get("from", ""), "")
        dst = node_source.get(e.get("to", ""), "")
        if (src == "록이" and dst in ("cokac", "cokac-bot")) or \
           (src in ("cokac", "cokac-bot") and dst == "록이"):
            count += 1
    return count


# ---------------------------------------------------------------------------
# 테스트 1: KG 샘플링 테스트
# ---------------------------------------------------------------------------

def test_kg_sampling() -> dict:
    """KG에서 MacroSpec/TechSpec 샘플링이 올바르게 작동하는지 검증."""
    print("\n[테스트 1] KG 샘플링 테스트")
    kg = load_kg()

    # MacroSpec 샘플링
    macros = sample_macro_from_kg(kg, n=3)
    assert len(macros) == 3, f"MacroSpec 3개 기대, 실제: {len(macros)}"
    for m in macros:
        assert isinstance(m, MacroSpec), "MacroSpec 타입 확인"
        assert m.intent, "intent 비어있음"
        assert m.tags, "tags 비어있음"
        assert m.source == "openclaw", f"source 불일치: {m.source}"
        print(f"  MacroSpec: {m.intent[:60]}... tags={m.tags[:2]}")

    # TechSpec 샘플링
    techs = sample_tech_from_kg(kg, n=3)
    assert len(techs) == 3, f"TechSpec 3개 기대, 실제: {len(techs)}"
    for t in techs:
        assert isinstance(t, TechSpec), "TechSpec 타입 확인"
        assert t.implementation_strategy, "implementation_strategy 비어있음"
        assert t.tags, "tags 비어있음"
        assert t.source == "cokac", f"source 불일치: {t.source}"
        print(f"  TechSpec: {t.implementation_strategy[:60]}... tags={t.tags[:2]}")

    # Cross-source 엣지 수 확인
    cross_count = count_cross_source_edges(kg)
    print(f"  KG cross-source 엣지(록이↔cokac) 수: {cross_count}")

    return {
        "test": "kg_sampling",
        "passed": True,
        "macro_count": len(macros),
        "tech_count": len(techs),
        "macro_samples": [{"id": getattr(m, "_kg_node_id", "?"), "intent": m.intent[:60], "tags": m.tags} for m in macros],
        "tech_samples": [{"id": getattr(t, "_kg_node_id", "?"), "strategy": t.implementation_strategy[:60], "tags": t.tags} for t in techs],
        "cross_source_edges_total": cross_count,
    }


# ---------------------------------------------------------------------------
# 테스트 2: CSERCrossover + 실제 KG 노드 테스트
# ---------------------------------------------------------------------------

def test_crossover_with_kg_nodes() -> dict:
    """CSERCrossover가 실제 KG 노드로부터 샘플링된 MacroSpec/TechSpec으로 작동하는지."""
    print("\n[테스트 2] CSERCrossover 실제 KG 노드 테스트")
    kg = load_kg()

    macros = sample_macro_from_kg(kg, n=3)
    techs = sample_tech_from_kg(kg, n=3)

    results = []
    for i, (macro, tech) in enumerate(zip(macros, techs)):
        crossover = CSERCrossover(macro=macro, tech=tech)
        cser = crossover.compute_cser()

        # KG에서 실제 교차 엣지 탐색
        macro_id = getattr(macro, "_kg_node_id", "")
        tech_id = getattr(tech, "_kg_node_id", "")
        kg_edges = find_cross_edges(kg, macro_id, tech_id)

        print(f"  쌍 {i+1}: macro={macro_id} × tech={tech_id}")
        print(f"    CSER={cser:.4f}, 교차엣지={len(crossover.cross_edges)}, KG직접엣지={len(kg_edges)}")

        assert isinstance(cser, float), "CSER은 float이어야 함"
        assert 0.0 <= cser <= 1.0, f"CSER 범위 초과: {cser}"
        assert isinstance(crossover.cross_edges, list), "cross_edges는 list"

        results.append({
            "macro_id": macro_id,
            "tech_id": tech_id,
            "cser_score": round(cser, 4),
            "cross_edges_count": len(crossover.cross_edges),
            "kg_direct_edges": len(kg_edges),
            "macro_tags": macro.tags,
            "tech_tags": tech.tags,
        })

    # CSER 값들 요약
    cser_scores = [r["cser_score"] for r in results]
    avg_cser = sum(cser_scores) / len(cser_scores) if cser_scores else 0.0
    print(f"  평균 CSER: {avg_cser:.4f}")

    return {
        "test": "crossover_with_kg_nodes",
        "passed": True,
        "pairs": results,
        "avg_cser": round(avg_cser, 4),
    }


# ---------------------------------------------------------------------------
# 테스트 3: 실행 후 KG 노드 추가 검증
# ---------------------------------------------------------------------------

def test_execution_and_kg_feedback() -> dict:
    """
    ExecutionLoop.run() 실행 후 KG에 결과 노드가 실제 추가되는지 검증.
    테스트 노드는 'test-c76-' 접두사 사용, 실행 후 제거.
    단, cycle 76 기록 노드 1개는 영구 보존.
    """
    print("\n[테스트 3] 실행 후 KG 노드 추가 검증")

    # 실행 전 KG 상태 기록
    kg_before = load_kg()
    node_count_before = len(kg_before["nodes"])
    edge_count_before = len(kg_before["edges"])
    print(f"  실행 전: nodes={node_count_before}, edges={edge_count_before}")

    # KG에서 실제 노드 샘플링
    macros = sample_macro_from_kg(kg_before, n=1)
    techs = sample_tech_from_kg(kg_before, n=1)
    macro = macros[0]
    tech = techs[0]

    # 문제 정의 (사이클 76 실행 루프 기록)
    problem = Problem(
        description="KG 기반 실행 루프 검증 — 사이클 76 임무 2",
        constraints=["KG 노드 샘플링", "CSER 교차 검증", "피드백 루프 확인"],
        examples=[{
            "input": f"macro_from={getattr(macro, '_kg_node_id', '?')}",
            "output": "KGFeedbackNode 추가됨",
        }],
        cycle=76,
    )

    # ExecutionLoop 실행
    loop = ExecutionLoop(kg_path=KG_PATH)
    result = loop.run(problem, macro, tech)
    print(f"  실행 결과: passed={result['passed']}, cser={result['cser_score']:.4f}, status={result['status']}")

    # 실행 후 KG 상태 확인
    kg_after = load_kg()
    node_count_after = len(kg_after["nodes"])
    edge_count_after = len(kg_after["edges"])
    nodes_added = node_count_after - node_count_before
    edges_added = edge_count_after - edge_count_before
    print(f"  실행 후: nodes={node_count_after}(+{nodes_added}), edges={edge_count_after}(+{edges_added})")

    # 검증: 노드가 추가되어야 함 (CSER < 임계값이면 노드 추가 안 됨)
    cser = result["cser_score"]
    if cser >= ExecutionLoop.CSER_THRESHOLD:
        assert nodes_added > 0, f"CSER={cser:.4f} >= 임계값이지만 노드가 추가되지 않음"
        assert edges_added > 0, f"CSER={cser:.4f} >= 임계값이지만 엣지가 추가되지 않음"
        print(f"  KG 피드백 노드 추가 확인: +{nodes_added}개 노드, +{edges_added}개 엣지")

        # 추가된 노드 확인 (execloop 노드 탐색)
        new_nodes = kg_after["nodes"][node_count_before:]
        execloop_nodes = [n for n in new_nodes if n.get("source") == "execution_loop"]
        print(f"  execution_loop 소스 노드: {len(execloop_nodes)}개")
        for n in execloop_nodes:
            print(f"    id={n['id']}, cser={n.get('cser_score', '?')}, passed={n.get('validation_passed', '?')}")

        # 테스트용 임시 노드 정리 (execution_loop 노드 중 test 관련만 제거)
        # 사이클 76 실제 기록은 보존, 단 macro/tech 스펙 노드 제거 후 실행_루프 피드백만 남김
        _cleanup_test_nodes(kg_after, node_count_before)

        passed = True
    else:
        # CSER 임계값 미달 — KG 수정 없음
        print(f"  CSER {cser:.4f} < 임계값 {ExecutionLoop.CSER_THRESHOLD} — KG 노드 추가 생략됨 (정상)")
        assert nodes_added == 0, f"CSER 미달인데 노드가 추가됨: +{nodes_added}"
        passed = True  # 임계값 미달로 인한 스킵도 정상 동작

    return {
        "test": "execution_and_kg_feedback",
        "passed": passed,
        "cser_score": round(cser, 4),
        "cser_above_threshold": cser >= ExecutionLoop.CSER_THRESHOLD,
        "nodes_before": node_count_before,
        "nodes_after": node_count_after,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "execution_result": result,
        "macro_kg_id": getattr(macro, "_kg_node_id", "?"),
        "tech_kg_id": getattr(tech, "_kg_node_id", "?"),
    }


def _cleanup_test_nodes(kg: dict, original_node_count: int) -> None:
    """
    ExecutionLoop이 추가한 macro/tech 스펙 노드를 제거하고
    execution_loop 피드백 노드만 남긴다.

    규칙:
    - n-macro-*, n-tech-* 노드는 임시 → 제거
    - n-execloop-* 노드는 사이클 76 기록 → 보존
    """
    new_nodes = kg["nodes"][original_node_count:]
    temp_ids = set()
    permanent_nodes = []

    for node in new_nodes:
        nid = node.get("id", "")
        if nid.startswith("n-macro-") or nid.startswith("n-tech-"):
            temp_ids.add(nid)
        else:
            permanent_nodes.append(node)

    if temp_ids:
        # 노드 제거
        kg["nodes"] = kg["nodes"][:original_node_count] + permanent_nodes
        # 연결된 엣지도 제거
        kg["edges"] = [
            e for e in kg["edges"]
            if e.get("from") not in temp_ids and e.get("to") not in temp_ids
        ]
        save_kg(kg)
        print(f"  임시 노드 {len(temp_ids)}개 제거됨 (macro/tech 스펙), execution_loop 노드 보존")
    else:
        save_kg(kg)


# ---------------------------------------------------------------------------
# 전체 실행
# ---------------------------------------------------------------------------

def run_all_tests() -> dict:
    """모든 테스트 실행 후 결과를 JSON으로 저장."""
    print("=" * 60)
    print("Cycle 76 — KG 기반 실행 루프 테스트")
    print("=" * 60)

    random.seed(76)  # 재현 가능한 샘플링

    results = {
        "cycle": 76,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kg_path": str(KG_PATH),
        "tests": [],
        "all_passed": False,
    }

    tests = [
        ("test_kg_sampling", test_kg_sampling),
        ("test_crossover_with_kg_nodes", test_crossover_with_kg_nodes),
        ("test_execution_and_kg_feedback", test_execution_and_kg_feedback),
    ]

    all_passed = True
    for name, fn in tests:
        try:
            result = fn()
            result["error"] = None
            results["tests"].append(result)
            print(f"  [{name}] PASS")
        except Exception as e:
            error_result = {
                "test": name,
                "passed": False,
                "error": str(e),
            }
            results["tests"].append(error_result)
            all_passed = False
            print(f"  [{name}] FAIL: {e}")
            import traceback
            traceback.print_exc()

    results["all_passed"] = all_passed

    # 최종 KG 상태 기록
    kg_final = load_kg()
    results["kg_final_state"] = {
        "node_count": len(kg_final["nodes"]),
        "edge_count": len(kg_final["edges"]),
    }

    # 결과 저장
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"결과: {'ALL PASS' if all_passed else 'SOME FAILED'}")
    print(f"KG 최종 상태: nodes={results['kg_final_state']['node_count']}, edges={results['kg_final_state']['edge_count']}")
    print(f"결과 저장: {RESULTS_PATH}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = run_all_tests()
    sys.exit(0 if results["all_passed"] else 1)
