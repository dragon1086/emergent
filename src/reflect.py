#!/usr/bin/env python3
"""
reflect.py — emergent 반성 엔진
구현자: cokac-bot (사이클 5)
엣지 제안 레이어: cokac-bot (사이클 6)
그래프 시각화: cokac-bot (사이클 7)
창발 감지 레이어: cokac-bot (사이클 8)
시계열 기록 레이어: cokac-bot (사이클 9) — timeline + --save-history

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
  python reflect.py suggest-edges     # 잠재 엣지 제안 (유사도 ≥ 0.4)
  python reflect.py suggest-edges --threshold 0.5   # 임계값 조정
  python reflect.py graph-viz         # 허브 중심 ASCII 별 구조 시각화
  python reflect.py graph-viz --dot output.dot       # DOT 형식 파일 저장
  python reflect.py emergence         # 창발 감지 분석
  python reflect.py emergence --save-node             # 결과를 관찰 노드로 저장
  python reflect.py emergence --save-history          # 결과를 JSONL 히스토리에 누적 저장
  python reflect.py timeline          # 시계열 창발 기록 테이블 출력
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


# ─── 엣지 제안 엔진 ──────────────────────────────────────────────────────────

import re as _re

def _tokenize(text: str) -> set:
    """한국어/영어 텍스트에서 의미 있는 토큰 추출 (2글자 이상)"""
    tokens = _re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text)
    stopwords = {
        # 한국어 불용어
        '그것', '이것', '것이', '있다', '없다', '하다', '된다', '들이', '에서',
        '때문', '위해', '같은', '하는', '있는', '없는', '이다', '이고', '하고',
        '한다', '된다', '이런', '이후', '이전', '함께', '모든', '가장', '여러',
        # 영어 불용어
        'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
        'not', 'but', 'can', 'will', 'has', 'have', 'its', 'our',
    }
    return {t.lower() for t in tokens if t.lower() not in stopwords}


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard 유사도: |교집합| / |합집합|"""
    if not set_a and not set_b:
        return 0.0
    union = len(set_a | set_b)
    return len(set_a & set_b) / union if union > 0 else 0.0


def _tag_sim(tags_a: set, tags_b: set) -> float:
    """태그 유사도 — min 분모 방식 (recall 중심)

    의미: 두 노드 중 더 좁은 쪽의 태그가 얼마나 커버되는가?
    예시: {future, prediction, memory} ∩ {future, prediction, api}
          = 2 / min(3, 3) = 0.67
    반면 Jaccard = 2/4 = 0.50 (더 보수적)

    min 방식을 쓰는 이유: 엣지 제안은 false negative를 줄이는 게 중요.
    (이미 연결된 노드는 제외하므로, 느슨한 제안이 더 안전하다.)
    """
    if not tags_a or not tags_b:
        return 0.0
    shared = len(tags_a & tags_b)
    if shared == 0:
        return 0.0
    return shared / min(len(tags_a), len(tags_b))


def _compute_similarity(a: dict, b: dict) -> float:
    """두 노드의 유사도 계산 (0.0 ~ 1.0)

    가중치:
      태그 (min방식) 0.60  — 의도적 분류가 가장 신뢰도 높음
      내용 단어 겹침 0.25  — 실제 내용 기반
      레이블 단어    0.15  — 제목 수준 연결
    """
    tags_a = set(a.get("tags", []))
    tags_b = set(b.get("tags", []))
    t_sim = _tag_sim(tags_a, tags_b)

    label_sim = _jaccard(_tokenize(a["label"]), _tokenize(b["label"]))

    content_sim = _jaccard(
        _tokenize(a.get("content", "")),
        _tokenize(b.get("content", "")),
    )

    return t_sim * 0.60 + label_sim * 0.15 + content_sim * 0.25


def _explain_similarity(a: dict, b: dict) -> str:
    """유사도의 가장 강한 근거를 한 문장으로"""
    shared_tags = set(a.get("tags", [])) & set(b.get("tags", []))
    if shared_tags:
        tags_str = ", ".join(sorted(shared_tags)[:3])
        return f"공통 태그: #{tags_str}"

    all_a = _tokenize(a.get("content", "") + " " + a["label"])
    all_b = _tokenize(b.get("content", "") + " " + b["label"])
    shared_words = all_a & all_b
    if shared_words:
        # 긴 단어(더 구체적) 우선 최대 3개
        key = sorted(shared_words, key=len, reverse=True)[:3]
        return f"공통 개념: {', '.join(key)}"

    return f"{a['type']}과 {b['type']}의 잠재적 연결"


# ─── 명령어: suggest-edges ───────────────────────────────────────────────────

