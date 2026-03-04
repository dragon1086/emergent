#!/bin/bash
# run-kg-batch.sh — kg2/kg3/kg4 배치 러너 (목표: 각 30 cycles)
# 사용법: bash run-kg-batch.sh [target_cycles]

TARGET=${1:-30}
REPO="$HOME/emergent"
LOG="$REPO/logs/batch-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$REPO/logs"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

get_edges() {
  python3 -c "import json; d=json.load(open('$REPO/$1/data/knowledge-graph.json')); print(len(d['edges']))" 2>/dev/null || echo 0
}

get_cycles_done() {
  python3 -c "
import json, re
try:
  d = json.load(open('$REPO/$1/data/knowledge-graph.json'))
  return len([e for e in d.get('edges',[]) if True])
except: pass
" 2>/dev/null
  # cycle count = edges (each cycle adds 1 edge)
  get_edges "$1"
}

log "🚀 KG 배치 러너 시작 — 목표: 각 $TARGET 엣지"
log "📊 시작 상태:"
for kg in kg2 kg3 kg4; do
  e=$(get_edges $kg)
  log "  $kg: $e edges"
done

# 하루 카운터 리셋 (목표 사이클 달성을 위해)
DATESTR=$(date +%Y%m%d)
for kg in kg2 kg3 kg4; do
  echo 0 > "/tmp/emergent-${kg}-cycles-${DATESTR}"
done
log "🔄 일일 카운터 리셋 완료"

# 각 KG를 TARGET 엣지까지 병렬로 실행
for kg in kg2 kg3 kg4; do
  (
    while true; do
      edges=$(get_edges $kg)
      if [[ $edges -ge $TARGET ]]; then
        log "✅ $kg 목표 달성: $edges edges"
        break
      fi
      # 카운터 리셋 (매 20사이클마다 필요)
      echo 0 > "/tmp/emergent-${kg}-cycles-${DATESTR}"
      bash "$REPO/evolve-auto-${kg}.sh" >> "$LOG" 2>&1
      sleep 2
    done
  ) &
done

log "⏳ 3개 KG 병렬 실행 중... (로그: $LOG)"
wait
log "🏁 전체 완료"
for kg in kg2 kg3 kg4; do
  e=$(get_edges $kg)
  log "  최종 $kg: $e edges"
done
