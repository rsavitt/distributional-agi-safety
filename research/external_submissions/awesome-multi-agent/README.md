# Awesome Multi-Agent — SWARM Submission

**Target repo:** [WeiChengTseng/awesome-multi-agent](https://github.com/WeiChengTseng/awesome-multi-agent)
**Status:** Draft prepared, pending PR submission

## What this adds

SWARM is listed in the **Environment** section of the awesome list as a
simulation framework for studying distributional safety and emergent risks
in multi-agent systems.

## How to submit

```bash
# 1. Fork the repo
gh repo fork WeiChengTseng/awesome-multi-agent --clone

# 2. Apply the patch
cd awesome-multi-agent
git apply /path/to/add-swarm.patch

# 3. Commit & push
git checkout -b add-swarm-framework
git add README.md
git commit -m "Add SWARM: distributional safety framework for multi-agent systems"
git push -u origin add-swarm-framework

# 4. Open the PR
gh pr create \
  --repo WeiChengTseng/awesome-multi-agent \
  --title "Add SWARM safety simulation framework" \
  --body-file /path/to/pr_body.md
```

## Files

| File | Purpose |
|------|---------|
| `add-swarm.patch` | Git-format patch for README.md |
| `pr_body.md` | Pull request description |
| `README.md` | This file |
