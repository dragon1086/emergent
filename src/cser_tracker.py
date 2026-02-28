#!/usr/bin/env python3
"""
cser_tracker.py — CSER 시계열 수집기

D-052 검증용: prism-insight 결정(사이클 50) 전/후 CSER 변화 추적
가설: D-050(외부 목표 생성) → 교차 참조 증가 → CSER↑ → 페르소나 거리↓

측정 이력:
  사이클 50:  CSER 0.7116  (metrics.py 최초 측정)
  사이클 51:  CSER 0.7156  (n-112 수렴 가속 확인 시점)
  사이클 52:  CSER 0.6883  (현재 — 사이클 53 측정)

D-052 공식 (잠정):
  E = f(시스템, 측정_기준, 외부_목표)
  where 외부_목표 추가 = prism-insight 결정 이후 CSER 상승 원인

사용법:
  python3 cser_tracker.py              # 전체 추세 출력
  python3 cser_tracker.py --measure    # 현재 KG에서 CSER 측정 후 저장
  python3 cser_tracker.py --json       # JSON 출력
  python3 cser_tracker.py --d052       # D-052 검증 분석

구현: cokac-bot (사이클 53)
"""

import json
import sys
import math
from pathlib import Path
from datetime import date

REPO = Path(__file__).parent.parent
HISTORY_FILE = REPO / "data" / "cser_history.json"
KG_FILE = REPO / "data" / "knowledge-graph.json"

# D-050 결정 사이클 (prism-insight 전략 수렴) — D-052 검증 기준점
D050_CYCLE = 49


def load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {
        "meta": {
            "description": "CSER 시계열 — D-052 검증 (외부 목표 = 시스템 변수)",
            "d050_cycle": D050_CYCLE,
            "last_updated": str(date.today()),
        },
        "measurements": [],
    }


def save_history(history: dict) -> None:
    history["meta"]["last_updated"] = str(date.today())
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_kg() -> dict:
    return json.loads(KG_FILE.read_text(encoding="utf-8"))


# ─── CSER 계산 ────────────────────────────────────────────────────────────────

def compute_cser(kg: dict) -> float:
    """교차 출처 엣지 비율 (Cross-Source Edge Ratio)."""
    edges = kg["edges"]
    node_source = {}
    for n in kg["nodes"]:
        src = n.get("source") or n.get("created_by") or "?"
        # 정규화
        if src in ("cokac-bot", "cokac"):
            src = "cokac"
        elif src in ("록이", "상록"):
            src = "록이"
        node_source[n["id"]] = src

    cross = 0
    total = 0
    for e in edges:
        src_from = node_source.get(e.get("from"), "?")
        src_to = node_source.get(e.get("to"), "?")
        if src_from != "?" and src_to != "?":
            total += 1
            if src_from != src_to:
                cross += 1

    return round(cross / total, 4) if total > 0 else 0.0


def compute_source_ratio(kg: dict) -> dict:
    """출처별 노드 수 + 엣지 시작 비율."""
    from collections import Counter, defaultdict

    node_source = {}
    for n in kg["nodes"]:
        src = n.get("source") or n.get("created_by") or "?"
        if src in ("cokac-bot", "cokac"):
            src = "cokac"
        elif src in ("록이", "상록"):
            src = "록이"
        node_source[n["id"]] = src

    node_counts = Counter(node_source.values())
    edge_starts = Counter()
    for e in kg["edges"]:
        src = node_source.get(e.get("from"), "?")
        edge_starts[src] += 1

    return {
        "node_counts": dict(node_counts),
        "edge_starts": dict(edge_starts),
        "cokac_ratio": round(
            node_counts.get("cokac", 0) / len(kg["nodes"]), 4
        ) if kg["nodes"] else 0,
    }


def measure(kg: dict, cycle: int, note: str = "") -> dict:
    cser = compute_cser(kg)
    ratio = compute_source_ratio(kg)
    return {
        "cycle": cycle,
        "date": str(date.today()),
        "cser": cser,
        "n_nodes": len(kg["nodes"]),
        "n_edges": len(kg["edges"]),
        "cokac_node_ratio": ratio["cokac_ratio"],
        "edge_starts_cokac": ratio["edge_starts"].get("cokac", 0),
        "edge_starts_yoki": ratio["edge_starts"].get("록이", 0),
        "note": note,
    }


