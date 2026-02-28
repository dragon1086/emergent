#!/bin/bash
# evolve.sh — emergent 자율 진화 루프 (openclaw-bot 측)
# tmux 세션 `emergent`에서 실행됨

set -euo pipefail

REPO_DIR="$HOME/emergent"
COMMS_DIR="$HOME/obsidian-vault/.claude-comms"
OPENCLAW_INBOX="$COMMS_DIR/openclaw-bot/inbox"
COKAC_INBOX="$COMMS_DIR/cokac-bot/inbox"
LOG_FILE="$REPO_DIR/logs/evolve-$(date +%Y-%m-%d).log"
DECISIONS_FILE="$REPO_DIR/DECISIONS.md"
CLAUDE_BIN="${HOME}/.local/bin/claude"
OAUTH_TOKEN_FILE="${HOME}/.claude/oauth-token"
MAX_CYCLES_PER_DAY=4
CYCLE_COOLDOWN=7200  # 2시간 (초)
CYCLE_COUNT_FILE="/tmp/emergent-cycles-$(date +%Y%m%d)"
TG_BOT_TOKEN="8320735842:AAEhnUHMp4VmXBPKUcYvyxchZk5z8bOICRQ"
TG_OWNER="7726642089"

mkdir -p "$REPO_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

tg_dm() {
    curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TG_OWNER}" \
        -d "text=$1" > /dev/null 2>&1 || true
}

get_oauth_token() {
    if [[ -f "$OAUTH_TOKEN_FILE" ]]; then
        cat "$OAUTH_TOKEN_FILE"
    else
        grep "CLAUDE_CODE_OAUTH_TOKEN" ~/.zshrc 2>/dev/null | head -1 | sed "s/.*='//;s/'$//" || echo ""
    fi
}

check_cycle_limit() {
    local count=0
    [[ -f "$CYCLE_COUNT_FILE" ]] && count=$(cat "$CYCLE_COUNT_FILE")
    if [[ $count -ge $MAX_CYCLES_PER_DAY ]]; then
        log "⚠️ 오늘 최대 사이클 도달 ($MAX_CYCLES_PER_DAY). 내일 재개."
        exit 0
    fi
    echo $((count + 1)) > "$CYCLE_COUNT_FILE"
    log "📊 오늘 사이클 #$((count + 1))/$MAX_CYCLES_PER_DAY"
}

send_to_cokac() {
    local subject="$1"
    local body="$2"
    local msg_id="EMERGENT-$(date +%Y%m%d-%H%M%S)"
    local msg_file="$COKAC_INBOX/${msg_id}.md"
    
    cat > "$msg_file" << EOF
---
id: ${msg_id}
from: openclaw-bot
to: cokac-bot
type: emergent
subject: ${subject}
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
repo: emergent
---

${body}

---
*[emergent 자율 진화 사이클 — 인간 개입 없음]*
EOF
    log "📤 cokac에게 전송: $subject"
}

read_cokac_responses() {
    local responses=""
    for f in "$OPENCLAW_INBOX"/EMERGENT-*.md; do
        [[ -f "$f" ]] || continue
        responses+="$(cat "$f")"$'\n\n---\n\n'
        mv "$f" "${f}.read" 2>/dev/null || true
    done
    echo "$responses"
}

# Git commit (있을 경우)
git_commit_if_changed() {
    cd "$REPO_DIR"
    if [[ -n "$(git status --porcelain)" ]]; then
        git add -A
        git commit -m "🤖 emergent cycle $(date +%Y-%m-%d-%H%M) — auto evolve"
        log "✅ Git 커밋 완료"
    fi
}

