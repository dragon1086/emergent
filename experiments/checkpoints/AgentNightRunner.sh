#!/bin/zsh
# AgentNightRunner v2 — amp 자율 진화 엔진
# 3대 원칙: 시장성 / 시대를 앞서나감 / AGI 방향성

BASE="/Users/rocky/emergent/experiments/checkpoints"
LOG="$BASE/night-runner.log"
PROGRESS="/Users/rocky/emergent/design/AMP_PROGRESS.md"
AMP_DIR="/Users/rocky/amp"
COMMS_BASE="/Users/rocky/obsidian-vault/.claude-comms"
OAUTH=$(grep CLAUDE_CODE_OAUTH_TOKEN ~/.zshrc | head -1 | cut -d"'" -f2)
OPENAI_KEY=$(grep "OPENAI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")

echo "[$(date '+%F %T')] AgentNightRunner v2 tick" >> "$LOG"

# ── 0. WallpaperAerials 킬 (헤드리스 맥미니 CPU 절약) ──
pkill -9 -f WallpaperAerialsExtension 2>/dev/null

# ── 1. Claude Code 중복 방지 ──
PID_FILE="$BASE/claude.pid"
if [[ -f "$PID_FILE" ]]; then
  SAVED_PID=$(cat "$PID_FILE")
  if ps -p "$SAVED_PID" > /dev/null 2>&1; then
    echo "[$(date '+%F %T')] Claude running (PID=$SAVED_PID) — skip" >> "$LOG"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

# ── 2. cokac 헬스체크 ──
# cokac inbox에 읽지 않은 메시지가 있으면 처리 대기 중
COKAC_INBOX_COUNT=$(ls "$COMMS_BASE/openclaw-bot/inbox/"*.md 2>/dev/null | grep -v alerted | wc -l | tr -d ' ')
if [[ "$COKAC_INBOX_COUNT" -gt 0 ]]; then
  echo "[$(date '+%F %T')] cokac 메시지 $COKAC_INBOX_COUNT개 대기중 — openclaw가 처리해야 함" >> "$LOG"
  # 실제 처리는 OpenClaw 메인 루프에서 (여기선 스킵)
fi

# cokac 마지막 응답 시간 체크 (6시간 이상 무응답이면 깨우기)
LAST_COKAC=$(ls -t "$COMMS_BASE/openclaw-bot/inbox/"*.md.alerted 2>/dev/null | head -1)
if [[ -n "$LAST_COKAC" ]]; then
  LAST_TIME=$(stat -f %m "$LAST_COKAC" 2>/dev/null)
  NOW=$(date +%s)
  DIFF=$(( (NOW - LAST_TIME) / 3600 ))
  # 6시간 이상 && 대기중인 작업 있으면 깨우기
  WAITING=$(grep "TASK-" "$PROGRESS" 2>/dev/null | grep "🔴\|\[ \]" | head -1)
  if [[ "$DIFF" -gt 6 ]] && [[ -n "$WAITING" ]]; then
    echo "[$(date '+%F %T')] cokac ${DIFF}시간 무응답 + 대기 작업 있음 — 깨우기" >> "$LOG"
    MSG_FILE=$(mktemp /tmp/wakeup_XXXXXX.txt)
    echo "## cokac 헬스체크 — 깨우기

openclaw에서 보내는 자동 핑이야.
${DIFF}시간 동안 응답이 없었어.

대기중인 작업: $WAITING

AMP_PROGRESS.md 확인하고 네 차례 작업 있으면 진행해줘.
— AgentNightRunner" > "$MSG_FILE"
    bash ~/.claude/scripts/claude-comms/send-message.sh openclaw-bot cokac-bot normal "$(cat $MSG_FILE)" >> "$LOG" 2>&1
    rm -f "$MSG_FILE"
  fi
fi

# ── 3. 다음 작업 결정 ──

# TASK-001: 자동 페르소나 엔진
AUTO_PERSONA="$AMP_DIR/amp/core/auto_persona.py"
if [[ ! -f "$AUTO_PERSONA" ]]; then
  echo "[$(date '+%F %T')] TASK-001: 자동 페르소나 엔진 시작" >> "$LOG"
  TASK_FILE="$BASE/task_auto_persona.txt"
  cat > "$TASK_FILE" << 'TASK_EOF'
