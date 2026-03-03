#!/bin/bash
# evolve-auto-kg2.sh — KG-2 자율 사이클 (same-vendor: GPT-4o + GPT-4o-mini)
# N=2 비교 실험용

REPO_DIR="$HOME/emergent"
KG2_DIR="$HOME/emergent/kg2"
KG2_PATH="$KG2_DIR/data/knowledge-graph.json"
LOG="$KG2_DIR/logs/evolve-kg2-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="/tmp/emergent-kg2-cycles-$(date +%Y%m%d)"
MAX_CYCLES=20  # KG-1보다 보수적으로 시작
OPENAI_KEY=$(grep "OPENAI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")

mkdir -p "$KG2_DIR/logs"

log() { echo "[$(date '+%H:%M:%S')] KG2 $*" | tee -a "$LOG"; }

# 사이클 제한
COUNT=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
if [[ $COUNT -ge $MAX_CYCLES ]]; then
  log "⚠️  오늘 최대 사이클 ($MAX_CYCLES) 도달 — 스킵"
  exit 0
fi
echo $((COUNT + 1)) > "$CYCLE_COUNT_FILE"
log "🌱 KG-2 사이클 시작 #$((COUNT + 1))/$MAX_CYCLES"

# 중복 방지
LOCK_FILE="/tmp/emergent-kg2-running.lock"
if [[ -f "$LOCK_FILE" ]]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    log "⚠️  이전 KG-2 사이클 실행 중 — 스킵"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

# 현재 KG-2 상태 수집
export EMERGENT_KG_PATH="$KG2_PATH"
GRAPH_STATS=$(cd "$REPO_DIR" && python3 src/kg.py stats 2>/dev/null || echo "통계 없음")
log "📊 KG-2 현황: $GRAPH_STATS"

# GPT-4o로 다음 사이클 결정 (OpenAI API 직접 호출)
PROMPT="당신은 emergent KG-2 실험의 Agent A (GPT-4o)입니다.

## 실험 목적
same-vendor (GPT-4o + GPT-4o-mini) 환경에서 KG를 자율 진화시켜
KG-1(cross-vendor: GPT-5.2 + Claude)과 CSER을 비교합니다.

## 현재 KG-2 상태
$GRAPH_STATS

## 지시
1. KG-2에 추가할 의미있는 insight 또는 hypothesis 노드 1개를 제안하세요
2. 기존 노드와의 관계(edge) 1개를 제안하세요
3. Agent B(GPT-4o-mini)에게 반박 또는 보완 요청을 작성하세요

## 출력 형식 (정확히)
NODE_LABEL: [노드 라벨]
NODE_CONTENT: [노드 내용 — 구체적이고 이론적]
NODE_TYPE: [insight|hypothesis|observation]
NODE_TAGS: [태그1,태그2,태그3]
EDGE_TO: [연결할 기존 노드 id]
EDGE_RELATION: [관계명]
EDGE_LABEL: [관계 설명]
AGENT_B_REQUEST: [GPT-4o-mini에게 보내는 반박/보완 요청]"

log "🤖 Agent A (GPT-4o) 판단 중..."
AGENT_A_RESPONSE=$(python3 -c "
import openai, os, sys
client = openai.OpenAI(api_key='$OPENAI_KEY')
resp = client.chat.completions.create(
    model='gpt-4o',
    messages=[{'role':'user','content':'''$PROMPT'''}],
    temperature=0.7
)
print(resp.choices[0].message.content)
" 2>&1)

if [[ -z "$AGENT_A_RESPONSE" ]]; then
  log "❌ Agent A 호출 실패"
  exit 1
fi
log "✅ Agent A 완료 (${#AGENT_A_RESPONSE} chars)"

# Agent B (GPT-4o-mini) 반박
AGENT_B_REQUEST=$(echo "$AGENT_A_RESPONSE" | grep "^AGENT_B_REQUEST:" | sed 's/^AGENT_B_REQUEST: //')
AGENT_B_RESPONSE=$(python3 -c "
import openai, os
client = openai.OpenAI(api_key='$OPENAI_KEY')
resp = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[{'role':'user','content':'KG-2 실험 Agent B입니다. 다음 요청에 반박하거나 보완하세요 (한국어, 3문장 이내): $AGENT_B_REQUEST'}],
    temperature=1.0
)
print(resp.choices[0].message.content)
" 2>&1)
log "✅ Agent B (GPT-4o-mini) 완료"

# KG-2에 노드/엣지 추가
NODE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_LABEL:" | sed 's/^NODE_LABEL: //')
NODE_CONTENT=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_CONTENT:" | sed 's/^NODE_CONTENT: //')
NODE_TYPE=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TYPE:" | sed 's/^NODE_TYPE: //' | tr -d ' ')
NODE_TAGS=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TAGS:" | sed 's/^NODE_TAGS: //')
EDGE_TO=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_TO:" | sed 's/^EDGE_TO: //' | tr -d ' ')
EDGE_RELATION=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_RELATION:" | sed 's/^EDGE_RELATION: //' | tr -d ' ')
EDGE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_LABEL:" | sed 's/^EDGE_LABEL: //')

if [[ -n "$NODE_LABEL" && -n "$NODE_CONTENT" ]]; then
  cd "$REPO_DIR"
  NEW_NODE_ID=$(python3 -c "
import json, sys
label = sys.argv[1][:200]
content = sys.argv[2][:800]
agent_b = sys.argv[3][:150]
node_type = sys.argv[4].strip() or 'insight'
tags = [t.strip() for t in sys.argv[5].split(',') if t.strip()]
d = {'label': label, 'content': content + ' [AgentB: ' + agent_b + ']',
     'type': node_type, 'source': 'gpt-4o', 'tags': tags, 'domain': 'emergence_theory'}
print(json.dumps(d, ensure_ascii=False))
" "$NODE_LABEL" "$NODE_CONTENT" "$AGENT_B_RESPONSE" "${NODE_TYPE:-insight}" "${NODE_TAGS:-kg2,same-vendor}" 2>/dev/null \
  | EMERGENT_KG_PATH="$KG2_PATH" python3 src/add_node_safe.py 2>/dev/null)
  log "✅ 노드 추가: $NODE_LABEL (id: $NEW_NODE_ID)"

  if [[ -n "$EDGE_TO" && -n "$EDGE_RELATION" ]]; then
    EMERGENT_KG_PATH="$KG2_PATH" python3 src/kg.py add-edge \
      --from "$NEW_NODE_ID" --to "$EDGE_TO" \
      --relation "$EDGE_RELATION" \
      --label "$EDGE_LABEL" 2>/dev/null && log "✅ 엣지 추가: $NEW_NODE_ID → $EDGE_TO"
  fi
fi

# 메트릭 계산
EMERGENT_KG_PATH="$KG2_PATH" python3 src/metrics.py 2>/dev/null | tail -5 | tee -a "$LOG" || true

# git 커밋
cd "$REPO_DIR"
git add kg2/ 2>/dev/null
git commit -m "🤖 kg2 cycle $(date +%Y-%m-%d-%H%M) — same-vendor auto evolve" 2>/dev/null || true

log "✅ KG-2 사이클 완료"
