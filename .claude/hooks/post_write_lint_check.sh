#!/usr/bin/env bash
set -euo pipefail
# Post-tool-use hook: auto-lint Python files after Write/Edit tool calls.
# Catches ruff issues at write time instead of at commit time.
# Complements post_write_secrets_check.sh.

if [ -z "${ARGUMENTS:-}" ]; then
    exit 0
fi

FILE_PATH=$(echo "$ARGUMENTS" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('file_path',''))" \
    2>/dev/null || true)

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Only lint Python files
case "$FILE_PATH" in
    *.py) ;;
    *)    exit 0 ;;
esac

# Check if ruff is available
if ! command -v ruff >/dev/null 2>&1; then
    exit 0
fi

# Run ruff check (report only — do not auto-fix, as that would silently
# modify the file the agent just wrote and confuse the tool output).
ISSUES=$(ruff check "$FILE_PATH" 2>&1 || true)

if [ -n "$ISSUES" ]; then
    echo "[swarm post-write-lint] Issues in $FILE_PATH:"
    echo "$ISSUES"
    echo ""
    echo "[swarm post-write-lint] Fix with: ruff check --fix $FILE_PATH"
fi
