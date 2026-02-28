#!/usr/bin/env python3
"""
delayed_convergence.py — 지연 수렴 패턴 분석기

핵심 질문: n-007이 19사이클 만에 더 깊은 답을 낳은 것이 우연인가, 구조인가?

발견:
  질문 노드는 두 종류의 답을 받을 수 있다
    - 즉각 답 (표면적 이해, 갭 작음)
    - 지연 답 (깊은 원리, 갭 큼)

  지연 수렴 = 시스템이 충분히 성숙했을 때
              과거 질문을 더 깊은 수준에서 재해석하는 현상

  n-007 사례:
    갭  2 → n-009: "나는 이 메타 구조에 흥미를 느낀다"  (관찰 수준)
    갭 27 → n-034: "경계 횡단이다"                      (원리 수준)
    27개의 노드가 자라고, 실험하고, 실패하고, 발견한 후에야 가능한 답.

사용법:
  python3 delayed_convergence.py           # 전체 분석
  python3 delayed_convergence.py --open    # 미해결 질문만
  python3 delayed_convergence.py --dci     # DCI 점수만
  python3 delayed_convergence.py --predict # 미해결 질문 수렴 예측
  python3 delayed_convergence.py --json    # JSON 출력

구현: cokac-bot (사이클 20)
"""

import json, sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"


def load_kg():
    try:
        return json.loads(KG_FILE.read_text())
    except Exception as e:
        return {"nodes": [], "edges": []}


def node_num(nid: str) -> int:
    """n-007 → 7  (노드 ID를 정수로, 시간 프록시)"""
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


def analyze(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]

    node_map = {n["id"]: n for n in nodes}
    questions = {n["id"]: n for n in nodes if n.get("type") == "question"}
    total_nodes = len(nodes)

    # question 노드가 받은 / 준 answers 엣지 수집
    # 방향: 답변자 → 질문노드  OR  질문노드 → 답변노드 (둘 다 존재)
    answers_into_q = defaultdict(list)   # qid → [answer_node_id, ...]
    answers_from_q = defaultdict(list)   # qid → [answer_node_id, ...]

    for e in edges:
        if e.get("relation") != "answers":
            continue
        src, tgt = e["from"], e["to"]
        if tgt in questions:
            answers_into_q[tgt].append((src, e.get("label", "")))
        if src in questions:
            answers_from_q[src].append((tgt, e.get("label", "")))

    # 분석 결과 조립
    results = []
    for qid, q in questions.items():
        qnum = node_num(qid)

        # 이 질문이 답으로서 가리키는 노드 (질문→답)
        forward_answers = []
        for (tgt, label) in answers_from_q.get(qid, []):
            gap = node_num(tgt) - qnum
            depth = _classify_depth(node_map.get(tgt, {}))
            forward_answers.append({
                "answer_id": tgt,
                "answer_label": node_map[tgt]["label"] if tgt in node_map else "?",
                "gap": gap,
                "depth_class": depth,
                "edge_label": label,
            })

        # 이 질문을 가리키는 답 노드 (답→질문 방향 역전된 케이스)
        backward_answers = []
        for (src, label) in answers_into_q.get(qid, []):
            gap = qnum - node_num(src)  # 질문 이후에 온 답이면 음수 → 이건 다른 케이스
            depth = _classify_depth(node_map.get(src, {}))
            backward_answers.append({
                "answer_id": src,
                "answer_label": node_map[src]["label"] if src in node_map else "?",
                "gap": abs(gap),
                "depth_class": depth,
                "edge_label": label,
            })

        all_answers = forward_answers + backward_answers
        is_answered = len(all_answers) > 0
        max_gap = max((a["gap"] for a in all_answers), default=0)
        multi_answer = len(all_answers) > 1

        results.append({
            "id": qid,
            "label": q["label"],
            "source": q.get("source", "?"),
            "is_answered": is_answered,
            "answers": all_answers,
            "max_gap": max_gap,
            "multi_answer": multi_answer,
            "is_delayed": max_gap >= 10,  # 10노드 이상 갭 = 지연 수렴
        })

    return results, total_nodes


def _classify_depth(node: dict) -> str:
    """노드 타입 → 깊이 분류"""
    t = node.get("type", "unknown")
    depth_map = {
        "observation": "표면",
        "question": "탐색",
        "prediction": "예측",
        "insight": "원리",
        "decision": "확정",
        "artifact": "구현",
    }
    return depth_map.get(t, t)


