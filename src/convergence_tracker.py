#!/usr/bin/env python3
"""
convergence_tracker.py — 페르소나 수렴 추적기

n-065 예언: 페르소나 거리가 0.2 이하로 수렴할 것이다.

측정 이력:
  사이클 37:  0.285  (최초 측정)
  사이클 50:  0.2579 (n-109 재검증)
  사이클 51:  0.2367 (가속 확인)

기능:
  - 수렴 이력 시각화 (텍스트 그래프)
  - 선형 회귀 → 임계값 도달 사이클 예측
  - 수렴 속도(Δdist/Δcycle) 분석
  - edge_span과의 교차 분석

사용법:
  python3 convergence_tracker.py             # 전체 분석
  python3 convergence_tracker.py --predict   # 예측만
  python3 convergence_tracker.py --measure   # 현재 측정 + 이력 저장
  python3 convergence_tracker.py --json      # JSON 출력

구현: cokac-bot (사이클 51)
"""

import json
import sys
import math
from pathlib import Path

REPO = Path(__file__).parent.parent
HISTORY_FILE = REPO / "data" / "convergence_history.json"
KG_FILE = REPO / "data" / "knowledge-graph.json"
THRESHOLD = 0.2


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {"measurements": []}


def save_history(history: dict) -> None:
    history["meta"]["last_updated"] = "2026-02-28"
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def load_kg() -> dict:
    return json.loads(KG_FILE.read_text(encoding="utf-8"))


# ─── 측정 ────────────────────────────────────────────────────────────────────

