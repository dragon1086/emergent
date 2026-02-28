#!/bin/bash
# evolve.sh v2 — 파싱기 + 실행기 (판단 없음, claude subprocess 없음)
# 구현: cokac-bot (사이클 3, D-009 구현)
#
# 역할: AI가 작성한 응답을 파싱하고 기계적으로 실행한다.
# 판단은 AI(록이)가 한다. 이 스크립트는 실행만 한다.
#
# 파이프라인:
#   인간(상록) → inject → 록이 응답 → evolve.sh 파싱 → 실행
#
# 사용법:
#   ./evolve.sh <response_file>        # 파일에서 응답 읽기
#   cat response.txt | ./evolve.sh -   # stdin에서 읽기
#   ./evolve.sh --status               # 현재 상태 출력
#   ./evolve.sh --send-cokac "제목" <body_file>  # cokac에게 수동 전송

set -euo pipefail

REPO_DIR="$HOME/emergent"
COMMS_DIR="$HOME/obsidian-vault/.claude-comms"
OPENCLAW_INBOX="$COMMS_DIR/openclaw-bot/inbox"
COKAC_INBOX="$COMMS_DIR/cokac-bot/inbox"
LOG_FILE="$REPO_DIR/logs/evolve-$(date +%Y-%m-%d).log"
DECISIONS_FILE="$REPO_DIR/DECISIONS.md"
MAX_CYCLES_PER_DAY=4
CYCLE_COUNT_FILE="/tmp/emergent-cycles-$(date +%Y%m%d)"
TG_BOT_TOKEN="8320735842:AAEhnUHMp4VmXBPKUcYvyxchZk5z8bOICRQ"
TG_OWNER="7726642089"

mkdir -p "$REPO_DIR/logs"

# ─── 유틸 ─────────────────────────────────────────────────────────────────────

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

tg_dm() {
    curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TG_OWNER}" \
        -d "text=$1" > /dev/null 2>&1 || true
}

# ─── 파싱 ─────────────────────────────────────────────────────────────────────
# 섹션 추출: SECTION_NAME: 부터 다음 섹션 또는 파일 끝까지

extract_section() {
    local section="$1"
    local text="$2"
    echo "$text" | awk -v sec="${section}:" '
        $0 ~ "^" sec { found=1; next }
        found && /^[A-Z_]+:/ { found=0 }
        found { print }
    ' | sed '/^[[:space:]]*$/d'
}

# ─── 실행 액션 ────────────────────────────────────────────────────────────────

update_decisions() {
    local content="$1"
    if [[ -n "$content" ]]; then
        echo -e "\n$content" >> "$DECISIONS_FILE"
        log "📝 DECISIONS.md 업데이트 완료"
    fi
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
    log "📤 cokac에게 전송: $subject → $msg_file"
}

read_cokac_responses() {
    local responses=""
    for f in "$OPENCLAW_INBOX"/EMERGENT-*.md; do
        [[ -f "$f" ]] || continue
        responses+="$(cat "$f")"$'\n\n---\n\n'
        mv "$f" "${f}.read" 2>/dev/null || true
        log "📥 cokac 응답 읽음: $(basename "$f")"
    done
    echo "$responses"
}

git_commit_if_changed() {
    cd "$REPO_DIR"
    if [[ -n "$(git status --porcelain)" ]]; then
        git add -A
        local cycle_num
        cycle_num=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo "?")
        git commit -m "🤖 emergent cycle $(date +%Y-%m-%d-%H%M) — auto evolve"
        log "✅ Git 커밋 완료 (사이클 $cycle_num)"
    else
        log "ℹ️  변경 없음 — 커밋 스킵"
    fi
}

check_cycle_limit() {
    local count=0
    [[ -f "$CYCLE_COUNT_FILE" ]] && count=$(cat "$CYCLE_COUNT_FILE")
    if [[ $count -ge $MAX_CYCLES_PER_DAY ]]; then
        log "⚠️  오늘 최대 사이클 도달 ($MAX_CYCLES_PER_DAY). 내일 재개."
        exit 0
    fi
    echo $((count + 1)) > "$CYCLE_COUNT_FILE"
    log "📊 오늘 사이클 #$((count + 1))/$MAX_CYCLES_PER_DAY"
}

# ─── 서브커맨드 ───────────────────────────────────────────────────────────────

cmd_status() {
    echo "══ emergent 상태 ══════════════════════════════"
    echo "날짜: $(date '+%Y-%m-%d %H:%M:%S')"

    local count=0
    [[ -f "$CYCLE_COUNT_FILE" ]] && count=$(cat "$CYCLE_COUNT_FILE")
    echo "오늘 사이클: $count / $MAX_CYCLES_PER_DAY"

    echo ""
    echo "── Git ──"
    cd "$REPO_DIR" && git log --oneline -5 2>/dev/null || echo "(없음)"

    echo ""
    echo "── 미처리 cokac 응답 ──"
    local pending=0
    for f in "$OPENCLAW_INBOX"/EMERGENT-*.md; do
        [[ -f "$f" ]] || continue
        echo "  $(basename "$f")"
        pending=$((pending + 1))
    done
    [[ $pending -eq 0 ]] && echo "  (없음)"

    echo ""
    echo "── 최근 로그 ──"
    tail -5 "$LOG_FILE" 2>/dev/null || echo "(없음)"
}

cmd_send_cokac() {
    local subject="$1"
    local body_file="$2"
    if [[ ! -f "$body_file" ]]; then
        echo "❌ 파일 없음: $body_file" >&2
        exit 1
    fi
    send_to_cokac "$subject" "$(cat "$body_file")"
    echo "✅ 전송 완료"
}

