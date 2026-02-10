# /healthcheck

Scan the codebase for code health issues that arise from parallel commits, merges, or external changes. Complements `/preflight` (which checks before commit) by checking after external changes arrive.

## Usage

`/healthcheck` or `/healthcheck --fix`

## Behavior

### Step 1: Duplicate Definitions

Scan all `.py` files under `swarm/` and `tests/` for duplicate function and class definitions within the same file:

```bash
# For each .py file, extract all "def name" and "class name" lines
# Flag any name that appears more than once in the same file
```

For each duplicate found, report:
```
DUPLICATE: swarm/research/swarm_papers/track_a.py
  def _build_related_work  (lines 57, 2258, 2337)
  Keep the most robust version (longest, or the one with helper calls)
```

### Step 2: Dead Imports

Run ruff's F401 (unused import) check across modified files:

```bash
ruff check swarm/ tests/ --select F401
```

Report any unused imports that may have been left behind by external edits.

### Step 3: Import Conflicts

Check for the same name imported from different modules in the same file:

```bash
# Scan for "from X import Name" and "from Y import Name" in same file
```

### Step 4: Merge Artifacts

Scan for leftover merge conflict markers:

```bash
grep -rn "^<<<<<<< \|^=======$\|^>>>>>>> " swarm/ tests/ scripts/
```

### Step 5: Stale Re-exports

Check `__init__.py` files for names that no longer exist in their source modules.

### Step 6: Report

```
Healthcheck Results
══════════════════════════════════════════
  Duplicates:     1 found (1 file)
  Dead imports:   0
  Import conflicts: 0
  Merge artifacts:  0
  Stale re-exports: 0
══════════════════════════════════════════
```

### `--fix` mode

When `/healthcheck --fix` is used:
- For duplicate definitions: keep the most robust version (prefer the one with helper function calls, proper escaping, or more complete logic). Remove the others.
- For dead imports: run `ruff check --fix --select F401`
- For merge artifacts and import conflicts: report only (manual fix required)

## Why This Exists

When multiple sessions (Claude Code, Codex, manual edits) commit to the same branch in parallel, HEAD race conditions can cause:
1. **Duplicate function definitions** — the same function added by two commits, both land
2. **Dead imports** — one commit removes a function, another adds an import for it
3. **Merge conflict markers** — incomplete merges leave `<<<<<<<` in files

These issues pass all existing checks (ruff won't flag duplicate `def` names, mypy crashes before reaching them, tests may still pass if Python uses the last definition). `/healthcheck` catches them.

## When to Run

- After `git pull` when other sessions have been active
- At the start of a resumed session (after `/status`)
- After merging a PR
- When tests pass but behavior seems wrong

## Relation to Other Commands

- `/status` shows git state — run it first
- `/healthcheck` checks code health after external changes
- `/preflight` checks staged code before commit
- `/stage` validates and stages files
