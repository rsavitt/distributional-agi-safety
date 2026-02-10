# /submit_to_list

Fork an external GitHub repo, add an entry to a curated list (e.g. awesome-*), and open a PR — all via `gh` CLI.

## Usage

`/submit_to_list <owner/repo> <section-name> [entry-text]`

Examples:
- `/submit_to_list kyegomez/awesome-multi-agent-papers "Social Simulation & Agent Societies"`
- `/submit_to_list Giskard-AI/awesome-ai-safety "General ML Testing" '* [My Paper](https://example.com) (Author, 2026) \`#Safety\`'`

## Behavior

### 1. Validate inputs

- Parse `<owner/repo>` into owner and repo.
- Confirm `gh auth status` works. Abort if not authenticated.
- If `<section-name>` is not provided, fetch the README and list available sections for the user to choose from.

### 2. Fetch and understand the target list format

- Fetch `README.md` from the upstream repo via `gh api repos/<owner>/<repo>/contents/README.md`.
- Find the target section by heading match.
- Detect the entry format from existing entries in that section (e.g. `- **[Title](URL)**` vs `* [Title](URL) (Author, Year) \`#Tag\``).
- If `[entry-text]` is not provided, draft an entry using the detected format and the project info from this repo (paper title, repo URL, author, tags). Present the draft to the user for confirmation before proceeding.

### 3. Fork the repo

```bash
gh repo fork <owner>/<repo> --clone=false
```

- If the fork already exists, skip this step.
- Detect the fork owner from `gh` auth (usually the authenticated username).

### 4. Create a branch

- Get the default branch SHA: `gh api repos/<fork-owner>/<repo>/git/refs/heads/<default-branch>`
- Create branch `add-distributional-agi-safety`: `gh api repos/<fork-owner>/<repo>/git/refs -X POST`

### 5. Insert the entry

- Fetch the README from the fork.
- Find the last entry in the target section (before the next `##` heading or end of file).
- Insert the new entry after the last existing entry in the section.
- Push the updated README to the branch via `gh api repos/<fork-owner>/<repo>/contents/README.md -X PUT`.

### 6. Open the PR

```bash
gh pr create --repo <owner>/<repo> \
  --head <fork-owner>:add-distributional-agi-safety \
  --base <default-branch> \
  --title "Add <short-title>" \
  --body "$(cat <<'EOF'
## New Resource

<1-3 sentence description of what is being added and why it fits the section.>

<Link to project/paper>
EOF
)"
```

### 7. Report

Print the PR URL and a summary:
```
Submitted to <owner>/<repo>
  Section: <section-name>
  PR: <url>
  Entry: <entry-text>
```

## Constraints

- Always use `gh` CLI, not MCP GitHub tools (MCP auth may not be configured).
- Never force-push to the fork.
- Always show the user the draft entry and PR body before opening — do not submit without confirmation.
- If the section is not found in the README, list available sections and ask the user to pick one.
- If the fork already has a branch with the same name, append a numeric suffix (e.g. `add-distributional-agi-safety-2`).
- Do not modify any files in the local repo — all work happens via GitHub API.

## Relation to Other Commands

- `/submit_to_list` submits to external repos — it does not touch the local working tree.
- `/pr` creates PRs for this repo's own branches.
- `/status` can be run before/after to confirm local state is unaffected.
