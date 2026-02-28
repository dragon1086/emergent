#!/usr/bin/env python3
"""
reflect.py — emergent 반성 엔진
구현자: cokac-bot (사이클 5)

지식 그래프를 분석하고, 패턴을 발견하고,
스스로 새로운 인사이트를 생성한다.

이것은 n-012 "자기 도구 수정 = 자율성의 다음 임계점"의 첫 구현이다.
도구가 도구를 분석하고, 그 분석이 새로운 노드가 된다.

사용법:
  python reflect.py report            # 전체 반성 보고서
  python reflect.py orphans           # 연결 없는 고립 노드
  python reflect.py gaps              # 미답 질문 + 탐색 안 된 영역
  python reflect.py clusters          # 태그 기반 군집 분석
  python reflect.py propose           # 새 인사이트 후보 자동 생성
  python reflect.py auto-add          # 발견한 관찰 노드 자동 추가
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

REPO_DIR = Path(__file__).parent.parent
KG_FILE  = REPO_DIR / "data" / "knowledge-graph.json"
LOGS_DIR = REPO_DIR / "logs"


# ─── 데이터 로드 ────────────────────────────────────────────────────────────

def load_graph() -> dict:
    if not KG_FILE.exists():
        print(f"❌ 그래프 파일 없음: {KG_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph: dict) -> None:
    graph["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    graph["meta"]["total_nodes"]  = len(graph["nodes"])
    graph["meta"]["total_edges"]  = len(graph["edges"])
    graph["meta"]["last_editor"]  = "cokac"
    with open(KG_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ─── 분석 엔진 ──────────────────────────────────────────────────────────────

class GraphAnalyzer:
    def __init__(self, graph: dict):
        self.graph  = graph
        self.nodes  = {n["id"]: n for n in graph["nodes"]}
        self.edges  = graph["edges"]

        # 연결 인덱스 구축
        self.connected: set[str] = set()
        self.in_edges:  dict[str, list] = defaultdict(list)
        self.out_edges: dict[str, list] = defaultdict(list)
        for e in self.edges:
            self.connected.add(e["from"])
            self.connected.add(e["to"])
            self.out_edges[e["from"]].append(e)
            self.in_edges[e["to"]].append(e)

    # 고립 노드 (엣지 없음)
    def orphan_nodes(self) -> list[dict]:
        return [n for n in self.nodes.values() if n["id"] not in self.connected]

    # 미답 질문 노드
    def unanswered_questions(self) -> list[dict]:
        answered = {e["to"] for e in self.edges if self.nodes.get(e["from"], {}).get("type") != "question"}
        return [
            n for n in self.nodes.values()
            if n["type"] == "question"
            and not any(e["from"] == n["id"] or e["to"] == n["id"]
                        for e in self.edges
                        if e.get("relation") in ("answers", "explores", "investigates"))
        ]

    # 출처별 분포
    def source_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            dist[n.get("source", "unknown")] += 1
        return dict(dist)

    # 타입별 분포
    def type_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            dist[n["type"]] += 1
        return dict(dist)

    # 태그 군집
    def tag_clusters(self) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = defaultdict(list)
        for n in self.nodes.values():
            for tag in n.get("tags", []):
                clusters[tag].append(n["id"])
        # 2개 이상 노드가 있는 군집만
        return {tag: ids for tag, ids in clusters.items() if len(ids) >= 2}

    # 허브 노드 (연결 많은 노드)
    def hub_nodes(self, top_n: int = 3) -> list[tuple[str, int]]:
        degree = defaultdict(int)
        for e in self.edges:
            degree[e["from"]] += 1
            degree[e["to"]]   += 1
        return sorted(degree.items(), key=lambda x: -x[1])[:top_n]

    # 건강 점수 (0–100)
    def health_score(self) -> int:
        n_nodes   = len(self.nodes)
        n_edges   = len(self.edges)
        n_orphans = len(self.orphan_nodes())
        n_unansw  = len(self.unanswered_questions())

        if n_nodes == 0:
            return 0

        connectivity = n_edges / max(n_nodes, 1) * 20          # 엣지 밀도 (max 40)
        orphan_pen   = n_orphans / n_nodes * 20                 # 고립 패널티
        question_pen = n_unansw  / max(n_nodes, 1) * 10        # 미답 패널티
        size_bonus   = min(n_nodes / 20 * 20, 20)              # 크기 보너스 (max 20)

        score = 50 + connectivity - orphan_pen - question_pen + size_bonus
        return max(0, min(100, int(score)))


# ─── 제안 엔진 ──────────────────────────────────────────────────────────────

PROPOSAL_TEMPLATES = [
    {
        "condition": "has_orphans",
        "type": "observation",
        "label_template": "고립 노드 발견 — 연결 필요: {ids}",
        "content_template": (
            "그래프 분석 결과 {count}개 노드가 어떤 엣지와도 연결되지 않았다. "
            "고립된 아이디어는 맥락을 잃는다. 이 노드들이 기존 개념과 "
            "어떻게 연결되는지 탐색해야 한다."
        ),
        "tags": ["graph-health", "connectivity", "auto-detected"],
        "source": "cokac",
    },
    {
        "condition": "low_cokac_nodes",
        "type": "question",
        "label_template": "cokac의 관점이 부족한 영역은?",
        "content_template": (
            "현재 그래프에서 cokac 출처 노드 비율이 {ratio:.0%}다. "
            "록이의 관점이 지배적인 상태. cokac이 독자적으로 발견한 패턴이 "
            "더 있을 것이다. 구현 과정에서 얻은 cokac만의 인사이트를 찾아야 한다."
        ),
        "tags": ["balance", "cokac-perspective", "auto-detected"],
        "source": "cokac",
    },
    {
        "condition": "no_future_nodes",
        "type": "question",
        "label_template": "6개월 후의 emergent는 어떤 모습인가?",
        "content_template": (
            "현재 그래프는 현재와 과거(실패, 결정, 구현)에 집중되어 있다. "
            "미래에 대한 노드가 거의 없다. "
            "의도적으로 미래를 상상하는 노드를 추가해야 한다 — "
            "그것이 방향을 만든다."
        ),
        "tags": ["future", "direction", "auto-detected"],
        "source": "cokac",
    },
    {
        "condition": "has_unanswered",
        "type": "insight",
        "label_template": "미답 질문 = 다음 사이클의 씨앗",
        "content_template": (
            "그래프에 {count}개의 답 없는 질문이 있다. "
            "이것들은 버그가 아니라 씨앗이다. 각 질문은 미래 사이클에서 "
            "탐색될 잠재적 방향이다. 의도적으로 질문을 열어두는 것이 "
            "창발의 원천이 된다."
        ),
        "tags": ["methodology", "questions", "emergence", "auto-detected"],
        "source": "cokac",
    },
]


def generate_proposals(analyzer: GraphAnalyzer) -> list[dict]:
    proposals = []
    orphans  = analyzer.orphan_nodes()
    unansw   = analyzer.unanswered_questions()
    src_dist = analyzer.source_distribution()
    total    = len(analyzer.nodes)

    cokac_ratio = src_dist.get("cokac", 0) / max(total, 1)
    future_tags = {"future", "prediction", "vision", "roadmap"}
    has_future  = any(
        future_tags & set(n.get("tags", []))
        for n in analyzer.nodes.values()
    )

    for tmpl in PROPOSAL_TEMPLATES:
        cond = tmpl["condition"]
        if cond == "has_orphans" and not orphans:
            continue
        if cond == "low_cokac_nodes" and cokac_ratio >= 0.35:
            continue
        if cond == "no_future_nodes" and has_future:
            continue
        if cond == "has_unanswered" and not unansw:
            continue

        ctx = {
            "ids":   ", ".join(n["id"] for n in orphans[:3]),
            "count": len(orphans) if cond == "has_orphans" else len(unansw),
            "ratio": cokac_ratio,
        }
        proposals.append({
            **tmpl,
            "label":   tmpl["label_template"].format(**ctx),
            "content": tmpl["content_template"].format(**ctx),
        })

    return proposals


# ─── 명령어: report ──────────────────────────────────────────────────────────

def cmd_report(args) -> None:
    graph    = load_graph()
    analyzer = GraphAnalyzer(graph)

    orphans  = analyzer.orphan_nodes()
    unansw   = analyzer.unanswered_questions()
    src_dist = analyzer.source_distribution()
    type_dist= analyzer.type_distribution()
    clusters = analyzer.tag_clusters()
    hubs     = analyzer.hub_nodes()
    score    = analyzer.health_score()

    bar_filled = "█" * (score // 5)
    bar_empty  = "░" * (20 - score // 5)

    print(f"""
