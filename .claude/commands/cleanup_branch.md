# /cleanup_branch

Post-merge cleanup: switch to main, pull, and delete the merged feature branch locally and on the remote.

## Usage

`/cleanup_branch [branch-name]`

Examples:
- `/cleanup_branch` (detects current or most recently merged branch)
- `/cleanup_branch fix/pre-commit-scoped-lint`

## Behavior

1) Identify the branch to clean up:
- If `<branch-name>` is provided, use it.
- Otherwise, if currently on a non-main branch, use that branch.
- If already on `main`, check `gh pr list --state merged --limit 5` for recently merged branches and offer a choice.

2) Switch to main and pull:
- `git checkout main && git pull origin main`
- If there are uncommitted changes on the feature branch, stash them first and pop after checkout.

3) Delete the local branch:
- Use `git branch -D <branch>` (force-delete is safe because the PR was squash-merged, so git won't see it as "fully merged").

4) Delete the remote branch:
- `git push origin --delete <branch>`
- If the remote branch was already deleted (e.g. GitHub auto-delete), skip gracefully.

5) Print confirmation: branch name deleted, current HEAD on main.

## Constraints

- Never delete `main` or `master`.
- If the branch has unmerged commits that don't appear in any merged PR, warn the user before deleting.
- If stashing was needed, always verify the stash was popped successfully.
