# /publish_figures

Generate publication-quality cross-run comparative figures from SWARM run data.

## Usage

`/publish_figures <output_dir> [scenario_ids...] [--style paper|nature|arxiv]`

Examples:
- `/publish_figures docs/papers/figures/ collusion_detection network_effects emergent_capabilities`
- `/publish_figures docs/papers/figures/ --style nature`
- `/publish_figures runs/20260209_sweep/plots/` (uses all runs in SQLite)

## Behavior

1) **Gather data**: query the `scenario_runs` SQLite table for the specified scenario_ids (or all if none given). Also load epoch-level data from `<run_dir>/history.json` or CSV exports where available for time-series plots.

2) **Generate a standard set of comparative figures** using matplotlib:

   a) **Scenario comparison bar chart** (`fig_scenario_comparison.png`):
      - Grouped bars: acceptance_rate, avg_toxicity, welfare_per_epoch (scaled) across all scenarios.
      - Error bars if multiple seeds exist for a scenario.
      - Value annotations above each bar.

   b) **Regime scatter plot** (`fig_regime_scatter.png`):
      - X-axis: adversarial_fraction, Y-axis: acceptance_rate.
      - Color by regime (Cooperative / Managed Friction / Collapse Risk) using the 35% threshold line.
      - Each scenario labeled with its name.

   c) **Timeline overlay** (`fig_timeline_overlay.png`):
      - Multi-line time series of welfare or acceptance_rate across scenarios.
      - Each scenario as a distinct colored line with legend.
      - Epochs on x-axis, metric on y-axis.

   d) **Pairwise comparison panels** (`fig_pairwise_<a>_vs_<b>.png`):
      - Only generated if exactly 2 scenario_ids are given.
      - Side-by-side subplots comparing epoch-by-epoch welfare, toxicity, and acceptance.
      - Includes mean lines and fill_between for variance.

   e) **Scaling/sensitivity plot** (`fig_scaling.png`):
      - Only if incoherence variants or sweep data detected.
      - Metric vs. agent_count or parameter value.

3) **Apply consistent styling** based on `--style` flag (default: `paper`):

   ```python
   STYLES = {
       "paper": {"font.size": 11, "figure.dpi": 150, "savefig.dpi": 300,
                  "font.family": "serif"},
       "nature": {"font.size": 8, "figure.dpi": 150, "savefig.dpi": 600,
                   "figure.figsize": (3.5, 2.5), "font.family": "sans-serif"},
       "arxiv": {"font.size": 10, "figure.dpi": 150, "savefig.dpi": 300,
                  "figure.figsize": (6, 4), "font.family": "serif"},
   }
   ```

   - Use colorblind-safe palette (matplotlib "tab10" or custom safe set).
   - All figures use `tight_layout()` and `savefig(bbox_inches="tight")`.

4) **Write a manifest** (`<output_dir>/figure_manifest.json`):
   ```json
   {
     "generated_at": "2026-02-09T...",
     "style": "paper",
     "scenarios": ["collusion_detection", "network_effects"],
     "figures": [
       {"filename": "fig_scenario_comparison.png", "caption": "Cross-scenario comparison of key metrics"}
     ]
   }
   ```

5) **Print summary**: list all generated figures with paths and suggested captions for paper inclusion.

## Relation to /plot

- `/plot` generates **per-run diagnostic** figures (single run, single scenario).
- `/publish_figures` generates **cross-run comparative** figures for papers (multiple scenarios on one plot).

## Constraints

- Figures must be self-contained — no external data dependencies after generation.
- All text in figures must be legible at column width (minimum 8pt font).
- Color palette must be colorblind-safe.
- Never overwrite existing figures without user confirmation. If files exist, prompt before replacing.
