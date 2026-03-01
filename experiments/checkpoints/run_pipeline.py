#!/usr/bin/env python3
"""Pipeline: 기존 cokac 결과 재사용 (math_pipeline_results.json → checkpoint 형식 변환)"""
import json
from pathlib import Path

src = Path("/Users/rocky/emergent/experiments/math_pipeline_results.json")
data = json.loads(src.read_text())

# aime_hard_1 pipeline 결과 추출
raw = data["results"]["aime_hard_1"]["pipeline"]["raw"]
acc = data["results"]["aime_hard_1"]["pipeline"]["accuracy"]

result = {
    "aime_hard_1": {
        "accuracy": acc,
        "raw": raw,
        "expected": "202",
        "note": "cokac-bot 실행 결과 (재사용)"
    }
}
Path("/Users/rocky/emergent/experiments/checkpoints/pipeline.json").write_text(json.dumps(result, indent=2))
print(f"✅ Pipeline checkpoint saved: aime_hard_1={acc:.0%}")