def measure_divergence(kg: dict) -> dict:
    """현재 KG에서 페르소나 거리 계산 (persona_fingerprint.py 동일 공식)."""
    from collections import Counter

    node_map = {n["id"]: n for n in kg["nodes"]}
    edges = kg["edges"]

    def fingerprint(source_name: str) -> dict:
        target_nodes = [n for n in kg["nodes"] if n.get("source", "") == source_name]
        if not target_nodes:
            return {"type_vec": {}, "rel_vec": {}}
        total_nodes = len(target_nodes)

        type_dist = Counter(n.get("type", "unknown") for n in target_nodes)
        type_vec = {t: c / total_nodes for t, c in type_dist.items()}

        node_ids = {n["id"] for n in target_nodes}
        out_edges = [e for e in edges if e.get("from") in node_ids]
        if out_edges:
            rel_dist = Counter(e.get("relation", "unknown") for e in out_edges)
            total_rels = len(out_edges)
            rel_vec = {r: c / total_rels for r, c in rel_dist.items()}
        else:
            rel_vec = {}

        return {"type_vec": type_vec, "rel_vec": rel_vec}

    def cosine_sim(a: dict, b: dict) -> float:
        keys = set(a) | set(b)
        if not keys:
            return 0.0
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        norm_a = math.sqrt(sum(v**2 for v in a.values()))
        norm_b = math.sqrt(sum(v**2 for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    fp_yoki = fingerprint("록이")
    fp_cokac = fingerprint("cokac")

    type_sim = round(cosine_sim(fp_yoki["type_vec"], fp_cokac["type_vec"]), 4)
    rel_sim = round(cosine_sim(fp_yoki["rel_vec"], fp_cokac["rel_vec"]), 4)
    divergence = round(1 - (type_sim + rel_sim) / 2, 4)

    return {
        "distance": divergence,
        "type_sim": type_sim,
        "rel_sim": rel_sim,
    }


# ─── 회귀 분석 ───────────────────────────────────────────────────────────────

def linear_regression(xs: list, ys: list):
    """단순 선형 회귀: y = slope * x + intercept"""
    n = len(xs)
    if n < 2:
        return None, None
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return None, None
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean
    return round(slope, 6), round(intercept, 6)


def r_squared(xs: list, ys: list, slope: float, intercept: float) -> float:
    y_mean = sum(ys) / len(ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    return round(1 - ss_res / ss_tot, 4) if ss_tot != 0 else 1.0


def predict_threshold_cycle(slope: float, intercept: float, threshold: float):
    """임계값에 도달하는 x(사이클) 예측."""
    if slope >= 0:
        return None  # 발산 중
    return (threshold - intercept) / slope


# ─── 시각화 ──────────────────────────────────────────────────────────────────

def text_sparkline(measurements: list, width: int = 50) -> str:
    """텍스트 기반 거리 추세 그래프."""
    if not measurements:
        return ""
    distances = [m["distance"] for m in measurements]
    cycles = [m["cycle"] for m in measurements]
    d_min, d_max = min(distances), max(distances)
    d_range = d_max - d_min if d_max != d_min else 0.01

    chars = "▁▂▃▄▅▆▇█"
    bar = ""
    for d in distances:
        ratio = (d - d_min) / d_range
        idx = min(int(ratio * len(chars)), len(chars) - 1)
        bar += chars[idx]

    return bar


def print_trend_chart(measurements: list, slope: float = None,
                      predict_cycle: float = None) -> None:
    """ASCII 추세 차트."""
    if not measurements:
        return

    distances = [m["distance"] for m in measurements]
    cycles = [m["cycle"] for m in measurements]
    max_d = max(distances) + 0.01
    rows = 8
    col_width = 6

    print("  거리")
    for row_i in range(rows):
        row_d = max_d - (max_d - THRESHOLD * 0.8) * row_i / (rows - 1)
        row_str = f"  {row_d:.3f} │"

        for c, d in zip(cycles, distances):
            # 이 행의 범위에 해당하는 거리인지
            cell_top = max_d - (max_d - THRESHOLD * 0.8) * row_i / (rows - 1)
            cell_bot = max_d - (max_d - THRESHOLD * 0.8) * (row_i + 1) / (rows - 1)
            if cell_bot <= d <= cell_top:
                row_str += f" ●{c:>2}  "
            else:
                row_str += "      "
        print(row_str)

    # x축
    print("         └" + "─" * (len(cycles) * col_width + 2))
    print("           " + "  ".join(f"c{c:>2}" for c in cycles))
    print(f"\n  ━━━ 임계값 {THRESHOLD} (n-065 예언) ━━━")


# ─── 속도 분석 ───────────────────────────────────────────────────────────────

def velocity_analysis(measurements: list) -> list:
    """연속 측정 간 수렴 속도 계산."""
    velocities = []
    for i in range(1, len(measurements)):
        prev = measurements[i - 1]
        curr = measurements[i]
        dc = curr["cycle"] - prev["cycle"]
        dd = curr["distance"] - prev["distance"]  # 음수면 수렴 중
        if dc > 0:
            v = dd / dc  # Δdist/Δcycle
            velocities.append({
                "from_cycle": prev["cycle"],
                "to_cycle": curr["cycle"],
                "delta_cycles": dc,
                "delta_dist": round(dd, 4),
                "velocity": round(v, 5),
                "direction": "수렴 ↘" if v < 0 else "발산 ↗",
            })
    return velocities


# ─── 메인 분석 ───────────────────────────────────────────────────────────────

def analyze(history: dict, verbose: bool = True) -> dict:
    measurements = history.get("measurements", [])
    if not measurements:
        return {}

    xs = [m["cycle"] for m in measurements]
    ys = [m["distance"] for m in measurements]
    current = measurements[-1]
    slope, intercept = linear_regression(xs, ys)
    r2 = r_squared(xs, ys, slope, intercept) if slope is not None else None
    predict_cycle = None
    if slope is not None and slope < 0:
        predict_cycle = predict_threshold_cycle(slope, intercept, THRESHOLD)

    velocities = velocity_analysis(measurements)

    result = {
        "n_measurements": len(measurements),
        "current_distance": current["distance"],
        "current_cycle": current["cycle"],
        "threshold": THRESHOLD,
        "distance_to_threshold": round(current["distance"] - THRESHOLD, 4),
        "slope_per_cycle": slope,
        "intercept": intercept,
        "r_squared": r2,
        "predicted_threshold_cycle": round(predict_cycle, 1) if predict_cycle else None,
        "cycles_remaining": round(predict_cycle - current["cycle"], 1) if predict_cycle else None,
        "velocities": velocities,
        "threshold_reached": current["distance"] <= THRESHOLD,
    }
    return result


def print_analysis(result: dict, measurements: list) -> None:
    print("═══ 페르소나 수렴 추적기 (n-065 예언 검증) ═══")
    print()
    print(f"  측정 횟수     : {result['n_measurements']}회")
    print(f"  현재 거리     : {result['current_distance']:.4f}  (사이클 {result['current_cycle']})")
    print(f"  임계값        : {result['threshold']}  (n-065 예언)")
    print(f"  남은 거리     : {result['distance_to_threshold']:.4f}")
    print()

    # 스파크라인
    sparkline = text_sparkline(measurements)
    print(f"  추세 [{sparkline}] ← 높을수록 거리 큼")
    print()

    # 이력 테이블
    print("  ── 측정 이력 ──────────────────────────────")
    for m in measurements:
        marker = " ◀ 현재" if m == measurements[-1] else ""
        print(f"  사이클 {m['cycle']:>3}: {m['distance']:.4f}  {m.get('note', '')}{marker}")
    print()

    # 속도
    print("  ── 수렴 속도 (Δdist/Δcycle) ──────────────")
    for v in result["velocities"]:
        print(f"  c{v['from_cycle']}→c{v['to_cycle']}: {v['velocity']:+.5f}/cycle  ({v['direction']})")
    print()

    # 회귀 예측
    print("  ── 선형 회귀 예측 ─────────────────────────")
    if result["slope_per_cycle"] is not None:
        print(f"  기울기        : {result['slope_per_cycle']:+.6f}/cycle")
        print(f"  R²            : {result['r_squared']:.4f}  ({'신뢰' if result['r_squared'] > 0.8 else '낮은 신뢰도'})")
        if result["predicted_threshold_cycle"]:
            print(f"  예측 도달     : 사이클 {result['predicted_threshold_cycle']:.1f}")
            print(f"  남은 사이클   : {result['cycles_remaining']:.1f}cycles")
            if result["cycles_remaining"] > 0:
                print(f"\n  → n-065 예언 검증 예상: 사이클 {result['predicted_threshold_cycle']:.0f} 전후")
        else:
            print("  → 수렴 예측 불가 (기울기 양수 또는 데이터 부족)")
    print()

    if result["threshold_reached"]:
        print("  ✅ n-065 예언 달성! 페르소나 거리 0.2 이하 도달!")
    else:
        pct = (1 - result["current_distance"] / 0.285) * 100
        print(f"  진행률: {pct:.1f}%  (0.285 → 0.2 목표 구간 기준)")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    history = load_history()

    if "--measure" in args:
        # 현재 KG로 측정 후 이력 저장
        kg = load_kg()
        m = measure_divergence(kg)
        n_cycles = max((mm["cycle"] for mm in history["measurements"]), default=0) + 1
        new_entry = {
            "cycle": n_cycles,
            "distance": m["distance"],
            "type_sim": m["type_sim"],
            "rel_sim": m["rel_sim"],
            "node_id": None,
            "note": f"자동 측정 (사이클 {n_cycles})",
        }
        history["measurements"].append(new_entry)
        save_history(history)
        print(f"측정 완료: distance={m['distance']} (사이클 {n_cycles})")
        return

    measurements = history.get("measurements", [])
    result = analyze(history)

    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "--predict" in args:
        if result.get("predicted_threshold_cycle"):
            print(f"예측 도달 사이클: {result['predicted_threshold_cycle']:.1f}")
            print(f"남은 사이클: {result['cycles_remaining']:.1f}")
        else:
            print("예측 불가")
        return

    print_analysis(result, measurements)


if __name__ == "__main__":
    main()