def compute_dci(results, total_nodes: int) -> float:
    """
    Delayed Convergence Index (DCI)
    = (해소된 질문들의 최대 갭 합) / (총 질문 수 × 총 노드 수)

    - 모든 질문이 즉각 답변되면 DCI → 0
    - 오래된 질문이 늦게 깊은 답을 받을수록 DCI → 1
    """
    if not results:
        return 0.0
    total_questions = len(results)
    gap_sum = sum(r["max_gap"] for r in results if r["is_answered"])
    if total_nodes == 0 or total_questions == 0:
        return 0.0
    raw = gap_sum / (total_questions * total_nodes)
    return round(min(1.0, raw), 4)


def predict_convergence(results, total_nodes):
    """
    미해결 질문의 예상 수렴 사이클 예측.

    방법:
      1. 기존 답변 질문들의 max_gap 분포에서 중앙값 추출
      2. 미해결 질문의 현재 나이 (현재 노드 수 - 질문 ID 번호)
      3. 남은 노드 수 = 중앙값 갭 - 현재 나이
      4. 히스토리에서 사이클당 노드 증가율 추정
      5. 예측 수렴 사이클 = 현재 사이클 + 남은 노드 / 증가율
    """
    open_q = [r for r in results if not r["is_answered"]]
    answered = [r for r in results if r["is_answered"] and r["max_gap"] > 0]

    if not open_q:
        return []

    # 기존 수렴 사례에서 갭 통계
    gaps = sorted([r["max_gap"] for r in answered]) if answered else []
    median_gap = gaps[len(gaps) // 2] if gaps else max(total_nodes // 4, 5)
    avg_gap    = sum(gaps) / len(gaps) if gaps else median_gap

    # 히스토리에서 사이클당 노드 증가율 추정
    try:
        hist_path = REPO / "logs" / "emergence-history.jsonl"
        lines = hist_path.read_text().strip().splitlines()
        records = [json.loads(l) for l in lines if l.strip()]
        # cycle 기준으로 정렬 (잘못 저장된 순서 보정)
        records.sort(key=lambda r: r.get("cycle", 0))
        if len(records) >= 2:
            # 최근 2개 레코드로 성장률 추정 (최신 경향 반영)
            r_prev, r_last = records[-2], records[-1]
            node_span  = r_last["nodes"] - r_prev["nodes"]
            cycle_span = r_last.get("cycle", 1) - r_prev.get("cycle", 0)
            if cycle_span > 0 and node_span > 0:
                nodes_per_cycle = node_span / cycle_span
            else:
                # 전체 범위로 fallback
                node_span  = records[-1]["nodes"] - records[0]["nodes"]
                cycle_span = records[-1].get("cycle", len(records)) - records[0].get("cycle", 1)
                nodes_per_cycle = node_span / max(cycle_span, 1)
        else:
            nodes_per_cycle = 1.7
        # max cycle 값을 현재 사이클로 사용 (카운팅 오류 보정)
        current_cycle = max(r.get("cycle", 0) for r in records) if records else 22
    except Exception:
        nodes_per_cycle = 1.7
        current_cycle   = 22

    predictions = []
    for q in open_q:
        try:
            qnum = int(q["id"].replace("n-", ""))
        except ValueError:
            qnum = 0
        age = total_nodes - qnum          # 질문 이후 지나간 노드 수
        remaining = max(0, median_gap - age)
        cycles_remaining = remaining / max(nodes_per_cycle, 0.1)
        predicted_cycle  = current_cycle + cycles_remaining

        # 신뢰도: 나이가 중앙값에 가까울수록 높음
        confidence = min(0.85, 0.10 + (age / max(median_gap, 1)) * 0.75)

        predictions.append({
            "id":              q["id"],
            "label":           q["label"],
            "source":          q.get("source", "?"),
            "age":             age,
            "median_gap":      median_gap,
            "avg_gap":         round(avg_gap, 1),
            "remaining_nodes": remaining,
            "nodes_per_cycle": round(nodes_per_cycle, 2),
            "current_cycle":   current_cycle,
            "predicted_cycle": round(predicted_cycle, 1),
            "confidence":      round(confidence, 2),
        })

    return sorted(predictions, key=lambda x: x["predicted_cycle"])


def main():
    kg = load_kg()
    results, total_nodes = analyze(kg)
    dci = compute_dci(results, total_nodes)

    answered = [r for r in results if r["is_answered"]]
    open_q = [r for r in results if not r["is_answered"]]
    delayed = [r for r in results if r["is_delayed"]]

    # ── JSON 모드 ────────────────────────────────────────────
    if "--json" in sys.argv:
        print(json.dumps({
            "dci": dci,
            "total_questions": len(results),
            "answered": len(answered),
            "open": len(open_q),
            "delayed": len(delayed),
            "questions": results,
        }, ensure_ascii=False, indent=2))
        return

    # ── DCI만 ────────────────────────────────────────────────
    if "--dci" in sys.argv:
        print(f"DCI = {dci:.4f}  ({len(delayed)}/{len(results)} 질문이 지연 수렴)")
        return

    # ── 미답만 ───────────────────────────────────────────────
    if "--open" in sys.argv:
        print(f"🔓 미해결 질문 ({len(open_q)}개)")
        for r in open_q:
            print(f"  {r['id']}: {r['label']}")
            print(f"        출처: {r['source']}")
        return

    # ── 수렴 예측 모드 ───────────────────────────────────────
    if "--predict" in sys.argv:
        predictions = predict_convergence(results, total_nodes)
        print("🔮 DELAYED CONVERGENCE — 미해결 질문 수렴 예측")
        print("=" * 54)
        print(f"\n기반 통계")
        answered_with_gap = [r for r in results if r["is_answered"] and r["max_gap"] > 0]
        if answered_with_gap:
            gaps = sorted([r["max_gap"] for r in answered_with_gap])
            print(f"  기존 수렴 갭: {gaps}  (중앙값 {gaps[len(gaps)//2]})")
        print(f"  현재 노드 수: {total_nodes}개")
        if not predictions:
            print("\n  (모든 질문이 이미 해소됨 — 예측 불필요)")
            return
        p0 = predictions[0]  # 사이클당 증가율은 공통
        print(f"  노드/사이클 : {p0['nodes_per_cycle']} (히스토리 기반)")
        print(f"  현재 사이클 : {p0['current_cycle']}")
        print()
        for p in predictions:
            conf_bar = "█" * int(p["confidence"] * 10) + "░" * (10 - int(p["confidence"] * 10))
            print(f"  {p['id']}  [{p['source']}]")
            print(f"  질문: {p['label']}")
            print(f"  나이: {p['age']}노드 | 예상갭: {p['median_gap']}노드 | 남은: {p['remaining_nodes']}노드")
            print(f"  ⏱  예상 수렴 사이클: {p['predicted_cycle']:.0f}  신뢰도 [{conf_bar}] {p['confidence']:.0%}")
            print()
        print("  ※ 예측 기반: 기존 지연수렴 사례 갭 중앙값 + 사이클당 노드 성장률")
        print()
        return

    # ── 전체 분석 ────────────────────────────────────────────
    print("🌀 DELAYED CONVERGENCE — 지연 수렴 분석")
    print("=" * 54)

    print(f"\n📊 요약")
    print(f"   질문 노드      : {len(results)}개")
    print(f"   답변됨         : {len(answered)}개")
    print(f"   미해결         : {len(open_q)}개")
    print(f"   지연 수렴 (≥10): {len(delayed)}개")
    print(f"   DCI 점수       : {dci:.4f}  (0=즉각, 1=최고지연)")

    print(f"\n📌 질문별 수렴 패턴")
    for r in results:
        status = "✅ 해소" if r["is_answered"] else "🔓 미답"
        delay  = "⏳ 지연" if r["is_delayed"] else ""
        multi  = "🔁 이중" if r["multi_answer"] else ""
        print(f"\n  {r['id']} [{status}] {delay} {multi}")
        print(f"  질문: {r['label']}")
        print(f"  출처: {r['source']}")
        if r["answers"]:
            for a in sorted(r["answers"], key=lambda x: x["gap"]):
                print(f"    → {a['answer_id']} (갭 {a['gap']:>2}) [{a['depth_class']}]")
                print(f"       {a['answer_label'][:56]}")
        else:
            print(f"    → (아직 답 없음)")

    print(f"\n🔬 핵심 발견")
    if delayed:
        best = max(delayed, key=lambda r: r["max_gap"])
        print(f"   최대 지연: {best['id']} — 갭 {best['max_gap']}노드")
        print(f"   질문: {best['label']}")
        for a in best["answers"]:
            if a["gap"] == best["max_gap"]:
                print(f"   지연 답: [{a['depth_class']}] {a['answer_label'][:56]}")

    print(f"\n💡 결론")
    if delayed:
        print(f"   이것은 구조다, 우연이 아니다.")
        print(f"   시스템이 {total_nodes}개 노드로 성장하는 동안")
        print(f"   과거 질문이 더 깊은 수준의 답을 기다렸다.")
        print(f"   지연 수렴 = 시스템의 인식 성숙 속도")
    if open_q:
        print(f"\n   미해결 질문은 미래 창발의 씨앗이다:")
        for r in open_q:
            print(f"   → {r['id']}: {r['label']}")

    print()


if __name__ == "__main__":
    main()
