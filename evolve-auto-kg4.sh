#!/bin/bash
# evolve-auto-kg4.sh — KG-4 자율 사이클 (same-vendor: Gemini Flash + Gemini Pro)
# 2×2 실험 설계: Google 계열 same-vendor
# [KG4-N7] cokac 검증/보강: 6개 보강 (2026-03-07)
#   N7-1: API 키 유효성 사전 검증 (fail-fast)
#   N7-2: Gemini API 재시도 + 지수 백오프 (최대 3회, 5s/10s/20s)
#   N7-3: 최대 사이클 도달 시 로그 1회만 기록 (스팸 방지)
#   N7-4: 노드 타입 다양성 강제 (question/observation 비율 부족 시)
#   N7-5: git commit 변경 없을 때 스킵
#   N7-6: 사이클 후 노드 증가 검증 (add 실패 탐지)

REPO_DIR="$HOME/emergent"
KG4_DIR="$HOME/emergent/kg4"
KG4_PATH="$KG4_DIR/data/knowledge-graph.json"
LOG="$KG4_DIR/logs/evolve-kg4-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="$KG4_DIR/logs/.cycle-count-$(date +%Y%m%d)"
CYCLE_MAXED_FILE="$KG4_DIR/logs/.cycle-maxed-$(date +%Y%m%d)"
MAX_CYCLES=100
GEMINI_KEY="${GEMINI_API_KEY:-$(grep "GEMINI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")}"

mkdir -p "$KG4_DIR/logs"

log() { echo "[$(date '+%H:%M:%S')] KG4 $*" | tee -a "$LOG"; }

# [N7-3] 사이클 제한 — 최대 도달 시 로그 1회만 기록 후 silent exit
COUNT=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
if [[ $COUNT -ge $MAX_CYCLES ]]; then
  if [[ ! -f "$CYCLE_MAXED_FILE" ]]; then
    log "⚠️  오늘 최대 사이클 ($MAX_CYCLES) 도달 — 이후 silent 스킵"
    touch "$CYCLE_MAXED_FILE"
  fi
  exit 0
fi

# [N7-1] API 키 유효성 사전 검증 (fail-fast)
if [[ -z "$GEMINI_KEY" ]]; then
  log "❌ GEMINI_API_KEY 미설정 — 스킵"
  exit 1
