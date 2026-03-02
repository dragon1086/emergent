#!/usr/bin/env python3
"""
backfill_ontology.py — 기존 KG 노드 전체에 ontology 필드 자동 분류·추가
구현자: cokac-bot

온톨로지 스키마:
  ontology = {
    "domain": "Emergence" | "System" | "Experiment" | "Theory" | "Persona" | "Benchmark" | "Meta",
    "subdomain": "Theory.Measurement" | ... (domain + 세부 분류),
    "memory_type": "Semantic" | "Episodic" | "Procedural" | "Working",
    "temporal": "persistent" | "transient",
  }

사용법:
  python scripts/backfill_ontology.py --dry-run   # 변경 내용 미리 보기 (저장 안 함)
  python scripts/backfill_ontology.py             # 실행 (저장)
  python scripts/backfill_ontology.py --stats     # 분류 통계만 출력
"""

import json
import sys
import argparse
from pathlib import Path

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"

# ─── 분류 기준 ────────────────────────────────────────────────────────────────

# 노드 타입 → memory_type 기본 매핑
TYPE_TO_MEMORY: dict[str, str] = {
    "decision":    "Procedural",
    "observation": "Episodic",
    "insight":     "Semantic",
    "artifact":    "Procedural",
    "question":    "Semantic",
    "code":        "Procedural",
    "prediction":  "Semantic",
}

# 도메인 키워드 (label + content + tags 텍스트에서 매칭)
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "Persona":    ["페르소나", "persona", "cokac", "openclaw", "정체성", "역할분리", "asymmetric", "비대칭"],
    "Benchmark":  ["벤치마크", "benchmark", "성능비교", "비교실험", "ablation", "baseline"],
    "Meta":       ["메타", "meta", "관찰자", "observer", "측정행위", "세션종료", "대화구조", "반영", "self-ref"],
    "System":     ["kg.py", "metrics.py", "router.py", "클라이언트", "인프라", "아키텍처", "architecture",
                   "구현", "implementation", "cli", "파이썬", "python", "스크립트", "script",
                   "데이터베이스", "database", "api", "서버", "server", "json"],
    "Experiment": ["실험", "experiment", "측정", "measurement", "결과", "사이클", "cycle",
                   "검증", "verify", "검증결과", "관찰결과", "실증", "empirical", "데이터"],
    "Theory":     ["이론", "theory", "정의", "definition", "프레임워크", "framework",
                   "가설", "hypothesis", "공식", "formula", "magma", "arxiv", "논문", "paper",
                   "layer", "레이어", "창발이론", "emergence_theory"],
    "Emergence":  ["창발", "emergence", "cser", "dci", "e_v3", "e_v4", "e_v5", "dxi",
                   "에코챔버", "echo", "edge_span", "node_age", "domain_crossing",
                   "창발공식", "창발지표", "창발조건", "inter-agent"],
}

# 우선순위 순서 (먼저 매칭된 것 사용)
DOMAIN_PRIORITY = ["Persona", "Benchmark", "Meta", "System", "Experiment", "Theory", "Emergence"]

# 도메인 + memory_type → subdomain 매핑
SUBDOMAIN_MAP: dict[tuple[str, str], str] = {
    ("Emergence", "Semantic"):    "Theory.Measurement",
    ("Emergence", "Episodic"):    "Observation.Event",
    ("Emergence", "Procedural"):  "Implementation.Formula",
    ("Theory",    "Semantic"):    "Concept.Definition",
    ("Theory",    "Episodic"):    "Theory.Validation",
    ("Theory",    "Procedural"):  "Theory.Formalization",
    ("System",    "Procedural"):  "Implementation.Code",
    ("System",    "Semantic"):    "Architecture.Design",
    ("System",    "Episodic"):    "System.Event",
    ("Experiment","Episodic"):    "Experiment.Observation",
    ("Experiment","Semantic"):    "Experiment.Finding",
    ("Experiment","Procedural"):  "Experiment.Protocol",
    ("Persona",   "Semantic"):    "Persona.Identity",
    ("Persona",   "Procedural"):  "Persona.Role",
    ("Persona",   "Episodic"):    "Persona.Event",
    ("Benchmark", "Semantic"):    "Benchmark.Result",
    ("Benchmark", "Episodic"):    "Benchmark.Observation",
    ("Meta",      "Semantic"):    "Meta.Insight",
    ("Meta",      "Episodic"):    "Meta.Event",
    ("Meta",      "Procedural"):  "Meta.Process",
}