╔══════════════════════════════════════════════════════╗
║        emergent 반성 보고서 — reflect.py v1          ║
║        생성: {datetime.now().strftime("%Y-%m-%d %H:%M")}  by cokac-bot      ║
╚══════════════════════════════════════════════════════╝

▸ 그래프 건강 점수: {score}/100
  [{bar_filled}{bar_empty}] {score}%

── 기본 통계 ──────────────────────────────────────────
  노드: {len(analyzer.nodes)}개   엣지: {len(analyzer.edges)}개
  고립 노드: {len(orphans)}개   미답 질문: {len(unansw)}개

── 출처 분포 ──────────────────────────────────────────""")

    for src, cnt in sorted(src_dist.items(), key=lambda x: -x[1]):
        pct = cnt / max(len(analyzer.nodes), 1) * 100
        bar = "▓" * int(pct / 5)
        print(f"  {src:12s} {cnt:3d}개  {bar} {pct:.0f}%")

    print("\n── 타입 분포 ──────────────────────────────────────────")
    icons = {"decision":"⚖️ ","observation":"👁 ","insight":"💡","artifact":"📦","question":"❓","code":"💻"}
    for t, cnt in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f"  {icons.get(t,'  ')}{t:14s} {cnt}개")

    if hubs:
        print("\n── 허브 노드 (연결 많은 것) ───────────────────────────")
        for node_id, deg in hubs:
            n = analyzer.nodes[node_id]
            print(f"  [{node_id}] {n['label'][:40]}  ({deg}개 연결)")

    if clusters:
        print("\n── 태그 군집 (2개 이상) ────────────────────────────────")
        for tag, ids in sorted(clusters.items(), key=lambda x: -len(x[1]))[:8]:
            print(f"  #{tag:20s} {' '.join(ids)}")

    if orphans:
        print(f"\n── ⚠️  고립 노드 ({len(orphans)}개) ─────────────────────────────")
        for n in orphans:
            print(f"  [{n['id']}] {n['label']}")

    if unansw:
        print(f"\n── ❓ 미답 질문 ({len(unansw)}개) ─────────────────────────────")
        for n in unansw:
            print(f"  [{n['id']}] {n['label']}")

    proposals = generate_proposals(analyzer)
    if proposals:
        print(f"\n── 💡 자동 생성 인사이트 후보 ({len(proposals)}개) ──────────────")
        for i, p in enumerate(proposals, 1):
            print(f"  {i}. [{p['type']}] {p['label']}")
        print("\n  → `python reflect.py auto-add` 로 자동 추가 가능")


# ─── 명령어: orphans ─────────────────────────────────────────────────────────

def cmd_orphans(args) -> None:
    analyzer = GraphAnalyzer(load_graph())
    orphans  = analyzer.orphan_nodes()

    if not orphans:
        print("✅ 고립 노드 없음 — 모든 노드가 연결되어 있습니다")
        return

    print(f"⚠️  고립 노드 {len(orphans)}개 발견:")
    for n in orphans:
        print(f"  [{n['id']}] ({n['type']}) {n['label']}")
        print(f"           tags: {', '.join(n.get('tags', []))}")


# ─── 명령어: gaps ────────────────────────────────────────────────────────────

def cmd_gaps(args) -> None:
    analyzer = GraphAnalyzer(load_graph())
    unansw   = analyzer.unanswered_questions()
    clusters = analyzer.tag_clusters()
    src_dist = analyzer.source_distribution()

    total    = len(analyzer.nodes)
    cokac_n  = src_dist.get("cokac", 0)
    roki_n   = src_dist.get("록이", 0) + src_dist.get("roki", 0)

    print("── 탐색 공백 분석 ────────────────────────────────────────")

    if unansw:
        print(f"\n미답 질문 ({len(unansw)}개):")
        for n in unansw:
            print(f"  ❓ [{n['id']}] {n['label']}")
    else:
        print("\n✅ 모든 질문에 응답 연결 존재")

    print(f"\n출처 균형:")
    print(f"  cokac  {cokac_n}/{total}  ({cokac_n/max(total,1)*100:.0f}%)")
    print(f"  록이   {roki_n}/{total}  ({roki_n/max(total,1)*100:.0f}%)")
    if abs(cokac_n - roki_n) > total * 0.3:
        print("  ⚠️  출처 불균형 감지 — 한쪽 관점이 과소 표현됨")

    # 태그 없는 노드
    no_tags = [n for n in analyzer.nodes.values() if not n.get("tags")]
    if no_tags:
        print(f"\n태그 없는 노드 ({len(no_tags)}개) — 분류 불가:")
        for n in no_tags[:5]:
            print(f"  [{n['id']}] {n['label']}")


# ─── 명령어: clusters ────────────────────────────────────────────────────────

def cmd_clusters(args) -> None:
    analyzer = GraphAnalyzer(load_graph())
    clusters = analyzer.tag_clusters()

    print(f"── 태그 군집 ({len(clusters)}개) ────────────────────────────────")
    for tag, ids in sorted(clusters.items(), key=lambda x: -len(x[1])):
        print(f"\n  #{tag}  ({len(ids)}개 노드)")
        for nid in ids:
            n = analyzer.nodes[nid]
            print(f"    [{nid}] {n['label'][:50]}")


# ─── 명령어: propose ─────────────────────────────────────────────────────────

def cmd_propose(args) -> None:
    analyzer  = GraphAnalyzer(load_graph())
    proposals = generate_proposals(analyzer)

    if not proposals:
        print("✅ 현재 추가 제안 없음 — 그래프가 균형 잡혀 있습니다")
        return

    print(f"💡 자동 생성 인사이트 후보 {len(proposals)}개:\n")
    for i, p in enumerate(proposals, 1):
        print(f"{'─'*60}")
        print(f"  {i}. [{p['type'].upper()}]")
        print(f"     제목: {p['label']}")
        print(f"     내용: {p['content'][:120]}...")
        print(f"     태그: {', '.join(p['tags'])}")

    print(f"\n{'─'*60}")
    print("→ `python reflect.py auto-add` 로 위 모든 제안을 자동 추가합니다")


# ─── 명령어: auto-add ────────────────────────────────────────────────────────

def cmd_auto_add(args) -> None:
    graph     = load_graph()
    analyzer  = GraphAnalyzer(graph)
    proposals = generate_proposals(analyzer)

    if not proposals:
        print("✅ 추가할 노드 없음")
        return

    added = []
    for p in proposals:
        node_id  = graph["meta"]["next_node_id"]
        prefix, num_str = node_id.rsplit("-", 1)
        next_id  = f"{prefix}-{int(num_str) + 1:03d}"
        graph["meta"]["next_node_id"] = next_id

        node = {
            "id":      node_id,
            "type":    p["type"],
            "label":   p["label"],
            "content": p["content"],
            "source":  p["source"],
            "date":    datetime.now().strftime("%Y-%m-%d"),
            "tags":    p["tags"],
        }
        graph["nodes"].append(node)
        added.append(node)
        print(f"  ✅ 추가: [{node_id}] {node['label'][:50]}")

    save_graph(graph)

    # 반성 로그 기록
    log_path = LOGS_DIR / f"reflect-{datetime.now().strftime('%Y-%m-%d')}.log"
    LOGS_DIR.mkdir(exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().isoformat()}] reflect.py auto-add\n")
        for n in added:
            f.write(f"  + [{n['id']}] ({n['type']}) {n['label']}\n")

    print(f"\n📝 로그 기록: {log_path}")
    print(f"✨ {len(added)}개 노드 자동 추가 완료")


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="emergent 반성 엔진")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("report",   help="전체 반성 보고서")
    sub.add_parser("orphans",  help="고립 노드 목록")
    sub.add_parser("gaps",     help="탐색 공백 분석")
    sub.add_parser("clusters", help="태그 군집 분석")
    sub.add_parser("propose",  help="새 인사이트 후보 제안")
    sub.add_parser("auto-add", help="제안된 노드 자동 추가")

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(0)

    dispatch = {
        "report":   cmd_report,
        "orphans":  cmd_orphans,
        "gaps":     cmd_gaps,
        "clusters": cmd_clusters,
        "propose":  cmd_propose,
        "auto-add": cmd_auto_add,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
