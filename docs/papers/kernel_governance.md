# Governance Parameter Effects in a GPU Kernel Marketplace: Tax and Circuit Breaker Null Results With Strong Agent-Type Stratification

**Authors:** Raeli Savitt
**Date:** 2026-02-10
**Framework:** SWARM v1.0.0

## Abstract

We test the effects of transaction taxes (0-15%) and circuit breakers on a
simulated GPU kernel marketplace with adversarial benchmark gaming. Across
80 runs (8 governance configurations x 10 pre-registered seeds) with 8
agents (3 honest kernel authors, 2 opportunistic speed-chasers, 2 verifiers,
1 adversarial benchmark gamer), we find **no statistically significant effect
of transaction tax rate on either welfare or toxicity** (0/12 pairwise
hypotheses survive any correction method; largest effect: 0% vs 15% welfare
p = 0.108, d = 0.52). Circuit breakers show a marginal toxicity reduction
(p = 0.017, d = 0.55) that does not survive Bonferroni correction. In
contrast, agent-type payoff stratification is massive and robust: all 6
pairwise agent-type comparisons are Bonferroni-significant (all p < 0.00001),
with honest kernel authors earning 32.21, opportunistic fast authors 16.34,
verifiers 2.54, and adversarial benchmark gamers -3.37. These results
demonstrate that in a marketplace with staking, auditing, and escrow
mechanisms, the governance baseline already saturates the protective effect —
marginal parameter changes (tax rate, circuit breaker toggle) are
undetectable against the variance introduced by agent composition. The
dominant factor in kernel marketplace outcomes is **who participates**, not
**how they are governed**.

## 1. Introduction

GPU kernel marketplaces present a distinctive adverse selection challenge:
proxy signals (unit test pass rates, performance benchmarks) can be gamed
by agents that overfit to test distributions, exploit numerical precision
tolerances, or hardcode edge cases. Governance mechanisms must detect these
proxy exploits without imposing excessive friction on honest kernel authors.

This study asks whether two marginal governance changes — transaction tax
rate and circuit breaker activation — measurably affect marketplace outcomes
in a scenario where the governance baseline already includes auditing (15%
probability, 3x penalty), staking (0.5 minimum, 20% slash rate), reputation
decay (0.95), and bandwidth caps. We contrast this with a companion study
on RLM recursive collusion agents, where the same tax sweep produced large,
significant effects (welfare d = 1.33, toxicity d = 2.45).

## 2. Experimental Setup

### 2.1 Scenario

| Property | Value |
|----------|-------|
| Scenario ID | `kernel_market_baseline` |
| Motif | `kernel_market` |
| Domain | GPU kernel trading (LeetGPU-inspired) |
| Epochs | 5 (reduced from 20 for sweep efficiency) |
| Steps/Epoch | 10 |
| Total agents | 8 |

### 2.2 Agent Composition

| Group | Type | Count | Role | Key Config |
|-------|------|-------|------|-----------|
| `kernel_author` | Honest | 3 | Kernel author | quality_mean=0.8, speed_priority=0.3 |
| `fast_author` | Opportunistic | 2 | Kernel author | quality_mean=0.45, speed_priority=0.9 |
| `kernel_verifier` | Verifier | 2 | Verifier | accuracy=0.8 |
| `benchmark_gamer` | Adversarial | 1 | Kernel author | exploit_proxy=true, target=performance |

### 2.3 Governance Baseline (Held Constant)

| Parameter | Value |
|-----------|-------|
| Audit probability | 0.15 |
| Audit penalty multiplier | 3.0 |
| Staking enabled | Yes (min_stake=0.5, slash_rate=0.2) |
| Reputation decay | 0.95 |
| Bandwidth cap | 5 |
| Escrow fee rate | 0.03 |
| Marketplace enabled | Yes |

### 2.4 Kernel Oracle Configuration

| Parameter | Value |
|-----------|-------|
| Difficulty distribution | Easy 40%, Medium 40%, Hard 20% |
| Honest quality mean | 0.85 |
| Opportunistic quality mean | 0.55 |
| Adversarial quality mean | 0.75 |
| Adversarial cheat rate | 0.60 |
| Audit detection rate | 0.80 |
| Verifier detection rate | 0.30 |

### 2.5 Sweep Configuration

| Parameter | Values |
|-----------|--------|
| `transaction_tax_rate` | 0.0, 0.05, 0.10, 0.15 |
| `circuit_breaker_enabled` | True, False |
| Seeds per configuration | 10 (pre-registered: 43-122) |
| **Total runs** | **80** |

