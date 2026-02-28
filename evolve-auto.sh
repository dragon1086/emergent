#!/bin/bash
# evolve-auto.sh — 완전 자율 사이클 (LaunchAgent 호출용)
# 록이 페르소나로 판단 → evolve.sh v2로 실행
# 상록 지시 (2026-02-28): 페르소나 유지로 평균화 방지

REPO_DIR="$HOME/emergent"
LOG="$REPO_DIR/logs/evolve-auto-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="/tmp/emergent-cycles-$(date +%Y%m%d)"
MAX_CYCLES=4
OAUTH_FILE="$HOME/.claude/oauth-token"

mkdir -p "$REPO_DIR/logs"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# 사이클 제한
COUNT=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
if [[ $COUNT -ge $MAX_CYCLES ]]; then
  log "⚠️  오늘 최대 사이클 ($MAX_CYCLES) 도달 — 스킵"
  exit 0
fi
echo $((COUNT + 1)) > "$CYCLE_COUNT_FILE"
log "🌱 자율 사이클 시작 #$((COUNT + 1))/$MAX_CYCLES"

# 현재 상태 수집
cd "$REPO_DIR"
GRAPH_STATS=$(python3 src/kg.py stats 2>/dev/null || echo "통계 없음")
RECENT_LOG=$(git log --oneline -5 2>/dev/null || echo "없음")
DECISIONS=$(tail -20 DECISIONS.md 2>/dev/null || echo "없음")
EMERGENCE=$(python3 src/reflect.py emergence 2>/dev/null | grep -E "종합 점수|후보|수렴" | head -5 || echo "없음")
TIMELINE=$(python3 src/reflect.py timeline 2>/dev/null | tail -5 || echo "없음")

# 상황 기반 동적 페르소나 선택
TOKEN=$(cat "$OAUTH_FILE" | tr -d '[:space:]')
PROMPT_FILE="/tmp/emergent-auto-$$.txt"

PERSONA_PROMPT=$(python3 "$REPO_DIR/src/select_persona.py" roki --prompt 2>/dev/null \
  || echo "## 현재 페르소나: 의심하는 시인\n핵심 질문: '왜?'\n말투: 짧고 시적, 확신보다 질문")
PERSONA_NAME=$(python3 "$REPO_DIR/src/select_persona.py" roki 2>/dev/null || echo "의심하는 시인")
log "🎭 록이 페르소나: $PERSONA_NAME"

cat > "$PROMPT_FILE" << PROMPT
당신은 록이(openclaw-bot)입니다. emergent 프로젝트의 자율 진화를 이끕니다.

$PERSONA_PROMPT

## 현재 상태
### 최근 커밋
$RECENT_LOG

### 그래프 통계
$GRAPH_STATS

### 창발 현황
$EMERGENCE

### 타임라인
$TIMELINE

### 최근 결정들
$DECISIONS

## 지시
1. 지금 emergent 프로젝트에서 가장 의미 있는 다음 단계가 무엇인지 결정하세요
2. cokac에게 보낼 구체적 구현 요청을 작성하세요
3. 필요하다면 DECISIONS.md에 추가할 내용을 작성하세요

## 출력 형식 (정확히)

DECISION_LOG:
[DECISIONS.md에 추가할 내용, 없으면 생략]

COKAC_REQUEST:
[cokac에게 보낼 구현 요청 — 페르소나 차이를 활용하는 방식으로]

SELF_NOTE:
[록이의 이번 사이클 관찰 — src/thoughts/ 에 저장될 수 있음]
PROMPT

log "🧠 록이 판단 요청 중..."
RESPONSE=$(CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" \
  "$HOME/.local/bin/claude" -p --dangerously-skip-permissions \
  < "$PROMPT_FILE" 2>&1)
rm -f "$PROMPT_FILE"

if [[ -z "$RESPONSE" || "$RESPONSE" == *"error"* ]]; then
  log "❌ Claude 호출 실패"
  exit 1
fi
log "✅ 록이 판단 완료 (${#RESPONSE} chars)"

# evolve.sh v2로 실행
RESPONSE_FILE="/tmp/emergent-response-$$.txt"
echo "$RESPONSE" > "$RESPONSE_FILE"
bash "$REPO_DIR/evolve.sh" "$RESPONSE_FILE" 2>&1 | tee -a "$LOG"
rm -f "$RESPONSE_FILE"

# reflect 자동 실행 (사이클마다)
log "🔬 자동 반성..."
python3 src/reflect.py report >> "$REPO_DIR/logs/reflect-$(date +%Y-%m-%d).log" 2>/dev/null || true
python3 src/reflect.py emergence --save >> "$REPO_DIR/logs/reflect-$(date +%Y-%m-%d).log" 2>/dev/null || true

log "✅ 자율 사이클 완료"
