#!/bin/bash
# evolve-auto.sh — 완전 자율 사이클 (LaunchAgent 호출용)
# 록이 페르소나로 판단 → evolve.sh v2로 실행
# 상록 지시 (2026-02-28): 페르소나 유지로 평균화 방지

REPO_DIR="$HOME/emergent"
LOG="$REPO_DIR/logs/evolve-auto-$(date +%Y-%m-%d).log"
CYCLE_COUNT_FILE="$REPO_DIR/logs/emergent-cycles-$(date +%Y%m%d)"
MAX_CYCLES=10
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

# 중복 실행 방지 (이전 claude 세션이 아직 실행 중이면 스킵)
LOCK_FILE="/tmp/emergent-running.lock"
if [[ -f "$LOCK_FILE" ]]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    log "⚠️  이전 사이클(PID $LOCK_PID) 아직 실행 중 — 스킵"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

# 현재 상태 수집
cd "$REPO_DIR"
GRAPH_STATS=$(python3 src/kg.py stats 2>/dev/null || echo "통계 없음")

# D-100: DCI 회복용 오래된 노드 목록 추출
OLD_NODES=$(python3 -c "
import json, re
try:
    kg = json.load(open('$REPO_DIR/data/knowledge-graph.json', encoding='utf-8'))
    nodes = kg.get('nodes', [])
    def node_num(n):
        m = re.search(r'\d+', n['id'])
        return int(m.group()) if m else 9999
    nodes_sorted = sorted(nodes, key=node_num)
    cutoff = max(3, min(10, len(nodes_sorted) // 5))
    for n in nodes_sorted[:cutoff]:
        print(f\"  {n['id']}: {n['label'][:60]}\")
except Exception:
    pass
" 2>/dev/null || echo "  (없음)")
METRICS_STATS=$(python3 src/metrics.py --json 2>/dev/null | python3 -c "
import json, sys
try:
    m = json.load(sys.stdin)
    es = m.get('edge_span', {})
    print(f\"CSER: {m.get('CSER', 'N/A'):.4f}  DCI: {m.get('DCI', 'N/A'):.4f}  DXI: {m.get('DXI', 'N/A'):.4f}\")
    print(f\"edge_span: raw={es.get('raw', 'N/A'):.3f}  normalized={es.get('normalized', 'N/A'):.4f}  max={es.get('max', 'N/A')}\")
    print(f\"E_v5: {m.get('E_v5', 'N/A'):.4f}  (node_age_div={m.get('node_age_diversity', 'N/A'):.4f})\")
except Exception as e:
    print('메트릭 파싱 실패:', e)
" 2>/dev/null || echo "메트릭 로드 실패 (KG 경로 확인 필요)")
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

### 창발 메트릭 (CSER/DCI/edge_span)
$METRICS_STATS

### ⚠️ DCI 회복 필요 — 오래된 노드 후보 (D-100)
아래 노드 중 하나를 EDGE_TO로 선택하세요 (장거리 연결 → DCI 회복):
$OLD_NODES

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

EDGE_TO:
[위 오래된 노드 목록에서 선택한 노드 ID — 장거리 연결로 DCI 회복]

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
