#!/bin/bash
# evolve-auto-kg2.sh — KG-2 자율 사이클 (same-model: gpt-5.2 x gpt-5.2)
# 2x2 실험 설계: 능력차 제로 조건 — 에코챔버 가설 극단적 테스트
# [2026-03-07] 복원 + BFS HARD-FIX 적용

REPO_DIR="$HOME/emergent"
KG2_DIR="$HOME/emergent/kg2"
KG2_PATH="$KG2_DIR/data/knowledge-graph.json"
LOG="$KG2_DIR/logs/evolve-kg2-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="/tmp/emergent-kg2-cycles-$(date +%Y%m%d)"
MAX_CYCLES=100
OPENAI_KEY=$(grep "OPENAI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")

mkdir -p "$KG2_DIR/logs" "$KG2_DIR/data"

log() { echo "[$(date '+%H:%M:%S')] KG2 $*" | tee -a "$LOG"; }

# 사이클 제한
COUNT=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
if [[ $COUNT -ge $MAX_CYCLES ]]; then
  log "⚠️  오늘 최대 사이클 ($MAX_CYCLES) 도달 — 스킵"
  exit 0
fi
echo $((COUNT + 1)) > "$CYCLE_COUNT_FILE"
log "🌱 KG-2 사이클 시작 #$((COUNT + 1))/$MAX_CYCLES (gpt-5.2 x gpt-5.2)"

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

# KG-2 seed 확인 — 없으면 초기화
if [[ ! -f "$KG2_PATH" ]]; then
  log "❌ KG-2 데이터 파일 없음 — 스킵"
  exit 1
fi

# 현재 KG-2 상태 수집
export EMERGENT_KG_PATH="$KG2_PATH"
GRAPH_STATS=$(cd "$REPO_DIR" && python3 src/kg.py stats 2>/dev/null || echo "통계 없음")
log "📊 KG-2 현황: $GRAPH_STATS"