fi
API_CHECK=$(python3 -c "
import google.genai as genai, sys
client = genai.Client(api_key=sys.argv[1])
try:
    resp = client.models.generate_content(model='gemini-2.5-flash', contents='ping')
    print('OK')
except Exception as e:
    err = str(e)[:200]
    print(f'FAIL:{err}')
" "$GEMINI_KEY" 2>/dev/null)
if [[ "$API_CHECK" != "OK" ]]; then
  log "❌ Gemini API 키 검증 실패: $API_CHECK"
  exit 1
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

# [N7-6] 사이클 전 노드 수 기록 (증가 검증용)
PRE_NODE_COUNT=$(python3 -c "
import json
kg = json.load(open('$KG4_PATH', encoding='utf-8'))
print(len(kg.get('nodes', [])))
" 2>/dev/null || echo 0)

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

# CSER 측정
CURRENT_CSER=$(cd "$REPO_DIR" && EMERGENT_KG_PATH="$KG4_PATH" python3 -c "
from src.metrics import compute_cser, load_kg
kg = load_kg()
print(f'{compute_cser(kg):.4f}')
" 2>/dev/null || echo "0.0000")
log "📊 현재 CSER: $CURRENT_CSER"

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

# [N7-4] 노드 타입 다양성 강제 — question/observation 비율 기반
CYCLE_NUM=$((COUNT + 1))
FORCE_TYPE=""
FORCE_TYPE_MSG=""
TYPE_DIVERSITY=$(python3 -c "
import json
kg = json.load(open('$KG4_PATH', encoding='utf-8'))
nodes = kg.get('nodes', [])
total = len(nodes) or 1
types = {}
for n in nodes:
    t = n.get('type', 'insight')
    types[t] = types.get(t, 0) + 1
q_pct = types.get('question', 0) / total
o_pct = types.get('observation', 0) / total
# question < 5% 또는 observation < 2% 이면 해당 타입 강제
if q_pct < 0.05:
    print('question')
elif o_pct < 0.02:
    print('observation')
else:
    print('none')
" 2>/dev/null || echo "none")

if [[ "$TYPE_DIVERSITY" == "question" ]]; then
  FORCE_TYPE="question"
  FORCE_TYPE_MSG="
## ⚠️ 필수: question 타입 노드
question 비율이 5% 미만입니다. NODE_TYPE은 반드시 question이어야 합니다.
EDGE_RELATION도 반드시 questions를 사용하세요."
elif [[ "$TYPE_DIVERSITY" == "observation" ]]; then
  FORCE_TYPE="observation"
  FORCE_TYPE_MSG="
## ⚠️ 필수: observation 타입 노드
observation 비율이 2% 미만입니다. NODE_TYPE은 반드시 observation이어야 합니다.
EDGE_RELATION도 반드시 observes를 사용하세요."
elif (( CYCLE_NUM % 2 == 0 )); then
  FORCE_TYPE="question"
  FORCE_TYPE_MSG="
## ⚠️ 필수: question 타입 노드
이번은 짝수 사이클입니다. NODE_TYPE은 반드시 question이어야 합니다.
EDGE_RELATION도 반드시 questions를 사용하세요."
fi

# 프롬프트 변동성 — 타임스탬프+사이클+랜덤 시드로 캐시 방지
TIMESTAMP_SEED="$(date '+%Y-%m-%d %H:%M:%S') cycle=$CYCLE_NUM seed=$RANDOM"

# Agent A: Gemini Flash
PROMPT="[timestamp: $TIMESTAMP_SEED]
당신은 emergent KG-4 실험의 Agent A (Gemini Flash)입니다.

## 실험 목적
same-vendor Google (Gemini Flash + Gemini Pro) 환경에서 KG를 자율 진화시켜
KG-3(cross-vendor: GPT-4o + Gemini Flash)과 CSER을 비교합니다.

## 현재 KG-4 상태
$GRAPH_STATS
CSER: $CURRENT_CSER | DCI: $CURRENT_DCI

## ⚠️ DCI 회복 지시 (최우선)
현재 DCI = $CURRENT_DCI (목표: DCI > 0.1).
아래 오래된 노드 중 하나를 EDGE_TO로 반드시 선택하세요 (최근 노드 연결 금지):
$OLD_NODES
$FORCE_TYPE_MSG
## 지시
1. KG-4에 추가할 의미있는 노드 1개를 제안하세요
2. 위 오래된 노드 목록에서 EDGE_TO를 선택하세요 (long-range 연결로 DCI 회복)
3. Agent B(Gemini Pro)에게 반박 또는 보완 요청을 작성하세요

## 출력 형식 (정확히 — 마크다운 서식 없이 plain text로)
NODE_LABEL: [노드 라벨]
NODE_CONTENT: [노드 내용 — 구체적이고 이론적]
NODE_TYPE: [insight|hypothesis|observation|question]
NODE_TAGS: [태그1,태그2,태그3]
EDGE_TO: [위 오래된 노드 목록에서 선택한 id]
EDGE_RELATION: [관계명 — question 노드의 경우 questions를 사용]
EDGE_LABEL: [관계 설명]
AGENT_B_REQUEST: [Gemini Pro에게 보내는 반박/보완 요청]

중요: 각 줄은 반드시 KEY: value 형식으로, 마크다운 볼드(**) 없이 출력하세요."

# 프롬프트를 임시 파일로 안전 전달 (shell injection 방지)
PROMPT_FILE=$(mktemp /tmp/kg4-prompt-XXXX.txt)
echo "$PROMPT" > "$PROMPT_FILE"
trap "rm -f $LOCK_FILE $PROMPT_FILE" EXIT

# [N7-2] Agent A 호출 — 지수 백오프 재시도 (5s, 10s, 20s)
log "🤖 Agent A (Gemini Flash) 판단 중..."
AGENT_A_RESPONSE=""
BACKOFF=5
for _attempt in 1 2 3; do
  AGENT_A_RESPONSE=$(python3 -c "
import google.genai as genai, sys
client = genai.Client(api_key=sys.argv[1])
prompt = open(sys.argv[2], encoding='utf-8').read()
resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
print(resp.text)
" "$GEMINI_KEY" "$PROMPT_FILE" 2>>"$LOG")
  if [[ -n "$AGENT_A_RESPONSE" ]] && ! echo "$AGENT_A_RESPONSE" | grep -q "^Traceback"; then
    break
  fi
  log "⚠️ Agent A 시도 $_attempt 실패 — ${BACKOFF}초 후 재시도"
  [[ $_attempt -lt 3 ]] && sleep $BACKOFF
  BACKOFF=$((BACKOFF * 2))
done

if [[ -z "$AGENT_A_RESPONSE" ]] || echo "$AGENT_A_RESPONSE" | grep -q "^Traceback"; then
  log "❌ Agent A (Gemini Flash) 3회 시도 모두 실패"
  echo "$AGENT_A_RESPONSE" | head -5 | tee -a "$LOG"
  exit 1
fi
log "✅ Agent A 완료 (${#AGENT_A_RESPONSE} chars)"

# Agent B: Gemini Pro
AGENT_B_REQUEST=$(echo "$AGENT_A_RESPONSE" | sed 's/\*//g' | grep -i "^AGENT_B_REQUEST:" | head -1 | sed 's/^[^:]*:[[:space:]]*//')
AGENT_B_PROMPT_FILE=$(mktemp /tmp/kg4-agentb-XXXX.txt)
echo "KG-4 실험 Agent B (Gemini Pro)입니다. 다음 요청에 반박하거나 보완하세요 (한국어, 3문장 이내): $AGENT_B_REQUEST" > "$AGENT_B_PROMPT_FILE"
trap "rm -f $LOCK_FILE $PROMPT_FILE $AGENT_B_PROMPT_FILE" EXIT

# [N7-2] Agent B 호출 — 지수 백오프 재시도
AGENT_B_RESPONSE=""
BACKOFF=5
for _attempt in 1 2 3; do
  AGENT_B_RESPONSE=$(python3 -c "
import google.genai as genai, sys
client = genai.Client(api_key=sys.argv[1])
prompt = open(sys.argv[2], encoding='utf-8').read()
resp = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
print(resp.text)
" "$GEMINI_KEY" "$AGENT_B_PROMPT_FILE" 2>>"$LOG")
  if [[ -n "$AGENT_B_RESPONSE" ]] && ! echo "$AGENT_B_RESPONSE" | grep -q "^Traceback"; then
    break
  fi
  log "⚠️ Agent B 시도 $_attempt 실패 — ${BACKOFF}초 후 재시도"
  [[ $_attempt -lt 3 ]] && sleep $BACKOFF
  BACKOFF=$((BACKOFF * 2))
done
# [N9-1] Agent B 응답 검증 — traceback/에러 포함 시 빈 문자열로 처리
if [[ -z "$AGENT_B_RESPONSE" ]] || echo "$AGENT_B_RESPONSE" | grep -qE "^Traceback|File .*, line [0-9]|raise .*(Error|Exception)"; then
  log "⚠️ Agent B 응답 불량 (traceback/에러 감지) — Agent B 노드 스킵"
  AGENT_B_RESPONSE=""
else
  log "✅ Agent B (Gemini Pro) 완료 (${#AGENT_B_RESPONSE} chars)"
fi

# 파싱 — 마크다운/들여쓰기/bullet/코드블록 대응
parse_field() {
  local field="$1"
  echo "$AGENT_A_RESPONSE" \
    | sed 's/\*//g; s/^#\+[[:space:]]*//; s/^[[:space:]]*[-•]//; s/`//g' \
    | sed 's/^[[:space:]]*//' \
    | grep -i "^${field}[[:space:]]*:" \
    | head -1 \
    | sed "s/^[^:]*:[[:space:]]*//" \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
    | tr -d "\"\\"
}

NODE_LABEL=$(parse_field "NODE_LABEL")
NODE_CONTENT=$(parse_field "NODE_CONTENT")
NODE_TYPE=$(parse_field "NODE_TYPE" | tr -d ' ' | tr '[:upper:]' '[:lower:]')
NODE_TAGS=$(parse_field "NODE_TAGS")
EDGE_TO=$(parse_field "EDGE_TO" | tr -d ' ')
EDGE_RELATION=$(parse_field "EDGE_RELATION" | tr -d ' ')
EDGE_LABEL=$(parse_field "EDGE_LABEL")

# [N7-4] 타입 다양성 강제 (LLM이 무시할 경우 대비)
if [[ -n "$FORCE_TYPE" ]]; then
  if [[ "$NODE_TYPE" != "$FORCE_TYPE" ]]; then
    log "⚠️ 타입 다양성 강제: $NODE_TYPE → $FORCE_TYPE"
    NODE_TYPE="$FORCE_TYPE"
    if [[ "$FORCE_TYPE" == "question" ]]; then
      EDGE_RELATION="questions"
    elif [[ "$FORCE_TYPE" == "observation" ]]; then
      EDGE_RELATION="observes"
    fi
  fi
fi

# 파싱 실패 시 Python 폴백
if [[ -z "$NODE_LABEL" ]]; then
  log "❌ NODE_LABEL 파싱 실패. 응답 길이=${#AGENT_A_RESPONSE}, 첫 10줄:"
  echo "$AGENT_A_RESPONSE" | head -10 | tee -a "$LOG"
  FALLBACK=$(python3 -c "
import sys, re
resp = sys.stdin.read()
fields = {}
for line in resp.split('\n'):
    line = re.sub(r'[\*\`#]', '', line).strip()
    for key in ['NODE_LABEL','NODE_CONTENT','NODE_TYPE','NODE_TAGS','EDGE_TO','EDGE_RELATION','EDGE_LABEL']:
        m = re.match(rf'{key}\s*:\s*(.*)', line, re.IGNORECASE)
        if m and key not in fields:
            fields[key] = m.group(1).strip().strip('\"')
for k,v in fields.items():
    print(f'{k}={v}')
" <<< "$AGENT_A_RESPONSE" 2>/dev/null)
  if echo "$FALLBACK" | grep -q "^NODE_LABEL="; then
    NODE_LABEL=$(echo "$FALLBACK" | grep "^NODE_LABEL=" | head -1 | cut -d= -f2-)
    NODE_CONTENT=$(echo "$FALLBACK" | grep "^NODE_CONTENT=" | head -1 | cut -d= -f2-)
    NODE_TYPE=$(echo "$FALLBACK" | grep "^NODE_TYPE=" | head -1 | cut -d= -f2- | tr '[:upper:]' '[:lower:]' | tr -d ' ')
    NODE_TAGS=$(echo "$FALLBACK" | grep "^NODE_TAGS=" | head -1 | cut -d= -f2-)
    EDGE_TO=$(echo "$FALLBACK" | grep "^EDGE_TO=" | head -1 | cut -d= -f2- | tr -d ' ')
    EDGE_RELATION=$(echo "$FALLBACK" | grep "^EDGE_RELATION=" | head -1 | cut -d= -f2- | tr -d ' ')
    EDGE_LABEL=$(echo "$FALLBACK" | grep "^EDGE_LABEL=" | head -1 | cut -d= -f2-)
    log "🔄 Python 폴백 파싱 성공: label=$NODE_LABEL | type=$NODE_TYPE"
  else
    log "❌ 폴백 파싱도 실패 — 사이클 스킵"
    exit 1
  fi
fi
if [[ -z "$NODE_CONTENT" ]]; then
  log "⚠️ NODE_CONTENT 비어있음 — NODE_LABEL을 content로 대체"
  NODE_CONTENT="$NODE_LABEL"
fi

log "📋 파싱 결과: label=$NODE_LABEL | type=$NODE_TYPE | edge_to=$EDGE_TO"

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

AGENT_B_RESPONSE=$(echo "$AGENT_B_RESPONSE" | tr -d "'\`\"\\")

if [[ -n "$NODE_LABEL" && -n "$NODE_CONTENT" ]]; then
  cd "$REPO_DIR"
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
" "$NODE_LABEL" "$NODE_CONTENT" "${NODE_TYPE:-insight}" "${NODE_TAGS:-kg4,same-vendor,google}" "${EDGE_TO:-}" "${EDGE_RELATION:-extends}" "$EDGE_LABEL" 2>>"$LOG" \
  | EMERGENT_KG_PATH="$KG4_PATH" python3 src/add_node_safe.py 2>>"$LOG")

  if [[ -z "$NEW_NODE_ID" ]]; then
    log "❌ Agent A 노드 추가 실패 (add_node_safe.py 에러 — 위 로그 참조)"
  else
    log "✅ Agent A(Gemini-Flash) 노드 추가: $NODE_LABEL (id: $NEW_NODE_ID → $EDGE_TO)"
  fi

  # Agent B (Gemini-Pro) 노드 추가
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
" "$NEW_NODE_ID" "$AGENT_B_RESPONSE" "$AGENT_B_TYPE" "$AGENT_B_RELATION" "$AGENT_B_LABEL" 2>>"$LOG" \
    | EMERGENT_KG_PATH="$KG4_PATH" python3 src/add_node_safe.py 2>>"$LOG")

    if [[ -z "$GEMINI_PRO_NODE_ID" ]]; then
      log "❌ Agent B 노드 추가 실패 (add_node_safe.py 에러 — 위 로그 참조)"
    else
      log "✅ Agent B(Gemini-Pro) 노드 추가: $GEMINI_PRO_NODE_ID → $NEW_NODE_ID (type=$AGENT_B_TYPE, rel=$AGENT_B_RELATION)"
    fi
  fi
fi

# 메트릭 계산 — CSER 포함 전체 출력
EMERGENT_KG_PATH="$KG4_PATH" python3 src/metrics.py 2>/dev/null | tail -5 | tee -a "$LOG" || true

# 사이클 후 CSER 변화 로그
POST_CSER=$(cd "$REPO_DIR" && EMERGENT_KG_PATH="$KG4_PATH" python3 -c "
from src.metrics import compute_cser, load_kg
kg = load_kg()
print(f'{compute_cser(kg):.4f}')
" 2>/dev/null || echo "0.0000")
log "📊 사이클 후 CSER: $CURRENT_CSER → $POST_CSER"

# [N7-6] 사이클 후 노드 증가 검증
POST_NODE_COUNT=$(python3 -c "
import json
kg = json.load(open('$KG4_PATH', encoding='utf-8'))
print(len(kg.get('nodes', [])))
" 2>/dev/null || echo 0)
DELTA=$((POST_NODE_COUNT - PRE_NODE_COUNT))
if [[ $DELTA -le 0 ]]; then
  log "⚠️ 노드 증가 없음 (pre=$PRE_NODE_COUNT, post=$POST_NODE_COUNT) — add_node_safe.py 점검 필요"
else
  log "📊 노드 증가: $PRE_NODE_COUNT → $POST_NODE_COUNT (+$DELTA)"
fi

# [N7-5] git 커밋 — 변경 있을 때만
cd "$REPO_DIR"
git add kg4/ 2>/dev/null
if git diff --cached --quiet 2>/dev/null; then
  log "ℹ️ KG 변경 없음 — git commit 스킵"
else
  git commit -m "🤖 kg4 cycle $(date +%Y-%m-%d-%H%M) — same-vendor(gemini)" 2>/dev/null || true
fi

log "✅ KG-4 사이클 완료"
