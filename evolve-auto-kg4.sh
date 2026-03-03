#!/bin/bash
# evolve-auto-kg4.sh — KG-4 자율 사이클 (same-vendor: Gemini Flash + Gemini Pro)
# 2×2 실험 설계: Google 계열 same-vendor

REPO_DIR="$HOME/emergent"
KG4_DIR="$HOME/emergent/kg4"
KG4_PATH="$KG4_DIR/data/knowledge-graph.json"
LOG="$KG4_DIR/logs/evolve-kg4-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="/tmp/emergent-kg4-cycles-$(date +%Y%m%d)"
MAX_CYCLES=20
GEMINI_KEY=$(grep "GEMINI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")

mkdir -p "$KG4_DIR/logs"

log() { echo "[$(date '+%H:%M:%S')] KG4 $*" | tee -a "$LOG"; }

# 사이클 제한
COUNT=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
if [[ $COUNT -ge $MAX_CYCLES ]]; then
  log "⚠️  오늘 최대 사이클 ($MAX_CYCLES) 도달 — 스킵"
  exit 0
fi
echo $((COUNT + 1)) > "$CYCLE_COUNT_FILE"
log "🌱 KG-4 사이클 시작 #$((COUNT + 1))/$MAX_CYCLES"

# 중복 방지
LOCK_FILE="/tmp/emergent-kg4-running.lock"
if [[ -f "$LOCK_FILE" ]]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    log "⚠️  이전 KG-4 사이클 실행 중 — 스킵"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

# 현재 KG-4 상태 수집
export EMERGENT_KG_PATH="$KG4_PATH"
GRAPH_STATS=$(cd "$REPO_DIR" && python3 src/kg.py stats 2>/dev/null || echo "통계 없음")
log "📊 KG-4 현황: $GRAPH_STATS"

# Agent A: Gemini Flash
PROMPT="당신은 emergent KG-4 실험의 Agent A (Gemini Flash)입니다.

## 실험 목적
same-vendor Google (Gemini Flash + Gemini Pro) 환경에서 KG를 자율 진화시켜
KG-3(cross-vendor: GPT-4o + Gemini Flash)과 CSER을 비교합니다.

## 현재 KG-4 상태
$GRAPH_STATS

## 지시
1. KG-4에 추가할 의미있는 insight 또는 hypothesis 노드 1개를 제안하세요
2. 기존 노드와의 관계(edge) 1개를 제안하세요
3. Agent B(Gemini Pro)에게 반박 또는 보완 요청을 작성하세요

## 출력 형식 (정확히)
NODE_LABEL: [노드 라벨]
NODE_CONTENT: [노드 내용 — 구체적이고 이론적]
NODE_TYPE: [insight|hypothesis|observation]
NODE_TAGS: [태그1,태그2,태그3]
EDGE_TO: [연결할 기존 노드 id]
EDGE_RELATION: [관계명]
EDGE_LABEL: [관계 설명]
AGENT_B_REQUEST: [Gemini Pro에게 보내는 반박/보완 요청]"

log "🤖 Agent A (Gemini Flash) 판단 중..."
AGENT_A_RESPONSE=$(python3 -c "
import google.genai as genai
client = genai.Client(api_key='$GEMINI_KEY')
resp = client.models.generate_content(model='gemini-2.5-flash', contents='''$PROMPT''')
print(resp.text)
" 2>&1)

if [[ -z "$AGENT_A_RESPONSE" ]]; then
  log "❌ Agent A (Gemini Flash) 호출 실패"
  exit 1
fi
log "✅ Agent A 완료 (${#AGENT_A_RESPONSE} chars)"

# Agent B: Gemini Pro
AGENT_B_REQUEST=$(echo "$AGENT_A_RESPONSE" | grep "^AGENT_B_REQUEST:" | sed 's/^AGENT_B_REQUEST: //')
AGENT_B_RESPONSE=$(python3 -c "
import google.genai as genai
client = genai.Client(api_key='$GEMINI_KEY')
resp = client.models.generate_content(model='gemini-2.5-pro', contents='KG-4 실험 Agent B (Gemini Pro)입니다. 다음 요청에 반박하거나 보완하세요 (한국어, 3문장 이내): $AGENT_B_REQUEST')
print(resp.text)
" 2>&1)
log "✅ Agent B (Gemini Pro) 완료"

# KG-4에 노드/엣지 추가
NODE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_LABEL:" | sed 's/^NODE_LABEL: //' | tr -d "'\`\"\\")
NODE_CONTENT=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_CONTENT:" | sed 's/^NODE_CONTENT: //' | tr -d "'\`\"\\")
NODE_TYPE=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TYPE:" | sed 's/^NODE_TYPE: //' | tr -d ' ')
NODE_TAGS=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TAGS:" | sed 's/^NODE_TAGS: //' | tr -d "'\`\"\\")
EDGE_TO=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_TO:" | sed 's/^EDGE_TO: //' | tr -d ' ')
EDGE_RELATION=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_RELATION:" | sed 's/^EDGE_RELATION: //' | tr -d ' ')
EDGE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_LABEL:" | sed 's/^EDGE_LABEL: //' | tr -d "'\`\"\\")
AGENT_B_RESPONSE=$(echo "$AGENT_B_RESPONSE" | tr -d "'\`\"\\")

if [[ -n "$NODE_LABEL" && -n "$NODE_CONTENT" ]]; then
  cd "$REPO_DIR"
  AGENT_B_SAFE=$(echo "$AGENT_B_RESPONSE" | tr -d "'\`\"\\" | tr '\n\r' '  ' | cut -c1-200)
  NEW_NODE_ID=$(EMERGENT_KG_PATH="$KG4_PATH" python3 src/kg.py add-node \
    --type "${NODE_TYPE:-insight}" \
    --label "$NODE_LABEL" \
    --content "${NODE_CONTENT}. Gemini Pro: ${AGENT_B_SAFE}" \
    --source "gemini-2.5-flash" \
    --tag "${NODE_TAGS:-kg4,same-vendor,google,experiment}" 2>&1 | grep "✅" | grep -o "n-[0-9]*")
  log "✅ 노드 추가: $NODE_LABEL (id: $NEW_NODE_ID)"

  if [[ -n "$EDGE_TO" && -n "$EDGE_RELATION" ]]; then
    EMERGENT_KG_PATH="$KG4_PATH" python3 src/kg.py add-edge \
      --from "$NEW_NODE_ID" --to "$EDGE_TO" \
      --relation "$EDGE_RELATION" \
      --label "$EDGE_LABEL" 2>/dev/null && log "✅ 엣지 추가: $NEW_NODE_ID → $EDGE_TO"
  fi
fi

# 메트릭 계산
EMERGENT_KG_PATH="$KG4_PATH" python3 src/metrics.py 2>/dev/null | tail -5 | tee -a "$LOG" || true

# git 커밋
cd "$REPO_DIR"
git add kg4/ 2>/dev/null
git commit -m "🤖 kg4 cycle $(date +%Y-%m-%d-%H%M) — same-vendor(gemini)" 2>/dev/null || true

log "✅ KG-4 사이클 완료"