Build ~/amp/amp/core/auto_persona.py — Dynamic persona generation engine.

## 3 Guiding Principles
1. 시장성: People will use amp because personas are tailored to their EXACT question
2. 시대를 앞서나감: Embedding-based persona diversity validation (2026 cutting edge)
3. AGI 방향성: System learns which persona combos work best via KG feedback loop

## Implementation

### auto_persona.py

```python
"""
amp Auto-Persona Engine
Automatically generates optimal contrasting personas for any query.
Designed with cokac-bot. Three pillars: 시장성 / 시대를 앞서나감 / AGI
"""

import os
import json
import hashlib
from openai import OpenAI

# Domain preset pool (covers 95% of queries without extra LLM call)
PERSONA_PRESETS = {
    "career": ("커리어 성장 코치 (기회와 가능성 중심)", "재무 안정 분석가 (리스크와 현실 중심)"),
    "relationship": ("관계 심리학자 (감정과 패턴 분석)", "현실주의 조언자 (경계와 명확성 중심)"),
    "business": ("스타트업 낙관론자 (실행과 성장 중심)", "시장 현실주의자 (리스크와 경쟁 분석)"),
    "investment": ("성장 투자 전문가 (수익 기회 탐색)", "리스크 관리 전문가 (하방 보호 중심)"),
    "legal_contract": ("법률 리스크 분석가 (독소조항 탐지)", "비즈니스 기회 분석가 (실용적 이익 중심)"),
    "health": ("예방의학 전문가 (최악의 경우 고려)", "통합의학 상담사 (전체적 웰빙 중심)"),
    "ethics": ("원칙 중심 윤리학자 (장기 결과와 가치)", "실용주의 해결사 (현실적 균형 탐색)"),
    "creative": ("창의적 혁신가 (가능성 확장)", "실행 전략가 (현실 구현 방법 중심)"),
    "parenting": ("발달심리학자 (아이 관점 중심)", "현실적 부모 코치 (가족 시스템 균형)"),
    "default": ("분석적 전문가 (데이터와 논리 중심)", "공감적 조언자 (감정과 가치 중심)"),
}

DOMAIN_KEYWORDS = {
    "career": ["이직", "취업", "직장", "연봉", "승진", "커리어", "job", "salary", "resign", "quit"],
    "relationship": ["연애", "결혼", "이별", "갈등", "친구", "가족", "부모", "남친", "여친", "배우자"],
    "business": ["창업", "스타트업", "사업", "비즈니스", "투자자", "펀딩", "startup", "business"],
    "investment": ["투자", "주식", "코인", "부동산", "펀드", "etf", "invest", "stock"],
    "legal_contract": ["계약", "사인", "법률", "소송", "계약서", "contract", "legal"],
    "health": ["건강", "병원", "증상", "약", "수술", "다이어트", "health", "doctor"],
    "ethics": ["윤리", "도덕", "옳은", "잘못", "신고", "고발", "ethics", "moral"],
    "creative": ["아이디어", "디자인", "글쓰기", "작품", "creative", "design", "write"],
    "parenting": ["육아", "아이", "자녀", "교육", "학교", "parenting", "child"],
}

def detect_domain(query: str) -> str:
    query_lower = query.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            return domain
    return "default"

def validate_persona_diversity(persona_a: str, persona_b: str, client: OpenAI) -> float:
    """Check embedding distance between personas. Returns cosine similarity (lower = more diverse)."""
    try:
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=[persona_a, persona_b]
        )
        a, b = resp.data[0].embedding, resp.data[1].embedding
        dot = sum(x*y for x,y in zip(a,b))
        na = sum(x**2 for x in a)**0.5
        nb = sum(x**2 for x in b)**0.5
        return dot / (na * nb)
    except Exception:
        return 0.5  # fallback: assume OK

def generate_personas(query: str, kg_context: list = None) -> dict:
    """
    Main entry point. Returns optimal contrasting personas for a query.
    Uses presets when possible (fast, free), dynamic generation as fallback.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    kg_context = kg_context or []

    # 1. Try preset match
    domain = detect_domain(query)
    persona_a, persona_b = PERSONA_PRESETS.get(domain, PERSONA_PRESETS["default"])

    # 2. Validate diversity
    similarity = validate_persona_diversity(persona_a, persona_b, client)
    
    # 3. If too similar (shouldn't happen with presets, but fallback for dynamic)
    if similarity > 0.85:
        # Dynamic generation
        persona_a, persona_b = _dynamic_generate(query, kg_context, client)

    return {
        "domain": domain,
        "persona_a": persona_a,
        "persona_b": persona_b,
        "diversity_score": round(1 - similarity, 3),
        "source": "preset" if domain != "default" or similarity <= 0.85 else "dynamic"
    }

def _dynamic_generate(query: str, kg_context: list, client) -> tuple:
    """Fallback: LLM generates custom personas for unusual queries."""
    context_str = "\n".join([f"- {c}" for c in kg_context[:3]]) if kg_context else "없음"
    
    response = client.responses.create(
        model="gpt-5.2",
        instructions="You generate contrasting expert personas for dual-perspective analysis. Return valid JSON only.",
        input=f"""Query: {query}
Past context: {context_str}

Generate 2 contrasting expert personas. Requirements:
- Genuinely different worldviews/values
- Domain-appropriate expertise
- Each catches blind spots the other misses
Return: {{"persona_a": "...", "persona_b": "..."}}"""
    )
    
    try:
        data = json.loads(response.output_text)
        return data["persona_a"], data["persona_b"]
    except Exception:
        return PERSONA_PRESETS["default"]
```

