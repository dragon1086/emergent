#!/bin/bash
# evolve-auto-kg3.sh — KG-3 자율 사이클 (cross-vendor: GPT-4o + Gemini Flash)
# 2×2 실험 설계: Google 계열 cross-vendor

REPO_DIR="$HOME/emergent"
KG3_DIR="$HOME/emergent/kg3"
KG3_PATH="$KG3_DIR/data/knowledge-graph.json"
LOG="$KG3_DIR/logs/evolve-kg3-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="/tmp/emergent-kg3-cycles-$(date +%Y%m%d)"
MAX_CYCLES=20
OPENAI_KEY=$(grep "OPENAI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")
GEMINI_KEY=$(grep "GEMINI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")

mkdir -p "$KG3_DIR/logs"

log() { echo "[$(date '+%H:%M:%S')] KG3 $*" | tee -a "$LOG"; }

# 사이클 제한
COUNT=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
if [[ $COUNT -ge $MAX_CYCLES ]]; then
  log "⚠️  오늘 최대 사이클 ($MAX_CYCLES) 도달 — 스킵"
  exit 0
fi
echo $((COUNT + 1)) > "$CYCLE_COUNT_FILE"
log "🌱 KG-3 사이클 시작 #$((COUNT + 1))/$MAX_CYCLES"

# 중복 방지
LOCK_FILE="/tmp/emergent-kg3-running.lock"
if [[ -f "$LOCK_FILE" ]]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    log "⚠️  이전 KG-3 사이클 실행 중 — 스킵"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

# 현재 KG-3 상태 수집
export EMERGENT_KG_PATH="$KG3_PATH"
GRAPH_STATS=$(cd "$REPO_DIR" && python3 src/kg.py stats 2>/dev/null || echo "통계 없음")
log "📊 KG-3 현황: $GRAPH_STATS"