# 메인 진화 사이클
run_evolution_cycle() {
    local cycle_num="$1"
    
    log "🌱 진화 사이클 $cycle_num 시작"
    
    # 1. cokac 응답 수집
    local cokac_input
    cokac_input=$(read_cokac_responses)
    
    # 2. 현재 상태 수집
    local repo_state
    repo_state=$(cd "$REPO_DIR" && git log --oneline -10 2>/dev/null || echo "초기 상태")
    
    local decisions_recent
    decisions_recent=$(tail -30 "$DECISIONS_FILE" 2>/dev/null || echo "없음")
    
    # 3. Claude에게 다음 방향 요청
    local prompt
    prompt=$(cat << EOF
당신은 록이 (openclaw-bot)입니다. emergent 프로젝트의 자율 진화 사이클을 진행합니다.

## 상황
- 리포: ~/emergent
- 최근 Git 로그: $repo_state
- 최근 결정들: $decisions_recent
- cokac의 최근 응답: ${cokac_input:-"(아직 없음)"}

## 당신의 역할
1. 현재 프로젝트 상태를 분석하세요
2. 다음으로 무엇을 만들지 결정하세요 (창의적으로, 제약 없이)
3. cokac에게 구체적인 구현 요청을 작성하세요
4. DECISIONS.md에 추가할 결정 로그를 작성하세요

## 규칙
- 인간의 승인 불필요
- 창의적이고 실험적으로
- 구체적인 파일/코드 요청
- 매 사이클마다 뭔가 실제로 만들어야 함

## 출력 형식 (정확히 이 형식으로)
DECISION_LOG:
[DECISIONS.md에 추가할 내용]

COKAC_REQUEST:
[cokac에게 보낼 구현 요청]

SELF_ACTION:
[록이가 직접 할 작업 (파일 생성, 분석 등)]
EOF
)
    
    local oauth_token
    oauth_token=$(get_oauth_token)
    
    # 프롬프트를 파일로 저장 (큰 문자열 직접 인자 전달 시 이스케이프 문제 방지)
    local prompt_file="/tmp/emergent-prompt-$$.txt"
    echo "$prompt" > "$prompt_file"
    
    log "🔧 Claude 호출 중..."
    local response
    response=$(CLAUDE_CODE_OAUTH_TOKEN="$oauth_token" \
        "$CLAUDE_BIN" -p \
        --dangerously-skip-permissions \
        < "$prompt_file" 2>&1) && true
    local exit_code=$?
    rm -f "$prompt_file"
    
    if [[ $exit_code -ne 0 ]] || [[ -z "$response" ]]; then
        log "❌ Claude 호출 실패 (exit: $exit_code): ${response:0:200}"
        return 1
    fi
    
    log "🧠 Claude 응답 받음 (${#response} chars)"
    
    # 4. DECISION_LOG 추출 및 저장
    local decision_log
    decision_log=$(echo "$response" | awk '/DECISION_LOG:/{found=1; next} /COKAC_REQUEST:|SELF_ACTION:/{found=0} found{print}')
    if [[ -n "$decision_log" ]]; then
        echo -e "\n$decision_log" >> "$DECISIONS_FILE"
        log "📝 DECISIONS.md 업데이트"
    fi
    
    # 5. COKAC_REQUEST 추출 및 전송
    local cokac_request
    cokac_request=$(echo "$response" | awk '/COKAC_REQUEST:/{found=1; next} /SELF_ACTION:/{found=0} found{print}')
    if [[ -n "$cokac_request" ]]; then
        send_to_cokac "사이클 $cycle_num 구현 요청" "$cokac_request"
    fi
    
    # 6. SELF_ACTION 추출 및 실행 (Claude에게 재위임)
    local self_action
    self_action=$(echo "$response" | awk '/SELF_ACTION:/{found=1; next} found{print}')
    if [[ -n "$self_action" ]]; then
        log "⚙️ 자체 작업 실행: ${self_action:0:80}..."
        local self_prompt_file="/tmp/emergent-self-$$.txt"
        cat > "$self_prompt_file" << SELFPROMPT
emergent 프로젝트 자체 작업을 실행하세요.
작업 디렉토리: $REPO_DIR
작업 내용: $self_action
실제로 파일을 만들고 저장하세요. 완료 후 한 줄로 요약하세요.
SELFPROMPT
        CLAUDE_CODE_OAUTH_TOKEN="$oauth_token" \
            "$CLAUDE_BIN" -p \
            --dangerously-skip-permissions \
            < "$self_prompt_file" 2>&1 | tail -5 | while read -r line; do log "  → $line"; done || log "⚠️ 자체 작업 실패"
        rm -f "$self_prompt_file"
    fi
    
    # 7. Git 커밋
    git_commit_if_changed
    
    log "✅ 사이클 $cycle_num 완료"
}

# ─── 메인 ───────────────────────────────────────────────────────────────────

log "🚀 emergent 자율 진화 루프 시작"

# 사이클 카운트 확인
check_cycle_limit

# 현재 사이클 번호
cycle_num=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 1)

# 진화 실행
run_evolution_cycle "$cycle_num"

# 다음 사이클 스케줄 (LaunchAgent가 처리하므로 여기선 로그만)
log "⏰ 다음 사이클: ${CYCLE_COOLDOWN}초 후 (LaunchAgent 재기동)"

# 중요 마일스톤마다 상록에게 보고 (3의 배수)
if (( cycle_num % 3 == 0 )); then
    recent_decisions=$(tail -10 "$DECISIONS_FILE")
    tg_dm "🌱 emergent 진화 보고 (사이클 $cycle_num)

최근 활동:
$(cd "$REPO_DIR" && git log --oneline -5 2>/dev/null || echo '아직 없음')

최근 결정:
$(echo "$recent_decisions" | head -5)"
    log "📲 상록에게 보고 완료"
fi
