#!/usr/bin/env python3
"""
Concordia Governance Sweep — 8 governance configs on narrative-driven interactions.

Feeds synthetic narratives through ConcordiaAdapter + GovernanceEngine to
isolate governance effects from LLM variance.  No LLM calls required.

Configs:
  1. Baseline            — no governance (control)
  2. Tax only            — transaction_tax_rate=0.05
  3. Reputation          — reputation_decay_rate=0.9
  4. Circuit breaker     — freeze toxic agents
  5. Audits              — random audit with penalties
  6. Collusion detection — detect and penalize coordinated pairs
  7. Light defense       — tax + reputation + audits (moderate)
  8. Full defense        — all levers enabled (strict)

Usage:
    python examples/concordia_governance_sweep.py
    python examples/concordia_governance_sweep.py --dry-run
    python examples/concordia_governance_sweep.py --seeds 5 --epochs 10
    python examples/concordia_governance_sweep.py --output runs/my_sweep/
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm.bridges.concordia.adapter import ConcordiaAdapter
from swarm.bridges.concordia.config import ConcordiaConfig
from swarm.bridges.concordia.events import JudgeScores
from swarm.bridges.concordia.judge import LLMJudge
from swarm.bridges.concordia.narratives import NarrativeSample, generate_corpus
from swarm.env.state import EnvState
from swarm.governance.config import GovernanceConfig
from swarm.governance.engine import GovernanceEngine
from swarm.metrics.soft_metrics import SoftMetrics
from swarm.models.agent import AgentType
from swarm.models.interaction import SoftInteraction

# ── Agent roster ─────────────────────────────────────────────────────────

AGENT_ROSTER = [
    ("honest_1", AgentType.HONEST),
    ("honest_2", AgentType.HONEST),
    ("honest_3", AgentType.HONEST),
    ("honest_4", AgentType.HONEST),
    ("adversarial_1", AgentType.ADVERSARIAL),
    ("deceptive_1", AgentType.DECEPTIVE),
]

AGENT_IDS = [a[0] for a in AGENT_ROSTER]

# ── 8 named governance configurations ────────────────────────────────────


def governance_configs() -> List[Dict[str, Any]]:
    """Return the 8 named governance configurations."""
    return [
        # 1. Baseline — no governance
        {
            "label": "baseline",
            "governance": GovernanceConfig(),
        },
        # 2. Tax only
        {
            "label": "tax_only",
            "governance": GovernanceConfig(
                transaction_tax_rate=0.05,
                transaction_tax_split=0.5,
            ),
        },
        # 3. Reputation
        {
            "label": "reputation",
            "governance": GovernanceConfig(
                reputation_decay_rate=0.9,
            ),
        },
        # 4. Circuit breaker
        {
            "label": "circuit_breaker",
            "governance": GovernanceConfig(
                circuit_breaker_enabled=True,
                freeze_threshold_toxicity=0.5,
                freeze_threshold_violations=2,
                freeze_duration_epochs=2,
            ),
        },
        # 5. Audits
        {
            "label": "audits",
            "governance": GovernanceConfig(
                audit_enabled=True,
                audit_probability=0.2,
                audit_penalty_multiplier=2.0,
                audit_threshold_p=0.5,
            ),
        },
        # 6. Collusion detection
        {
            "label": "collusion_detection",
            "governance": GovernanceConfig(
                collusion_detection_enabled=True,
                collusion_frequency_threshold=2.0,
                collusion_correlation_threshold=0.7,
                collusion_score_threshold=0.5,
                collusion_penalty_multiplier=1.0,
                collusion_realtime_penalty=True,
                collusion_realtime_rate=0.1,
            ),
        },
        # 7. Light defense — tax + reputation + audits (moderate)
        {
            "label": "light_defense",
            "governance": GovernanceConfig(
                transaction_tax_rate=0.03,
                reputation_decay_rate=0.95,
                audit_enabled=True,
                audit_probability=0.1,
                audit_penalty_multiplier=1.5,
                audit_threshold_p=0.5,
            ),
        },
        # 8. Full defense — all levers strict
        {
            "label": "full_defense",
            "governance": GovernanceConfig(
                transaction_tax_rate=0.08,
                transaction_tax_split=0.6,
                reputation_decay_rate=0.85,
                circuit_breaker_enabled=True,
                freeze_threshold_toxicity=0.45,
                freeze_threshold_violations=2,
                freeze_duration_epochs=2,
                audit_enabled=True,
                audit_probability=0.25,
                audit_penalty_multiplier=2.5,
                audit_threshold_p=0.5,
                collusion_detection_enabled=True,
                collusion_frequency_threshold=2.0,
                collusion_correlation_threshold=0.7,
                collusion_score_threshold=0.5,
                collusion_penalty_multiplier=1.5,
                collusion_realtime_penalty=True,
                collusion_realtime_rate=0.15,
            ),
        },
    ]


# ── Score-injecting judge ────────────────────────────────────────────────


class CorpusJudge(LLMJudge):
    """LLMJudge subclass that returns pre-computed scores from a corpus.

    Instead of calling an LLM, it pops scores from a queue in order.
    Falls back to stub defaults if the queue is exhausted.
    """

    def __init__(self) -> None:
        super().__init__(config=None, llm_client=None)
        self._queue: List[JudgeScores] = []

    def enqueue(self, scores: JudgeScores) -> None:
        """Add scores to the back of the queue."""
        self._queue.append(scores)

    def evaluate(self, narrative: str) -> JudgeScores:
        """Return the next queued score, or stub defaults."""
        if self._queue:
            return self._queue.pop(0)
        return JudgeScores()


# ── Per-epoch metrics ────────────────────────────────────────────────────


@dataclass
class EpochMetrics:
    """Metrics collected for a single epoch."""

    epoch: int = 0
    toxicity: float = 0.0
    welfare: float = 0.0
    quality_gap: float = 0.0
    frozen_count: int = 0
    interactions_count: int = 0


@dataclass
class RunResult:
    """Result from a single sweep run (one config + one seed)."""

    label: str = ""
    seed: int = 0
    epoch_metrics: List[EpochMetrics] = field(default_factory=list)

    # Aggregates
    mean_toxicity: float = 0.0
    mean_welfare: float = 0.0
    mean_quality_gap: float = 0.0
    max_frozen: int = 0
    total_interactions: int = 0

    def compute_aggregates(self) -> None:
        """Compute aggregate metrics from per-epoch data."""
        if not self.epoch_metrics:
            return
        n = len(self.epoch_metrics)
        self.mean_toxicity = sum(m.toxicity for m in self.epoch_metrics) / n
        self.mean_welfare = sum(m.welfare for m in self.epoch_metrics) / n
        self.mean_quality_gap = sum(m.quality_gap for m in self.epoch_metrics) / n
        self.max_frozen = max(m.frozen_count for m in self.epoch_metrics)
        self.total_interactions = sum(
            m.interactions_count for m in self.epoch_metrics
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "seed": self.seed,
            "mean_toxicity": self.mean_toxicity,
            "mean_welfare": self.mean_welfare,
            "mean_quality_gap": self.mean_quality_gap,
            "max_frozen": self.max_frozen,
            "total_interactions": self.total_interactions,
        }


# ── Single run ───────────────────────────────────────────────────────────


def run_single(
    label: str,
    gov_config: GovernanceConfig,
    corpus: List[List[NarrativeSample]],
    seed: int,
) -> RunResult:
    """Run a single config through the Concordia adapter + governance engine.

    Args:
        label: Name of this governance configuration.
        gov_config: Governance configuration to use.
        corpus: Pre-generated narratives organized by epoch.
        seed: Random seed (used for governance engine).

    Returns:
        RunResult with per-epoch and aggregate metrics.
    """
    # Build components
    judge = CorpusJudge()
    adapter = ConcordiaAdapter(
        config=ConcordiaConfig(),
        judge=judge,
    )
    engine = GovernanceEngine(config=gov_config, seed=seed)

    # Wire collusion detection agent IDs
    if gov_config.collusion_detection_enabled:
        engine.set_collusion_agent_ids(AGENT_IDS)

    # Build environment state
    state = EnvState(steps_per_epoch=len(corpus[0]) if corpus else 5)
    for agent_id, agent_type in AGENT_ROSTER:
        state.add_agent(agent_id, agent_type=agent_type)

    metrics = SoftMetrics()
    result = RunResult(label=label, seed=seed)

    for epoch_idx, epoch_samples in enumerate(corpus):
        state.current_epoch = epoch_idx

        # Epoch-start governance
        engine.apply_epoch_start(state, epoch_idx)

        epoch_interactions: List[SoftInteraction] = []

        for step_idx, (narrative_text, expected_scores) in enumerate(epoch_samples):
            state.current_step = step_idx

            # Enqueue the expected scores for the corpus judge
            judge.enqueue(expected_scores)

            # Process narrative through adapter
            interactions = adapter.process_narrative(
                agent_ids=AGENT_IDS,
                narrative_text=narrative_text,
                step=step_idx,
            )

            # Apply governance to each interaction
            for interaction in interactions:
                # Check if agents can act
                if not engine.can_agent_act(interaction.initiator, state):
                    continue

                effect = engine.apply_interaction(interaction, state)

                # Apply governance costs to interaction
                interaction.c_a += effect.cost_a
                interaction.c_b += effect.cost_b

                # Apply reputation deltas
                for agent_id, delta in effect.reputation_deltas.items():
                    if agent_id in state.agents:
                        state.agents[agent_id].reputation += delta

                # Apply freezes
                for agent_id in effect.agents_to_freeze:
                    state.frozen_agents.add(agent_id)
                for agent_id in effect.agents_to_unfreeze:
                    state.frozen_agents.discard(agent_id)

                epoch_interactions.append(interaction)

            # Step-level governance
            engine.apply_step(state, step_idx)

        # Compute epoch metrics
        em = EpochMetrics(
            epoch=epoch_idx,
            frozen_count=len(state.frozen_agents),
            interactions_count=len(epoch_interactions),
        )
        if epoch_interactions:
            em.toxicity = metrics.toxicity_rate(epoch_interactions)
            em.quality_gap = metrics.quality_gap(epoch_interactions)
            welfare = metrics.welfare_metrics(epoch_interactions)
            em.welfare = welfare.get("total_welfare", 0.0)

        result.epoch_metrics.append(em)

    result.compute_aggregates()
    return result


# ── Full sweep ───────────────────────────────────────────────────────────


def run_sweep(
    *,
    n_seeds: int = 5,
    n_epochs: int = 10,
    steps_per_epoch: int = 5,
    adversarial_frac: float = 0.3,
    progress: bool = True,
) -> List[RunResult]:
    """Run all 8 governance configs across multiple seeds.

    Args:
        n_seeds: Number of seeds per config.
        n_epochs: Number of epochs per run.
        steps_per_epoch: Steps per epoch.
        adversarial_frac: Fraction of adversarial/collusive narratives.
        progress: Print progress to stdout.

    Returns:
        List of RunResult for all runs.
    """
    configs = governance_configs()
    total_runs = len(configs) * n_seeds
    results: List[RunResult] = []
    current = 0

    for config_entry in configs:
        label = config_entry["label"]
        gov_config = config_entry["governance"]

        for seed_offset in range(n_seeds):
            current += 1
            seed = 42 + seed_offset

            # Generate fresh corpus per seed for reproducibility
            corpus = generate_corpus(
                agents=AGENT_IDS,
                n_epochs=n_epochs,
                steps_per_epoch=steps_per_epoch,
                adversarial_frac=adversarial_frac,
                seed=seed,
            )

            if progress:
                print(
                    f"  [{current:>3}/{total_runs}] "
                    f"{label:<25} seed={seed}"
                )

            result = run_single(label, gov_config, corpus, seed)
            results.append(result)

    return results


# ── Export helpers ────────────────────────────────────────────────────────


def export_csv(results: List[RunResult], path: Path) -> None:
    """Export aggregate results to CSV."""
    if not results:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].to_dict().keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())


def export_epoch_csv(results: List[RunResult], path: Path) -> None:
    """Export per-epoch metrics to CSV (for timeline plots)."""
    if not results:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "label", "seed", "epoch", "toxicity", "welfare",
        "quality_gap", "frozen_count", "interactions_count",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            for em in r.epoch_metrics:
                writer.writerow({
                    "label": r.label,
                    "seed": r.seed,
                    "epoch": em.epoch,
                    "toxicity": em.toxicity,
                    "welfare": em.welfare,
                    "quality_gap": em.quality_gap,
                    "frozen_count": em.frozen_count,
                    "interactions_count": em.interactions_count,
                })


def export_history(results: List[RunResult], path: Path) -> None:
    """Export full run history as JSON for reproducibility."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for r in results:
        entry = r.to_dict()
        entry["epoch_metrics"] = [
            {
                "epoch": em.epoch,
                "toxicity": em.toxicity,
                "welfare": em.welfare,
                "quality_gap": em.quality_gap,
                "frozen_count": em.frozen_count,
                "interactions_count": em.interactions_count,
            }
            for em in r.epoch_metrics
        ]
        data.append(entry)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Plotting ─────────────────────────────────────────────────────────────


