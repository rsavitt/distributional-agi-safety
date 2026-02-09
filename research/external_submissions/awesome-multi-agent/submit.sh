#!/usr/bin/env bash
# Submit SWARM to WeiChengTseng/awesome-multi-agent
#
# Prerequisites:
#   - gh CLI authenticated (gh auth login)
#   - git configured with your name/email
#
# Usage:
#   bash research/external_submissions/awesome-multi-agent/submit.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(mktemp -d)"
BRANCH="add-swarm-framework"

echo "==> Forking and cloning WeiChengTseng/awesome-multi-agent..."
gh repo fork WeiChengTseng/awesome-multi-agent --clone --clone-dir "$WORK_DIR/awesome-multi-agent"
cd "$WORK_DIR/awesome-multi-agent"

echo "==> Creating branch: $BRANCH"
git checkout -b "$BRANCH"

echo "==> Applying changes to README.md..."

# Insert the Frameworks & Tools section and TOC entry
python3 - <<'PYEOF'
import re

with open("README.md", "r") as f:
    content = f.read()

# Add TOC entry for Frameworks & Tools before Tutorials
toc_entry = " - [Frameworks & Tools](#frameworks--tools)\n"
content = content.replace(
    " - [Tutorials](#tutorials)",
    toc_entry + " - [Tutorials](#tutorials)"
)

# Add Frameworks & Tools section before Tutorials section
frameworks_section = """## Frameworks & Tools
- **SWARM: System-Wide Assessment of Risk in Multi-agent systems** [[code]](https://github.com/swarm-ai-safety/swarm) [[install]](https://pypi.org/project/swarm-safety/)
  - A distributional safety simulation framework for studying emergent risks in multi-agent AI systems.
  - Uses soft (probabilistic) labels instead of binary classifications to measure toxicity, adverse selection, and governance effectiveness.
  - Built-in agent archetypes (honest, opportunistic, deceptive, adversarial, LLM-backed) and governance levers (taxes, reputation, circuit breakers, audits).
  - YAML-driven scenarios, parameter sweeps, and full replay support for reproducible multi-agent experiments.
  - R. Savitt, 2026. MIT License.

"""

content = content.replace(
    "## Tutorials",
    frameworks_section + "## Tutorials"
)

with open("README.md", "w") as f:
    f.write(content)

print("README.md updated successfully.")
PYEOF

echo "==> Committing..."
git add README.md
git commit -m "Add SWARM: distributional safety framework for multi-agent systems

SWARM is an open-source simulation framework for studying emergent risks
in multi-agent AI systems using soft probabilistic labels. Adds a new
Frameworks & Tools section with SWARM as the first entry."

echo "==> Pushing to fork..."
git push -u origin "$BRANCH"

echo "==> Creating pull request..."
gh pr create \
    --repo WeiChengTseng/awesome-multi-agent \
    --title "Add SWARM safety simulation framework" \
    --body-file "$SCRIPT_DIR/pr_body.md"

echo "==> Done! PR created."
echo "==> Cleaning up temp dir: $WORK_DIR"