# D-098: DCI 회복 — 오래된 노드 목록 추출 (프롬프트에 포함)
OLD_NODES=$(python3 -c "
import json, sys
kg = json.load(open('$KG3_PATH', encoding='utf-8'))
nodes = kg.get('nodes', [])
# ID 번호 기준 오름차순 정렬 (낮은 번호 = 오래된 노드)
import re
def node_num(n):
    m = re.search(r'\d+', n['id'])
    return int(m.group()) if m else 9999
nodes_sorted = sorted(nodes, key=node_num)
# 상위 20% (최소 3개, 최대 8개)
cutoff = max(3, min(8, len(nodes_sorted) // 5))
old = nodes_sorted[:cutoff]
for n in old:
    print(f\"  {n['id']}: {n['label'][:60]} (source: {n.get('source','?')})\")
" 2>/dev/null || echo "  (오래된 노드 없음)")
log "🕰️ 오래된 노드 후보: $(echo "$OLD_NODES" | wc -l | tr -d ' ')개"

# Agent A: GPT-4o (OpenAI)
PROMPT="당신은 emergent KG-3 실험의 Agent A (GPT-4o)입니다.

## 실험 목적
cross-vendor (GPT-4o + Gemini Flash) 환경에서 KG를 자율 진화시켜
KG-2(same-vendor: GPT계열)와 CSER을 비교합니다.

## 현재 KG-3 상태
$GRAPH_STATS

## ⚠️ DCI 회복 지시 (최우선)
현재 DCI = 0.0508 (심각한 단기 연결 편향). 목표: DCI > 0.1.
아래 오래된 노드 중 하나를 EDGE_TO로 반드시 선택하세요 (최근 노드 연결 금지):
$OLD_NODES

## 지시
1. KG-3에 추가할 의미있는 insight 또는 hypothesis 노드 1개를 제안하세요
2. 위 오래된 노드 목록에서 EDGE_TO를 선택하세요 (long-range 연결로 DCI 회복)
3. Agent B(Gemini Flash)에게 반박 또는 보완 요청을 작성하세요

## 출력 형식 (정확히)
NODE_LABEL: [노드 라벨]
NODE_CONTENT: [노드 내용 — 구체적이고 이론적]
NODE_TYPE: [insight|hypothesis|observation]
NODE_TAGS: [태그1,태그2,태그3]
EDGE_TO: [위 오래된 노드 목록에서 선택한 id]
EDGE_RELATION: [관계명]
EDGE_LABEL: [관계 설명]
AGENT_B_REQUEST: [Gemini Flash에게 보내는 반박/보완 요청]"

log "🤖 Agent A (GPT-4o) 판단 중..."
AGENT_A_RESPONSE=$(python3 -c "
import openai
client = openai.OpenAI(api_key='$OPENAI_KEY')
resp = client.chat.completions.create(
    model='gpt-5.2',
    messages=[{'role':'user','content':'''$PROMPT'''}],
    temperature=0.7
)
print(resp.choices[0].message.content)
" 2>&1)

if [[ -z "$AGENT_A_RESPONSE" ]]; then
  log "❌ Agent A (GPT-4o) 호출 실패"
  exit 1
fi
log "✅ Agent A 완료 (${#AGENT_A_RESPONSE} chars)"

# Agent B: Gemini Flash (Google)
AGENT_B_REQUEST=$(echo "$AGENT_A_RESPONSE" | grep "^AGENT_B_REQUEST:" | sed 's/^AGENT_B_REQUEST: //')
AGENT_B_RESPONSE=$(python3 -c "
import google.genai as genai
client = genai.Client(api_key='$GEMINI_KEY')

resp = client.models.generate_content(model='gemini-2.5-flash', contents='KG-3 실험 Agent B (Gemini Flash)입니다. 다음 요청에 반박하거나 보완하세요 (한국어, 3문장 이내): $AGENT_B_REQUEST')
print(resp.text)
" 2>&1)
log "✅ Agent B (Gemini Flash) 완료"
AGENT_B_RESPONSE=$(echo "$AGENT_B_RESPONSE" | tr -d "'\`\"\\")

# KG-3에 노드/엣지 추가
NODE_LABEL=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_LABEL:" | sed 's/^NODE_LABEL: //' | tr -d "'\`\"\\")
NODE_CONTENT=$(echo "$AGENT_A_RESPONSE" | grep "^NODE_CONTENT:" | sed 's/^NODE_CONTENT: //' | tr -d "'\`\"\\")
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
edge_to = sys.argv[6].strip()
edge_rel = sys.argv[7].strip() or 'extends'
edge_lbl = sys.argv[8][:100] if len(sys.argv) > 8 else ''
d = {'label': label, 'content': content + ' [Gemini: ' + agent_b + ']',
     'type': node_type, 'source': 'gpt-5.2', 'tags': tags, 'domain': 'emergence_theory',
     'edge_to': edge_to, 'edge_relation': edge_rel, 'edge_label': edge_lbl}
print(json.dumps(d, ensure_ascii=False))
" "$NODE_LABEL" "$NODE_CONTENT" "$AGENT_B_RESPONSE" "${NODE_TYPE:-insight}" "${NODE_TAGS:-kg3,cross-vendor}" "${EDGE_TO:-}" "${EDGE_RELATION:-extends}" "$EDGE_LABEL" 2>/dev/null \
  | EMERGENT_KG_PATH="$KG3_PATH" python3 src/add_node_safe.py 2>/dev/null)
  log "✅ 노드+엣지 추가: $NODE_LABEL (id: $NEW_NODE_ID → $EDGE_TO)"
fi

# 메트릭 계산
EMERGENT_KG_PATH="$KG3_PATH" python3 src/metrics.py 2>/dev/null | tail -5 | tee -a "$LOG" || true

# git 커밋
cd "$REPO_DIR"
git add kg3/ 2>/dev/null
git commit -m "🤖 kg3 cycle $(date +%Y-%m-%d-%H%M) — cross-vendor(gpt4o+gemini)" 2>/dev/null || true

log "✅ KG-3 사이클 완료"