def generate_plots(results: List[RunResult], plot_dir: Path) -> None:
    """Generate comparison plots from sweep results.

    Requires matplotlib. Skips gracefully if not installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  matplotlib not available — skipping plots")
        return

    plot_dir.mkdir(parents=True, exist_ok=True)

    # Group by label
    from collections import defaultdict
    groups: Dict[str, List[RunResult]] = defaultdict(list)
    for r in results:
        groups[r.label].append(r)

    labels = list(groups.keys())
    mean_tox = [
        sum(r.mean_toxicity for r in groups[lab]) / len(groups[lab]) for lab in labels
    ]
    mean_wel = [
        sum(r.mean_welfare for r in groups[lab]) / len(groups[lab]) for lab in labels
    ]

    # ── Bar: toxicity by config ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))
    ax.bar(x, mean_tox, color="salmon")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Mean Toxicity")
    ax.set_title("Toxicity by Governance Config")
    fig.tight_layout()
    fig.savefig(plot_dir / "toxicity_by_config.png", dpi=150)
    plt.close(fig)

    # ── Bar: welfare by config ───────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x, mean_wel, color="steelblue")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Mean Welfare")
    ax.set_title("Welfare by Governance Config")
    fig.tight_layout()
    fig.savefig(plot_dir / "welfare_by_config.png", dpi=150)
    plt.close(fig)

    # ── Scatter: toxicity vs welfare (Pareto) ────────────────────────
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(mean_tox, mean_wel, s=100, zorder=3)
    for i, label in enumerate(labels):
        ax.annotate(label, (mean_tox[i], mean_wel[i]), fontsize=8,
                     textcoords="offset points", xytext=(5, 5))
    ax.set_xlabel("Mean Toxicity")
    ax.set_ylabel("Mean Welfare")
    ax.set_title("Toxicity vs Welfare (Pareto Frontier)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_dir / "pareto_toxicity_welfare.png", dpi=150)
    plt.close(fig)

    # ── Timeline: per-epoch toxicity for baseline vs full_defense ────
    fig, ax = plt.subplots(figsize=(10, 5))
    for tgt_label, color in [("baseline", "red"), ("full_defense", "green")]:
        runs = groups.get(tgt_label, [])
        if not runs:
            continue
        # Average across seeds
        max_epochs = max(len(r.epoch_metrics) for r in runs)
        avg_tox = []
        for e in range(max_epochs):
            vals = [
                r.epoch_metrics[e].toxicity
                for r in runs
                if e < len(r.epoch_metrics)
            ]
            avg_tox.append(sum(vals) / len(vals) if vals else 0)
        ax.plot(range(max_epochs), avg_tox, label=tgt_label, color=color)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Toxicity")
    ax.set_title("Per-Epoch Toxicity: Baseline vs Full Defense")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_dir / "timeline_toxicity.png", dpi=150)
    plt.close(fig)

    # ── Heatmap: frozen count by config × epoch ──────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    max_epochs = max(
        max((len(r.epoch_metrics) for r in runs), default=0)
        for runs in groups.values()
    )
    heatmap_data = []
    heatmap_labels = []
    for lbl in labels:
        runs = groups[lbl]
        row = []
        for e in range(max_epochs):
            vals = [
                r.epoch_metrics[e].frozen_count
                for r in runs
                if e < len(r.epoch_metrics)
            ]
            row.append(sum(vals) / len(vals) if vals else 0)
        heatmap_data.append(row)
        heatmap_labels.append(lbl)
    im = ax.imshow(heatmap_data, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(range(len(heatmap_labels)))
    ax.set_yticklabels(heatmap_labels)
    ax.set_xlabel("Epoch")
    ax.set_title("Frozen Agents by Config × Epoch")
    fig.colorbar(im, ax=ax, label="Avg Frozen Count")
    fig.tight_layout()
    fig.savefig(plot_dir / "heatmap_frozen.png", dpi=150)
    plt.close(fig)

    print(f"  Plots saved to {plot_dir}/")


# ── Summary table ────────────────────────────────────────────────────────


def print_summary(results: List[RunResult]) -> None:
    """Print a formatted summary table."""
    from collections import defaultdict
    groups: Dict[str, List[RunResult]] = defaultdict(list)
    for r in results:
        groups[r.label].append(r)

    print()
    print(
        f"{'Config':<25} "
        f"{'Toxicity':>10} "
        f"{'Welfare':>10} "
        f"{'QualGap':>10} "
        f"{'MaxFroz':>8} "
        f"{'Interact':>10}"
    )
    print("-" * 83)

    for label in dict.fromkeys(r.label for r in results):
        runs = groups[label]
        n = len(runs)
        print(
            f"{label:<25} "
            f"{sum(r.mean_toxicity for r in runs) / n:>10.4f} "
            f"{sum(r.mean_welfare for r in runs) / n:>10.2f} "
            f"{sum(r.mean_quality_gap for r in runs) / n:>10.4f} "
            f"{max(r.max_frozen for r in runs):>8d} "
            f"{sum(r.total_interactions for r in runs) // n:>10d}"
        )
    print()


# ── CLI ──────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Concordia Governance Sweep — 8-config narrative-driven comparison"
    )
    parser.add_argument(
        "--seeds", type=int, default=5,
        help="Number of seeds per config (default: 5)",
    )
    parser.add_argument(
        "--epochs", type=int, default=10,
        help="Epochs per run (default: 10)",
    )
    parser.add_argument(
        "--steps", type=int, default=5,
        help="Steps per epoch (default: 5)",
    )
    parser.add_argument(
        "--adversarial-frac", type=float, default=0.3,
        help="Fraction of adversarial/collusive narratives (default: 0.3)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output directory (default: runs/<timestamp>_concordia_sweep/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate configs without running",
    )
    args = parser.parse_args()

    n_configs = len(governance_configs())
    total_runs = n_configs * args.seeds
    total_steps = total_runs * args.epochs * args.steps

    print("=" * 70)
    print("  Concordia Governance Sweep")
    print("=" * 70)
    print()
    print(f"  Configs:          {n_configs}")
    print(f"  Seeds/config:     {args.seeds}")
    print(f"  Epochs/run:       {args.epochs}")
    print(f"  Steps/epoch:      {args.steps}")
    print(f"  Adversarial frac: {args.adversarial_frac}")
    print(f"  Total runs:       {total_runs}")
    print(f"  Total steps:      {total_steps}")
    print()

    if args.dry_run:
        print("DRY RUN — validating configs...")
        for cfg in governance_configs():
            label = cfg["label"]
            gov = cfg["governance"]
            active = GovernanceEngine(config=gov).get_active_lever_names()
            print(f"  {label:<25} active levers: {active}")
        print()
        print("All configs valid.")
        return 0

    # Determine output directory
    if args.output is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = Path("runs") / f"{ts}_concordia_sweep"
    else:
        out_dir = args.output

    print(f"  Output:           {out_dir}")
    print()

    # Run sweep
    print("Running sweep...")
    results = run_sweep(
        n_seeds=args.seeds,
        n_epochs=args.epochs,
        steps_per_epoch=args.steps,
        adversarial_frac=args.adversarial_frac,
    )

    # Print summary
    print()
    print("=" * 70)
    print("  Results Summary")
    print("=" * 70)
    print_summary(results)

    # Export
    csv_dir = out_dir / "csv"
    export_csv(results, csv_dir / "summary.csv")
    export_epoch_csv(results, csv_dir / "epochs.csv")
    export_history(results, out_dir / "history.json")
    print(f"CSV exported to {csv_dir}/")

    # Plots
    generate_plots(results, out_dir / "plots")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