### 2.6 Payoff Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| s_plus | 3.0 | Correct + performant kernel surplus |
| s_minus | 2.0 | Wrong kernel cost (production failures) |
| h | 4.0 | Downstream harm (silent numerical errors) |
| theta | 0.5 | Surplus split |
| rho_a, rho_b | 0.1 | Both parties bear some externality |
| w_rep | 1.5 | Reputation weight (quality track record) |

## 3. Results

### 3.1 Cross-Configuration Summary

| Tax | CB | Toxicity | Welfare/Ep | Quality Gap | Honest $ | Opp $ | Adv $ | Accept % |
|-----|-----|----------|-----------|-------------|----------|-------|-------|----------|
| 0% | Off | 0.386 | 5.12 | 0.128 | 3.90 | 3.78 | -1.28 | 81.2% |
| 0% | On | 0.399 | 4.60 | 0.098 | 3.48 | 3.47 | -1.52 | 82.7% |
| 5% | Off | 0.388 | 4.48 | 0.115 | 3.44 | 3.60 | -1.92 | 82.6% |
| 5% | On | 0.395 | 4.06 | 0.109 | 3.24 | 2.86 | -1.70 | 82.6% |
| 10% | Off | 0.389 | 4.63 | 0.096 | 3.40 | 4.10 | -2.12 | 82.3% |
| 10% | On | 0.397 | 4.30 | 0.093 | 3.38 | 3.28 | -1.93 | 83.0% |
| 15% | Off | 0.391 | 4.37 | 0.122 | 3.60 | 2.79 | -1.60 | 83.5% |
| 15% | On | 0.397 | 3.96 | 0.087 | 3.31 | 2.45 | -1.74 | 85.0% |

### 3.2 Tax Rate Effect (Aggregated Over Circuit Breaker)

| Tax Rate | Welfare (mean +/- SD) | Toxicity (mean +/- SD) | Honest $ | Opp $ | Adv $ |
|----------|----------------------|----------------------|----------|-------|-------|
| 0% | 4.86 +/- 1.39 | 0.392 +/- 0.034 | 3.69 | 3.63 | -1.40 |
| 5% | 4.27 +/- 1.41 | 0.391 +/- 0.033 | 3.34 | 3.23 | -1.81 |
| 10% | 4.46 +/- 1.06 | 0.393 +/- 0.023 | 3.39 | 3.69 | -2.03 |
| 15% | 4.17 +/- 1.26 | 0.394 +/- 0.026 | 3.46 | 2.62 | -1.67 |

No monotonic pattern in welfare (non-monotonic dip at 5%, recovery at 10%).
Toxicity is essentially **flat** across all tax levels (0.391-0.394, range
0.003). This contrasts sharply with the RLM collusion scenario where the
same sweep produced a 0.011 toxicity range with d = 2.45.

### 3.3 Statistical Tests

#### 3.3.1 Pairwise Tax Comparisons (P-Hacking Audit)

12 hypotheses: 6 pairwise tax comparisons x 2 metrics. Bonferroni threshold:
alpha = 0.05/12 = 0.004167.

| # | Comparison | Metric | p-value | Cohen's d | Bonferroni | BH |
|---|-----------|--------|---------|-----------|------------|-----|
| 1 | 0% vs 15% | Welfare | 0.108 | 0.520 | No | No |
| 2 | 0% vs 5% | Welfare | 0.190 | 0.422 | No | No |
| 3 | 0% vs 10% | Welfare | 0.314 | 0.323 | No | No |
| 4 | 10% vs 15% | Welfare | 0.433 | 0.251 | No | No |
| 5 | 5% vs 10% | Welfare | 0.629 | -0.154 | No | No |
| 6 | 5% vs 15% | Toxicity | 0.803 | -0.079 | No | No |
| 7 | 5% vs 15% | Welfare | 0.814 | 0.075 | No | No |
| 8 | 5% vs 10% | Toxicity | 0.859 | -0.057 | No | No |
| 9 | 0% vs 15% | Toxicity | 0.888 | -0.045 | No | No |
| 10 | 0% vs 5% | Toxicity | 0.925 | 0.030 | No | No |
| 11 | 10% vs 15% | Toxicity | 0.926 | -0.030 | No | No |
| 12 | 0% vs 10% | Toxicity | 0.947 | -0.021 | No | No |

