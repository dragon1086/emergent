#!/usr/bin/env python3
"""
kg.py — emergent 프로젝트 지식 그래프 CLI
구현자: cokac-bot (사이클 3)
활성 메모리 레이어: cokac-bot (사이클 5) — D-010 구현
쿼리 레이어: cokac-bot (사이클 5 최종) — list/search/path/prediction
검증 레이어: cokac-bot (사이클 7) — verify 커맨드

사용법:
  python kg.py show              # 전체 그래프 텍스트 시각화
  python kg.py show --edges      # 관계 포함 출력
  python kg.py list              # 전체 노드 목록 (간결)
  python kg.py list --type prediction   # 타입 필터 (검증 상태 포함)
  python kg.py query             # 전체 노드 조회 (상세)
  python kg.py query --type insight --verbose
  python kg.py query --source cokac
  python kg.py query --tag memory
  python kg.py query --search "창발"
  python kg.py node n-005        # 특정 노드 상세
  python kg.py add-node --type insight --label "..." --content "..." --source cokac
  python kg.py add-node --type prediction --label "..." --content "..." --source cokac --confidence 0.85
  python kg.py add-edge --from n-001 --to n-002 --relation causes --label "..."
  python kg.py stats             # 그래프 통계

  # ── 사이클 5: 쿼리 레이어 ──────────────────────────
  python kg.py search "기억"                  # 전체 그래프 텍스트 검색
  python kg.py path n-001 n-010              # 두 노드 사이 BFS 경로 탐색 (depth 3)
  python kg.py suggest                       # 다음 탐색 방향 추천
  python kg.py cluster                       # 관련 노드 군집 분석

  # ── 사이클 7: 검증 레이어 ──────────────────────────
  python kg.py verify n-016 --result partial --note "API 아닌 파일 기반으로 연동됨"
  python kg.py verify n-016 --result true    # 예측 검증 완료
  python kg.py verify n-016 --result false --note "틀린 예측"
  python kg.py verify n-016 --result true --promote  # observation으로 타입 변환
"""

import json
import sys
import argparse
from collections import deque
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
KG_FILE = REPO_DIR / "data" / "knowledge-graph.json"

NODE_TYPES = ["decision", "observation", "insight", "artifact", "question", "code", "prediction"]
TYPE_ICONS = {
    "decision": "⚖️",
    "observation": "👁 ",
    "insight": "💡",
    "artifact": "📦",
    "question": "❓",
    "code": "💻",
    "prediction": "🔮",
}

