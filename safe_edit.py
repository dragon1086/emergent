#!/usr/bin/env python3
"""
safe_edit.py — 정확한 문자열 매칭 없이도 안전하게 파일 편집
사용: python3 safe_edit.py <파일> <찾을_패턴(정규식)> <대체_문자열> [--line N]
"""
import sys, re, argparse, shutil
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument('file')
    p.add_argument('--old', required=True, help='찾을 문자열 (Python regex)')
    p.add_argument('--new', required=True, help='대체할 문자열')
    p.add_argument('--count', type=int, default=1, help='최대 교체 횟수 (0=전체)')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding='utf-8')
    count = args.count if args.count > 0 else 0

    new_text, n = re.subn(args.old, args.new, text, count=count)
    if n == 0:
        print(f"❌ 패턴을 찾지 못했습니다: {args.old[:80]!r}")
        sys.exit(1)

    print(f"✅ {n}곳 교체됨")
    if args.dry_run:
        print("[dry-run] 저장 안 함")
        return

    # 백업
    shutil.copy(path, path.with_suffix(path.suffix + '.bak'))
    path.write_text(new_text, encoding='utf-8')
    print(f"💾 저장 완료: {path}")

if __name__ == '__main__':
    main()