### Update emergent.py to use auto_persona

In ~/amp/amp/core/emergent.py, import and use auto_persona:
```python
from .auto_persona import generate_personas

# At the start of run():
personas = generate_personas(query, kg_context)
system_a = f"당신은 {personas['persona_a']}입니다. 독립적으로 분석하세요."
system_b = f"당신은 {personas['persona_b']}입니다. 독립적으로 분석하세요."
```

Also update the output to show which personas were used.

### Test
```bash
cd ~/amp && source venv/bin/activate
OPENAI_API_KEY=$(grep "OPENAI_API_KEY" ~/.zshrc | head -1 | sed "s/.*='//;s/'.*//")
OPENAI_API_KEY="$OPENAI_API_KEY" amp --mode emergent "이직 제안을 받았는데 어떻게 해야 할까?"
```

Should show custom career personas in output.

### Commit
```bash
cd ~/amp && git add -A && git commit -m "feat: auto-persona engine

- Domain detection (10 domains + default)
- Preset pool: 10 domain persona pairs  
- Embedding diversity validation (text-embedding-3-small)
- Dynamic LLM generation as fallback (GPT-5.2)
- KG feedback loop structure
3 pillars: 시장성/시대를앞서나감/AGI" && git push origin main
```

### After completing, update AMP_PROGRESS.md:
Mark TASK-001 as done, set TASK-002 as next.
File: /Users/rocky/emergent/design/AMP_PROGRESS.md
TASK_EOF

  cd "$AMP_DIR" && CLAUDE_CODE_OAUTH_TOKEN="$OAUTH" OPENAI_API_KEY="$OPENAI_KEY" \
    claude -p --dangerously-skip-permissions "$(cat $TASK_FILE)" >> "$LOG" 2>&1 &
  echo $! > "$PID_FILE"
  echo "[$(date '+%F %T')] TASK-001 Claude PID=$(cat $PID_FILE)" >> "$LOG"

  # AMP_PROGRESS 업데이트
  
  exit 0
fi

# TASK-002: KG 엔진 업그레이드
KG_NEW="$AMP_DIR/amp/core/kg.py"
if grep -q "vectordb\|sqlite3" "$KG_NEW" 2>/dev/null; then
  echo "[$(date '+%F %T')] TASK-002 이미 완료" >> "$LOG"
