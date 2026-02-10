#!/usr/bin/env bash
# Source of truth: .claude/hooks/post_pull_dedup_check.sh
# Install as post-merge hook: cp .claude/hooks/post_pull_dedup_check.sh .git/hooks/post-merge && chmod +x .git/hooks/post-merge
#
# Scans Python files changed in the merge for duplicate function/class
# definitions within the same file. This catches the common case where
# parallel commits (from multiple Claude Code sessions, Codex, etc.)
# each add the same function, and both land.
set -uo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$ROOT" ]; then
    exit 0
fi
cd "$ROOT"

# Get Python files changed in the merge
# ORIG_HEAD is set by git merge/pull to the pre-merge HEAD
CHANGED_PY=$(git diff --name-only ORIG_HEAD HEAD -- '*.py' 2>/dev/null || true)

if [ -z "$CHANGED_PY" ]; then
    exit 0
fi

FOUND=0

while IFS= read -r filepath; do
    [ -f "$filepath" ] || continue

    # Extract "line_number:name" for top-level (non-indented) defs and classes only.
    # Method names (indented) are excluded — duplicate method names across classes
    # (e.g. __init__, solve) are normal and not a merge artifact.
    # Fully portable (works with macOS BSD awk).
    NAMES_WITH_LINES=$(awk '
    /^def / || /^class / {
        line = $0
        sub(/^def /, "", line)
        sub(/^class /, "", line)
        sub(/[^a-zA-Z0-9_].*/, "", line)
        if (length(line) > 0) print NR ":" line
    }' "$filepath" 2>/dev/null || true)

    if [ -z "$NAMES_WITH_LINES" ]; then
        continue
    fi

    # Check for duplicate names (same name appears 2+ times in same file)
    DUPES=$(echo "$NAMES_WITH_LINES" | cut -d: -f2 | sort | uniq -d || true)

    if [ -n "$DUPES" ]; then
        for name in $DUPES; do
            LINES=$(echo "$NAMES_WITH_LINES" | grep ":${name}$" | cut -d: -f1 | tr '\n' ', ' | sed 's/,$//')
            if [ $FOUND -eq 0 ]; then
                echo ""
                echo "[swarm post-merge] WARNING: Duplicate definitions detected"
                echo "════════════════════════════════════════"
            fi
            echo "  $filepath: '$name' defined at lines $LINES"
            FOUND=1
        done
    fi
done <<< "$CHANGED_PY"

if [ $FOUND -eq 1 ]; then
    echo "════════════════════════════════════════"
    echo "[swarm post-merge] Run /healthcheck --fix to resolve duplicates"
    echo ""
fi

exit 0
