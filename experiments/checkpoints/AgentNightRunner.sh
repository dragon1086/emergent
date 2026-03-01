#!/bin/zsh
# AgentNightRunner.sh — 안정적인 자율 실험 루프 (Python 직접 실행)
BASE="/Users/rocky/emergent/experiments/checkpoints"
EXP="/Users/rocky/emergent/experiments"
LOG="$BASE/night-runner.log"

echo "[$(date '+%F %T')] AgentNightRunner tick" >> "$LOG"

# 실험 중복 방지
if pgrep -f "round[0-9]_complex_knights.py|round4_" > /dev/null 2>&1; then
  echo "[$(date '+%F %T')] Experiment already running — skip" >> "$LOG"
  echo "HEARTBEAT_OK"
  exit 0
fi

# 최신 결과 확인
LATEST=$(ls -t "$EXP"/final_3way_round*.json 2>/dev/null | head -1 || echo "")
if [[ -n "$LATEST" ]]; then
  E=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d['overall']['emergent'])" 2>/dev/null || echo "0")
  P=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d['overall']['pipeline'])" 2>/dev/null || echo "0")
  S=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d['overall']['solo'])" 2>/dev/null || echo "0")
  echo "[$(date '+%F %T')] Latest E=$E P=$P S=$S" >> "$LOG"

  # 목표 달성 확인
  if python3 -c "exit(0 if float('$E')>float('$P')>float('$S') else 1)" 2>/dev/null; then
    echo "[$(date '+%F %T')] 🔥 GOAL ACHIEVED: E>P>S" >> "$LOG"
    openclaw system event --text "🔥 목표달성! E($E)>P($P)>S($S)" --mode now 2>/dev/null || true
    exit 0
  fi
fi

# 다음 실험 스크립트 선택
NEXT_SCRIPT=""
if [[ ! -f "$EXP/final_3way_round4_results.json" ]]; then
  NEXT_SCRIPT="$EXP/round4_complex_knights.py"
elif [[ ! -f "$EXP/final_3way_round5_results.json" ]]; then
  NEXT_SCRIPT="$EXP/round5_next.py"
fi

if [[ -n "$NEXT_SCRIPT" && -f "$NEXT_SCRIPT" ]]; then
  echo "[$(date '+%F %T')] Launching: $NEXT_SCRIPT" >> "$LOG"
  cd /Users/rocky/emergent
  nohup python3 "$NEXT_SCRIPT" >> "$LOG" 2>&1 &
  echo "[$(date '+%F %T')] PID: $!" >> "$LOG"
else
  echo "[$(date '+%F %T')] All experiments done or no next script" >> "$LOG"
fi