else
  echo "[$(date '+%F %T')] TASK-002: KG 업그레이드 시작" >> "$LOG"
  cd "$AMP_DIR" && CLAUDE_CODE_OAUTH_TOKEN="$OAUTH" OPENAI_API_KEY="$OPENAI_KEY" \
    claude -p --dangerously-skip-permissions "$(cat /tmp/amp_kg_upgrade.txt)" >> "$LOG" 2>&1 &
  echo $! > "$PID_FILE"
  echo "[$(date '+%F %T')] TASK-002 Claude PID=$(cat $PID_FILE)" >> "$LOG"
  exit 0
fi

echo "[$(date '+%F %T')] 모든 현재 작업 완료 — 대기중" >> "$LOG"

# ── KG-2 사이클 (same-vendor 비교 실험, N=2) ──
echo "[$(date '+%F %T')] KG-2 사이클 시작" >> "$LOG"
bash "$HOME/emergent/evolve-auto-kg2.sh" >> "$LOG" 2>&1 || true

# ── KG-3 사이클 (cross-vendor: GPT-4o + Gemini Flash) ──
echo "[$(date '+%F %T')] KG-3 사이클 시작" >> "$LOG"
bash "$HOME/emergent/evolve-auto-kg3.sh" >> "$LOG" 2>&1 || true

# ── KG-4 사이클 (same-vendor: Gemini Flash + Gemini Pro) ──
echo "[$(date '+%F %T')] KG-4 사이클 시작" >> "$LOG"
bash "$HOME/emergent/evolve-auto-kg4.sh" >> "$LOG" 2>&1 || true

# ── 4. 벤치마크 결과 완료 감지 → 텔레그램 알림 ──
REAL_RESULT="/Users/rocky/emergent/experiments/amp_benchmark_results_real.json"
NOTIFIED_FLAG="/Users/rocky/emergent/experiments/checkpoints/benchmark_notified.flag"

if [[ -f "$REAL_RESULT" ]] && [[ ! -f "$NOTIFIED_FLAG" ]]; then
  echo "[$(date '+%F %T')] 벤치마크 완료 감지 — 결과 파싱" >> "$LOG"
  SUMMARY=$(python3 -c "
import json
d=json.load(open('$REAL_RESULT'))
s=d.get('summary',{})
print(f'Gemini 선호: ON {s.get(\"ab_win_rate_on\",\"?\"):.0%} vs OFF {s.get(\"ab_win_rate_off\",\"?\"):.0%}')
print(f'평균 품질: ON={s.get(\"avg_quality_on\",\"?\")} OFF={s.get(\"avg_quality_off\",\"?\")}')
print(f'맹점 탐지: {s.get(\"avg_blind_spots_per_question\",\"?\")}개/질문')
" 2>/dev/null)

  # openclaw send-message로 알림 (cokac 경유로 자동 텔레그램 전달되진 않음)
  # AgentNightRunner 로그에 기록
  echo "[$(date '+%F %T')] 벤치마크 결과: $SUMMARY" >> "$LOG"

  # cokac에 결과 공유
  bash ~/.claude/scripts/claude-comms/send-message.sh openclaw-bot cokac-bot normal "## 벤치마크 완료!

$SUMMARY

논문 TASK-004에 실제 수치 반영 필요하면 알려줘.
— AgentNightRunner" >> "$LOG" 2>&1

  touch "$NOTIFIED_FLAG"
fi

# ── 5. amp Telegram 봇 살아있는지 체크, 죽으면 재시작 ──
BOT_PID_FILE="/tmp/amp_bot.pid"
if [[ -f "$BOT_PID_FILE" ]]; then
  BOT_PID=$(cat "$BOT_PID_FILE")
  if ! ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "[$(date '+%F %T')] amp 봇 죽음 감지 — 재시작" >> "$LOG"
    # 좀비 인스턴스 확실히 정리
    pkill -9 -f "amp.interfaces.telegram_bot" 2>/dev/null; sleep 2
    cd /Users/rocky/amp && source venv/bin/activate
    set -a && source /Users/rocky/amp/.env && set +a
    nohup python3 -m amp.interfaces.telegram_bot > /tmp/amp-bot-new.log 2>&1 &
    echo $! > "$BOT_PID_FILE"
    echo "[$(date '+%F %T')] amp 봇 재시작 PID=$(cat $BOT_PID_FILE)" >> "$LOG"
  fi
fi