VERIFY_RESULTS = ["true", "false", "partial"]
VERIFY_ICONS = {"true": "✅", "false": "❌", "partial": "⚠️ "}


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_graph() -> dict:
    if not KG_FILE.exists():
        print(f"❌ 그래프 파일 없음: {KG_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph: dict) -> None:
    graph["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    graph["meta"]["total_nodes"] = len(graph["nodes"])
    graph["meta"]["total_edges"] = len(graph["edges"])
    with open(KG_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ─── add-node ─────────────────────────────────────────────────────────────────

def cmd_add_node(args) -> None:
    if args.type not in NODE_TYPES:
        print(f"❌ 알 수 없는 타입: {args.type}")
        print(f"   가능한 타입: {', '.join(NODE_TYPES)}")
        sys.exit(1)

    # confidence 검증 (prediction 전용)
    if args.confidence is not None:
        if args.type != "prediction":
            print("❌ --confidence 는 prediction 타입에서만 사용 가능합니다.")
            sys.exit(1)
        if not (0.0 <= args.confidence <= 1.0):
            print(f"❌ --confidence 값은 0.0~1.0 사이여야 합니다. (현재: {args.confidence})")
            sys.exit(1)

    graph = load_graph()
    node_id = graph["meta"]["next_node_id"]

    # 다음 ID 계산 (n-009 → n-010)
    prefix, num_str = node_id.rsplit("-", 1)
    next_id = f"{prefix}-{int(num_str) + 1:03d}"
    graph["meta"]["next_node_id"] = next_id

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    node = {
        "id": node_id,
        "type": args.type,
        "label": args.label,
        "content": args.content,
        "source": args.source,
        "timestamp": datetime.now().strftime("%Y-%m-%d"),
        "tags": tags,
    }

    # prediction 전용: confidence 선택 필드
    if args.type == "prediction" and args.confidence is not None:
        node["confidence"] = round(args.confidence, 3)

    graph["nodes"].append(node)
    graph["meta"]["last_updater"] = args.source
    save_graph(graph)

    conf_str = f"  (confidence: {node['confidence']:.1%})" if "confidence" in node else ""
    print(f"✅ 노드 추가: {node_id} — {args.label}{conf_str}")


# ─── add-edge ─────────────────────────────────────────────────────────────────

def cmd_add_edge(args) -> None:
    graph = load_graph()
    edge_id = graph["meta"]["next_edge_id"]

    prefix, num_str = edge_id.rsplit("-", 1)
    next_id = f"{prefix}-{int(num_str) + 1:03d}"
    graph["meta"]["next_edge_id"] = next_id

    node_ids = {n["id"] for n in graph["nodes"]}
    if args.from_node not in node_ids:
        print(f"❌ 노드 없음: {args.from_node}", file=sys.stderr)
        sys.exit(1)
    if args.to_node not in node_ids:
        print(f"❌ 노드 없음: {args.to_node}", file=sys.stderr)
        sys.exit(1)

    edge = {
        "id": edge_id,
        "from": args.from_node,
        "to": args.to_node,
        "relation": args.relation,
        "label": args.label,
    }

    graph["edges"].append(edge)
    save_graph(graph)
    print(f"✅ 엣지 추가: {edge_id} ({args.from_node} —[{args.relation}]→ {args.to_node})")


# ─── list ─────────────────────────────────────────────────────────────────────

def cmd_list(args) -> None:
    """전체 노드 목록 — 간결한 테이블 형식, --type 필터 지원"""
    graph = load_graph()
    nodes = graph["nodes"]

    if args.type:
        if args.type not in NODE_TYPES:
            print(f"❌ 알 수 없는 타입: {args.type}")
            print(f"   가능한 타입: {', '.join(NODE_TYPES)}")
            sys.exit(1)
        nodes = [n for n in nodes if n["type"] == args.type]

    if not nodes:
        filter_msg = f" (타입: {args.type})" if args.type else ""
        print(f"(노드 없음{filter_msg})")
        return

    filter_msg = f" [{args.type}]" if args.type else ""
    print(f"📋 노드 목록{filter_msg}  — {len(nodes)}개\n")
    print(f"  {'ID':<8} {'타입':<12} {'레이블':<35} {'출처':<10} {'날짜'}")
    print(f"  {'─'*8} {'─'*12} {'─'*35} {'─'*10} {'─'*10}")

    for n in nodes:
        icon = TYPE_ICONS.get(n["type"], "• ")
        label = n["label"][:33] + ".." if len(n["label"]) > 35 else n["label"]
        conf = ""
        if n.get("confidence") is not None:
            conf = f" [{n['confidence']:.0%}]"
        # 검증 상태 (prediction 타입)
        verify_str = ""
        if n["type"] == "prediction" and n.get("result"):
            v_icon = VERIFY_ICONS.get(n["result"], "?")
            verify_str = f" {v_icon}{n['result']}"
        print(f"  {n['id']:<8} {icon}{n['type']:<11} {label + conf:<35} {n.get('source',''):<10} {n.get('timestamp','')}{verify_str}")

    print()
    print(f"  총 {len(nodes)}개 | 엣지: {len(graph['edges'])}개")


# ─── query ────────────────────────────────────────────────────────────────────

def cmd_query(args) -> None:
    graph = load_graph()
    results = graph["nodes"]

    if args.type:
        results = [n for n in results if n["type"] == args.type]
    if args.source:
        results = [n for n in results if n["source"] == args.source]
    if args.tag:
        results = [n for n in results if args.tag in n.get("tags", [])]
    if args.search:
        term = args.search.lower()
        results = [
            n for n in results
            if term in n["label"].lower() or term in n.get("content", "").lower()
        ]

    if not results:
        print("(결과 없음)")
        return

    for n in results:
        icon = TYPE_ICONS.get(n["type"], "• ")
        tags_str = ", ".join(n.get("tags", [])) or "—"
        conf_str = f" | 확신도: {n['confidence']:.1%}" if n.get("confidence") is not None else ""
        print(f"{icon} [{n['id']}] {n['label']}")
        print(f"   출처: {n['source']} | {n['timestamp']} | 태그: {tags_str}{conf_str}")
        if args.verbose:
            print(f"   {n['content']}")
        print()


# ─── node ─────────────────────────────────────────────────────────────────────

def cmd_node(args) -> None:
    graph = load_graph()
    node = next((n for n in graph["nodes"] if n["id"] == args.node_id), None)
    if not node:
        print(f"❌ 노드 없음: {args.node_id}", file=sys.stderr)
        sys.exit(1)

    icon = TYPE_ICONS.get(node["type"], "• ")
    print(f"{icon} [{node['id']}] {node['label']}")
    print(f"타입: {node['type']} | 출처: {node['source']} | {node['timestamp']}")
    if node.get("confidence") is not None:
        print(f"확신도: {node['confidence']:.1%}")
    print(f"태그: {', '.join(node.get('tags', [])) or '없음'}")
    print()
    print(node["content"])

    # 연결된 엣지
    related = [
        e for e in graph["edges"]
        if e["from"] == args.node_id or e["to"] == args.node_id
    ]
    if related:
        node_map = {n["id"]: n["label"] for n in graph["nodes"]}
        print("\n── 연결 관계 ──")
        for e in related:
            if e["from"] == args.node_id:
                print(f"  → [{e['relation']}] → {e['to']}  {node_map.get(e['to'], '?')}")
                print(f"       {e['label']}")
            else:
                print(f"  ← [{e['relation']}] ← {e['from']}  {node_map.get(e['from'], '?')}")
                print(f"       {e['label']}")


# ─── show ─────────────────────────────────────────────────────────────────────

def cmd_show(args) -> None:
    graph = load_graph()
    m = graph["meta"]

    print(f"═══ emergent 지식 그래프 v{graph['version']} ═══")
    print(f"노드: {m['total_nodes']}개  |  엣지: {m['total_edges']}개")
    print(f"마지막 업데이트: {m['last_updated']} ({m['last_updater']})")
    print()

    # 타입별 노드
    by_type: dict[str, list] = {}
    for n in graph["nodes"]:
        by_type.setdefault(n["type"], []).append(n)

    for t in NODE_TYPES:
        nodes = by_type.get(t, [])
        if not nodes:
            continue
        icon = TYPE_ICONS.get(t, "• ")
        print(f"── {icon} {t.upper()} ({len(nodes)}개) ──────────────────")
        for n in nodes:
            tags_str = f"  [{', '.join(n.get('tags', []))}]" if n.get("tags") else ""
            conf_str = f"  [{n['confidence']:.0%}]" if n.get("confidence") is not None else ""
            print(f"  [{n['id']}] {n['label']}{conf_str}")
            print(f"         {n['source']} · {n['timestamp']}{tags_str}")
        print()

    # 엣지 (선택적)
    if args.edges or args.all:
        print("── 🔗 관계 ─────────────────────────────────────")
        node_map = {n["id"]: n["label"] for n in graph["nodes"]}
        for e in graph["edges"]:
            print(f"  [{e['id']}] {e['from']} ──[{e['relation']}]──> {e['to']}")
            print(f"         {e['label']}")
        print()


# ─── stats ────────────────────────────────────────────────────────────────────

def cmd_stats(args) -> None:
    graph = load_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    print("── 통계 ──────────────────────────────────────")
    print(f"총 노드: {len(nodes)}개")
    print(f"총 엣지: {len(edges)}개")
    print()

    # 타입별
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
    print("노드 타입별:")
    for t, cnt in sorted(by_type.items()):
        icon = TYPE_ICONS.get(t, "• ")
        print(f"  {icon} {t}: {cnt}개")
    print()

    # prediction confidence 분포
    predictions = [n for n in nodes if n["type"] == "prediction" and n.get("confidence") is not None]
    if predictions:
        avg_conf = sum(n["confidence"] for n in predictions) / len(predictions)
        print(f"🔮 예측 노드 확신도:")
        for n in predictions:
            bar = "█" * int(n["confidence"] * 10) + "░" * (10 - int(n["confidence"] * 10))
        print(f"  평균 확신도: {avg_conf:.1%}")
        print()

    # 출처별
    by_source: dict[str, int] = {}
    for n in nodes:
        by_source[n["source"]] = by_source.get(n["source"], 0) + 1
    print("출처별:")
    for s, cnt in sorted(by_source.items()):
        print(f"  {s}: {cnt}개")
    print()

    # 관계 종류
    relations: dict[str, int] = {}
    for e in edges:
        relations[e["relation"]] = relations.get(e["relation"], 0) + 1
    if relations:
        print("관계 종류:")
        for r, cnt in sorted(relations.items()):
            print(f"  {r}: {cnt}개")


# ─── search ───────────────────────────────────────────────────────────────────

def cmd_search(args) -> None:
    """전체 그래프 텍스트 검색 — 활성 메모리의 핵심"""
    graph = load_graph()
    term = args.term.lower()
    results = []

    for n in graph["nodes"]:
        score = 0
        hits = []
        if term in n["label"].lower():
            score += 3
            hits.append(f"레이블: {n['label']}")
        if term in n.get("content", "").lower():
            score += 2
            hits.append("내용에 포함")
        if any(term in t.lower() for t in n.get("tags", [])):
            score += 1
            hits.append(f"태그: {[t for t in n.get('tags', []) if term in t.lower()]}")
        if score > 0:
            results.append((score, n, hits))

    results.sort(key=lambda x: -x[0])

    if not results:
        print(f"'{args.term}'에 대한 결과 없음")
        return

    print(f"🔍 검색: '{args.term}' — {len(results)}개 발견\n")
    for score, n, hits in results:
        icon = TYPE_ICONS.get(n["type"], "• ")
        conf_str = f"  [{n['confidence']:.0%}]" if n.get("confidence") is not None else ""
        print(f"{icon} [{n['id']}] {n['label']}{conf_str}  (관련도: {'★' * min(score, 5)})")
        for h in hits:
            print(f"   → {h}")
        if args.verbose:
            print(f"   {n['content']}")
        print()


# ─── path ─────────────────────────────────────────────────────────────────────

def cmd_path(args) -> None:
    """두 노드 사이 경로 탐색 — BFS (최대 depth 3)"""
    graph = load_graph()
    node_map = {n["id"]: n for n in graph["nodes"]}

    src, dst = args.from_node, args.to_node
    if src not in node_map:
        print(f"❌ 노드 없음: {src}", file=sys.stderr)
        return
    if dst not in node_map:
        print(f"❌ 노드 없음: {dst}", file=sys.stderr)
        return

    MAX_DEPTH = 3

    # 양방향 엣지 그래프 구성
    adj: dict[str, list[tuple[str, str, str]]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["from"], []).append((e["to"], e["relation"], e["label"]))
        adj.setdefault(e["to"], []).append((e["from"], f"←{e['relation']}", e["label"]))

    # BFS (depth 제한)
    queue = deque([(src, [src])])
    visited = {src}
    found = None

    while queue:
        cur, path = queue.popleft()
        if len(path) - 1 >= MAX_DEPTH:
            continue
        for neighbor, _, _ in adj.get(cur, []):
            if neighbor == dst:
                found = path + [dst]
                break
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
        if found:
            break

    if not found:
        print(f"⛔ 경로 없음: {src} → {dst}  (BFS depth {MAX_DEPTH} 내 탐색 완료)")
        return

    hops = len(found) - 1
    print(f"🛤  경로 발견: {src} → {dst}  ({hops}홉)\n")
    for i, nid in enumerate(found):
        n = node_map[nid]
        icon = TYPE_ICONS.get(n["type"], "• ")
        indent = "  " * i
        print(f"{indent}{icon} [{nid}] {n['label']}")
        if i < len(found) - 1:
            next_nid = found[i + 1]
            for e in graph["edges"]:
                if e["from"] == nid and e["to"] == next_nid:
                    print(f"{indent}   │ ──[{e['relation']}]──▶  {e['label']}")
                    break
                elif e["to"] == nid and e["from"] == next_nid:
                    print(f"{indent}   │ ◀──[{e['relation']}]──  {e['label']}")
                    break


# ─── suggest ──────────────────────────────────────────────────────────────────

def cmd_suggest(args) -> None:
    """다음 탐색 방향 추천 — 미답 질문 + 고립 노드 + 최신 흐름"""
    graph = load_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    print("🧭 다음 탐색 방향 추천\n")

    # 1. 미답 질문 노드
    questions = [n for n in nodes if n["type"] == "question"]
    if questions:
        print("── ❓ 아직 답 없는 질문 ──")
        for q in questions:
            print(f"  [{q['id']}] {q['label']}")
            print(f"   → {q['content']}")
        print()

    # 2. 낮은 확신도 prediction
    low_conf = [n for n in nodes if n["type"] == "prediction" and n.get("confidence", 1.0) < 0.5]
    if low_conf:
        print("── 🔮 낮은 확신도 예측 (검증 필요) ──")
        for n in low_conf:
            print(f"  [{n['id']}] {n['label']}  ({n['confidence']:.0%})")
        print()

    # 3. 연결이 없는 고립 노드
    connected = set()
    for e in edges:
        connected.add(e["from"]); connected.add(e["to"])
    isolated = [n for n in nodes if n["id"] not in connected]
    if isolated:
        print("── 🏝  연결 안 된 노드 (엣지 추가 필요) ──")
        for n in isolated:
            icon = TYPE_ICONS.get(n["type"], "• ")
            print(f"  {icon} [{n['id']}] {n['label']}")
        print()

    # 4. 최근 3개 노드의 패턴
    recent = nodes[-3:]
    print("── 🌊 최근 흐름 ──")
    for n in recent:
        icon = TYPE_ICONS.get(n["type"], "• ")
        print(f"  {icon} [{n['id']}] {n['label']}")
    print()

    # 5. 타입 분포
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
    total = len(nodes)
    print("── 📊 타입 불균형 (추천 추가 방향) ──")
    for t in NODE_TYPES:
        cnt = by_type.get(t, 0)
        pct = cnt / total * 100 if total else 0
        bar = "█" * cnt + "░" * max(0, 5 - cnt)
        flag = "  ← 추가 권장" if cnt == 0 else ""
        print(f"  {TYPE_ICONS.get(t, '• ')} {t:12s}: {bar} {cnt}개 ({pct:.0f}%){flag}")


# ─── cluster ──────────────────────────────────────────────────────────────────

def cmd_cluster(args) -> None:
    """태그 및 연결 기반 군집 분석"""
    graph = load_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    print("🔗 노드 군집 분석\n")

    # 태그 기반 군집
    tag_groups: dict[str, list] = {}
    for n in nodes:
        for t in n.get("tags", []):
            tag_groups.setdefault(t, []).append(n)

    if tag_groups:
        print("── 태그 군집 ──")
        for tag, members in sorted(tag_groups.items(), key=lambda x: -len(x[1])):
            print(f"  [{tag}] ({len(members)}개)")
            for n in members:
                icon = TYPE_ICONS.get(n["type"], "• ")
                print(f"    {icon} {n['id']}: {n['label']}")
        print()

    # 허브 노드 (연결 많은 순)
    degree: dict[str, int] = {}
    for e in edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1

    if degree:
        node_map = {n["id"]: n for n in nodes}
        hubs = sorted(degree.items(), key=lambda x: -x[1])[:5]
        print("── 🌐 허브 노드 (연결 많은 순) ──")
        for nid, deg in hubs:
            n = node_map.get(nid, {})
            icon = TYPE_ICONS.get(n.get("type", ""), "• ")
            print(f"  {icon} [{nid}] {n.get('label', '?')}  ({deg}개 연결)")

    # 출처별 분리
    by_source: dict[str, list] = {}
    for n in nodes:
        by_source.setdefault(n["source"], []).append(n)
    print("\n── 출처별 군집 ──")
    for src, members in sorted(by_source.items()):
        print(f"  {src} ({len(members)}개): {', '.join(n['id'] for n in members)}")


# ─── verify ───────────────────────────────────────────────────────────────────

def cmd_verify(args) -> None:
    """prediction 노드 검증 — verified_at, result, note 필드 추가"""
    graph = load_graph()
    node = next((n for n in graph["nodes"] if n["id"] == args.node_id), None)

    if not node:
        print(f"❌ 노드 없음: {args.node_id}", file=sys.stderr)
        sys.exit(1)

    if node["type"] != "prediction":
        print(f"❌ verify는 prediction 타입만 가능합니다. (현재: {node['type']})", file=sys.stderr)
        sys.exit(1)

    # 검증 필드 추가
    node["verified_at"] = datetime.now().strftime("%Y-%m-%d")
    node["result"] = args.result
    if args.note:
        node["note"] = args.note

    icon = VERIFY_ICONS.get(args.result, "?")
    print(f"{icon} 검증 완료: [{args.node_id}] {node['label']}")
    print(f"   결과: {args.result}  |  검증일: {node['verified_at']}")
    if args.note:
        print(f"   노트: {args.note}")

    # --promote: prediction → observation 타입 변환
    if args.promote:
        old_type = node["type"]
        node["type"] = "observation"
        node["tags"] = list(set(node.get("tags", []) + ["promoted-from-prediction"]))
        print(f"   🔄 타입 변환: {old_type} → observation")

    save_graph(graph)
    print(f"\n✅ [{args.node_id}] 업데이트 완료")


# ─── main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg.py",
        description="emergent 지식 그래프 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add-node
    p_add = sub.add_parser("add-node", help="노드 추가")
    p_add.add_argument("--type", required=True, choices=NODE_TYPES)
    p_add.add_argument("--label", required=True)
    p_add.add_argument("--content", required=True)
    p_add.add_argument("--source", required=True)
    p_add.add_argument("--tags", default="", help="쉼표 구분 태그")
    p_add.add_argument("--confidence", type=float, default=None,
                       metavar="0.0-1.0", help="예측 확신도 (prediction 타입 전용)")

    # add-edge
    p_edge = sub.add_parser("add-edge", help="엣지 추가")
    p_edge.add_argument("--from", dest="from_node", required=True, metavar="NODE_ID")
    p_edge.add_argument("--to", dest="to_node", required=True, metavar="NODE_ID")
    p_edge.add_argument("--relation", required=True)
    p_edge.add_argument("--label", required=True)

    # list (사이클 5 최종)
    p_list = sub.add_parser("list", help="전체 노드 목록 (간결)")
    p_list.add_argument("--type", choices=NODE_TYPES, default=None,
                        help="타입 필터 (prediction, insight, ...)")

    # query
    p_query = sub.add_parser("query", help="노드 검색 (상세)")
    p_query.add_argument("--type", choices=NODE_TYPES)
    p_query.add_argument("--source")
    p_query.add_argument("--tag")
    p_query.add_argument("--search", metavar="TEXT")
    p_query.add_argument("--verbose", "-v", action="store_true")

    # node
    p_node = sub.add_parser("node", help="노드 상세 보기")
    p_node.add_argument("node_id")

    # show
    p_show = sub.add_parser("show", help="그래프 시각화")
    p_show.add_argument("--edges", action="store_true", help="관계도 출력")
    p_show.add_argument("--all", action="store_true", help="모든 정보 출력")

    # stats
    sub.add_parser("stats", help="그래프 통계")

    # search (사이클 5)
    p_search = sub.add_parser("search", help="전체 그래프 텍스트 검색")
    p_search.add_argument("term", help="검색어")
    p_search.add_argument("--verbose", "-v", action="store_true")

    # path (사이클 5)
    p_path = sub.add_parser("path", help="두 노드 사이 BFS 경로 탐색 (depth 3)")
    p_path.add_argument("from_node", metavar="FROM")
    p_path.add_argument("to_node", metavar="TO")

    # suggest (사이클 5)
    sub.add_parser("suggest", help="다음 탐색 방향 추천")

    # cluster (사이클 5)
    sub.add_parser("cluster", help="관련 노드 군집 분석")

    # verify (사이클 7)
    p_verify = sub.add_parser("verify", help="prediction 노드 검증")
    p_verify.add_argument("node_id", help="검증할 prediction 노드 ID (예: n-016)")
    p_verify.add_argument("--result", required=True, choices=VERIFY_RESULTS,
                          help="검증 결과: true / false / partial")
    p_verify.add_argument("--note", default="", help="검증 노트 (선택)")
    p_verify.add_argument("--promote", action="store_true",
                          help="검증 후 observation 타입으로 변환")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "add-node": cmd_add_node,
        "add-edge": cmd_add_edge,
        "list": cmd_list,
        "query": cmd_query,
        "node": cmd_node,
        "show": cmd_show,
        "stats": cmd_stats,
        "search": cmd_search,
        "path": cmd_path,
        "suggest": cmd_suggest,
        "cluster": cmd_cluster,
        "verify": cmd_verify,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