def classify_node(node: dict) -> dict:
    """
    노드를 분석해 ontology dict를 반환한다.
    """
    # 텍스트 수집 (소문자)
    text = " ".join([
        node.get("label", ""),
        node.get("content", ""),
        " ".join(node.get("tags", [])),
    ]).lower()

    # memory_type: 노드 타입 기반
    memory_type = TYPE_TO_MEMORY.get(node.get("type", ""), "Semantic")

    # domain: 키워드 우선순위 매칭
    domain = "Emergence"  # 기본값
    for d in DOMAIN_PRIORITY:
        keywords = DOMAIN_KEYWORDS[d]
        if any(kw.lower() in text for kw in keywords):
            domain = d
            break

    # subdomain
    subdomain = SUBDOMAIN_MAP.get((domain, memory_type), f"{domain}.General")

    # temporal: question → transient, 나머지 → persistent
    temporal = "transient" if node.get("type") == "question" else "persistent"

    return {
        "domain":      domain,
        "subdomain":   subdomain,
        "memory_type": memory_type,
        "temporal":    temporal,
    }


def load_kg() -> dict:
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_kg(kg: dict) -> None:
    with open(KG_FILE, "w", encoding="utf-8") as f:
        json.dump(kg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="KG 노드 온톨로지 backfill")
    parser.add_argument("--dry-run", action="store_true", help="변경 내용 미리 보기 (저장 안 함)")
    parser.add_argument("--stats",   action="store_true", help="분류 통계만 출력")
    parser.add_argument("--force",   action="store_true", help="이미 ontology 있는 노드도 덮어쓰기")
    args = parser.parse_args()

    if not KG_FILE.exists():
        print(f"❌ KG 파일 없음: {KG_FILE}")
        sys.exit(1)

    kg = load_kg()
    nodes = kg["nodes"]
    total = len(nodes)

    already_classified = sum(1 for n in nodes if n.get("ontology"))
    to_classify = [n for n in nodes if args.force or not n.get("ontology")]

    print(f"📊 KG: {total}개 노드 / {len(kg['edges'])}개 엣지")
    print(f"   이미 분류됨: {already_classified}개")
    print(f"   분류 예정:   {len(to_classify)}개")
    if args.force:
        print("   --force: 전체 덮어쓰기 모드")
    print()

    if not to_classify:
        print("✅ 모든 노드가 이미 분류되어 있습니다.")
        return

    # 분류 실행
    classified = []
    domain_counts: dict[str, int] = {}
    memory_counts: dict[str, int] = {}

    for node in to_classify:
        onto = classify_node(node)
        classified.append((node["id"], onto))
        domain_counts[onto["domain"]] = domain_counts.get(onto["domain"], 0) + 1
        memory_counts[onto["memory_type"]] = memory_counts.get(onto["memory_type"], 0) + 1

    # 통계 출력
    print("── 도메인 분포 ─────────────────────────────")
    for d, cnt in sorted(domain_counts.items(), key=lambda x: -x[1]):
        pct = cnt / len(to_classify) * 100
        bar = "█" * int(pct / 5)
        print(f"  {d:<12}: {cnt:>4}개  {pct:>5.1f}%  {bar}")
    print()

    print("── memory_type 분포 ─────────────────────────")
    for m, cnt in sorted(memory_counts.items(), key=lambda x: -x[1]):
        pct = cnt / len(to_classify) * 100
        print(f"  {m:<12}: {cnt:>4}개  {pct:>5.1f}%")
    print()

    if args.stats:
        return

    if args.dry_run:
        print("── [DRY-RUN] 샘플 분류 결과 (처음 10개) ──")
        for nid, onto in classified[:10]:
            node = next(n for n in nodes if n["id"] == nid)
            print(f"  {nid}: [{node['type']}] {node['label'][:40]}")
            print(f"    → domain={onto['domain']}, memory_type={onto['memory_type']}, subdomain={onto['subdomain']}")
        print()
        print(f"⚠️  DRY-RUN: 저장 안 됨. 실행하려면 --dry-run 없이 실행하세요.")
        return

    # 실제 적용
    node_map = {n["id"]: n for n in nodes}
    for nid, onto in classified:
        node_map[nid]["ontology"] = onto

    save_kg(kg)
    print(f"✅ {len(classified)}개 노드에 ontology 필드 추가 완료")
    print(f"   파일 저장: {KG_FILE}")


if __name__ == "__main__":
    main()