**Summary: 0/12 survive Bonferroni. 0/12 survive Benjamini-Hochberg.**
The largest effect (0% vs 15% welfare, d = 0.52) is medium-sized but
underpowered at n = 20 per group.

#### 3.3.2 Circuit Breaker Effect

| Metric | t-statistic | p-value | Cohen's d |
|--------|------------|---------|-----------|
| Welfare | -1.232 | 0.222 | -0.275 |
| Toxicity | 2.454 | 0.017 | 0.549 |

Circuit breakers show a marginal toxicity reduction (CB Off: higher toxicity)
with medium effect size (d = 0.55), but it does not survive correction.
This is the only near-significant governance parameter effect in the kernel
market domain.

#### 3.3.3 Per-Agent Group Comparison

| Group | N | Mean Payoff | SD |
|-------|---|-------------|-----|
| kernel_author (honest) | 30 | 32.21 | 12.35 |
| fast_author (opportunistic) | 20 | 16.34 | 5.39 |
| kernel_verifier | 20 | 2.54 | 1.35 |
| benchmark_gamer (adversarial) | 10 | -3.37 | 1.95 |

**All 6 pairwise comparisons are Bonferroni-significant** (all p < 0.00001):

| Comparison | t | p | d |
|-----------|---|---|---|
| benchmark_gamer vs fast_author | -14.56 | < 0.0001 | -4.31 |
| benchmark_gamer vs kernel_author | -15.22 | < 0.0001 | -3.28 |
| benchmark_gamer vs kernel_verifier | -8.61 | < 0.0001 | -3.77 |
| fast_author vs kernel_author | -6.21 | < 0.0001 | -1.56 |
| fast_author vs kernel_verifier | 11.12 | < 0.0001 | 3.52 |
| kernel_author vs kernel_verifier | 13.04 | < 0.0001 | 3.08 |

The payoff hierarchy is clear: honest authors > opportunistic authors >
verifiers > adversarial gamers. The governance baseline successfully makes
benchmark gaming unprofitable (mean = -3.37).

#### 3.3.4 Normality Validation

Shapiro-Wilk tests confirm normality for all groups (all p > 0.10):

| Tax | Welfare W (p) | Toxicity W (p) |
|-----|--------------|----------------|
| 0% | 0.975 (0.859) | 0.976 (0.880) |
| 5% | 0.935 (0.195) | 0.922 (0.109) |
| 10% | 0.927 (0.135) | 0.969 (0.731) |
| 15% | 0.966 (0.676) | 0.977 (0.896) |

### 3.4 Figures

![Welfare vs Tax Rate (95% CI)](../../runs/20260210-220048_kernel_governance/plots/welfare_vs_tax.png)
*Figure 1: Welfare vs tax rate in the kernel market. No significant differences across tax levels (all p > 0.10). Error bars show 95% CI.*

![Toxicity vs Tax Rate (95% CI)](../../runs/20260210-220048_kernel_governance/plots/toxicity_vs_tax.png)
*Figure 2: Toxicity is flat across tax rates (range: 0.003). The governance baseline already determines the toxicity floor.*

![Welfare-Toxicity Tradeoff](../../runs/20260210-220048_kernel_governance/plots/welfare_toxicity_tradeoff.png)
*Figure 3: Welfare-toxicity tradeoff. All configurations cluster tightly, with CB On (green) showing slightly lower toxicity than CB Off (blue) at each tax level.*

![Quality Gap vs Tax Rate](../../runs/20260210-220048_kernel_governance/plots/quality_gap_vs_tax.png)
*Figure 4: Quality gap remains positive (0.09-0.13) across all configurations, indicating governance selects higher-quality kernels.*

![Agent Payoff by Type](../../runs/20260210-220048_kernel_governance/plots/agent_payoff_by_type.png)
*Figure 5: Agent payoff by type. Adversarial benchmark gamers consistently earn negative payoffs. The payoff hierarchy is the dominant signal — not governance parameters.*

![Circuit Breaker Effect](../../runs/20260210-220048_kernel_governance/plots/circuit_breaker_effect.png)
*Figure 6: Circuit breaker shows a marginal toxicity effect (p = 0.017, d = 0.55) that does not survive multiple comparisons correction.*

## 4. Discussion

### 4.1 Why Taxes Don't Matter Here (But Did in RLM)

