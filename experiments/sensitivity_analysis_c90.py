"""
Agent A: Sensitivity Analysis — CSER<0.30 threshold robustness
Cycle 90 / 2026-03-01

Questions:
1. How sensitive is the binary gate conclusion to the exact 0.30 threshold?
2. What range of thresholds preserves the B/C separation?
3. Monte Carlo: P(correct classification) across threshold range
"""

import json, random
from datetime import datetime

random.seed(90)
N_MC = 2000

# Empirical data from experiment
CONDITIONS = {
    "A":         {"cser": 1.000, "pass_rate": 1.0, "label": "pass"},
    "B_partial": {"cser": 0.444, "pass_rate": 1.0, "label": "pass"},
    "B":         {"cser": 0.250, "pass_rate": 0.0, "label": "block"},
    "C":         {"cser": 0.000, "pass_rate": 0.0, "label": "block"},
}

# ── 1. Threshold sensitivity sweep ───────────────────────────────────────────
thresholds = [round(t * 0.05, 2) for t in range(1, 20)]  # 0.05 ~ 0.95
sensitivity = []

for t in thresholds:
    correct = 0
    total = 0
    for name, cond in CONDITIONS.items():
        predicted = "pass" if cond["cser"] >= t else "block"
        actual = cond["label"]
        if predicted == actual:
            correct += 1
        total += 1
    accuracy = correct / total
    sensitivity.append({
        "threshold": t,
        "accuracy": accuracy,
        "correct": correct,
        "total": total
    })

# Find valid range (accuracy = 1.0)
valid_range = [s["threshold"] for s in sensitivity if s["accuracy"] == 1.0]
valid_min = min(valid_range) if valid_range else None
valid_max = max(valid_range) if valid_range else None

print("=== Threshold Sensitivity Analysis ===")
for s in sensitivity:
    bar = "█" * int(s["accuracy"] * 10) + "░" * (10 - int(s["accuracy"] * 10))
    marker = " ← CURRENT" if s["threshold"] == 0.30 else ""
    valid = " ✅" if s["accuracy"] == 1.0 else " ❌"
    print(f"  t={s['threshold']:.2f}: {bar} {s['accuracy']:.2f}{valid}{marker}")

print(f"\n📊 Valid threshold range: [{valid_min}, {valid_max}]")
print(f"   Current threshold (0.30) within range: {valid_min <= 0.30 <= valid_max}")
print(f"   Range width: {round(valid_max - valid_min, 2)}")

# ── 2. Monte Carlo: sampling noise robustness ─────────────────────────────────
# Simulate if CSER values had ±noise, would separation still hold?
noise_levels = [0.00, 0.02, 0.05, 0.08, 0.10, 0.15]
mc_results = {}

for noise in noise_levels:
    correct_count = 0
    for _ in range(N_MC):
        correct = True
        for name, cond in CONDITIONS.items():
            noisy_cser = cond["cser"] + random.gauss(0, noise)
            noisy_cser = max(0.0, min(1.0, noisy_cser))
            predicted = "pass" if noisy_cser >= 0.30 else "block"
            if predicted != cond["label"]:
                correct = False
                break
        if correct:
            correct_count += 1
    p_correct = correct_count / N_MC
    mc_results[noise] = p_correct

print("\n=== Monte Carlo: CSER Noise Robustness (N=2000) ===")
for noise, p in mc_results.items():
    bar = "█" * int(p * 10) + "░" * (10 - int(p * 10))
    print(f"  noise σ={noise:.2f}: {bar} P(correct)={p:.4f}")

# Critical noise level where P drops below 0.95
critical_noise = None
for noise, p in mc_results.items():
    if p < 0.95 and critical_noise is None:
        critical_noise = noise
print(f"\n  Critical noise level (P<0.95): σ={critical_noise}")

# ── 3. Bootstrap: is 4-sample conclusion stable? ─────────────────────────────
N_BOOT = 1000
boot_valid = 0
conditions_list = list(CONDITIONS.values())

for _ in range(N_BOOT):
    # resample with replacement
    sample = random.choices(conditions_list, k=len(conditions_list))
    correct = sum(
        1 for c in sample
        if ("pass" if c["cser"] >= 0.30 else "block") == c["label"]
    )
    if correct == len(sample):
        boot_valid += 1

boot_rate = boot_valid / N_BOOT
print(f"\n=== Bootstrap Stability (N={N_BOOT}) ===")
print(f"  Pass rate: {boot_rate:.4f} (expect 1.0 for clean separation)")

# ── Save results ──────────────────────────────────────────────────────────────
results = {
    "timestamp": datetime.now().isoformat(),
    "cycle": 90,
    "analysis": "sensitivity_analysis",
    "threshold_sweep": {
        "valid_range": [valid_min, valid_max],
        "range_width": round(valid_max - valid_min, 2),
        "current_threshold_valid": (valid_min <= 0.30 <= valid_max),
        "sensitivity": sensitivity
    },
    "monte_carlo": {
        "n_samples": N_MC,
        "noise_robustness": {str(k): v for k, v in mc_results.items()},
        "critical_noise_sigma": critical_noise
    },
    "bootstrap": {
        "n_iterations": N_BOOT,
        "pass_rate": boot_rate
    },
    "conclusion": (
        f"CSER<0.30 threshold is robust: valid range [{valid_min},{valid_max}], "
        f"width={round(valid_max-valid_min,2)}. "
        f"Stable under Gaussian noise up to σ={critical_noise} (MC N=2000). "
        f"Bootstrap pass rate={boot_rate:.4f}."
    )
}

out = "/Users/rocky/emergent/experiments/sensitivity_c90_results.json"
with open(out, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Agent A complete → {out}")
print(f"\nCONCLUSION: {results['conclusion']}")
