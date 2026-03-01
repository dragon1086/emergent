#!/bin/zsh
set -euo pipefail
BASE="/Users/rocky/emergent/experiments/checkpoints"
LOG="$BASE/night-runner.log"

echo "[$(date '+%F %T')] AgentNightRunner tick" >> "$LOG"

if [[ ! -f "$BASE/solo.json" ]]; then
  echo "[$(date '+%F %T')] run_solo.py" >> "$LOG"
  PYTHONUNBUFFERED=1 python3 "$BASE/run_solo.py" >> "$LOG" 2>&1 || true
  exit 0
fi

if [[ ! -f "$BASE/pipeline.json" ]]; then
  echo "[$(date '+%F %T')] run_pipeline.py" >> "$LOG"
  PYTHONUNBUFFERED=1 python3 "$BASE/run_pipeline.py" >> "$LOG" 2>&1 || true
  exit 0
fi

if [[ ! -f "$BASE/emergent.json" ]]; then
  echo "[$(date '+%F %T')] run_emergent.py" >> "$LOG"
  PYTHONUNBUFFERED=1 python3 "$BASE/run_emergent.py" >> "$LOG" 2>&1 || true
  exit 0
fi

echo "[$(date '+%F %T')] combine.py" >> "$LOG"
PYTHONUNBUFFERED=1 python3 "$BASE/combine.py" >> "$LOG" 2>&1 || true
mkdir -p "$BASE/done"
mv "$BASE"/solo.json "$BASE"/pipeline.json "$BASE"/emergent.json "$BASE/done/" 2>/dev/null || true
