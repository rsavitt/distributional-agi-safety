# /merge_all_sessions

Batch merge ALL `session/pane-*` branches into `main` sequentially. Run this from the main repo (not a worktree) to land all session work at once.

## Arguments

- `--cleanup` — after merging, remove worktrees and delete branches for successfully merged sessions

## Behavior

1. **Enumerate branches** — list all branches matching `session/pane-*`, sorted numerically by pane number.

2. **For each branch**, in order:

   a. Check how many commits the branch is ahead of `origin/main`:
      ```bash
      git rev-list --count origin/main..<branch>
      ```
      If 0 → mark as SKIPPED ("nothing to merge") and continue.

   b. Check if the corresponding worktree (`.worktrees/session-<N>`) has a dirty working tree:
      ```bash
      git -C .worktrees/session-<N> status --porcelain
      ```
      If dirty → mark as SKIPPED ("dirty worktree") and continue.

   c. Check out the branch in a temporary detached state and rebase:
      ```bash
      git fetch origin main
      git checkout <branch>
      git rebase origin/main
      ```
      If conflict → `git rebase --abort`, `git checkout -` , mark as CONFLICT and continue.

   d. Push:
      ```bash
      git push origin HEAD:main
      ```
      If rejected → fetch, rebase, retry once. If still fails → mark as FAILED, `git checkout -`, continue.

   e. Mark as SUCCESS. Return to previous branch: `git checkout -`

3. **Report results table**:
   ```
   Session Merge Results
   ═══════════════════════════════════════════
   session/pane-1   SUCCESS    3 commits
   session/pane-2   SKIPPED    nothing to merge
   session/pane-3   CONFLICT   swarm/core/proxy.py
   session/pane-4   SUCCESS    1 commit
   ═══════════════════════════════════════════
   ```

4. **If `--cleanup` was passed**: for each SUCCESS branch, remove the worktree and delete the branch:
   ```bash
   git worktree remove --force .worktrees/session-<N>
   git branch -D session/pane-<N>
   ```
   Prune worktree refs: `git worktree prune`

## Constraints

- Never force-push
- Process branches in numeric order (pane-1 before pane-2, etc.)
- Always rebase, never merge commit
- Skip rather than fail on dirty worktrees
- Leave CONFLICT and FAILED branches untouched for manual resolution
