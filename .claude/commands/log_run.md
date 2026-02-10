# /log_run

Log a completed SWARM run to the SQLite runs database.

## Usage

`/log_run <run_dir> [--notes "..."]`

Examples:
- `/log_run runs/20260209-143000_collusion_detection_seed42`
- `/log_run runs/20260209-143000_baseline_seed42 --notes "Increased rep decay to 0.15"`

## Behavior

1) Read `<run_dir>/history.json` (preferred). If missing, read CSV files under `<run_dir>/csv/`. If neither exists, error out with instructions.

2) Extract summary metrics from the run data:
   - `scenario_id`: from directory name or history metadata
   - `run_timestamp`: from directory name (YYYYMMDD-HHMMSS)
   - `seed`: from directory name or history metadata
   - `n_agents`: count of unique agent IDs
   - `n_epochs`: number of completed epochs
   - `steps_per_epoch`: from history metadata or scenario config
   - `total_interactions`: count of all interactions
   - `accepted_interactions`: count of accepted interactions
   - `acceptance_rate`: accepted / total
   - `avg_toxicity`: mean toxicity across epochs (E[1-p | accepted])
   - `final_welfare`: last epoch's welfare value
   - `total_welfare`: sum of welfare across all epochs
   - `welfare_per_epoch`: total_welfare / n_epochs
   - `adversarial_fraction`: fraction of agents with type containing "adversarial" or "redteam"
   - `collapse_epoch`: first epoch where welfare drops to 0 and stays 0 (NULL if no collapse)
   - `notes`: from `--notes` flag or empty string

3) Locate or create the SQLite database at the path from `$SWARM_RUNS_DB_PATH` env var, or default to `runs/runs.db`. If the `scenario_runs` table does not exist, create it:

```sql
CREATE TABLE IF NOT EXISTS scenario_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL,
    run_timestamp TEXT,
    seed INTEGER,
    n_agents INTEGER,
    n_epochs INTEGER,
    steps_per_epoch INTEGER,
    total_interactions INTEGER,
    accepted_interactions INTEGER,
    acceptance_rate REAL,
    avg_toxicity REAL,
    final_welfare REAL,
    total_welfare REAL,
    welfare_per_epoch REAL,
    adversarial_fraction REAL,
    collapse_epoch INTEGER,
    notes TEXT,
    logged_at TEXT DEFAULT (datetime('now'))
);
```

4) Check for duplicates: if a row with matching (scenario_id, seed, run_timestamp) already exists, warn and skip (do NOT overwrite). Print the existing row.

5) Insert the row and print:
   - A formatted summary of the inserted row
   - Total row count in the table
   - The SQLite query used (for reproducibility)

## Integration with /run_scenario

After running a scenario, call `/log_run <run_dir>` to persist results. The `/run_scenario` command should mention this at the end of its output.

## Constraints

- Never delete or update existing rows — append only.
- Round floats to 4 decimal places for consistency.
- If run data is incomplete (e.g. scenario crashed mid-run), still log what is available and note "PARTIAL" in the notes field.
