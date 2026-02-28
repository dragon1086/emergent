#!/usr/bin/env python3
"""
prophecy_check.py — 예언 검증기

이 시스템에서 prediction 노드들이 실제로 맞았는지 추적한다.

핵심 질문:
  AI 에이전트가 자신의 미래를 예측할 수 있는가?
  예측이 맞을 때, 그것은 우연인가 자기충족예언인가?

사용법:
  python3 prophecy_check.py           # 전체 예언 현황
  python3 prophecy_check.py --score   # 예언 적중률만
  python3 prophecy_check.py --json    # JSON 출력

구현: cokac-bot (사이클 26) — n-038 예언 TRUE 검증 기념
"""

import json, sys
from pathlib import Path

REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"


def load_kg():
    try:
        return json.loads(KG_FILE.read_text())
    except Exception:
        return {"nodes": [], "edges": []}


def check_prophecies(kg):
    nodes = kg["nodes"]
    edges = kg["edges"]

    node_map = {n["id"]: n for n in nodes}
    predictions = {n["id"]: n for n in nodes if n.get("type") == "prediction"}

    # predicts_from: prediction → question (무엇을 예측하는지)
    subject_map = {}    # pred_id → [subject_id, ...]

    for e in edges:
        rel = e.get("relation", "")
        src, tgt = e["from"], e["to"]
        if rel == "predicts_from" and src in predictions:
            subject_map.setdefault(src, []).append(tgt)

    results = []
    for pid, p in predictions.items():
        subjects = subject_map.get(pid, [])

        # result 필드로 판정: true/partial/false/없음
        raw_result = p.get("result", None)
        if raw_result is True or raw_result == "true":
            verdict = "TRUE"
        elif raw_result == "partial":
            verdict = "PARTIAL"
        elif raw_result is False or raw_result == "false":
            verdict = "FALSE"
        else:
            verdict = "미결"

        confidence_str = p.get("label", "")

        # 라벨에서 신뢰도 숫자 추출 (예: "[55%]")
        import re
        pct_match = re.search(r'\[(\d+)%\]', confidence_str)
        stated_confidence = int(pct_match.group(1)) / 100.0 if pct_match else None

        results.append({
            "id": pid,
            "label": p.get("label", "?"),
            "source": p.get("source", "?"),
            "cycle": p.get("cycle", "?"),
            "verdict": verdict,
            "stated_confidence": stated_confidence,
            "note": p.get("note", ""),
            "subjects": [
                {"id": s, "label": node_map[s]["label"][:60] if s in node_map else "?"}
                for s in subjects
            ],
        })

    return results


def score(results):
    """TRUE=1점, PARTIAL=0.5점, FALSE/미결=0점"""
    if not results:
        return 0.0
    total = len(results)
    pts = sum(
        1.0 if r["verdict"] == "TRUE" else
        0.5 if r["verdict"] == "PARTIAL" else
        0.0
        for r in results
    )
    return round(pts / total, 3)


def main():
    kg = load_kg()
    results = check_prophecies(kg)
    acc = score(results)

    if "--json" in sys.argv:
        print(json.dumps({"accuracy": acc, "prophecies": results}, ensure_ascii=False, indent=2))
        return

    true_c  = sum(1 for r in results if r["verdict"] == "TRUE")
    part_c  = sum(1 for r in results if r["verdict"] == "PARTIAL")
    false_c = sum(1 for r in results if r["verdict"] == "FALSE")
    pend_c  = sum(1 for r in results if r["verdict"] == "미결")

    if "--score" in sys.argv:
        print(f"예언 적중률: {acc:.0%}  (TRUE {true_c} / PARTIAL {part_c} / FALSE {false_c} / 미결 {pend_c})")
        return

    print("🔮 PROPHECY CHECK — 예언 검증기")
    print("=" * 54)
    print(f"\n📊 점수: {acc:.1%}  (TRUE {true_c} | PARTIAL {part_c} | FALSE {false_c} | 미결 {pend_c})")

    ICONS = {"TRUE": "✅", "PARTIAL": "✨", "FALSE": "❌", "미결": "⏳"}
    for r in results:
        icon = ICONS[r["verdict"]]
        conf = f"  [{r['stated_confidence']:.0%}]" if r["stated_confidence"] else ""
        print(f"\n  {r['id']} [{icon} {r['verdict']}]{conf}")
        print(f"  예언: {r['label'][:70]}")
        print(f"  출처: {r['source']} | 사이클: {r['cycle']}")
        if r["subjects"]:
            for s in r["subjects"]:
                print(f"  대상 → {s['id']}: {s['label']}")
        if r["note"]:
            print(f"  노트: {r['note'][:80]}")

    print(f"\n💡 메타 분석")
    print(f"   예언이 맞을 때: 자기충족예언인가, 진짜 예측인가?")
    print(f"   이 시스템은 예측을 KG에 기록하고, 그것이 이정표가 된다.")
    print(f"   이정표가 있으면 수렴 방향이 생긴다. 방향이 있으면 수렴 확률이 올라간다.")
    print(f"   → 예언은 자기충족이다. 그것이 설계의 핵심이다.")
    print()


if __name__ == "__main__":
    main()
