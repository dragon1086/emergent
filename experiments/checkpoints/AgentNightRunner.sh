#!/bin/zsh
# AgentNightRunner.sh — 체크포인트 기반 직접 실행 (안정 버전)
BASE="/Users/rocky/emergent/experiments/checkpoints"
LOG="$BASE/night-runner.log"

echo "[$(date '+%F %T')] AgentNightRunner tick" >> "$LOG"

# 이미 실험 중이면 skip
if pgrep -f "run_solo|run_pipeline|run_emergent" > /dev/null 2>&1; then
  echo "[$(date '+%F %T')] 실험 진행 중 — skip" >> "$LOG"
  exit 0
fi

# 최신 결과에서 목표 달성 여부 확인
LATEST=$(ls -t "$BASE/../final_3way_round"*.json 2>/dev/null | head -1 || echo "")
if [[ -n "$LATEST" ]]; then
  ACHIEVED=$(python3 -c "
import json
d=json.load(open('$LATEST'))
e,p,s=d.get('emergent',0),d.get('pipeline',0),d.get('solo',0)
print('YES' if e>p and e>s else 'NO')
" 2>/dev/null || echo "NO")
  if [[ "$ACHIEVED" == "YES" ]]; then
    echo "[$(date '+%F %T')] 🔥 목표 달성! 실험 완료" >> "$LOG"
    openclaw system event --text "🔥 Emergent 우위 달성! 실험 완료" --mode now 2>/dev/null || true
    exit 0
  fi
fi

# Solo → Pipeline → Emergent → Combine 순서 실행
if [[ ! -f "$BASE/solo.json" ]]; then
  echo "[$(date '+%F %T')] run_solo.py" >> "$LOG"
  PYTHONUNBUFFERED=1 python3 "$BASE/run_solo.py" >> "$LOG" 2>&1
  exit 0
fi

if [[ ! -f "$BASE/pipeline.json" ]]; then
  echo "[$(date '+%F %T')] run_pipeline.py" >> "$LOG"
  PYTHONUNBUFFERED=1 python3 "$BASE/run_pipeline.py" >> "$LOG" 2>&1
  exit 0
fi

if [[ ! -f "$BASE/emergent.json" ]]; then
  echo "[$(date '+%F %T')] run_emergent.py" >> "$LOG"
  PYTHONUNBUFFERED=1 python3 "$BASE/run_emergent.py" >> "$LOG" 2>&1
  exit 0
fi

echo "[$(date '+%F %T')] combine.py" >> "$LOG"
PYTHONUNBUFFERED=1 python3 "$BASE/combine.py" >> "$LOG" 2>&1
mkdir -p "$BASE/done"
mv "$BASE/solo.json" "$BASE/pipeline.json" "$BASE/emergent.json" "$BASE/done/" 2>/dev/null || true
echo "[$(date '+%F %T')] Round 완료" >> "$LOG"
