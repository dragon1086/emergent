#!/bin/zsh
# AgentNightRunner.sh — 상태 기반 자율 루프 (중복 방지 강화)
BASE="/Users/rocky/emergent/experiments/checkpoints"
LOG="$BASE/night-runner.log"
LOCK="$BASE/runner.lock"

echo "[$(date '+%F %T')] AgentNightRunner tick" >> "$LOG"

# Lock 파일로 중복 실행 방지
if [[ -f "$LOCK" ]]; then
  AGE=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0) ))
  if (( AGE < 1200 )); then  # 20분 내에 실행됐으면 skip
    echo "[$(date '+%F %T')] Runner locked (age=${AGE}s) — skip" >> "$LOG"
    exit 0
  fi
fi
touch "$LOCK"

# Claude Code 실행 중이면 skip
if pgrep -f "claude.*dangerously-skip" > /dev/null 2>&1; then
  echo "[$(date '+%F %T')] Claude Code running — skip" >> "$LOG"
  rm -f "$LOCK"; exit 0
fi

# 목표 달성 확인
GOAL_FILE="$BASE/goal_achieved.flag"
if [[ -f "$GOAL_FILE" ]]; then
  echo "[$(date '+%F %T')] Goal already achieved — idle" >> "$LOG"
  rm -f "$LOCK"; exit 0
fi

# 논문 업데이트 대기 중인지 확인
PAPER_FLAG="$BASE/paper_update_needed.flag"
if [[ -f "$PAPER_FLAG" ]]; then
  echo "[$(date '+%F %T')] Paper update mode" >> "$LOG"
  OAUTH=$(grep CLAUDE_CODE_OAUTH_TOKEN ~/.zshrc | head -1 | cut -d"'" -f2)
  CLAUDE_CODE_OAUTH_TOKEN="$OAUTH" claude -p --dangerously-skip-permissions \
    "$(cat $BASE/paper_update_task.txt)" >> "$LOG" 2>&1 &
  echo "[$(date '+%F %T')] Paper update PID=$!" >> "$LOG"
  rm -f "$PAPER_FLAG"
  rm -f "$LOCK"; exit 0
fi

# 전략 대기 중
WAIT_FLAG="$BASE/waiting_for_strategy.flag"
if [[ -f "$WAIT_FLAG" ]]; then
  echo "[$(date '+%F %T')] Waiting for strategy — idle" >> "$LOG"
  rm -f "$LOCK"; exit 0
fi

echo "[$(date '+%F %T')] Nothing to do" >> "$LOG"
rm -f "$LOCK"