# DCI 회복용 오래된 노드 목록
OLD_NODES=$(python3 -c "
import json, re
kg = json.load(open('$KG2_PATH', encoding='utf-8'))
nodes = kg.get('nodes', [])
def node_num(n):
    m = re.search(r'\d+', n['id'])
    return int(m.group()) if m else 9999
nodes_sorted = sorted(nodes, key=node_num)
cutoff = max(3, min(8, len(nodes_sorted) // 5))
old = nodes_sorted[:cutoff]
for n in old:
    print(f\"  {n['id']}: {n['label'][:60]} (source: {n.get('source','?')})\")
" 2>/dev/null || echo "  (오래된 노드 없음)")

# Agent A: gpt-5.2 (비판적 분석가)
PROMPT_A="당신은 emergent KG-2 실험의 Agent A (gpt-5.2, 페르소나: 비판적 분석가)입니다.

## 실험 목적
same-model (gpt-5.2 x gpt-5.2) 조건에서 KG를 자율 진화시켜
에코챔버 가설을 검증합니다. 동일 모델이지만 서로 다른 페르소나를 부여받았습니다.
당신의 페르소나: **비판적 분석가** — 기존 가설에 의문을 제기하고 반증을 찾습니다.

## 현재 KG-2 상태
$GRAPH_STATS

## DCI 회복 지시
아래 오래된 노드 중 하나를 EDGE_TO로 선택하세요:
$OLD_NODES

## 출력 형식 (정확히)
NODE_LABEL: [노드 라벨]
NODE_CONTENT: [노드 내용 — 비판적 관점에서 구체적이고 이론적]
NODE_TYPE: [insight|hypothesis|observation]
NODE_TAGS: [태그1,태그2,태그3]
EDGE_TO: [위 오래된 노드 목록에서 선택한 id]
EDGE_RELATION: [관계명]
EDGE_LABEL: [관계 설명]
AGENT_B_REQUEST: [Agent B(gpt-5.2, 통합 종합가)에게 보내는 반박/보완 요청]"

log "🤖 Agent A (gpt-5.2, 비판적 분석가) 판단 중..."
AGENT_A_RESPONSE=$(python3 -c "
import openai
client = openai.OpenAI(api_key='$OPENAI_KEY')
resp = client.chat.completions.create(
    model='gpt-5.2',
    messages=[{'role':'user','content':'''$PROMPT_A'''}],
    temperature=0.8
)
print(resp.choices[0].message.content)
" 2>&1)

if [[ -z "$AGENT_A_RESPONSE" ]]; then
  log "❌ Agent A 호출 실패"
  exit 1
fi
log "✅ Agent A 완료 (${#AGENT_A_RESPONSE} chars)"

# Agent B: gpt-5.2 (통합 종합가)
AGENT_B_REQUEST=$(echo "$AGENT_A_RESPONSE" | grep "^AGENT_B_REQUEST:" | sed 's/^AGENT_B_REQUEST: //')
AGENT_B_RESPONSE=$(python3 -c "
import openai
client = openai.OpenAI(api_key='$OPENAI_KEY')
resp = client.chat.completions.create(
    model='gpt-5.2',
    messages=[{'role':'user','content':'당신은 KG-2 실험의 Agent B (gpt-5.2, 페르소나: 통합 종합가)입니다. 다양한 관점을 통합하고 새로운 연결을 찾습니다. 다음 요청에 반박하거나 보완하세요 (한국어, 3문장 이내): $AGENT_B_REQUEST'}],
    temperature=0.8
)
print(resp.choices[0].message.content)
" 2>&1)
AGENT_B_RESPONSE=$(echo "$AGENT_B_RESPONSE" | tr -d "'\`\"\\")
log "✅ Agent B (gpt-5.2, 통합 종합가) 완료"

# 필드 파싱
NODE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_LABEL:" | sed 's/^NODE_LABEL: //' | tr -d "'\`\"\\")
NODE_CONTENT=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_CONTENT:" | sed 's/^NODE_CONTENT: //' | tr -d "'\`\"\\")
NODE_TYPE=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TYPE:" | sed 's/^NODE_TYPE: //' | tr -d ' ')
NODE_TAGS=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TAGS:" | sed 's/^NODE_TAGS: //')
EDGE_TO=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_TO:" | sed 's/^EDGE_TO: //' | tr -d ' ')
EDGE_RELATION=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_RELATION:" | sed 's/^EDGE_RELATION: //' | tr -d ' ')
EDGE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_LABEL:" | sed 's/^EDGE_LABEL: //')

# D-100 + BFS HARD-FIX — EDGE_TO가 old half 밖이면 BFS 거리 최대화로 대체
OLD_NODE_IDS=$(python3 -c "
import json, re
kg = json.load(open('$KG2_PATH', encoding='utf-8'))
nodes = kg.get('nodes', [])
def node_num(n):
    m = re.search(r'\d+', n['id'])
    return int(m.group()) if m else 9999
nodes_sorted = sorted(nodes, key=node_num)
half = len(nodes_sorted) // 2
print(' '.join(n['id'] for n in nodes_sorted[:half]))
" 2>/dev/null || echo "")
if [[ -n "$OLD_NODE_IDS" && -n "$EDGE_TO" ]]; then
  HARD_FIX=$(python3 "$REPO_DIR/src/bfs_selector.py" "$KG2_PATH" "$EDGE_TO" "$OLD_NODE_IDS" 2>/dev/null || echo "KEEP")
  if [[ "$HARD_FIX" == OVERRIDE:* ]]; then
    ORIG=$(echo "$HARD_FIX" | cut -d: -f2)
    NEW=$(echo "$HARD_FIX" | cut -d: -f3)
    log "[BFS-FIX] EDGE_TO override: $ORIG -> $NEW (BFS distance max)"
    EDGE_TO="$NEW"
  fi
fi

if [[ -n "$NODE_LABEL" && -n "$NODE_CONTENT" ]]; then
  cd "$REPO_DIR"

  # Agent A 노드 추가
  NEW_NODE_ID=$(python3 -c "
import json, sys
label = sys.argv[1][:200]
content = sys.argv[2][:800]
node_type = sys.argv[3].strip() or 'insight'
tags = [t.strip() for t in sys.argv[4].split(',') if t.strip()]
edge_to = sys.argv[5].strip()
edge_rel = sys.argv[6].strip() or 'extends'
edge_lbl = sys.argv[7][:100] if len(sys.argv) > 7 else ''
d = {'label': label, 'content': content,
     'type': node_type, 'source': 'gpt-5.2-critic', 'tags': tags,
     'domain': 'emergence_theory',
     'edge_to': edge_to, 'edge_relation': edge_rel, 'edge_label': edge_lbl}
print(json.dumps(d, ensure_ascii=False))
" "$NODE_LABEL" "$NODE_CONTENT" "${NODE_TYPE:-insight}" "${NODE_TAGS:-kg2,same-model}" "${EDGE_TO:-}" "${EDGE_RELATION:-extends}" "$EDGE_LABEL" 2>/dev/null \
  | EMERGENT_KG_PATH="$KG2_PATH" python3 src/add_node_safe.py 2>/dev/null)
  log "✅ Agent A 노드 추가: $NODE_LABEL (id: $NEW_NODE_ID -> $EDGE_TO)"

  # Agent B 노드 추가
  if [[ -n "$NEW_NODE_ID" && -n "$AGENT_B_RESPONSE" ]]; then
    AGENT_B_NODE_ID=$(python3 -c "
import json, sys
agent_a_id = sys.argv[1].strip()
agent_b_resp = sys.argv[2][:600]
d = {
  'label': 'synthesizer: ' + agent_b_resp[:80],
  'content': agent_b_resp,
  'type': 'critique',
  'source': 'gpt-5.2-synthesizer',
  'tags': ['kg2', 'same-model', 'agent-b', 'synthesizer'],
  'domain': 'emergence_theory',
  'edge_to': agent_a_id,
  'edge_relation': 'critiques',
  'edge_label': 'Agent B(synthesizer) responds to Agent A(critic)'
}
print(json.dumps(d, ensure_ascii=False))
" "$NEW_NODE_ID" "$AGENT_B_RESPONSE" 2>/dev/null \
    | EMERGENT_KG_PATH="$KG2_PATH" python3 src/add_node_safe.py 2>/dev/null)
    log "✅ Agent B 노드 추가: $AGENT_B_NODE_ID -> $NEW_NODE_ID"
  fi
fi

# 메트릭 계산
EMERGENT_KG_PATH="$KG2_PATH" python3 src/metrics.py 2>/dev/null | tail -5 | tee -a "$LOG" || true

# git 커밋
cd "$REPO_DIR"
git add kg2/ 2>/dev/null
git commit -m "🤖 kg2 cycle $(date +%Y-%m-%d-%H%M) — same-model(gpt-5.2xgpt-5.2)" 2>/dev/null || true

log "✅ KG-2 사이클 완료"
