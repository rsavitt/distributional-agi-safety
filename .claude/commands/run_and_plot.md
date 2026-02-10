# /run_and_plot

Run a SWARM scenario and immediately generate plots from the results. Combines `/run_scenario` + `/plot` into one step.

## Usage

`/run_and_plot <scenario_path_or_id> [seed] [epochs] [steps]`

Examples:
- `/run_and_plot baseline`
- `/run_and_plot scenarios/strict_governance.yaml 42 15 12`
- `/run_and_plot collusion_detection 123 20 10`

ARGUMENTS: $ARGUMENTS

## Behavior

### Step 1: Run the scenario (same as `/run_scenario`)

1) Resolve `<scenario_path_or_id>`:
- If it contains `/` or ends with `.yaml`, treat it as a path.
- Otherwise resolve to `scenarios/<id>.yaml`.

2) Create a run directory:
- `runs/<YYYYMMDD-HHMMSS>_<scenario_id>_seed<seed>/`

3) Run the scenario via the project CLI:
- `python -m swarm run <scenario.yaml> --seed <seed> --epochs <epochs> --steps <steps> --export-json <run_dir>/history.json --export-csv <run_dir>/csv`

4) If the scenario YAML declares `outputs.event_log` or `outputs.metrics_csv`, copy those artifacts into `<run_dir>/artifacts/`.

### Step 2: Generate plots (same as `/plot`)

5) Run the plotting script against the run directory:
- `python examples/plot_run.py <run_dir>`

6) Display the generated plot images inline (read each PNG).

### Step 3: Print consolidated summary

7) Print a single PR-ready block combining run results and plot paths:
- Scenario id, seed, epochs, steps
- Total interactions, accepted interactions, avg toxicity, final welfare
- Success criteria pass/fail
- List of generated plots
- All paths written under `runs/...`

## Constraints / invariants

- Never overwrite an existing `runs/<...>/` directory; if it exists, create a new run id.
- Keep the run folder self-contained (history JSON + CSV exports + plots).
- If plotting fails (missing deps), still report the run results and write a fallback README in the plots directory.
