#!/usr/bin/env bash
set -euo pipefail

REPO="Orchestra-Research/AI-Research-SKILLs"
REF="main"
DEST="${CODEX_HOME:-$HOME/.codex}/skills"
TMP_DIR=""

usage() {
  cat <<USAGE
Install every SKILL.md in ${REPO} into Codex skills.

Usage: $(basename "$0") [--ref <git-ref>] [--dest <skills-dir>] [--repo <owner/repo>]

Examples:
  $(basename "$0")
  $(basename "$0") --ref dev
  $(basename "$0") --dest ~/.codex/skills
USAGE
}

cleanup() {
  if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="$2"
      shift 2
      ;;
    --dest)
      DEST="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$DEST"
TMP_DIR="$(mktemp -d)"
REPO_DIR="$TMP_DIR/repo"

echo "Cloning https://github.com/${REPO} (ref=${REF}) ..."
git clone --depth 1 --branch "$REF" "https://github.com/${REPO}.git" "$REPO_DIR"

mapfile -t SKILL_DIRS < <(find "$REPO_DIR" -type f -name SKILL.md -exec dirname {} \; | sed "s#^$REPO_DIR/##" | sort -u)

if [[ ${#SKILL_DIRS[@]} -eq 0 ]]; then
  echo "No SKILL.md files found in ${REPO}@${REF}."
  exit 1
fi

echo "Discovered ${#SKILL_DIRS[@]} skill(s):"
printf '  - %s\n' "${SKILL_DIRS[@]}"

echo
python /opt/codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo "$REPO" \
  --ref "$REF" \
  --dest "$DEST" \
  --path "${SKILL_DIRS[@]}"

echo
echo "Installed skills into: $DEST"
echo "Restart Codex to pick up new skills."
