#!/usr/bin/env bash
set -euo pipefail
# Post-tool-use hook: extract file_path from $ARGUMENTS JSON and scan for secrets.
# Called automatically by Claude Code after Write/Edit tool calls.

if [ -z "${ARGUMENTS:-}" ]; then
    exit 0
fi

FILE_PATH=$(echo "$ARGUMENTS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || true)

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Only scan code/config files, skip binaries and images
case "$FILE_PATH" in
    *.py|*.js|*.ts|*.yaml|*.yml|*.json|*.sh|*.env|*.md|*.toml|*.cfg|*.ini)
        ;;
    *)
        exit 0
        ;;
esac

exec bash "$(dirname "$0")/scan_secrets.sh" "$FILE_PATH"
