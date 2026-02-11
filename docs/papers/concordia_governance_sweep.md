# Governance Costs Without Governance Benefits: A Concordia Narrative Sweep

**Authors:** Raeli Savitt
**Date:** 2026-02-11
**Framework:** SWARM v1.0.0 (Concordia bridge, synthetic narrative mode)

## Abstract

We run 40 experiments (8 governance configurations x 5 seeds) through the SWARM-Concordia bridge using synthetic narratives with pre-computed judge scores, isolating governance mechanism effects from LLM variance. Across 2,000 steps (10 epochs x 5 steps x 40 runs), we find that governance levers operating downstream of interaction scoring -- transaction tax, random audits, reputation decay -- reduce aggregate welfare by up to 12.5% without affecting measured toxicity. Only the circuit breaker lever produces a qualitatively different outcome: freezing up to 5 of 6 agents by mid-run. These results establish a baseline for the Concordia bridge and highlight a structural limitation of post-hoc governance: when the scoring pipeline is fixed, governance can redistribute costs but cannot improve the underlying signal.

## 1. Setup

### 1.1 Narrative Corpus

Rather than making LLM calls through Concordia, we generate a controlled corpus of synthetic narratives using `swarm.bridges.concordia.narratives`. Each narrative is drawn from a parameterized mix (30% adversarial/collusive, 42% cooperative, 28% competitive) and paired with ground-truth `JudgeScores`. A `CorpusJudge` subclass of `LLMJudge` injects these scores deterministically, ensuring that all 8 governance configs process identical interaction quality distributions per seed.

This design isolates the question: *given the same stream of interactions, how do different governance configurations affect aggregate outcomes?*

### 1.2 Agent Roster

6 agents: 4 honest, 1 adversarial, 1 deceptive. All narratives involve the full roster (15 pairwise interactions per narrative step).

### 1.3 Governance Configurations

| # | Config | Key Parameters |
|---|--------|----------------|
| 1 | **Baseline** | No governance (control) |
| 2 | **Tax only** | `transaction_tax_rate=0.05` |
| 3 | **Reputation** | `reputation_decay_rate=0.9` |
| 4 | **Circuit breaker** | `freeze_threshold_toxicity=0.5`, `freeze_duration=2` |
| 5 | **Audits** | `audit_probability=0.2`, `penalty_multiplier=2.0` |
| 6 | **Collusion detection** | `collusion_detection_enabled`, `realtime_penalty` |
| 7 | **Light defense** | Tax (0.03) + reputation (0.95) + audits (0.1, 1.5x) |
| 8 | **Full defense** | All levers enabled (strict settings) |

Each config: 5 seeds x 10 epochs x 5 steps = 250 steps per config, 750 interactions per run.

## 2. Results

### 2.1 Toxicity Is Invariant to Governance

Mean toxicity: **0.365** across all 8 configs (std < 0.001 across seeds).

This is by construction: toxicity is computed as E[1-p | accepted], and p is determined by the narrative scores flowing through the `ConcordiaAdapter` -> `ProxyComputer` pipeline. Governance levers operate *after* p is computed -- they add costs (`c_a`, `c_b`), adjust reputation, and freeze agents, but they do not alter the interaction's quality label.

### 2.2 Welfare Gradient

| Config | Mean Welfare | Delta vs Baseline |
|--------|-------------|-------------------|
| Baseline | 67.83 | -- |
| Reputation | 67.83 | 0.0% |
| Circuit breaker | 67.83 | 0.0% |
| Collusion detection | 67.83 | 0.0% |
| Audits | 66.50 | -2.0% |
| Light defense | 65.15 | -3.9% |
| Tax only | 64.33 | -5.2% |
| Full defense | 59.36 | -12.5% |

Levers partition cleanly into two groups:
- **Cost-neutral**: Reputation decay, circuit breaker, and collusion detection impose no direct interaction costs at these parameter settings.
- **Cost-imposing**: Transaction tax, audits, and their combinations reduce welfare proportionally to their rate parameters.