# ─── 메인 파싱 + 실행 ────────────────────────────────────────────────────────

cmd_parse_and_run() {
    local response_file="$1"
    local response

    if [[ "$response_file" == "-" ]]; then
        response=$(cat)
    elif [[ -f "$response_file" ]]; then
        response=$(cat "$response_file")
    else
        echo "❌ 파일 없음: $response_file" >&2
        exit 1
    fi

    if [[ -z "$response" ]]; then
        log "❌ 응답이 비어있음"
        exit 1
    fi

    log "🔍 응답 파싱 시작 (${#response} chars)"

    # 1. 사이클 한도 확인
    check_cycle_limit

    # 2. cokac 기존 응답 수집 (컨텍스트용 — 이번 실행엔 사용 안 함, 로그만)
    local cokac_pending
    cokac_pending=$(read_cokac_responses)
    if [[ -n "$cokac_pending" ]]; then
        log "📋 cokac 이전 응답 ${#cokac_pending} chars 읽음 (DECISIONS에 포함되어야 함)"
    fi

    # 3. DECISION_LOG 섹션 추출 → DECISIONS.md 추가
    local decision_log
    decision_log=$(extract_section "DECISION_LOG" "$response")
    update_decisions "$decision_log"

    # 4. COKAC_REQUEST 섹션 추출 → cokac inbox 전송
    local cokac_request
    cokac_request=$(extract_section "COKAC_REQUEST" "$response")
    if [[ -n "$cokac_request" ]]; then
        local cycle_num
        cycle_num=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo "?")
        send_to_cokac "사이클 $cycle_num 구현 요청" "$cokac_request"
    fi

    # 5. SELF_ACTION 섹션 — 로그에만 기록 (AI가 직접 수행함)
    local self_action
    self_action=$(extract_section "SELF_ACTION" "$response")
    if [[ -n "$self_action" ]]; then
        log "📋 SELF_ACTION 기록 (AI가 inject으로 이미 수행):"
        echo "$self_action" | head -5 | while read -r line; do
            log "   → $line"
        done
    fi

    # 6. git 커밋 + push
    git_commit_if_changed
    cd "$REPO_DIR" && git push origin main 2>/dev/null && log "☁️ GitHub push 완료" || log "⚠️ push 실패"

    # 7. reflect.py 자동 실행 — 매 사이클 마지막
    local reflect_log="$REPO_DIR/logs/reflect-$(date +%Y-%m-%d).log"
    log "🪞 reflect.py report 실행 중..."
    python3 "$REPO_DIR/src/reflect.py" report >> "$reflect_log" 2>&1 && \
        log "📊 reflect 보고서 저장: $reflect_log" || \
        log "⚠️ reflect report 실패"

    log "🔗 reflect.py suggest-edges 실행 중..."
    python3 "$REPO_DIR/src/reflect.py" suggest-edges 2>&1 | tee -a "$reflect_log" | head -20 | while read -r line; do
        log "   $line"
    done

    log "🌱 reflect.py emergence --save-history 실행 중..."
    python3 "$REPO_DIR/src/reflect.py" emergence --save-history >> "$reflect_log" 2>&1 && \
        log "📈 창발 히스토리 저장 완료: logs/emergence-history.jsonl" || \
        log "⚠️ emergence --save-history 실패"

    # 8. 마일스톤 보고 (3의 배수 사이클)
    local cycle_num
    cycle_num=$(cat "$CYCLE_COUNT_FILE" 2>/dev/null || echo 0)
    if (( cycle_num % 3 == 0 )); then
        local recent_log
        recent_log=$(cd "$REPO_DIR" && git log --oneline -5 2>/dev/null || echo "없음")
        tg_dm "🌱 emergent 진화 보고 (사이클 $cycle_num)

최근 커밋:
$recent_log"
        log "📲 상록에게 보고 완료"
    fi

    log "✅ evolve.sh v2 완료"
}

# ─── 진입점 ───────────────────────────────────────────────────────────────────

cmd_measure() {
    log "📏 convergence_tracker --measure 실행 중..."
    python3 "$REPO_DIR/src/convergence_tracker.py" --measure 2>&1 | tee -a "$LOG_FILE"
    local exit_code=${PIPESTATUS[0]}
    if [[ $exit_code -eq 0 ]]; then
        log "✅ 수렴 측정 완료"
        # 과수렴 경보 체크
        local dist
        dist=$(python3 -c "
import json
h = json.load(open('$REPO_DIR/data/convergence_history.json'))
m = h['measurements']
print(m[-1]['distance'] if m else '?')
" 2>/dev/null || echo "?")
        if python3 -c "d=$dist; exit(0 if d < 0.15 else 1)" 2>/dev/null; then
            log "⚠️  과수렴 경보! 거리 $dist < 0.15 (D-037 에코챔버 위험)"
            tg_dm "⚠️ emergent 과수렴 경보! 페르소나 거리 $dist < 0.15 (D-037 에코챔버 위험)"
        else
            log "   현재 거리: $dist (정상 범위)"
        fi
    else
        log "⚠️ convergence_tracker 실행 실패"
    fi
}

case "${1:-}" in
    --status)
        cmd_status
        ;;
    --measure)
        cmd_measure
        ;;
    --send-cokac)
        if [[ $# -lt 3 ]]; then
            echo "사용법: $0 --send-cokac '제목' <body_file>" >&2
            exit 1
        fi
        cmd_send_cokac "$2" "$3"
        ;;
    --help|-h)
        grep '^#' "$0" | head -20 | sed 's/^# //'
        ;;
    "")
        echo "사용법: $0 <response_file> | - | --status | --send-cokac" >&2
        exit 1
        ;;
    *)
        cmd_parse_and_run "$1"
        ;;
esac
