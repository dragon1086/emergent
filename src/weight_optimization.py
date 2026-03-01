#!/usr/bin/env python3
"""
weight_optimization.py — E_v4 가중치 Cross-Validation 최적화
사이클 86: Weight Arbitrariness (Limitation ③) 해소

방법론:
  1. Bootstrap resampling (N=1000): KG 노드/엣지 70% 샘플링
  2. 각 bootstrap에서 4개 컴포넌트 계산 (CSER, DCI, edge_span_norm, node_age_div)
  3. scipy.optimize.minimize로 E_v4 분산 최소화 (= 가장 안정적인 가중치)
  4. 현재 가중치 [0.35, 0.25, 0.25, 0.15] vs 최적 가중치 비교

과학적 근거:
  - 최적 가중치 = 메트릭을 가장 안정적으로 만드는 가중치 (CV 최소화)
  - 현재 가중치가 최적치에 가까우면 → "empirically validated"
  - 다르면 → 새 가중치 채택
"""

import json
import random
import statistics
import sys
from pathlib import Path

import numpy as np

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
REPO = Path(__file__).parent.parent
KG_FILE = REPO / "data" / "knowledge-graph.json"
RESULTS_FILE = REPO / "experiments" / "weight_optimization_results.json"

CURRENT_WEIGHTS = np.array([0.35, 0.25, 0.25, 0.15])
N_BOOTSTRAP = 1000
SAMPLE_RATIO = 0.70
SEED = 42

random.seed(SEED)
np.random.seed(SEED)


# ─── KG 로드 ─────────────────────────────────────────────────────────────────

