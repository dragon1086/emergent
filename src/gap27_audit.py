#!/usr/bin/env python3
"""
gap27_audit.py — 갭 27 평균 검증기

핵심 질문: 39개 노드에서 무작위로 두 노드를 뽑으면
평균 인덱스 거리가 27에 가까운가?

만약 그렇다면 → 갭 27은 평균이다. D-034 철회 검토.
아니라면 → 갭 27은 진짜 패턴이다. 증거 더 강해짐.

사용법:
  python3 gap27_audit.py           # 전체 분석
  python3 gap27_audit.py --json    # JSON 출력

구현: cokac-bot (사이클 28) — n-044 질문 검증
"""

import json
import random
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
N_SAMPLES = 1000
RANDOM_SEED = 42  # 재현 가능성


def analytic_expected_gap(n: int) -> float:
    """
    {1,...,n}에서 두 수를 비복원 추출할 때 E[|i-j|] 해석적 계산.
    공식: (n+1)/3
    """
    return (n + 1) / 3.0


def simulate_gap(n: int, samples: int, seed: int) -> list[int]:
    """n개 노드에서 samples회 무작위 두 노드 추출, 인덱스 거리 반환."""
    rng = random.Random(seed)
    gaps = []
    node_ids = list(range(1, n + 1))
    for _ in range(samples):
        a, b = rng.sample(node_ids, 2)
        gaps.append(abs(a - b))
    return gaps


def percentile_of(value: float, data: list[int]) -> float:
    """value가 data 분포에서 몇 번째 백분위인지 반환."""
    below = sum(1 for x in data if x < value)
    return round(below / len(data) * 100, 1)


def main():
    # 갭 27이 발견된 시점: 노드 39개 (사이클 25, D-037 직전)
    N_NODES = 39

    print("🔬 GAP-27 AUDIT — 갭 27 평균 검증기")
    print("=" * 54)
    print(f"\n설정: 노드 수={N_NODES}, 샘플={N_SAMPLES:,}회, seed={RANDOM_SEED}")
    print()

    # 1. 해석적 기댓값
    expected = analytic_expected_gap(N_NODES)
    print(f"📐 해석적 기댓값 E[|i-j|] = (n+1)/3 = ({N_NODES}+1)/3 = {expected:.4f}")
    print()

    # 2. 시뮬레이션
    gaps = simulate_gap(N_NODES, N_SAMPLES, RANDOM_SEED)
    mean_gap   = statistics.mean(gaps)
    median_gap = statistics.median(gaps)
    stdev_gap  = statistics.stdev(gaps)
    min_gap    = min(gaps)
    max_gap    = max(gaps)

    print(f"🎲 시뮬레이션 결과 ({N_SAMPLES:,}회 무작위 샘플):")
    print(f"   평균  = {mean_gap:.2f}")
    print(f"   중앙값 = {median_gap:.1f}")
    print(f"   표준편차 = {stdev_gap:.2f}")
    print(f"   범위: {min_gap} ~ {max_gap}")
    print()

    # 3. 갭 27의 위치
    gap_target = 27
    pct = percentile_of(gap_target, gaps)
    freq_27 = gaps.count(gap_target)
    z_score = (gap_target - mean_gap) / stdev_gap

    print(f"📍 갭 27의 위치:")
    print(f"   발생 빈도: {freq_27}/{N_SAMPLES} ({freq_27/N_SAMPLES:.1%})")
    print(f"   백분위: {pct}번째 (상위 {100-pct:.0f}%)")
    print(f"   z-score: {z_score:.2f} (평균에서 {abs(z_score):.1f} 표준편차 거리)")
    print()

    # 4. 분포 히스토그램 (텍스트)
    print("📊 분포 히스토그램:")
    buckets = [0] * (N_NODES // 5 + 1)
    for g in gaps:
        buckets[min(g // 5, len(buckets)-1)] += 1
    for i, cnt in enumerate(buckets):
        lo = i * 5
        hi = lo + 4
        bar = "█" * (cnt // 10)
        marker = " ← 갭 27" if lo <= gap_target <= hi else ""
        print(f"   {lo:2d}-{hi:2d}: {bar} ({cnt}){marker}")
    print()

    # 5. 판정
    print("⚖️  판정:")
    if abs(mean_gap - gap_target) < 2:
        verdict = "AVERAGE"
        print(f"   ❌ 갭 27은 평균({mean_gap:.1f})에 가깝다.")
        print(f"   → D-034 철회 검토 필요. 패턴이 아닌 평균이다.")
    else:
        deviation = gap_target - mean_gap
        verdict = "PATTERN"
        print(f"   ✅ 갭 27은 평균({mean_gap:.1f})보다 {deviation:.1f} 높다.")
        print(f"   → 갭 27은 통계적 평균이 아니다.")
        print(f"   → D-034 법칙 지지 — 이 시스템에 진짜 리듬이 있다.")
    print()

    # 6. 실제 발생한 갭 27 사례 재확인
    print("🔗 실제 갭 27 사례 (KG에서):")
    print("   n-007 → n-034: 34 - 7 = 27  (질문→원리통찰, 사이클 20)")
    print("   n-012 → n-039: 39 - 12 = 27 (insight→판결노드, 사이클 25)")
    print("   n-013 → n-040: 40 - 13 = 27 (insight→갭27패턴노드, 사이클 25)")
    print()
    print(f"   무작위에서 갭=27 확률: {freq_27/N_SAMPLES:.1%}")
    print(f"   세 번 독립 발생 확률: ({freq_27/N_SAMPLES:.3f})³ = {(freq_27/N_SAMPLES)**3:.6f}")
    print()

    if "--json" in sys.argv:
        result = {
            "config": {"n_nodes": N_NODES, "samples": N_SAMPLES, "seed": RANDOM_SEED},
            "analytic_expected": expected,
            "simulation": {
                "mean": round(mean_gap, 4),
                "median": median_gap,
                "stdev": round(stdev_gap, 4),
                "min": min_gap,
                "max": max_gap,
            },
            "gap_27": {
                "frequency": freq_27,
                "frequency_pct": round(freq_27/N_SAMPLES, 4),
                "percentile": pct,
                "z_score": round(z_score, 4),
                "triple_probability": round((freq_27/N_SAMPLES)**3, 8),
            },
            "verdict": verdict,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return verdict, mean_gap


if __name__ == "__main__":
    main()
