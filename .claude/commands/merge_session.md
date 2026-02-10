# /merge_session

Merge the current session branch into `main` via rebase + fast-forward push. Use this from inside a session worktree pane to land your work.

## Behavior

Run the following steps. Stop immediately on any failure and report the issue.

1. **Verify branch** — run `git branch --show-current`. If it does not match `session/*`, print an error and stop:
   ```
   Error: Not on a session branch (current: <branch>). /merge_session only works from session/* branches.
   ```

2. **Check working tree** — run `git status --porcelain`. If there is any output, print an error and stop:
   ```
   Error: Working tree is dirty. Commit or stash changes before merging.
   ```
   List the dirty files so the user knows what to deal with.

3. **Fetch latest main**:
   ```bash
   git fetch origin main
   ```

4. **Rebase onto main**:
   ```bash
   git rebase origin/main
   ```
   If the rebase fails with conflicts:
   - Run `git rebase --abort`
   - Run `git diff --name-only --diff-filter=U` to list conflicting files
   - Print the list and stop:
     ```
     Rebase conflict — aborted. Conflicting files:
       <file1>
       <file2>
     Resolve manually or coordinate with the other session.
     ```

5. **Push to main**:
   ```bash
   git push origin HEAD:main
   ```
   If the push is rejected (non-fast-forward):
   - Fetch again: `git fetch origin main`
   - Rebase again: `git rebase origin/main` (abort on conflict as above)
   - Retry push once: `git push origin HEAD:main`
   - If it fails again, report the error and stop.

6. **Report success**:
   ```
   Merged session branch to main:
     Branch: <branch>
     Commits: <N> commits rebased
     HEAD:   <short_hash> <message>
   ```

## Constraints

- Never force-push
- Never push to any remote branch other than `main`
- Always rebase (never merge commit) to keep linear history
- If anything goes wrong, leave the branch in a clean state (rebase --abort if needed)
