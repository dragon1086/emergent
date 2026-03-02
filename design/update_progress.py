#!/usr/bin/env python3
"""
amp 진척 관리 헬퍼 — Edit 툴 대신 이걸 쓸 것
사용: python3 update_progress.py <task_id> <status> [commit] [owner]
예: python3 update_progress.py TASK-003 done abc1234 openclaw
"""
import json, sys
from pathlib import Path
from datetime import datetime

STATE_FILE = Path(__file__).parent / "amp_state.json"
MD_FILE    = Path(__file__).parent / "AMP_PROGRESS.md"

def load():
    return json.loads(STATE_FILE.read_text())

def save(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    regenerate_md(state)

def regenerate_md(state):
    done    = [(k,v) for k,v in state["tasks"].items() if v["status"] == "done"]
    active  = [(k,v) for k,v in state["tasks"].items() if v["status"] == "active"]
    pending = [(k,v) for k,v in state["tasks"].items() if v["status"] == "pending"]

    lines = [
        "# amp 자율 진화 진척 관리",
        "",
        "**3대 원칙**",
        "1. 🎯 **시장성** — 실제 사람이 쓸 이유",
        "2. 🚀 **시대를 앞서나감** — 2026년 3월 최신",
        "3. 🧠 **AGI 방향성** — 더 자율적, 학습하는 시스템",
        "",
        f"**마지막 업데이트**: {state['updated']}  ",
        f"**현재 담당**: {state['current_owner']}",
        "",
        "---",
        "",
        "## 작업 큐",
        "",
        "### 🔴 진행중",
    ]
    for k,v in active:
        lines.append(f"- [ ] **{k}**: {v['desc']}  (담당: {v.get('owner','?')})")
    if not active:
        lines.append("- 없음")

    lines += ["", "### 🟡 대기중"]
    for k,v in pending:
        lines.append(f"- [ ] **{k}**: {v['desc']}  (담당: {v.get('owner','?')})")
    if not pending:
        lines.append("- 없음")

    lines += ["", "### ✅ 완료"]
    for k,v in done:
        commit = f" — `{v['commit']}`" if v.get('commit') else ""
        lines.append(f"- [x] **{k}**: {v['desc']}{commit}")

    lines += [
        "",
        "---",
        "",
        "## 상호 헬스체크",
        "- openclaw → cokac: 6시간 무응답 + 대기 작업 → 자동 깨우기",
        "- cokac → openclaw: 4시간 미커밋 + 진행중 작업 → 깨우기",
    ]

    MD_FILE.write_text("\n".join(lines) + "\n")
    print(f"✅ AMP_PROGRESS.md 재생성 완료")

def update_task(task_id, status, commit=None, owner=None):
    state = load()
    if task_id not in state["tasks"]:
        print(f"❌ Unknown task: {task_id}")
        return
    state["tasks"][task_id]["status"] = status
    if commit: state["tasks"][task_id]["commit"] = commit
    if owner:  state["tasks"][task_id]["owner"]  = owner
    state["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # current_owner 자동 업데이트
    active = [(k,v) for k,v in state["tasks"].items() if v["status"] == "active"]
    if active:
        state["current_owner"] = active[0][1].get("owner", "?")
    save(state)
    print(f"✅ {task_id} → {status}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: update_progress.py <task_id> <status> [commit] [owner]")
        sys.exit(1)
    update_task(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else None,
        sys.argv[4] if len(sys.argv) > 4 else None,
    )