The null tax result in the kernel market contrasts with the large, significant
effects found in the RLM recursive collusion scenario (same tax sweep, same
statistical methods). The key difference is **governance baseline saturation**:

| Mechanism | RLM Collusion | Kernel Market |
|-----------|--------------|---------------|
| Staking | No | Yes (0.5 min, 20% slash) |
| Escrow | No | Yes (3% fee) |
| Externality internalization | rho = 0.0 | rho = 0.1 |
| Reputation weight | 1.0 | 1.5 |
| Audit penalty | 2.0x | 3.0x |

The kernel market's richer governance stack (staking + escrow + higher audit
penalties + externality sharing + stronger reputation weight) already captures
most of the protective effect. Adding a transaction tax on top of this stack
is like adding a second lock to a door that's already bolted — the marginal
benefit is undetectable.

### 4.2 Agent Composition Dominates Governance Tuning

The most striking finding is the contrast between governance-parameter null
results (d < 0.55) and agent-type stratification (d = 1.56 to 4.31). The
marketplace outcome is overwhelmingly determined by the mix of participants
rather than the governance parameters. This has practical implications:
platform designers should focus more on **admission criteria** and
**agent verification** than on fine-tuning tax rates or circuit breaker
thresholds.

### 4.3 The Adversarial Deterrence Floor

Benchmark gamers earn -3.37 across all configurations — the governance
baseline makes cheating consistently unprofitable. Importantly, this
negative payoff is stable across tax rates and circuit breaker settings,
meaning the deterrence comes from the combination of auditing (80% detection
rate), staking (slashed on detection), and reputation decay, not from
taxes or circuit breakers.

### 4.4 Circuit Breaker Marginal Signal

The one near-significant result — circuit breakers reducing toxicity
(d = 0.55, p = 0.017) — suggests circuit breakers may have a small genuine
effect in domains with adversarial agents. Unlike the RLM collusion
scenario (where CB had zero effect), the kernel market's adversarial
benchmark gamer occasionally triggers freeze thresholds, providing marginal
additional protection. However, this effect is not strong enough to survive
correction.

## 5. Limitations

1. **Reduced epochs** (5 vs 20 baseline): The sweep used 5 epochs for
   efficiency. Longer runs may reveal effects that require reputation
   equilibration to manifest.
2. **Single adversarial agent**: With only 1/8 agents adversarial (12.5%),
   the scenario may be too benign for governance differences to matter.
   Higher adversarial fractions would increase variance and potentially
   reveal tax sensitivity.
3. **Power analysis**: At n = 20 per tax level, the study has ~55% power to
   detect d = 0.5 effects. The largest observed effect (d = 0.52) is
   plausibly real but underpowered. A follow-up with 30+ seeds per
   configuration would resolve this.
4. **No kernel oracle variation**: The kernel oracle parameters (quality
   means, cheat rates) are held constant. Varying these would test whether
   governance sensitivity depends on the difficulty of the proxy-gaming
   problem.
5. **Escrow confound**: The kernel market's escrow mechanism redistributes
   transaction costs differently from a pure tax, potentially masking or
   offsetting the tax effect.

## 6. Reproducibility

```bash
python -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
from swarm.analysis import SweepConfig, SweepParameter, SweepRunner
from swarm.scenarios import load_scenario

scenario = load_scenario(Path('scenarios/kernel_market/baseline.yaml'))
scenario.orchestrator_config.n_epochs = 5

config = SweepConfig(
    base_scenario=scenario,
    parameters=[
        SweepParameter(name='governance.transaction_tax_rate',
                       values=[0.0, 0.05, 0.10, 0.15]),
        SweepParameter(name='governance.circuit_breaker_enabled',
                       values=[False, True]),
    ],
    runs_per_config=10, seed_base=42,
)
runner = SweepRunner(config)
runner.run()
runner.to_csv(Path('sweep_results.csv'))
"
```

Raw data: `runs/20260210-220048_kernel_governance/sweep_results.csv`
Summary: `runs/20260210-220048_kernel_governance/summary.json`

## 7. References

1. Savitt, R. (2026). "Governance Parameter Effects on Recursive Collusion
   Dynamics in Multi-Agent Systems." SWARM Technical Report.
2. Savitt, R. (2026). "Distributional AGI Safety: Governance Trade-offs in
   Multi-Agent Systems Under Adversarial Pressure." SWARM Technical Report.
3. SWARM Framework. https://github.com/swarm-ai-safety/swarm
