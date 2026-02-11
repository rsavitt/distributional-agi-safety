# /stats

Run the full statistical analysis battery on a sweep CSV and output a summary.

## Usage

`/stats <sweep_csv> [--output <dir>]`

Examples:
- `/stats runs/20260210-223119_kernel_market_v2/sweep_results.csv`
- `/stats runs/latest/sweep_results.csv --output runs/latest/`

## Arguments

- `sweep_csv`: Path to a sweep results CSV (output of `/sweep` or `SweepRunner.to_csv()`).
- `--output`: Directory to write `summary.json`. Default: same directory as the CSV.

## Behavior

### Step 1: Load and normalize columns

Read the CSV with pandas. Normalize known column aliases:

```
avg_toxicity       → toxicity_rate
total_welfare      → welfare
honest_avg_payoff  → honest_payoff
opportunistic_avg_payoff → opportunistic_payoff
adversarial_avg_payoff   → adversarial_payoff
deceptive_avg_payoff     → deceptive_payoff
avg_quality_gap    → quality_gap
```

Keep originals if canonical names already exist. Print detected sweep parameters (columns that are not metrics).

### Step 2: Identify swept parameters

Any column whose name contains a `.` (e.g. `governance.transaction_tax_rate`) is a sweep parameter. All other numeric columns are metrics.

### Step 3: Pairwise comparisons

For each swept parameter with discrete values:
- For each pair of values and each metric in `[welfare, toxicity_rate, honest_payoff, opportunistic_payoff, adversarial_payoff, quality_gap]` (using whichever exist):
  1. **Welch's t-test** (two-sided, unequal variance)
  2. **Mann-Whitney U** (non-parametric robustness check)
  3. **Cohen's d** effect size (pooled SD)
  4. Record group means, SDs, and sample sizes

### Step 4: Multiple comparisons correction

Count total hypotheses tested. Apply:
1. **Bonferroni**: reject if `p < 0.05 / n_tests`
2. **Benjamini-Hochberg**: rank p-values, reject if `p_i <= (i / n_tests) * 0.05`

Flag each result with `bonferroni_sig` and `bh_sig` booleans.

### Step 5: Normality checks

Run **Shapiro-Wilk** on the primary metric (welfare) for each group of the first swept parameter. Report W statistic and p-value. Flag groups as NORMAL (p > 0.05) or NON-NORMAL.

### Step 6: Agent-type stratification (if applicable)

If columns for 2+ agent types exist (e.g. `honest_payoff`, `adversarial_payoff`):
- Run **paired t-test** for all agent-type pairs across all runs
- Compute Cohen's d
- Apply Bonferroni correction (over agent-type pairs only)

### Step 7: Output

Print a formatted report:

```
Statistical Analysis: <csv_filename>
============================================================
Swept parameters: governance.transaction_tax_rate (4 values), governance.circuit_breaker_enabled (2 values)
Total runs: 80
Total hypotheses: 42

=== Significant Results (Bonferroni) ===
  welfare: 0.0 vs 0.15 — p=0.0006, d=1.19

=== Agent-Type Stratification ===
  honest=2.21, opp=2.34, adv=-1.65
  honest vs adversarial: d=3.45***

=== Normality (Shapiro-Wilk) ===
  All groups normal (all p > 0.05)
```

Save `summary.json` with structure:

```json
{
  "csv": "<path>",
  "total_runs": 80,
  "total_hypotheses": 42,
  "n_bonferroni_significant": 1,
  "n_bh_significant": 1,
  "swept_parameters": {...},
  "results": [...],
  "agent_stratification": [...],
  "normality": [...]
}
```

## Key APIs

```python
from scipy import stats
import numpy as np
import pandas as pd

# Welch's t-test
stats.ttest_ind(g1, g2, equal_var=False)

# Mann-Whitney U
stats.mannwhitneyu(g1, g2, alternative='two-sided')

# Cohen's d
pooled_sd = np.sqrt((np.std(g1, ddof=1)**2 + np.std(g2, ddof=1)**2) / 2)
d = (np.mean(g1) - np.mean(g2)) / pooled_sd

# Shapiro-Wilk
stats.shapiro(values)

# Paired t-test (for agent stratification)
stats.ttest_rel(g1, g2)
```

## Statistical rigor requirements

- Always report effect sizes alongside p-values
- Always apply multiple comparisons correction
- Always report total number of hypotheses tested
- Always validate normality assumption before interpreting t-tests
- Use Welch's t-test (not Student's) — do not assume equal variance
- Report both parametric (t-test) and non-parametric (Mann-Whitney) results

## Constraints

- Never modify the input CSV
- If fewer than 5 observations per group, warn and skip parametric tests
- Column normalization must be idempotent (running twice gives same result)
- Print progress as analysis proceeds
