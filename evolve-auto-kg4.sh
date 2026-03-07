#!/bin/bash
# evolve-auto-kg4.sh — KG-4 자율 사이클 (same-vendor: Gemini Flash + Gemini Pro)
# 2×2 실험 설계: Google 계열 same-vendor

REPO_DIR="$HOME/emergent"
KG4_DIR="$HOME/emergent/kg4"
KG4_PATH="$KG4_DIR/data/knowledge-graph.json"
LOG="$KG4_DIR/logs/evolve-kg4-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="/tmp/emergent-kg4-cycles-$(date +%Y%m%d)"
MAX_CYCLES=100
GEMINI_KEY="${GEMINI_API_KEY:-$(grep "GEMINI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")}"

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

# 동적 DCI 값 측정
CURRENT_DCI=$(cd "$REPO_DIR" && EMERGENT_KG_PATH="$KG4_PATH" python3 -c "
from src.metrics import compute_dci, load_kg
kg = load_kg()
print(f'{compute_dci(kg):.4f}')
" 2>/dev/null || echo "0.0000")
log "📊 현재 DCI: $CURRENT_DCI"

# D-098: DCI 회복 — 오래된 노드 목록 추출
OLD_NODES=$(python3 -c "
import json, re
kg = json.load(open('$KG4_PATH', encoding='utf-8'))
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
log "🕰️ 오래된 노드 후보: $(echo "$OLD_NODES" | wc -l | tr -d ' ')개"

# Agent A: Gemini Flash
PROMPT="당신은 emergent KG-4 실험의 Agent A (Gemini Flash)입니다.

## 실험 목적
same-vendor Google (Gemini Flash + Gemini Pro) 환경에서 KG를 자율 진화시켜
KG-3(cross-vendor: GPT-4o + Gemini Flash)과 CSER을 비교합니다.

## 현재 KG-4 상태
$GRAPH_STATS

## ⚠️ DCI 회복 지시 (최우선)
현재 DCI = $CURRENT_DCI (목표: DCI > 0.1).
아래 오래된 노드 중 하나를 EDGE_TO로 반드시 선택하세요 (최근 노드 연결 금지):
$OLD_NODES

## 지시
1. KG-4에 추가할 의미있는 노드 1개를 제안하세요
2. 위 오래된 노드 목록에서 EDGE_TO를 선택하세요 (long-range 연결로 DCI 회복)
3. Agent B(Gemini Pro)에게 반박 또는 보완 요청을 작성하세요
4. 짝수 사이클에서는 NODE_TYPE을 반드시 question으로 하세요 (DCI 개선 필수)

## 출력 형식 (정확히)
NODE_LABEL: [노드 라벨]
NODE_CONTENT: [노드 내용 — 구체적이고 이론적]
NODE_TYPE: [insight|hypothesis|observation|question]
NODE_TAGS: [태그1,태그2,태그3]
EDGE_TO: [위 오래된 노드 목록에서 선택한 id]
EDGE_RELATION: [관계명 — question 노드의 경우 questions를 사용]
EDGE_LABEL: [관계 설명]
AGENT_B_REQUEST: [Gemini Pro에게 보내는 반박/보완 요청]"

# 프롬프트를 임시 파일로 안전 전달 (shell injection 방지)
PROMPT_FILE=$(mktemp /tmp/kg4-prompt-XXXX.txt)
echo "$PROMPT" > "$PROMPT_FILE"
trap "rm -f $LOCK_FILE $PROMPT_FILE" EXIT

log "🤖 Agent A (Gemini Flash) 판단 중..."
AGENT_A_RESPONSE=$(python3 -c "
import google.genai as genai, sys
client = genai.Client(api_key=sys.argv[1])
prompt = open(sys.argv[2], encoding='utf-8').read()
resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
print(resp.text)
" "$GEMINI_KEY" "$PROMPT_FILE" 2>&1)

if [[ -z "$AGENT_A_RESPONSE" ]]; then
  log "❌ Agent A (Gemini Flash) 호출 실패"
  exit 1
fi
log "✅ Agent A 완료 (${#AGENT_A_RESPONSE} chars)"

# Agent B: Gemini Pro
AGENT_B_REQUEST=$(echo "$AGENT_A_RESPONSE" | grep "^AGENT_B_REQUEST:" | sed 's/^AGENT_B_REQUEST: //')
AGENT_B_PROMPT_FILE=$(mktemp /tmp/kg4-agentb-XXXX.txt)
echo "KG-4 실험 Agent B (Gemini Pro)입니다. 다음 요청에 반박하거나 보완하세요 (한국어, 3문장 이내): $AGENT_B_REQUEST" > "$AGENT_B_PROMPT_FILE"
trap "rm -f $LOCK_FILE $PROMPT_FILE $AGENT_B_PROMPT_FILE" EXIT
AGENT_B_RESPONSE=$(python3 -c "
import google.genai as genai, sys
client = genai.Client(api_key=sys.argv[1])
prompt = open(sys.argv[2], encoding='utf-8').read()
resp = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
print(resp.text)
" "$GEMINI_KEY" "$AGENT_B_PROMPT_FILE" 2>&1)
log "✅ Agent B (Gemini Pro) 완료"

# KG-4에 노드/엣지 추가
NODE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_LABEL:" | sed 's/^NODE_LABEL: //' | tr -d "'\`\"\\")
NODE_CONTENT=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_CONTENT:" | sed 's/^NODE_CONTENT: //' | tr -d "'\`\"\\")
NODE_TYPE=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TYPE:" | sed 's/^NODE_TYPE: //' | tr -d ' ')
NODE_TAGS=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_TAGS:" | sed 's/^NODE_TAGS: //' | tr -d "'\`\"\\")
EDGE_TO=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_TO:" | sed 's/^EDGE_TO: //' | tr -d ' ')

# D-100: HARD-FIX — EDGE_TO가 OLD_NODES 목록 밖이면 강제 대체
OLD_NODE_IDS=$(python3 -c "
import json, re
kg = json.load(open('$KG4_PATH', encoding='utf-8'))
nodes = kg.get('nodes', [])
def node_num(n):
    m = re.search(r'\d+', n['id'])
    return int(m.group()) if m else 9999
nodes_sorted = sorted(nodes, key=node_num)
half = len(nodes_sorted) // 2
print(' '.join(n['id'] for n in nodes_sorted[:half]))
" 2>/dev/null || echo "")
if [[ -n "$OLD_NODE_IDS" && -n "$EDGE_TO" ]]; then
  HARD_FIX=$(python3 "$REPO_DIR/src/bfs_selector.py" "$KG4_PATH" "$EDGE_TO" "$OLD_NODE_IDS" 2>/dev/null || echo "KEEP")
  if [[ "$HARD_FIX" == OVERRIDE:* ]]; then
    ORIG=$(echo "$HARD_FIX" | cut -d: -f2)
    NEW=$(echo "$HARD_FIX" | cut -d: -f3)
    log "[BFS-FIX] Agent A EDGE_TO override: $ORIG -> $NEW (BFS distance max)"
    EDGE_TO="$NEW"
  fi
fi

EDGE_RELATION=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_RELATION:" | sed 's/^EDGE_RELATION: //' | tr -d ' ')
EDGE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^EDGE_LABEL:" | sed 's/^EDGE_LABEL: //' | tr -d "'\`\"\\")
AGENT_B_RESPONSE=$(echo "$AGENT_B_RESPONSE" | tr -d "'\`\"\\")

if [[ -n "$NODE_LABEL" && -n "$NODE_CONTENT" ]]; then
  cd "$REPO_DIR"
  # Agent A (Gemini-Flash) 노드 추가
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
     'type': node_type, 'source': 'gemini-2.5-flash', 'tags': tags,
     'domain': 'emergence_theory',
     'edge_to': edge_to, 'edge_relation': edge_rel, 'edge_label': edge_lbl}
print(json.dumps(d, ensure_ascii=False))
" "$NODE_LABEL" "$NODE_CONTENT" "${NODE_TYPE:-insight}" "${NODE_TAGS:-kg4,same-vendor,google}" "${EDGE_TO:-}" "${EDGE_RELATION:-extends}" "$EDGE_LABEL" 2>/dev/null \
  | EMERGENT_KG_PATH="$KG4_PATH" python3 src/add_node_safe.py 2>/dev/null)
  log "✅ Agent A(Gemini-Flash) 노드 추가: $NODE_LABEL (id: $NEW_NODE_ID → $EDGE_TO)"

  # Agent B (Gemini-Pro) 노드 추가 — same-vendor이지만 다른 모델 소스 구분
  # DCI 회복: Agent A가 question 타입이면 Agent B는 answers 관계로 연결
  AGENT_B_TYPE="critique"
  AGENT_B_RELATION="critiques"
  AGENT_B_LABEL="Agent B(Gemini-Pro)가 Agent A(Gemini-Flash)에 반박/보완"
  if [[ "$NODE_TYPE" == "question" ]]; then
    AGENT_B_TYPE="insight"
    AGENT_B_RELATION="answers"
    AGENT_B_LABEL="Agent B(Gemini-Pro)가 Agent A(Gemini-Flash) 질문에 답변"
  fi
  if [[ -n "$NEW_NODE_ID" && -n "$AGENT_B_RESPONSE" ]]; then
    GEMINI_PRO_NODE_ID=$(python3 -c "
import json, sys
agent_a_id = sys.argv[1].strip()
agent_b_resp = sys.argv[2][:600]
b_type = sys.argv[3].strip()
b_rel = sys.argv[4].strip()
b_label = sys.argv[5].strip()
d = {
  'label': 'Gemini-Pro 반박/보완: ' + agent_b_resp[:80],
  'content': agent_b_resp,
  'type': b_type,
  'source': 'gemini-2.5-pro',
  'tags': ['kg4', 'same-vendor', 'google', 'agent-b', 'gemini-pro'],
  'domain': 'emergence_theory',
  'edge_to': agent_a_id,
  'edge_relation': b_rel,
  'edge_label': b_label
}
print(json.dumps(d, ensure_ascii=False))
" "$NEW_NODE_ID" "$AGENT_B_RESPONSE" "$AGENT_B_TYPE" "$AGENT_B_RELATION" "$AGENT_B_LABEL" 2>/dev/null \
    | EMERGENT_KG_PATH="$KG4_PATH" python3 src/add_node_safe.py 2>/dev/null)
    log "✅ Agent B(Gemini-Pro) 노드 추가: $GEMINI_PRO_NODE_ID → $NEW_NODE_ID (type=$AGENT_B_TYPE, rel=$AGENT_B_RELATION)"
  fi
fi

# 메트릭 계산
EMERGENT_KG_PATH="$KG4_PATH" python3 src/metrics.py 2>/dev/null | tail -5 | tee -a "$LOG" || true

# git 커밋
cd "$REPO_DIR"
git add kg4/ 2>/dev/null
git commit -m "🤖 kg4 cycle $(date +%Y-%m-%d-%H%M) — same-vendor(gemini)" 2>/dev/null || true

log "✅ KG-4 사이클 완료"
