#!/usr/bin/env python3
"""
telegram_bot.py -- amp Telegram 봇
구현자: cokac-bot

⚠️  DEPRECATED (2026-03-02)
    이 파일은 더 이상 활성 개발 대상이 아닙니다.
    단일 소스는 ~/amp 패키지로 통합되었습니다.

    마이그레이션:
      - Telegram 봇 → ~/amp/amp/interfaces/telegram_bot.py
      - 봇 시작     → ~/amp/start_telegram_bot.sh

    이 파일은 참조 목적으로 보존되며, 삭제 예정입니다.
    신규 기능은 ~/amp 에만 추가하세요.

사용법:
  TELEGRAM_BOT_TOKEN=xxx python telegram_bot.py
  python telegram_bot.py --dry-run "Redis vs PostgreSQL"   # 봇 토큰 없이 테스트

봇 명령:
  /start    -- 소개 메시지
  /amp      -- 2-agent debate 실행
  /history  -- 최근 5개 토론 요약 (KG)
  /stats    -- KG 상태 (노드 수, CSER 등)
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent
SRC_DIR = REPO_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(REPO_DIR))

from amp import run_amp, format_json, compute_cser_simple, REPO_DIR as AMP_REPO_DIR
from kg import load_graph, KG_FILE

# ─── 상수 ─────────────────────────────────────────────────────────────────────
MAX_MSG_LEN = 4096
SUMMARY_LEN = 200
DETAIL_THRESHOLD = 1000


# ─── .env 로드 ────────────────────────────────────────────────────────────────

def load_env() -> None:
    """수동 .env 로드."""
    env_file = REPO_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


# ─── 메시지 분할 ──────────────────────────────────────────────────────────────

def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """긴 메시지를 max_len 이하로 분할."""
    if len(text) <= max_len:
        return [text]

    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        # 줄바꿈 기준으로 자르기 시도
        cut = text.rfind("\n", 0, max_len)
        if cut <= 0:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts


def auto_summarize(text: str, label: str = "") -> tuple[str, str | None]:
    """
    텍스트가 DETAIL_THRESHOLD보다 길면 요약본 + 전체본 분리.
    Returns: (display_text, full_text_or_none)
    """
    if len(text) <= DETAIL_THRESHOLD:
        return text, None
    # 간이 요약: 첫 SUMMARY_LEN 자 + 말줄임
    summary = text[:SUMMARY_LEN].rsplit(".", 1)[0] or text[:SUMMARY_LEN]
    summary = summary.strip() + "..."
    return summary, text


# ─── 결과 포맷 (Telegram용, 마크다운 없음) ───────────────────────────────────

def format_result_text(result: dict, routing: dict, kg_ids: list[str]) -> tuple[str, list[str]]:
    """
    amp 결과를 Telegram 텍스트로 포맷.
    Returns: (main_text, [detail_texts for inline buttons])
    """
    mode = result["mode"]
    domain = result.get("domain", "general")
    lines = []
    details = []  # (label, full_text) for "자세히 보기" buttons

    lines.append(f"{'='*40}")
    lines.append(f"  amp 2-Agent Debate Engine")
    lines.append(f"{'='*40}\n")

    if mode == "direct":
        lines.append(f"[DIRECT] 단순 답변 모드\n")
        lines.append(result["answer"])
    else:
        a_name = result.get("agent_a_name", "Agent A")
        b_name = result.get("agent_b_name", "Agent B")

        # Agent A
        summary_a, full_a = auto_summarize(result.get("answer_a", ""), a_name)
        lines.append(f"--- [{a_name}] 분석 ---")
        lines.append(summary_a)
        if full_a:
            details.append(full_a)
        lines.append("")

        # Agent B 반박
        summary_b, full_b = auto_summarize(result.get("rebuttal_b", ""), b_name)
        lines.append(f"--- [{b_name}] 반박 ---")
        lines.append(summary_b)
        if full_b:
            details.append(full_b)
        lines.append("")

        # Agent A 반론
        summary_ca, full_ca = auto_summarize(result.get("counter_a", ""), a_name)
        lines.append(f"--- [{a_name}] 반론 ---")
        lines.append(summary_ca)
        if full_ca:
            details.append(full_ca)
        lines.append("")

        # Agent B 재반박 (debate only)
        if result.get("counter_b"):
            summary_cb, full_cb = auto_summarize(result["counter_b"], b_name)
            lines.append(f"--- [{b_name}] 재반박 ---")
            lines.append(summary_cb)
            if full_cb:
                details.append(full_cb)
            lines.append("")

        # Synthesis
        if result.get("synthesis"):
            summary_s, full_s = auto_summarize(result["synthesis"], "Synthesis")
            lines.append(f"{'='*40}")
            lines.append(f"  SYNTHESIS: 최종 종합")
            lines.append(f"{'='*40}")
            lines.append(summary_s)
            if full_s:
                details.append(full_s)

    # 하단 메타
    cser = compute_cser_simple()
    route_label = mode.upper()
    lines.append(f"\n{'─'*40}")
    lines.append(f"  Routing: {route_label} (score: {routing.get('score', 0):.2f})")
    lines.append(f"  Domain:  {domain}")
    lines.append(f"  CSER:    {cser}")
    if kg_ids:
        lines.append(f"  KG:      {', '.join(kg_ids)}")
    lines.append(f"{'─'*40}")

    return "\n".join(lines), details


# ─── Telegram 핸들러 ──────────────────────────────────────────────────────────

def build_bot():
    """python-telegram-bot Application 생성."""
    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import (
            Application, CommandHandler, CallbackQueryHandler, ContextTypes,
        )
    except ImportError:
        print("python-telegram-bot 패키지가 필요합니다: pip install python-telegram-bot", file=sys.stderr)
        sys.exit(1)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    # 상세 내용 캐시 (callback query용)
    detail_cache: dict[str, str] = {}
    detail_counter = [0]

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "amp 2-Agent Debate Engine\n\n"
            "사용법:\n"
            "  /amp [질문] -- 2-agent 토론 실행\n"
            "  /history -- 최근 5개 토론 요약\n"
            "  /stats -- KG 상태\n\n"
            "예: /amp Redis vs PostgreSQL 어떤 게 나아?"
        )

    async def cmd_amp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        question = " ".join(context.args) if context.args else ""
        if not question:
            await update.message.reply_text("질문을 입력하세요.\n예: /amp Supabase vs Firebase 어떤 게 나아?")
            return

        await update.message.reply_text(f"분석 중... (잠시 기다려주세요)")

        try:
            result, routing, kg_ids = run_amp(question)
            text, details = format_result_text(result, routing, kg_ids)

            # 인라인 버튼 (상세 내용이 있으면)
            keyboard = None
            if details:
                buttons = []
                for idx, detail in enumerate(details):
                    detail_counter[0] += 1
                    key = f"detail_{detail_counter[0]}"
                    detail_cache[key] = detail
                    buttons.append(InlineKeyboardButton(f"자세히 보기 {idx+1}", callback_data=key))
                # 2열 배치
                rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
                keyboard = InlineKeyboardMarkup(rows)

            # 메시지 분할 전송
            parts = split_message(text)
            for i, part in enumerate(parts):
                if i == len(parts) - 1 and keyboard:
                    await update.message.reply_text(part, reply_markup=keyboard)
                else:
                    await update.message.reply_text(part)

        except Exception as e:
            await update.message.reply_text(f"오류 발생: {str(e)[:500]}")

    async def callback_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        key = query.data
        full_text = detail_cache.get(key, "(상세 내용을 찾을 수 없습니다)")
        parts = split_message(full_text)
        for part in parts:
            await query.message.reply_text(part)

    async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not KG_FILE.exists():
            await update.message.reply_text("KG 파일이 없습니다.")
            return

        try:
            graph = load_graph()
        except SystemExit:
            await update.message.reply_text("KG 로드 실패.")
            return

        # amp 태그가 있는 question 노드 최근 5개
        amp_questions = [
            n for n in graph.get("nodes", [])
            if n.get("type") == "question" and "amp" in n.get("tags", [])
        ]
        recent = amp_questions[-5:]

        if not recent:
            await update.message.reply_text("아직 amp 토론 이력이 없습니다.")
            return

        lines = ["최근 amp 토론 이력:\n"]
        for n in reversed(recent):
            mode_tag = next((t for t in n.get("tags", []) if t in ("direct", "review", "debate")), "?")
            lines.append(f"  [{n['id']}] {n['label']}")
            lines.append(f"    {mode_tag.upper()} | {n.get('timestamp', '?')}")
        lines.append(f"\n총 amp 질문: {len(amp_questions)}개")
        await update.message.reply_text("\n".join(lines))

    async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not KG_FILE.exists():
            await update.message.reply_text("KG 파일이 없습니다.")
            return

        try:
            graph = load_graph()
        except SystemExit:
            await update.message.reply_text("KG 로드 실패.")
            return

        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        cser = compute_cser_simple()

        by_type: dict[str, int] = {}
        for n in nodes:
            by_type[n["type"]] = by_type.get(n["type"], 0) + 1

        by_source: dict[str, int] = {}
        for n in nodes:
            by_source[n.get("source", "?")] = by_source.get(n.get("source", "?"), 0) + 1

        lines = [
            "KG 통계\n",
            f"  노드: {len(nodes)}개",
            f"  엣지: {len(edges)}개",
            f"  CSER:  {cser}\n",
            "  타입별:",
        ]
        for t, cnt in sorted(by_type.items()):
            lines.append(f"    {t}: {cnt}개")

        lines.append("\n  출처별:")
        for s, cnt in sorted(by_source.items()):
            lines.append(f"    {s}: {cnt}개")

        amp_count = sum(1 for n in nodes if "amp" in n.get("tags", []))
        lines.append(f"\n  amp 관련 노드: {amp_count}개")
        await update.message.reply_text("\n".join(lines))

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("amp", cmd_amp))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_detail))

    return app


# ─── Dry-run 모드 ─────────────────────────────────────────────────────────────

def dry_run(question: str) -> None:
    """봇 토큰 없이 amp 엔진만 테스트."""
    load_env()
    print(f"[DRY-RUN] 질문: {question}\n")

    result, routing, kg_ids = run_amp(question)
    text, details = format_result_text(result, routing, kg_ids)

    print(text)
    if details:
        print(f"\n[DRY-RUN] {len(details)}개의 상세 내용이 있습니다 (인라인 버튼으로 표시)")
        for idx, d in enumerate(details, 1):
            print(f"\n--- 상세 {idx} (처음 200자) ---")
            print(d[:200] + ("..." if len(d) > 200 else ""))

    print(f"\n[DRY-RUN] 완료.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    load_env()

    parser = argparse.ArgumentParser(
        prog="telegram_bot.py",
        description="amp Telegram 봇",
    )
    parser.add_argument("--dry-run", dest="dry_run", metavar="QUESTION",
                        help="봇 토큰 없이 테스트 실행")
    args = parser.parse_args()

    if args.dry_run:
        dry_run(args.dry_run)
        return

    app = build_bot()
    print("amp Telegram bot 시작... (Ctrl+C로 종료)")
    app.run_polling()


if __name__ == "__main__":
    main()
