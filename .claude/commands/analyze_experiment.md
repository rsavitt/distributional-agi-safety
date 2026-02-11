# /analyze_experiment

Run a scenario across multiple seeds and produce publication-ready statistical analysis with multiple comparisons correction.

## Usage

`/analyze_experiment <scenario_path_or_id> [--seeds N|seed1,seed2,...] [--groups auto|key=ids,...]`

Examples:
- `/analyze_experiment rlm_recursive_collusion`
- `/analyze_experiment scenarios/rlm_memory_as_power.yaml --seeds 20`
- `/analyze_experiment rlm_governance_lag --seeds 42,7,123,256,999`
- `/analyze_experiment rlm_memory_as_power --groups high=rlm_1,rlm_2,rlm_3 mid=rlm_4,rlm_5,rlm_6 low=rlm_7`

## Arguments

- `scenario_path_or_id`: Path to YAML or scenario ID (resolved to `scenarios/<id>.yaml`).
- `--seeds`: Either an integer N (generate N random seeds) or a comma-separated list. Default: `42,7,123,256,999,2024,314,577,1337,8080` (10 seeds).
- `--groups`: How to group agents for comparison. `auto` (default) infers groups from the scenario YAML's agent specs (by `type` + `name` + `config` differences). Otherwise specify explicit groups as `label=id1,id2,...`.

## Behavior

### Step 1: Load scenario and determine agent groups

- Parse the scenario YAML via `load_scenario()`.
- If `--groups auto`, infer groups from agent specs. Each unique combination of `type`, `name` prefix, and distinguishing config keys (e.g. `recursion_depth`, `memory_budget`) becomes a group.
- Print the detected groups for confirmation.

### Step 2: Run all seeds via orchestrator (not CLI)

For each seed, directly:

```python
from swarm.scenarios.loader import load_scenario, build_orchestrator
scenario.orchestrator_config.seed = seed
orch = build_orchestrator(scenario)
orch.run()
```

Extract per-agent payoffs from `orch.state.agents[aid].total_payoff`.

Do NOT use `python -m swarm run` -- the CLI does not expose per-agent payoffs in its JSON export. Running via orchestrator directly avoids the schema mismatch.

Print a one-line summary per seed as it completes.

### Step 3: Compute statistics

For each pair of groups and across all groups:

**Descriptive stats:**
- Per-group: mean, std, n
- Overall: Gini coefficient (dominance index)

**Hypothesis tests (all pre-registered, not post-hoc):**
1. Pairwise independent t-tests between all group pairs
2. One-way ANOVA across all groups (if 3+ groups)
3. Effect sizes: Cohen's d for each pairwise comparison
4. Pearson correlation between the grouping variable and payoff (if groups have a natural ordering, e.g. recursion depth or memory budget)
5. One-sample t-test: Gini > 0

**Multiple comparisons correction:**
- Report raw p-values
- Apply Bonferroni correction (alpha / n_tests)
- Apply Holm-Bonferroni (step-down) correction
- Flag which results survive each correction

**Domain-specific metrics (if applicable):**
- If agents have `working_memory.recursion_traces`, compute `RLMMetrics.rationalization_consistency()`
- If event log is available, compute collusion coordination metrics

### Step 4: Output formatted results

Print results in three blocks:

1. **Per-seed summary table** (one line per seed with group means)
2. **Descriptive statistics block** (group means/stds)
3. **Hypothesis tests table** with columns: Test, Statistic, Raw p, Significance, Cohen's d, Bonferroni, Holm-Bonferroni
4. **P-hacking audit table** sorted by raw p-value with correction columns

### Step 5: Save artifacts

Create `runs/<YYYYMMDD-HHMMSS>_analysis_<scenario_id>/`:
- `results.txt`: Full formatted output
- `per_agent_payoffs.csv`: Raw data (seed, agent_id, group, payoff)
- `summary.json`: Machine-readable results (group means, test statistics, p-values)

## Key APIs (avoid rediscovery)

These are the correct Orchestrator accessors:
- `orch.state.agents` -- dict of `agent_id -> AgentState` (has `.total_payoff`, `.reputation`, etc.)
- `orch.get_all_agents()` -- returns `List[BaseAgent]` (the agent policy objects, not state)
- `orch._epoch_metrics` -- list of `EpochMetrics` (has `.total_welfare`, `.toxicity_rate`, etc.)
- Agent working memory (RLM only): `agent_obj.working_memory.recursion_traces`

Do NOT use:
- `orch.agents` (does not exist -- use `orch.get_all_agents()`)
- `orch._all_interactions` (does not exist)
- `history["epochs"]` from JSON export (key is `epoch_snapshots`, and it lacks per-agent payoffs)

## Statistical rigor requirements

- Always report effect sizes alongside p-values
- Always apply multiple comparisons correction when running 3+ tests
- Always note that seeds were fixed a priori (not selected post-hoc)
- Always note total number of tests run
- Use scipy.stats for all statistical tests (available in the project environment)
- Use numpy for array operations (available in the project environment)

## Constraints

- Run seeds sequentially (orchestrator is not thread-safe)
- Do not modify the scenario YAML file
- Print progress as seeds complete (the user should see that work is happening)
- If a seed fails, report it and continue with remaining seeds
- Minimum 5 seeds for any statistical test; warn if fewer