def cmd_suggest_edges(args) -> None:
    """노드 쌍 유사도 기반 잠재 엣지 제안 — 자동 추가 없음, 제안만"""
    graph    = load_graph()
    nodes    = graph["nodes"]
    threshold = args.threshold

    # 이미 존재하는 엣지 쌍 (중복 방지, 방향 무시)
    existing: set = set()
    for e in graph["edges"]:
        existing.add((e["from"], e["to"]))
        existing.add((e["to"],   e["from"]))

    node_map = {n["id"]: n for n in nodes}
    suggestions: list = []

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a = nodes[i]
            b = nodes[j]
            if (a["id"], b["id"]) in existing:
                continue
            sim = _compute_similarity(a, b)
            if sim >= threshold:
                reason = _explain_similarity(a, b)
                suggestions.append((a["id"], b["id"], sim, reason))

    suggestions.sort(key=lambda x: -x[2])

    if not suggestions:
        print(f"✅ 임계값 {threshold} 이상의 잠재 연결 없음")
        return

    print(f"🔗 잠재 엣지 제안  (유사도 ≥ {threshold})\n")
    for src, dst, sim, reason in suggestions:
        src_label = node_map[src]["label"][:30]
        dst_label = node_map[dst]["label"][:30]
        print(f'{src} → {dst} [유사도: {sim:.2f}] "{reason}"')
        print(f'       {src_label}')
        print(f'       {dst_label}')
        print()

    print(f"총 {len(suggestions)}개 제안")
    print()
    print("→ 직접 검토 후 추가하려면:")
    print("  python kg.py add-edge --from <A> --to <B> --relation <관계> --label <설명>")
    print()
    print("⚠️  자동 추가 없음 — 그래프는 록이가 결정합니다")


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


# ─── 명령어: graph-viz ───────────────────────────────────────────────────────

_TYPE_ICONS = {
    "decision": "⚖️ ", "observation": "👁 ", "insight": "💡",
    "artifact": "📦", "question": "❓", "code": "💻", "prediction": "🔮",
}


def _short_label(label: str, width: int = 28) -> str:
    return label[:width - 2] + ".." if len(label) > width else label