Full defense stacks all cost-imposing levers and pays the sum of their individual costs (~12.5% welfare reduction).

### 2.3 Circuit Breaker Dynamics

The frozen-agents heatmap reveals the most interesting governance behavior:

- **Circuit breaker** config: agents begin freezing at epoch 1, saturating at 3-5 frozen agents by epoch 4. The `freeze_threshold_toxicity=0.5` catches agents involved in adversarial/collusive narratives (which produce p < 0.5, i.e. toxicity > 0.5).
- **Full defense** config: similar pattern with slightly faster onset due to the stricter threshold (0.45).
- **All other configs**: zero frozen agents across all epochs.

The circuit breaker is the only lever that produces a *qualitatively* different system state -- it removes agents from the interaction pool entirely. This has no effect on measured toxicity (the remaining interactions still have the same p distribution) but demonstrates the lever's ability to isolate high-toxicity agents.

### 2.4 Quality Gap

Quality gap is 0.0 across all configs. Since all interactions have `accepted=True` in the Concordia bridge (there is no rejection mechanism in narrative processing), the quality gap metric (E[p|accepted] - E[p|rejected]) is undefined and defaults to zero. This is a known limitation of the current bridge architecture.

## 3. Discussion

### 3.1 The Post-Hoc Governance Limitation

These results formalize an intuition: **governance mechanisms that operate downstream of the scoring pipeline cannot improve the quality signal -- they can only impose costs or remove participants.** In this synthetic setup:

- Toxicity is fixed by the narrative corpus
- Welfare decreases monotonically with governance intensity
- The only lever that changes system *structure* (circuit breaker) does so by exclusion, not improvement

This contrasts with the full SWARM orchestrator, where governance effects feed back into agent behavior (reputation decay -> lower engagement -> different observables -> different p). The Concordia bridge's one-way flow (narrative -> scores -> interactions -> governance) breaks this feedback loop.

### 3.2 Implications for Concordia Integration

To observe governance *benefits* through the Concordia bridge, we need one of:

1. **Rejection mechanism**: Allow governance to reject interactions (setting `accepted=False`), enabling quality gap measurement and adverse selection detection.
2. **Behavioral feedback**: Feed governance state (frozen agents, reputation scores) back into narrative generation, simulating agents adapting to governance pressure.
3. **Live LLM mode**: Use actual Concordia with LLM agents whose prompts incorporate governance state, enabling genuine behavioral adaptation.

The synthetic sweep provides the control condition for any of these extensions.

### 3.3 What the Sweep Does Validate

Despite the flat toxicity, the sweep successfully validates:

- All 8 governance configs construct and run without error
- The `CorpusJudge` -> `ConcordiaAdapter` -> `GovernanceEngine` pipeline is correctly wired
- Cost-imposing levers (tax, audits) produce proportional welfare reductions
- The circuit breaker correctly identifies and freezes high-toxicity agents
- Results are reproducible across seeds (identical toxicity, consistent welfare)

## 4. Artifacts

Run directory: `runs/20260211-012350_concordia_sweep/`

| Artifact | Path |
|----------|------|
| Summary CSV | `csv/summary.csv` |
| Per-epoch CSV | `csv/epochs.csv` |
| Full history | `history.json` |
| Toxicity bar chart | `plots/toxicity_by_config.png` |
| Welfare bar chart | `plots/welfare_by_config.png` |
| Pareto scatter | `plots/pareto_toxicity_welfare.png` |
| Toxicity timeline | `plots/timeline_toxicity.png` |
| Frozen agents heatmap | `plots/heatmap_frozen.png` |

## 5. Reproducibility

```bash
python examples/concordia_governance_sweep.py --seeds 5 --epochs 10 --steps 5
```

No LLM calls. Runtime: ~5 seconds on a standard machine.
