#!/bin/bash
# tex_edit.sh — LaTeX 파일 안전 편집
# 사용: bash tex_edit.sh <파일> <시작줄> <끝줄> <새내용파일>
# 또는: bash tex_edit.sh <파일> --grep <검색어> [--context 3]
#
# Edit 툴 실패 방지용: grep으로 위치 먼저 확인 후 sed로 교체

FILE="$1"
MODE="$2"

if [[ "$MODE" == "--grep" ]]; then
    PATTERN="$3"
    CTX="${5:-2}"
    echo "=== '$PATTERN' 위치 확인 ==="
    grep -n "$PATTERN" "$FILE" | head -20
    echo ""
    if [[ -n "$3" ]]; then
        LINE=$(grep -n "$PATTERN" "$FILE" | head -1 | cut -d: -f1)
        START=$((LINE - CTX))
        END=$((LINE + CTX))
        echo "=== 주변 맥락 (줄 $START-$END) ==="
        sed -n "${START},${END}p" "$FILE"
    fi
elif [[ "$MODE" == "--line" ]]; then
    START="$3"
    END="$4"
    echo "=== 줄 $START-$END exact content ==="
    sed -n "${START},${END}p" "$FILE" | cat -A
else
    echo "사용법:"
    echo "  $0 <파일> --grep <패턴>         # 위치 확인"
    echo "  $0 <파일> --line <시작> <끝>    # exact content 확인"
fi
