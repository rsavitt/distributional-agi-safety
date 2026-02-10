# /warmup

Session opening sequence. Runs `/status`, `/healthcheck`, and tests in one shot.

## Usage

`/warmup` or `/warmup --skip-tests`

## Behavior

### Step 1: /status

Run the full `/status` check (branch, remote, working tree, stashes, open PRs, recent commits). Present the consolidated summary.

### Step 2: /healthcheck

Run the full `/healthcheck` scan (duplicate defs, dead imports, import conflicts, merge artifacts, stale re-exports). Present the results.

### Step 3: Tests

Run the test suite:

```bash
python -m pytest tests/ -x -q
```

Report pass/fail count and duration.

### `--skip-tests` mode

When `/warmup --skip-tests` is used, skip Step 3. Useful when you just need orientation without waiting for the full test run.

## Output Format

Present all three results in a single consolidated block:

```
Session Warmup
══════════════════════════════════════════

  1/3  STATUS
  Branch:      main
  Remote:      0 ahead, 0 behind — in sync
  Working tree: clean
  ...

  2/3  HEALTHCHECK
  Duplicates: 0 | Dead imports: 0 | Merge artifacts: 0
  Status: CLEAN

  3/3  TESTS
  2202 passed in 28.1s

══════════════════════════════════════════
  Ready to work.
```

## Why This Exists

Every resumed session needs the same 3-step orientation:
1. Where am I? (git state)
2. Is the code healthy? (post-merge issues)
3. Are tests passing? (runtime baseline)

`/warmup` bundles these into one command instead of three separate invocations.

## Relation to Other Commands

- `/warmup` is the first thing to run in a session
- `/preflight` checks staged code before commit — run it later
- `/stage` prepares files for commit — run it after editing