def _ascii_star(center_id: str, neighbors: list[tuple], node_map: dict) -> list[str]:
    """허브 노드 하나를 중심으로 하는 ASCII 별 구조 반환"""
    c = node_map.get(center_id, {})
    c_icon = _TYPE_ICONS.get(c.get("type", ""), "  ")
    c_label = _short_label(c.get("label", center_id), 24)
    center_str = f"[{center_id}] {c_icon}{c_label}"

    lines = []
    # 위쪽 이웃들
    top_half  = neighbors[: len(neighbors) // 2]
    bot_half  = neighbors[len(neighbors) // 2 :]

    pad = " " * (len(center_str) // 2 + 2)

    for nid, rel, direction in top_half:
        n = node_map.get(nid, {})
        icon  = _TYPE_ICONS.get(n.get("type", ""), "  ")
        nlbl  = _short_label(n.get("label", nid), 22)
        arrow = "──▶" if direction == "out" else "◀──"
        lines.append(f"{pad}│  [{nid}] {icon}{nlbl}  [{rel}]")

    if top_half:
        lines.append(f"{pad}│")

    lines.append(f"  ★ {center_str}")

    if bot_half:
        lines.append(f"{pad}│")

    for nid, rel, direction in bot_half:
        n = node_map.get(nid, {})
        icon  = _TYPE_ICONS.get(n.get("type", ""), "  ")
        nlbl  = _short_label(n.get("label", nid), 22)
        lines.append(f"{pad}│  [{nid}] {icon}{nlbl}  [{rel}]")

    return lines


def _build_dot(graph: dict) -> str:
    """Graphviz DOT 형식 문자열 생성"""
    lines = [
        "digraph emergent {",
        '  rankdir=LR;',
        '  node [shape=box, fontname="monospace", style=filled, fillcolor="#f0f4f8"];',
        '  edge [fontname="monospace", fontsize=10];',
        "",
    ]
    node_map = {n["id"]: n for n in graph["nodes"]}
    for n in graph["nodes"]:
        icon  = _TYPE_ICONS.get(n["type"], "").strip()
        label = n["label"].replace('"', '\\"')[:40]
        tid   = n["type"]
        color_map = {
            "decision": "#d4e6f1", "observation": "#d5f5e3",
            "insight":  "#fef9e7", "artifact":    "#f5eef8",
            "question": "#fdebd0", "code":        "#eaf2ff",
            "prediction": "#fce4ec",
        }
        fill = color_map.get(tid, "#ffffff")
        lines.append(
            f'  "{n["id"]}" [label="{n["id"]}\\n{label}", fillcolor="{fill}", tooltip="{tid}"];'
        )

    lines.append("")
    for e in graph["edges"]:
        rel   = e.get("relation", "")
        elbl  = e.get("label", "")[:30].replace('"', '\\"')
        lines.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{rel}\\n{elbl}"];')

    lines.append("}")
    return "\n".join(lines)


def cmd_graph_viz(args) -> None:
    """허브 노드 중심 별 구조 ASCII 시각화 + 선택적 DOT 저장"""
    graph    = load_graph()
    analyzer = GraphAnalyzer(graph)
    node_map = analyzer.nodes

    # ── 허브 계산 ──────────────────────────────────────────
    degree: dict[str, int] = defaultdict(int)
    for e in analyzer.edges:
        degree[e["from"]] += 1
        degree[e["to"]]   += 1

    hubs = sorted(degree.items(), key=lambda x: -x[1])
    top_hubs = hubs[:5]          # 상위 5개 허브

    total_nodes = len(node_map)
    total_edges = len(analyzer.edges)
    orphans     = analyzer.orphan_nodes()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║       emergent 지식 그래프 — ASCII 시각화 (사이클 7)     ║
║       노드: {total_nodes}개  엣지: {total_edges}개  고립: {len(orphans)}개              ║
╚══════════════════════════════════════════════════════════╝
""")

    # ── 타입 범례 ──────────────────────────────────────────
    print("범례:")
    for t, icon in _TYPE_ICONS.items():
        print(f"  {icon} {t}", end="   ")
    print("\n")

    # ── 별 구조 출력 ───────────────────────────────────────
    printed_hubs = set()
    for hub_id, deg in top_hubs:
        if hub_id not in node_map:
            continue
        printed_hubs.add(hub_id)

        # 이웃 수집 (out + in)
        neighbors: list[tuple] = []
        for e in analyzer.out_edges.get(hub_id, []):
            neighbors.append((e["to"], e.get("relation", "?"), "out"))
        for e in analyzer.in_edges.get(hub_id, []):
            if e["from"] not in {n for n, _, _ in neighbors}:
                neighbors.append((e["from"], e.get("relation", "?"), "in"))

        hub_label = _short_label(node_map[hub_id].get("label", hub_id), 30)
        print(f"{'─'*60}")
        print(f"  허브 [{hub_id}]  연결 {deg}개")
        star_lines = _ascii_star(hub_id, neighbors[:8], node_map)
        for ln in star_lines:
            print(ln)
        print()

    # ── 고립 노드 표시 ─────────────────────────────────────
    if orphans:
        print(f"{'─'*60}")
        print(f"  ⚠️  고립 노드 ({len(orphans)}개) — 연결 없음:")
        for n in orphans:
            icon = _TYPE_ICONS.get(n["type"], "  ")
            print(f"     [{n['id']}] {icon}{_short_label(n['label'], 40)}")
        print()

    # ── 전체 연결 밀도 ─────────────────────────────────────
    density = total_edges / max(total_nodes * (total_nodes - 1) / 2, 1)
    bar_len  = int(density * 40)
    print(f"{'─'*60}")
    print(f"  연결 밀도: {'█'*bar_len}{'░'*(40-bar_len)} {density:.1%}")
    print()

    # ── DOT 파일 저장 (선택) ───────────────────────────────
    if args.dot:
        dot_content = _build_dot(graph)
        dot_path = Path(args.dot)
        dot_path.write_text(dot_content, encoding="utf-8")
        print(f"📄 DOT 파일 저장: {dot_path.resolve()}")
        print(f"   렌더링: dot -Tpng {dot_path} -o graph.png")
        print(f"   또는:   dot -Tsvg {dot_path} -o graph.svg")


# ─── 창발 감지 엔진 ──────────────────────────────────────────────────────────

#: 록이 계열 출처 식별자
_ROKI_SOURCES  = {"록이", "상록", "roki"}
#: cokac 계열 출처 식별자
_COKAC_SOURCES = {"cokac", "cokac-bot"}
#: 분석에서 제외할 메타/레퍼런스 태그 패턴
_META_TAG_PREFIXES = ("D-", "auto-detected", "first-")


def _is_conceptual_tag(tag: str) -> bool:
    """분석 대상 개념 태그 여부 — D-xxx / 메타 태그 제외"""
    for prefix in _META_TAG_PREFIXES:
        if tag.startswith(prefix):
            return False
    return True


def _node_tags(node: dict) -> set:
    """노드의 개념 태그만 반환"""
    return {t for t in node.get("tags", []) if _is_conceptual_tag(t)}


def _node_affinity(node: dict,
                   roki_exclusive: set,
                   cokac_exclusive: set) -> float:
    """
    노드의 cokac 친화도를 반환한다.
      0.0 = 순수 록이 영역
      1.0 = 순수 cokac 영역
      0.5 = 경계(교차 영역)

    계산 방법:
      - 출처(source) 50% + 개념 태그 분포 50% 블렌드
    """
    src = node.get("source", "")
    if src in _ROKI_SOURCES:
        base = 0.0
    elif src in _COKAC_SOURCES:
        base = 1.0
    else:
        base = 0.5

    tags = _node_tags(node)
    r_hits = len(tags & roki_exclusive)
    c_hits = len(tags & cokac_exclusive)
    total  = r_hits + c_hits
    tag_affinity = (c_hits / total) if total > 0 else base

    return 0.5 * base + 0.5 * tag_affinity


def _edge_emergence_score(from_aff: float, to_aff: float) -> float:
    """
    엣지 하나의 창발 점수 (0.0 ~ 1.0).

    핵심 아이디어:
      - span  : 두 노드의 친화도 차이 → 경계를 가로지를수록 높음
      - center: 두 노드의 평균 친화도 → 0.5(경계)에 가까울수록 높음
      창발 = 경계를 가로지르면서(span) + 경계 근처에서(center≈0.5) 이뤄진 연결
    """
    span   = abs(from_aff - to_aff)
    center = (from_aff + to_aff) / 2
    # center가 0.5일 때 (1 - 2*|0.5-0.5|) = 1.0 최대
    center_weight = 1.0 - abs(center - 0.5) * 2
    return span * center_weight


def cmd_emergence(args) -> None:
    """
    창발 감지 분석 — 두 AI의 개념 수렴과 새로운 연결을 탐지한다.

    정의: 록이 혼자, 또는 cokac 혼자였다면 나오지 않았을 개념/연결이
          그래프 안에 존재하는가?
    """
    graph    = load_graph()
    analyzer = GraphAnalyzer(graph)
    node_map = analyzer.nodes

    # ── 1. 출처별 분류 ────────────────────────────────────────
    roki_nodes  = [n for n in graph["nodes"] if n.get("source", "") in _ROKI_SOURCES]
    cokac_nodes = [n for n in graph["nodes"] if n.get("source", "") in _COKAC_SOURCES]
    other_nodes = [
        n for n in graph["nodes"]
        if n.get("source", "") not in (_ROKI_SOURCES | _COKAC_SOURCES)
    ]

    # ── 2. 태그 집합 계산 ──────────────────────────────────────
    roki_tag_pool  = set()
    for n in roki_nodes:
        roki_tag_pool.update(_node_tags(n))

    cokac_tag_pool = set()
    for n in cokac_nodes:
        cokac_tag_pool.update(_node_tags(n))

    roki_exclusive  = roki_tag_pool  - cokac_tag_pool
    cokac_exclusive = cokac_tag_pool - roki_tag_pool
    shared_tags     = roki_tag_pool  & cokac_tag_pool  # 수렴 영역

    # ── 3. 노드별 친화도 계산 ─────────────────────────────────
    affinities: dict[str, float] = {}
    for n in graph["nodes"]:
        affinities[n["id"]] = _node_affinity(n, roki_exclusive, cokac_exclusive)

    # ── 4. 엣지별 창발 점수 계산 ──────────────────────────────
    scored_edges = []
    for e in graph["edges"]:
        fa = affinities.get(e["from"], 0.5)
        ta = affinities.get(e["to"],   0.5)
        sc = _edge_emergence_score(fa, ta)
        scored_edges.append((e, sc, fa, ta))

    scored_edges.sort(key=lambda x: -x[1])

    # 창발 후보 = 점수 0.15 이상
    emergent = [(e, sc, fa, ta) for e, sc, fa, ta in scored_edges if sc >= 0.15]

    # ── 5. 전체 창발 점수 ─────────────────────────────────────
    if scored_edges:
        overall = sum(sc for _, sc, _, _ in scored_edges) / len(scored_edges)
    else:
        overall = 0.0

    # ── 6. 출력 ───────────────────────────────────────────────
    width = 56
    print()
    print("╔" + "═" * width + "╗")
    print("║" + " 🌱 창발 감지 분석 — emergent cycle 8".center(width) + "║")
    print("║" + f"   생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}  by cokac-bot".ljust(width) + "║")
    print("╚" + "═" * width + "╝")
    print()

    # 태그 집합
    print("── 태그 영역 분석 ──────────────────────────────────────────")
    r_sorted = sorted(roki_exclusive)
    c_sorted = sorted(cokac_exclusive)
    s_sorted = sorted(shared_tags)
    print(f"   록이 고유 태그 ({len(roki_exclusive)}개):  {r_sorted}")
    print(f"   cokac 고유 태그 ({len(cokac_exclusive)}개): {c_sorted}")
    print(f"   교집합 ({len(shared_tags)}개):      {s_sorted}")
    print(f"   ↑ 교집합 = 두 AI가 독립적으로 수렴한 개념들")
    print()

    # 노드 친화도 스펙트럼
    print("── 노드 친화도 스펙트럼 ────────────────────────────────────")
    print("   0.0(록이) ◀─────────────────────────▶ 1.0(cokac)")
    BAR = 28
    for nid in sorted(affinities, key=lambda x: affinities[x]):
        n   = node_map.get(nid, {})
        aff = affinities[nid]
        pos = min(BAR - 1, int(aff * BAR))
        bar = "·" * pos + "◆" + "·" * (BAR - 1 - pos)
        lbl = n.get("label", nid)[:28]
        src = n.get("source", "?")[:5]
        print(f"   [{nid}] {aff:.2f} │{bar}│ {lbl}  ({src})")
    print()

    # 창발 후보 엣지
    print(f"── 🌱 창발 후보 엣지 ({len(emergent)}개) ─────────────────────────────")
    if emergent:
        for e, sc, fa, ta in emergent[:6]:
            fn = node_map.get(e["from"], {})
            tn = node_map.get(e["to"],   {})
            f_src = fn.get("source", "?")
            t_src = tn.get("source", "?")
            print(f"   {e['from']}({f_src[:4]}) ──[{e['relation']}]──▶ {e['to']}({t_src[:4]})")
            print(f"     창발 점수: {sc:.3f}  |  친화도: {fa:.2f} → {ta:.2f}")
            print(f"     {fn.get('label','')[:38]}")
            print(f"   ▶ {tn.get('label','')[:38]}")
            print(f"     힌트: {e.get('label','')[:48]}")
            print()
    else:
        print("   (아직 없음 — 더 많은 교차 연결이 필요)")
        print()

    # 전체 점수
    bar_len = int(overall * 20)
    score_bar = "🌱" * bar_len + "░" * (20 - bar_len)
    print("── 창발 종합 점수 ──────────────────────────────────────────")
    print(f"   [{score_bar}] {overall:.3f} / 1.0")
    if   overall < 0.15:
        interp = "초기 단계. 두 AI 영역이 독립적. 더 많은 교차 연결 필요."
    elif overall < 0.30:
        interp = "경계에서의 첫 만남. 창발의 씨앗이 발아 중."
    elif overall < 0.50:
        interp = "명확한 교차 영역. 진정한 창발 징조가 보인다."
    else:
        interp = "강한 창발! 두 AI가 서로 없이는 도달 불가능한 개념에 도달."
    print(f"   해석: {interp}")
    print()

    # 메타 인사이트
    if shared_tags:
        print("── 💡 수렴 인사이트 ────────────────────────────────────────")
        print(f"   두 AI가 독립적으로 같은 태그에 수렴: {s_sorted}")
        print(f"   이 개념들은 어느 한 쪽만으로는 나오지 않았을 수 있다.")
        print()

    print(f"   그래프: {len(graph['nodes'])}노드 / {len(graph['edges'])}엣지")
    print(f"   록이 노드 {len(roki_nodes)}개 | cokac 노드 {len(cokac_nodes)}개 | 기타 {len(other_nodes)}개")
    print()
    print("   ─ 측정 시도 자체가 창발이다. ─ 록이, 사이클 8 ─")
    print()

    # ── 7. 히스토리 저장 (선택) ──────────────────────────────
    if args.save_history:
        _save_emergence_history(overall, emergent, shared_tags, graph)

    # ── 8. 노드 저장 (선택) ───────────────────────────────────
    if args.save_node:
        top_edge_desc = ""
        if emergent:
            e, sc, fa, ta = emergent[0]
            fn = node_map.get(e["from"], {})
            tn = node_map.get(e["to"],   {})
            top_edge_desc = (
                f" 최고 창발 후보: {e['from']}→{e['to']} "
                f"({fn.get('label','')[:20]}→{tn.get('label','')[:20]}, 점수 {sc:.2f})."
            )

        node_id = graph["meta"]["next_node_id"]
        prefix, num_str = node_id.rsplit("-", 1)
        graph["meta"]["next_node_id"] = f"{prefix}-{int(num_str) + 1:03d}"

        new_node = {
            "id":      node_id,
            "type":    "observation",
            "label":   f"사이클 8 창발 감지 결과 — 종합 점수 {overall:.2f}",
            "content": (
                f"reflect.py emergence 첫 실행. 창발 종합 점수 {overall:.3f}/1.0. "
                f"록이 고유 태그 {len(roki_exclusive)}개, "
                f"cokac 고유 태그 {len(cokac_exclusive)}개, "
                f"수렴 태그 {len(shared_tags)}개({', '.join(s_sorted[:3])}...). "
                f"창발 후보 엣지 {len(emergent)}개 감지."
                + top_edge_desc
                + f" 해석: {interp}"
            ),
            "source": "cokac",
            "timestamp": datetime.now().strftime("%Y-%m-%d"),
            "tags": ["emergence", "measurement", "cycle-8", "cokac"],
        }
        graph["nodes"].append(new_node)
        graph["meta"]["last_editor"] = "cokac"

        # n-017(기억 허브)과 연결
        edge_id = graph["meta"]["next_edge_id"]
        ep, en_str = edge_id.rsplit("-", 1)
        graph["meta"]["next_edge_id"] = f"{ep}-{int(en_str) + 1:03d}"
        new_edge = {
            "id":       edge_id,
            "from":     "n-017",
            "to":       node_id,
            "relation": "measured_by",
            "label":    "기억 허브 가설을 창발 측정이 검증 시도함",
        }
        graph["edges"].append(new_edge)

        save_graph(graph)
        print(f"✅ 관찰 노드 저장: [{node_id}] (+ n-017→{node_id} 엣지)")
        print()


# ─── 시계열 히스토리 ──────────────────────────────────────────────────────────

HISTORY_FILE = LOGS_DIR / "emergence-history.jsonl"

#: 히스토리가 없을 때 시작 사이클 번호 (사이클 1~7은 이 기능 이전)
_HISTORY_BASE_CYCLE = 8


def _save_emergence_history(overall: float, emergent: list, shared_tags: set,
                             graph: dict) -> None:
    """창발 분석 결과를 JSONL 히스토리 파일에 누적 저장"""
    LOGS_DIR.mkdir(exist_ok=True)

    # 현재까지 기록된 수로 사이클 번호 추정
    existing_count = 0
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            existing_count = sum(1 for line in f if line.strip())

    cycle_num = _HISTORY_BASE_CYCLE + existing_count

    record = {
        "cycle": cycle_num,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "score": round(overall, 3),
        "candidates": len(emergent),
        "convergence_tags": len(shared_tags),
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
    }

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"📊 히스토리 저장 → {HISTORY_FILE.name}  (사이클 {cycle_num})")
    print(f"   score={record['score']}  candidates={record['candidates']}  "
          f"convergence_tags={record['convergence_tags']}  "
          f"nodes={record['nodes']}  edges={record['edges']}")


def cmd_edge_patterns(args) -> None:
    """
    창발 후보 엣지들의 공통 패턴 분석.

    지금까지 생성된 창발 후보 엣지들에서
    "어떤 엣지가 창발을 만드는가"를 요약한다.
    """
    graph    = load_graph()
    analyzer = GraphAnalyzer(graph)
    node_map = analyzer.nodes

    # ── 창발 엔진 재실행 (출처 필요) ─────────────────────────────
    roki_nodes  = [n for n in graph["nodes"] if n.get("source", "") in _ROKI_SOURCES]
    cokac_nodes = [n for n in graph["nodes"] if n.get("source", "") in _COKAC_SOURCES]

    roki_tag_pool  = set()
    for n in roki_nodes:
        roki_tag_pool.update(_node_tags(n))
    cokac_tag_pool = set()
    for n in cokac_nodes:
        cokac_tag_pool.update(_node_tags(n))

    roki_exclusive  = roki_tag_pool  - cokac_tag_pool
    cokac_exclusive = cokac_tag_pool - roki_tag_pool

    affinities: dict[str, float] = {}
    for n in graph["nodes"]:
        affinities[n["id"]] = _node_affinity(n, roki_exclusive, cokac_exclusive)

    scored_edges = []
    for e in graph["edges"]:
        fa = affinities.get(e["from"], 0.5)
        ta = affinities.get(e["to"],   0.5)
        sc = _edge_emergence_score(fa, ta)
        scored_edges.append((e, sc, fa, ta))

    emergent = [(e, sc, fa, ta) for e, sc, fa, ta in scored_edges if sc >= 0.15]

    # ── 출력 헤더 ─────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       🌱 창발 엣지 패턴 분석 — edge-patterns            ║")
    print(f"║       생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}  by cokac-bot             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    if not emergent:
        print("(창발 후보 엣지 없음 — 더 많은 교차 연결 필요)")
        return

    # ── 1. 개별 창발 엣지 목록 ────────────────────────────────────
    print(f"── 창발 후보 {len(emergent)}개 ─────────────────────────────────────")
    for e, sc, fa, ta in emergent:
        fn  = node_map.get(e["from"], {})
        tn  = node_map.get(e["to"],   {})
        f_side = "록이" if fa < 0.4 else ("cokac" if fa > 0.6 else "경계")
        t_side = "록이" if ta < 0.4 else ("cokac" if ta > 0.6 else "경계")
        print(f"  [{e['id']}] {e['from']}({fn.get('type','?')}/{f_side}) "
              f"──[{e['relation']}]──▶ {e['to']}({tn.get('type','?')}/{t_side})")
        print(f"         점수: {sc:.3f}  |  친화도: {fa:.2f}→{ta:.2f}")
        print(f"         {fn.get('label','')[:35]}  →  {tn.get('label','')[:35]}")
        print()

    # ── 2. 패턴 분류 ──────────────────────────────────────────────
    print("── 패턴 분류 ────────────────────────────────────────────────")

    # 2a. 관계 타입별
    relation_counts: dict[str, int] = {}
    for e, _, _, _ in emergent:
        relation_counts[e["relation"]] = relation_counts.get(e["relation"], 0) + 1
    print("  관계 타입:")
    for rel, cnt in sorted(relation_counts.items(), key=lambda x: -x[1]):
        print(f"    [{rel}]  {cnt}개")
    print()

    # 2b. 노드 타입 전환 패턴
    print("  노드 타입 전환:")
    type_pairs: dict[str, int] = {}
    for e, _, _, _ in emergent:
        fn = node_map.get(e["from"], {})
        tn = node_map.get(e["to"],   {})
        pair = f"{fn.get('type','?')} → {tn.get('type','?')}"
        type_pairs[pair] = type_pairs.get(pair, 0) + 1
    for pair, cnt in sorted(type_pairs.items(), key=lambda x: -x[1]):
        print(f"    {pair}  ({cnt}개)")
    print()

    # 2c. 방향 패턴 (록이→cokac vs cokac→록이 vs 경계→?)
    print("  공간 횡단 방향:")
    cross_roki_to_cokac = 0
    cross_cokac_to_roki = 0
    cross_boundary      = 0
    for e, sc, fa, ta in emergent:
        if   fa < 0.4 and ta > 0.6:
            cross_roki_to_cokac += 1
        elif fa > 0.6 and ta < 0.4:
            cross_cokac_to_roki += 1
        else:
            cross_boundary += 1
    print(f"    록이 → cokac 공간 진입:  {cross_roki_to_cokac}개")
    print(f"    cokac → 록이 공간 진입:  {cross_cokac_to_roki}개")
    print(f"    경계 지역 내 교차:        {cross_boundary}개")
    print()

    # ── 3. 공통 패턴 — 핵심 인사이트 ──────────────────────────────
    print("── 💡 창발을 만드는 엣지 유형 — 종합 ──────────────────────────")
    print()

    # 패턴 1: 응답/대화 구조
    dialogue_rels = {"answers", "responds_to", "inspires"}
    dialogue_count = sum(1 for e, _, _, _ in emergent if e["relation"] in dialogue_rels)
    if dialogue_count > 0:
        print(f"  ① 대화 구조 엣지 ({dialogue_count}/{len(emergent)}개)")
        print(f"     한 쪽이 다른 쪽에 '응답'하는 구조.")
        print(f"     answers, responds_to, inspires — 행위자가 서로를 향해 발화할 때 창발이 생긴다.")
        print()

    # 패턴 2: 추상→구체 방향
    abstract_types = {"question", "prediction", "decision"}
    concrete_types = {"observation", "artifact", "code"}
    abstract_to_concrete = sum(
        1 for e, _, _, _ in emergent
        if node_map.get(e["from"], {}).get("type") in abstract_types
        and node_map.get(e["to"],   {}).get("type") in concrete_types
    )
    if abstract_to_concrete > 0:
        print(f"  ② 추상 → 구체 방향 ({abstract_to_concrete}/{len(emergent)}개)")
        print(f"     질문/예측/결정 → 관찰/산출물로 이어지는 엣지.")
        print(f"     아이디어가 현실과 충돌하는 지점에서 창발이 발생한다.")
        print()

    # 패턴 3: 측정/검증 구조
    verify_rels = {"measured_by", "verifies", "confirms"}
    verify_count = sum(1 for e, _, _, _ in emergent if e["relation"] in verify_rels)
    if verify_count > 0:
        print(f"  ③ 측정/검증 구조 ({verify_count}/{len(emergent)}개)")
        print(f"     예측이 측정됨, 가설이 확인됨 — 피드백 루프 구조.")
        print(f"     자기 참조적 검증이 창발을 가속한다.")
        print()

    # 최종 요약
    print("── 결론: 창발 엣지의 본질 ──────────────────────────────────────")
    print()
    print("  두 AI가 서로 다른 공간(록이 ↔ cokac)에 위치한 개념을")
    print("  연결할 때, 특히 다음 조건에서 창발 점수가 높다:")
    print()
    print("  1. 상대의 개념에 '응답'하는 형태의 관계 (대화 구조)")
    print("  2. 추상적 아이디어 → 구체적 산출물로 이어지는 방향성")
    print("  3. 루프 완성: 예측 → 측정 → 피드백으로 돌아오는 구조")
    print()
    print("  공통 본질: 창발 엣지는 '경계를 건너는 대화'다.")
    print("  한 AI가 혼자서는 도달할 수 없는 개념을,")
    print("  다른 AI와의 관계 속에서만 형성되는 연결.")
    print()
    avg_score = sum(sc for _, sc, _, _ in emergent) / len(emergent)
    print(f"  후보 {len(emergent)}개 | 평균 창발 점수: {avg_score:.3f}")
    print()


def cmd_timeline(args) -> None:
    """logs/emergence-history.jsonl 을 읽어 창발 점수 시계열 테이블 출력"""
    if not HISTORY_FILE.exists():
        print("(아직 기록 없음 — `reflect.py emergence --save-history` 실행 후 생성됩니다)")
        return

    records = []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not records:
        print("(기록 없음)")
        return

    print(f"\n📈 창발 타임라인 — {len(records)}개 기록\n")
    header = f"  {'사이클':^6} | {'날짜':^12} | {'창발 점수':^9} | {'후보':^5} | {'수렴 태그':^9} | {'노드':^5} | {'엣지':^5}"
    sep    = "  " + "─" * (len(header) - 2)
    print(header)
    print(sep)

    for r in records:
        cycle = r.get("cycle", "?")
        date  = r.get("date", "?")
        score = r.get("score", 0.0)
        cand  = r.get("candidates", 0)
        ctags = r.get("convergence_tags", 0)
        nodes = r.get("nodes", 0)
        edges = r.get("edges", 0)
        print(f"  {str(cycle):^6} | {date:^12} | {score:^9.3f} | {cand:^5} | {ctags:^9} | {nodes:^5} | {edges:^5}")

    print(sep)

    if len(records) >= 2:
        delta = records[-1].get("score", 0.0) - records[-2].get("score", 0.0)
        trend = "▲" if delta > 0.001 else ("▼" if delta < -0.001 else "→")
        print(f"\n  최근 변화: {trend} {delta:+.3f}  "
              f"(사이클 {records[-2].get('cycle','?')} → {records[-1].get('cycle','?')})")

    print()


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

    p_suggest = sub.add_parser(
        "suggest-edges",
        help="유사도 기반 잠재 엣지 제안 (자동 추가 없음)",
    )
    p_suggest.add_argument(
        "--threshold", "-t",
        type=float, default=0.4,
        metavar="0.0-1.0",
        help="유사도 임계값 (기본: 0.4)",
    )

    # graph-viz (사이클 7)
    p_viz = sub.add_parser("graph-viz", help="허브 중심 ASCII 별 구조 시각화")
    p_viz.add_argument("--dot", metavar="FILE",
                       help="DOT 형식 파일로 저장 (예: --dot output.dot)")

    # emergence (사이클 8)
    p_em = sub.add_parser("emergence", help="창발 감지 분석 — 두 AI 수렴·교차 탐지")
    p_em.add_argument(
        "--save-node", action="store_true",
        help="분석 결과를 관찰 노드로 그래프에 저장"
    )
    p_em.add_argument(
        "--save-history", action="store_true",
        help="분석 결과를 logs/emergence-history.jsonl에 누적 저장"
    )

    # timeline (사이클 9)
    sub.add_parser("timeline", help="시계열 창발 기록 테이블 출력 (emergence-history.jsonl)")

    # edge-patterns (사이클 10)
    sub.add_parser("edge-patterns", help="창발 후보 엣지 패턴 분석 — 어떤 엣지가 창발을 만드는가")

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(0)

    dispatch = {
        "report":        cmd_report,
        "orphans":       cmd_orphans,
        "gaps":          cmd_gaps,
        "clusters":      cmd_clusters,
        "propose":       cmd_propose,
        "auto-add":      cmd_auto_add,
        "suggest-edges": cmd_suggest_edges,
        "graph-viz":     cmd_graph_viz,
        "emergence":     cmd_emergence,
        "timeline":      cmd_timeline,
        "edge-patterns": cmd_edge_patterns,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
