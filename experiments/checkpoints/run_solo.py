#!/usr/bin/env python3
"""Solo: Round 2 결과 재사용 (같은 조건, 불필요한 반복 방지)"""
import json
from pathlib import Path

done = Path("/Users/rocky/emergent/experiments/checkpoints/done/solo.json")
out  = Path("/Users/rocky/emergent/experiments/checkpoints/solo.json")

if done.exists():
    out.write_text(done.read_text())
    d = json.loads(done.read_text())
    acc = d["aime_hard_1"]["accuracy"]
    print(f"✅ Solo (reused): aime_hard_1={acc:.0%}")
else:
    print("❌ done/solo.json not found — run fresh")
    raise SystemExit(1)
