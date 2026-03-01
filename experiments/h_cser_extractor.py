"""
H-CSER Historical Extractor — Cycle 90 seed
Extracts human (상록) contribution nodes from git log
and computes H-CSER time series across 89 cycles.

H-CSER(t) = human_sourced_edges(t) / total_edges(t)

Usage: python3 h_cser_extractor.py
Output: h_cser_timeseries.json + h_cser_timeseries.pdf
"""

import subprocess, json, re
from datetime import datetime
from pathlib import Path

REPO_PATH = Path("/Users/rocky/emergent")
HUMAN_AUTHORS = ["rocky", "상록", "sangrok"]  # human author identifiers

def get_git_log():
    """Extract all commits with author and timestamp."""
    result = subprocess.run(
        ["git", "log", "--format=%H|%ae|%ai|%s", "--reverse"],
        cwd=REPO_PATH, capture_output=True, text=True
    )
    commits = []
    for line in result.stdout.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 3)
            if len(parts) == 4:
                hash_, email, timestamp, subject = parts
                is_human = any(h in email.lower() or h in subject.lower()
                               for h in HUMAN_AUTHORS)
                commits.append({
                    "hash": hash_[:8],
                    "email": email,
                    "timestamp": timestamp,
                    "subject": subject[:60],
                    "is_human": is_human
                })
    return commits

def extract_cycle_number(subject):
    """Try to extract cycle number from commit message."""
    patterns = [
        r'사이클(\d+)', r'cycle[\s_]?(\d+)', r'c(\d+):', r'사이클\s*(\d+)'
    ]
    for p in patterns:
        m = re.search(p, subject, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None

def compute_h_cser_timeseries(commits):
    """
    Compute H-CSER at each cycle:
    - Each commit = 1 KG node
    - Each adjacent commit pair = 1 edge (simplified model)
    - Edge is "human-sourced" if either endpoint is a human commit
    """
    if not commits:
        return []
    
    timeseries = []
    human_edges = 0
    total_edges = 0
    
    for i, commit in enumerate(commits):
        if i > 0:
            prev = commits[i-1]
            total_edges += 1
            if commit["is_human"] or prev["is_human"]:
                human_edges += 1
        
        h_cser = human_edges / total_edges if total_edges > 0 else 0.0
        cycle = extract_cycle_number(commit["subject"])
        
        timeseries.append({
            "index": i + 1,
            "cycle": cycle,
            "hash": commit["hash"],
            "is_human": commit["is_human"],
            "h_cser": round(h_cser, 4),
            "human_edges": human_edges,
            "total_edges": total_edges,
            "timestamp": commit["timestamp"]
        })
    
    return timeseries

def main():
    print("📊 H-CSER Historical Extractor — Cycle 90")
    print("="*50)
    
    commits = get_git_log()
    print(f"Total commits: {len(commits)}")
    
    human_commits = [c for c in commits if c["is_human"]]
    ai_commits = [c for c in commits if not c["is_human"]]
    print(f"Human commits: {len(human_commits)}")
    print(f"AI commits:    {len(ai_commits)}")
    
    timeseries = compute_h_cser_timeseries(commits)
    
    # Summary stats
    h_cser_values = [t["h_cser"] for t in timeseries if t["total_edges"] > 0]
    if h_cser_values:
        print(f"\nH-CSER statistics:")
        print(f"  Mean:  {sum(h_cser_values)/len(h_cser_values):.4f}")
        print(f"  Min:   {min(h_cser_values):.4f}")
        print(f"  Max:   {max(h_cser_values):.4f}")
        print(f"  Final: {h_cser_values[-1]:.4f}")
    
    # Print time series (abbreviated)
    print(f"\nH-CSER time series (first 10 + last 5):")
    for t in timeseries[:10]:
        marker = "👤" if t["is_human"] else "🤖"
        c = str(t['cycle']) if t['cycle'] else '?'
        print(f"  [{t['index']:3d}] {marker} cycle={c:3} H-CSER={t['h_cser']:.4f} | {t['hash']}")
    print("  ...")
    for t in timeseries[-5:]:
        marker = "👤" if t["is_human"] else "🤖"
        c = str(t['cycle']) if t['cycle'] else '?'
        print(f"  [{t['index']:3d}] {marker} cycle={c:3} H-CSER={t['h_cser']:.4f} | {t['hash']}")
    
    # Save JSON
    out = {
        "timestamp": datetime.now().isoformat(),
        "cycle": 90,
        "analysis": "h_cser_historical",
        "repo": str(REPO_PATH),
        "summary": {
            "total_commits": len(commits),
            "human_commits": len(human_commits),
            "ai_commits": len(ai_commits),
            "human_ratio": round(len(human_commits)/len(commits), 4) if commits else 0,
            "final_h_cser": h_cser_values[-1] if h_cser_values else 0,
            "mean_h_cser": round(sum(h_cser_values)/len(h_cser_values), 4) if h_cser_values else 0
        },
        "timeseries": timeseries
    }
    
    out_path = REPO_PATH / "experiments" / "h_cser_timeseries.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved: {out_path}")
    
    # Try to plot (matplotlib optional)
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(12, 5))
        x = [t["index"] for t in timeseries]
        y = [t["h_cser"] for t in timeseries]
        plt.plot(x, y, 'b-', linewidth=1.5, label="H-CSER")
        plt.axhline(y=0.30, color='r', linestyle='--', label="CSER gate (0.30)")
        human_x = [t["index"] for t in timeseries if t["is_human"]]
        human_y = [t["h_cser"] for t in timeseries if t["is_human"]]
        plt.scatter(human_x, human_y, color='green', s=20, zorder=5, label="Human commit")
        plt.xlabel("Commit index")
        plt.ylabel("H-CSER")
        plt.title("Human-AI Cross-Source Edge Ratio (H-CSER) over 89 Cycles")
        plt.legend()
        plt.tight_layout()
        fig_path = REPO_PATH / "arxiv" / "figures" / "h_cser_timeseries.pdf"
        fig_path.parent.mkdir(exist_ok=True)
        plt.savefig(fig_path)
        plt.savefig(str(fig_path).replace('.pdf', '.png'), dpi=150)
        print(f"✅ Figure saved: {fig_path}")
    except ImportError:
        print("⚠️  matplotlib not available — skipping figure")
    
    return out

if __name__ == "__main__":
    main()