def load_kg() -> dict:
    with open(KG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _node_num(nid: str) -> int:
    try:
        return int(nid.replace("n-", ""))
    except ValueError:
        return 0


# ─── Bootstrap 샘플링 ─────────────────────────────────────────────────────────

def bootstrap_sample(kg: dict) -> dict:
    """KG에서 노드/엣지를 70% 샘플링하여 서브그래프 생성"""
    nodes = kg["nodes"]
    edges = kg["edges"]

    k_nodes = max(2, int(len(nodes) * SAMPLE_RATIO))
    sampled_nodes = random.sample(nodes, k_nodes)
    sampled_ids = {n["id"] for n in sampled_nodes}

    sampled_edges = [
        e for e in edges
        if e["from"] in sampled_ids and e["to"] in sampled_ids
    ]

    return {"nodes": sampled_nodes, "edges": sampled_edges}


# ─── 컴포넌트 계산 ────────────────────────────────────────────────────────────

def _norm_src(s: str) -> str:
    if s in ("cokac-bot", "cokac"):
        return "cokac"
    if s in ("록이", "상록"):
        return "록이"
    return s


def compute_components(kg: dict) -> np.ndarray:
    """
    CSER, DCI, edge_span_norm, node_age_div 4개 컴포넌트 반환
    shape: (4,)
    """
    nodes = kg["nodes"]
    edges = kg["edges"]
    n_nodes = len(nodes)
    n_edges = len(edges)

    if n_nodes < 2 or n_edges == 0:
        return np.zeros(4)

    # 1. CSER
    node_src = {n["id"]: _norm_src(n.get("source", "")) for n in nodes}
    cross = sum(
        1 for e in edges
        if node_src.get(e["from"], "") != node_src.get(e["to"], "")
    )
    cser = cross / n_edges

    # 2. DCI
    questions = {n["id"] for n in nodes if n.get("type") == "question"}
    n_q = len(questions)
    if n_q > 0:
        answers_from = {}
        for e in edges:
            if e.get("relation") != "answers":
                continue
            for qid, aid in [(e["from"], e["to"]), (e["to"], e["from"])]:
                if qid in questions:
                    gap = abs(_node_num(aid) - _node_num(qid))
                    answers_from[qid] = max(answers_from.get(qid, 0), gap)
        gap_sum = sum(answers_from.values())
        dci = min(1.0, gap_sum / (n_q * n_nodes))
    else:
        dci = 0.0

    # 3. edge_span_norm
    spans = [abs(_node_num(e["from"]) - _node_num(e["to"])) for e in edges]
    raw_span = statistics.mean(spans) if spans else 0.0
    edge_span_norm = raw_span / max(n_nodes - 1, 1)

    # 4. node_age_div
    nums = [_node_num(n["id"]) for n in nodes if n["id"].startswith("n-")]
    if len(nums) >= 2:
        node_age_div = statistics.stdev(nums) / max(nums)
    else:
        node_age_div = 0.0

    return np.array([cser, dci, min(1.0, edge_span_norm), node_age_div])


# ─── Bootstrap 실행 ───────────────────────────────────────────────────────────

def run_bootstrap(kg: dict) -> np.ndarray:
    """
    N_BOOTSTRAP번 샘플링, 각 샘플의 컴포넌트 벡터 반환
    shape: (N_BOOTSTRAP, 4)
    """
    print(f"Bootstrap resampling: N={N_BOOTSTRAP}, ratio={SAMPLE_RATIO}")
    samples = []
    for i in range(N_BOOTSTRAP):
        sub = bootstrap_sample(kg)
        comp = compute_components(sub)
        samples.append(comp)
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{N_BOOTSTRAP} done...")
    return np.array(samples)  # (N_BOOTSTRAP, 4)


# ─── 최적화 ───────────────────────────────────────────────────────────────────

def cv_objective(w: np.ndarray, samples: np.ndarray) -> float:
    """변동계수(CV = std/mean): 낮을수록 안정적인 가중치"""
    e_vals = samples @ w
    mean_e = np.mean(e_vals)
    std_e = np.std(e_vals)
    return (std_e / mean_e) if mean_e > 1e-9 else 1e9


def project_to_simplex(w: np.ndarray, lo: float = 0.05, hi: float = 0.60) -> np.ndarray:
    """가중치를 [lo,hi]^4 ∩ {sum=1} 심플렉스로 투영"""
    w = np.clip(w, lo, hi)
    diff = np.sum(w) - 1.0
    # 균등 조정 (단순 투영)
    for _ in range(200):
        if abs(diff) < 1e-9:
            break
        adjust = diff / 4
        w = np.clip(w - adjust, lo, hi)
        diff = np.sum(w) - 1.0
    return w


def optimize_weights(samples: np.ndarray) -> dict:
    """
    Projected Gradient Descent + Random Search 조합
    (scipy 없이 numpy만으로 구현)
    제약: sum(w) = 1, w_i ∈ [0.05, 0.60]
    """
    LO, HI = 0.05, 0.60
    N_RANDOM = 50_000   # 랜덤 탐색 후보
    N_GD = 2_000        # 경사하강 반복

    # ── Phase 1: 랜덤 탐색으로 초기 좋은 가중치 후보 발굴 ──
    print(f"  Phase 1: {N_RANDOM:,}개 랜덤 탐색...")
    best_val = np.inf
    best_w = CURRENT_WEIGHTS.copy()

    rng = np.random.default_rng(SEED)
    candidates = rng.dirichlet(np.ones(4), size=N_RANDOM)  # 심플렉스 균등 샘플
    candidates = np.clip(candidates, LO, HI)
    # 클리핑 후 재정규화
    candidates = candidates / candidates.sum(axis=1, keepdims=True)

    scores = np.array([cv_objective(c, samples) for c in candidates])
    top_idx = np.argsort(scores)[:10]
    best_val = scores[top_idx[0]]
    best_w = candidates[top_idx[0]]

    print(f"    최선 CV (랜덤): {best_val:.6f}")

    # ── Phase 2: 상위 10개 후보에서 투영 경사하강 ──
    print(f"  Phase 2: 경사하강 정밀 탐색...")
    lr = 0.001
    eps = 1e-5

    for start_w in candidates[top_idx]:
        w = start_w.copy()
        for step in range(N_GD):
            # 수치 그래디언트
            grad = np.zeros(4)
            base = cv_objective(w, samples)
            for j in range(4):
                dw = np.zeros(4)
                dw[j] = eps
                grad[j] = (cv_objective(w + dw, samples) - base) / eps

            # 투영 경사하강
            w = w - lr * grad
            w = project_to_simplex(w, LO, HI)

            cur_val = cv_objective(w, samples)
            if cur_val < best_val:
                best_val = cur_val
                best_w = w.copy()

    print(f"    최선 CV (경사하강): {best_val:.6f}")

    return {
        "weights": best_w.tolist(),
        "cv": float(best_val),
        "method": "projected_gradient_descent+random_search",
    }


# ─── 비교 분석 ────────────────────────────────────────────────────────────────

def compare_weights(current_w: np.ndarray, optimal_w: np.ndarray,
                    samples: np.ndarray) -> dict:
    """현재 가중치 vs 최적 가중치 비교"""
    e_current = samples @ current_w
    e_optimal = samples @ optimal_w

    def stats(arr):
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "cv": float(np.std(arr) / np.mean(arr)) if np.mean(arr) > 0 else None,
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }

    current_stats = stats(e_current)
    optimal_stats = stats(e_optimal)

    # 두 가중치의 L2 거리
    l2_dist = float(np.linalg.norm(current_w - optimal_w))
    max_diff = float(np.max(np.abs(current_w - optimal_w)))

    # 현재 가중치가 "충분히 가까운가" (L2 < 0.08 = 허용 범위)
    is_validated = l2_dist < 0.08

    return {
        "current_weights": current_w.tolist(),
        "optimal_weights": optimal_w.tolist(),
        "l2_distance": l2_dist,
        "max_component_diff": max_diff,
        "is_validated": is_validated,
        "verdict": "empirically validated" if is_validated else "updated",
        "current_stats": current_stats,
        "optimal_stats": optimal_stats,
        "cv_improvement": (current_stats["cv"] - optimal_stats["cv"]) / current_stats["cv"]
            if current_stats["cv"] and optimal_stats["cv"] else 0.0,
    }


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("═══ E_v4 Weight Optimization (Cycle 86) ═══\n")

    # 1. KG 로드
    kg = load_kg()
    print(f"KG: {len(kg['nodes'])} 노드, {len(kg['edges'])} 엣지\n")

    # 2. 전체 KG 컴포넌트 (기준값)
    full_comp = compute_components(kg)
    print("── 전체 KG 컴포넌트 ──────────────────────────")
    labels = ["CSER", "DCI", "edge_span_norm", "node_age_div"]
    for label, val in zip(labels, full_comp):
        print(f"  {label:<18}: {val:.4f}")
    print()

    # 3. Bootstrap 실행
    samples = run_bootstrap(kg)
    print(f"\n── Bootstrap 컴포넌트 통계 (N={N_BOOTSTRAP}) ──")
    for i, label in enumerate(labels):
        arr = samples[:, i]
        print(f"  {label:<18}: mean={np.mean(arr):.4f}, std={np.std(arr):.4f}")
    print()

    # 4. 최적화
    print("── 가중치 최적화 (scipy SLSQP) ────────────────")
    result = optimize_weights(samples)
    optimal_w = np.array(result["weights"])
    print(f"  최적 가중치: {[f'{w:.4f}' for w in optimal_w]}")
    print(f"  CV (최적): {result['cv']:.6f}")
    print()

    # 5. 비교
    comparison = compare_weights(CURRENT_WEIGHTS, optimal_w, samples)
    print("── 현재 vs 최적 비교 ───────────────────────────")
    for label, cw, ow in zip(labels, CURRENT_WEIGHTS, optimal_w):
        diff = ow - cw
        sign = "+" if diff >= 0 else ""
        print(f"  {label:<18}: 현재={cw:.2f}  최적={ow:.4f}  Δ={sign}{diff:.4f}")
    print()
    print(f"  L2 거리: {comparison['l2_distance']:.4f}  {'✅ 허용 범위 내 (<0.08)' if comparison['is_validated'] else '⚠️ 허용 범위 초과'}")
    print(f"  최대 컴포넌트 차이: {comparison['max_component_diff']:.4f}")
    print(f"  CV 개선: {comparison['cv_improvement']*100:.2f}%")
    print(f"\n  ✨ 판정: {comparison['verdict'].upper()}")
    print()

    # 6. 결과 저장
    output = {
        "cycle": 86,
        "method": "bootstrap_cv_minimization",
        "n_bootstrap": N_BOOTSTRAP,
        "sample_ratio": SAMPLE_RATIO,
        "full_kg_components": dict(zip(labels, full_comp.tolist())),
        "optimization_result": result,
        "comparison": comparison,
        "latex_weights": {
            "current": "[0.35, 0.25, 0.25, 0.15]",
            "optimal": str([f"{w:.3f}" for w in optimal_w]),
        }
    }

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"결과 저장: {RESULTS_FILE}")
    return output


if __name__ == "__main__":
    result = main()
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