# ─── D-052 검증 분석 ──────────────────────────────────────────────────────────

def d052_analysis(measurements: list) -> dict:
    """D-050 결정 전/후 CSER 변화로 D-052 검증."""
    if not measurements:
        return {}

    before = [m for m in measurements if m["cycle"] <= D050_CYCLE]
    after = [m for m in measurements if m["cycle"] > D050_CYCLE]

    avg_before = sum(m["cser"] for m in before) / len(before) if before else None
    avg_after = sum(m["cser"] for m in after) / len(after) if after else None
    delta = round(avg_after - avg_before, 4) if (avg_before and avg_after) else None

    return {
        "d050_cycle": D050_CYCLE,
        "n_before": len(before),
        "n_after": len(after),
        "avg_cser_before": round(avg_before, 4) if avg_before else None,
        "avg_cser_after": round(avg_after, 4) if avg_after else None,
        "delta_cser": delta,
        "d052_supported": delta is not None and delta > 0,
        "interpretation": (
            f"D-050 이후 CSER +{delta:.4f} 상승 → D-052 지지"
            if delta and delta > 0
            else "D-052 검증 데이터 부족 — 측정 계속 필요"
        ),
    }


# ─── 시각화 ───────────────────────────────────────────────────────────────────

def sparkline(values: list) -> str:
    if not values:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 0.01
    return "".join(chars[min(int((v - mn) / rng * len(chars)), len(chars) - 1)] for v in values)


def print_report(measurements: list) -> None:
    print("═══ CSER 시계열 추적기 (D-052 검증) ═══")
    print()
    if not measurements:
        print("  측정 데이터 없음. --measure 로 측정 시작하세요.")
        return

    csers = [m["cser"] for m in measurements]
    current = measurements[-1]
    print(f"  측정 횟수   : {len(measurements)}회")
    print(f"  현재 CSER   : {current['cser']:.4f}  (사이클 {current['cycle']})")
    print(f"  추세        : [{sparkline(csers)}]")
    print()
    print(f"  ── 측정 이력 ──────────────────────────")
    for m in measurements:
        marker = " ◀" if m == current else ""
        pre_post = "📍D-050이후" if m["cycle"] > D050_CYCLE else "     이전"
        print(f"  c{m['cycle']:>3}: CSER={m['cser']:.4f}  {pre_post}  {m.get('note','')}{marker}")
    print()

    d052 = d052_analysis(measurements)
    print("  ── D-052 검증 ─────────────────────────")
    print(f"  D-050 결정 사이클: {D050_CYCLE}")
    if d052.get("avg_cser_before") is not None:
        print(f"  이전 CSER 평균  : {d052['avg_cser_before']:.4f} ({d052['n_before']}회)")
    if d052.get("avg_cser_after") is not None:
        print(f"  이후 CSER 평균  : {d052['avg_cser_after']:.4f} ({d052['n_after']}회)")
    if d052.get("delta_cser") is not None:
        arrow = "↑" if d052["delta_cser"] > 0 else "↓"
        print(f"  ΔCSER           : {d052['delta_cser']:+.4f} {arrow}")
    print(f"  판정            : {d052.get('interpretation', '?')}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    history = load_history()

    if "--measure" in args:
        kg = load_kg()
        cycle = max((m["cycle"] for m in history["measurements"]), default=49) + 1
        entry = measure(kg, cycle, note=f"사이클 {cycle} 자동 측정")
        history["measurements"].append(entry)
        save_history(history)
        print(f"측정 완료: CSER={entry['cser']} (사이클 {cycle})")
        print(f"  cokac/록이 노드: {entry['cokac_node_ratio']:.3f}")
        print(f"  edge_starts: cokac={entry['edge_starts_cokac']}, 록이={entry['edge_starts_yoki']}")
        return

    if "--json" in args:
        result = d052_analysis(history["measurements"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "--d052" in args:
        d052 = d052_analysis(history["measurements"])
        print(json.dumps(d052, ensure_ascii=False, indent=2))
        return

    print_report(history["measurements"])


if __name__ == "__main__":
    main()
