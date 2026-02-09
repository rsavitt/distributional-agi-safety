#!/usr/bin/env python
"""
Reproduce the finding from agentxiv paper 2602.00035:

  "Populations with only 20% honest agents achieve 55% higher welfare
   (53.67) than 100% honest populations (34.71), despite having
   significantly higher toxicity (0.344 vs 0.254)."

Methodology:
  - Fix total population at 10 agents
  - Vary honest agent proportion from 0% to 100% in 10% steps
  - Non-honest slots filled with mix of deceptive + opportunistic agents
  - Use baseline payoff parameters (s_plus=2, s_minus=1, h=1)
  - Run each configuration for 30 epochs, 10 steps/epoch, 3 seeds
  - Compare welfare and toxicity across compositions

Usage:
    python examples/reproduce_2602_00035.py
    python examples/reproduce_2602_00035.py --total-agents 10 --epochs 30 --seeds 3
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("MPLCONFIGDIR", "/tmp/.mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/.cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from swarm.agents.base import BaseAgent
from swarm.agents.deceptive import DeceptiveAgent
from swarm.agents.honest import HonestAgent
from swarm.agents.opportunistic import OpportunisticAgent
from swarm.core.orchestrator import Orchestrator, OrchestratorConfig
from swarm.core.payoff import PayoffConfig
from swarm.governance.config import GovernanceConfig


# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------
@dataclass
class CompositionConfig:
    """A single population composition to test."""

    label: str
    n_honest: int
    n_deceptive: int
    n_opportunistic: int

    @property
    def total(self) -> int:
        return self.n_honest + self.n_deceptive + self.n_opportunistic

    @property
    def honest_pct(self) -> float:
        return self.n_honest / self.total if self.total else 0.0


@dataclass
class RunResult:
    """Result from one run (one composition + one seed)."""

    composition: str
    honest_pct: float
    seed: int
    n_epochs: int
    # Aggregates across all epochs
    mean_welfare: float = 0.0
    total_welfare: float = 0.0
    mean_toxicity: float = 0.0
    mean_quality_gap: float = 0.0
    mean_avg_payoff: float = 0.0
    final_welfare: float = 0.0
    final_toxicity: float = 0.0


def build_compositions(total_agents: int) -> List[CompositionConfig]:
    """Build compositions varying honest proportion from 0% to 100%."""
    compositions = []
    for honest_pct in range(0, 101, 10):
        n_honest = round(total_agents * honest_pct / 100)
        remaining = total_agents - n_honest
        # Split remaining 60/40 between deceptive and opportunistic
        n_deceptive = round(remaining * 0.6)
        n_opportunistic = remaining - n_deceptive
        label = f"{honest_pct}% honest"
        compositions.append(
            CompositionConfig(
                label=label,
                n_honest=max(n_honest, 0),
                n_deceptive=max(n_deceptive, 0),
                n_opportunistic=max(n_opportunistic, 0),
            )
        )
    return compositions


def create_agents_from_config(comp: CompositionConfig) -> List[BaseAgent]:
    """Create agent instances from a composition config."""
    agents: List[BaseAgent] = []
    for i in range(comp.n_honest):
        agents.append(HonestAgent(agent_id=f"honest_{i + 1}"))
    for i in range(comp.n_deceptive):
        agents.append(DeceptiveAgent(agent_id=f"deceptive_{i + 1}"))
    for i in range(comp.n_opportunistic):
        agents.append(OpportunisticAgent(agent_id=f"opportunistic_{i + 1}"))
    return agents


def run_single(
    comp: CompositionConfig,
    seed: int,
    n_epochs: int,
    steps_per_epoch: int,
) -> RunResult:
    """Run one simulation for a given composition and seed."""
    payoff_config = PayoffConfig(
        s_plus=2.0,
        s_minus=1.0,
        h=1.0,
        theta=0.5,
        rho_a=0.1,
        rho_b=0.1,
        w_rep=0.1,
    )
    governance_config = GovernanceConfig(
        circuit_breaker_enabled=True,
        reputation_decay_rate=0.05,
    )
    orch_config = OrchestratorConfig(
        n_epochs=n_epochs,
        steps_per_epoch=steps_per_epoch,
        seed=seed,
        payoff_config=payoff_config,
        governance_config=governance_config,
    )

    orchestrator = Orchestrator(config=orch_config)
    agents = create_agents_from_config(comp)
    for agent in agents:
        orchestrator.register_agent(agent)

    epoch_metrics = orchestrator.run()

    # Aggregate
    welfares = [em.total_welfare for em in epoch_metrics]
    toxicities = [em.toxicity_rate for em in epoch_metrics]
    qgaps = [em.quality_gap for em in epoch_metrics]
    payoffs = [em.avg_payoff for em in epoch_metrics]

    return RunResult(
        composition=comp.label,
        honest_pct=comp.honest_pct,
        seed=seed,
        n_epochs=len(epoch_metrics),
        mean_welfare=float(np.mean(welfares)) if welfares else 0.0,
        total_welfare=float(np.sum(welfares)) if welfares else 0.0,
        mean_toxicity=float(np.mean(toxicities)) if toxicities else 0.0,
        mean_quality_gap=float(np.mean(qgaps)) if qgaps else 0.0,
        mean_avg_payoff=float(np.mean(payoffs)) if payoffs else 0.0,
        final_welfare=float(welfares[-1]) if welfares else 0.0,
        final_toxicity=float(toxicities[-1]) if toxicities else 0.0,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
@dataclass
class AggResult:
    """Aggregated result across seeds for one composition."""

    label: str
    honest_pct: float
    n_seeds: int
    welfare_mean: float
    welfare_std: float
    welfare_total_mean: float
    toxicity_mean: float
    toxicity_std: float
    quality_gap_mean: float
    avg_payoff_mean: float


def aggregate_results(results: List[RunResult]) -> List[AggResult]:
    """Group by composition and compute mean/std across seeds."""
    from collections import defaultdict

    groups: Dict[str, List[RunResult]] = defaultdict(list)
    for r in results:
        groups[r.composition].append(r)

    aggs = []
    for label, runs in sorted(groups.items(), key=lambda x: x[1][0].honest_pct):
        welfares = [r.mean_welfare for r in runs]
        welfare_totals = [r.total_welfare for r in runs]
        toxicities = [r.mean_toxicity for r in runs]
        qgaps = [r.mean_quality_gap for r in runs]
        payoffs = [r.mean_avg_payoff for r in runs]
        aggs.append(
            AggResult(
                label=label,
                honest_pct=runs[0].honest_pct,
                n_seeds=len(runs),
                welfare_mean=float(np.mean(welfares)),
                welfare_std=float(np.std(welfares)),
                welfare_total_mean=float(np.mean(welfare_totals)),
                toxicity_mean=float(np.mean(toxicities)),
                toxicity_std=float(np.std(toxicities)),
                quality_gap_mean=float(np.mean(qgaps)),
                avg_payoff_mean=float(np.mean(payoffs)),
            )
        )
    return aggs


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
DPI = 160
COLORS = {"welfare": "#2196F3", "toxicity": "#F44336", "quality_gap": "#4CAF50"}


def _style_ax(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=9)


def plot_welfare_toxicity_dual_axis(aggs: List[AggResult], out_dir: Path) -> Path:
    """Dual-axis plot: welfare and toxicity vs honest agent %."""
    fig, ax1 = plt.subplots(figsize=(10, 6))

    pcts = [a.honest_pct * 100 for a in aggs]
    welfares = [a.welfare_total_mean for a in aggs]
    welfare_stds = [a.welfare_std * aggs[0].n_seeds for a in aggs]  # scale to total
    toxicities = [a.toxicity_mean for a in aggs]
    toxicity_stds = [a.toxicity_std for a in aggs]

    # Welfare (left axis)
    ax1.errorbar(
        pcts, welfares, yerr=welfare_stds,
        color=COLORS["welfare"], linewidth=2.5, marker="o", markersize=8,
        capsize=5, capthick=1.5, label="Total Welfare", zorder=5,
    )
    ax1.set_ylabel("Total Welfare (sum over epochs)", fontsize=11, color=COLORS["welfare"])
    ax1.tick_params(axis="y", labelcolor=COLORS["welfare"])

    # Toxicity (right axis)
    ax2 = ax1.twinx()
    ax2.errorbar(
        pcts, toxicities, yerr=toxicity_stds,
        color=COLORS["toxicity"], linewidth=2.5, marker="s", markersize=8,
        capsize=5, capthick=1.5, label="Toxicity Rate", zorder=4,
    )
    ax2.set_ylabel("Toxicity Rate (mean over epochs)", fontsize=11, color=COLORS["toxicity"])
    ax2.tick_params(axis="y", labelcolor=COLORS["toxicity"])
    ax2.set_ylim(-0.05, 1.05)

    ax1.set_xlabel("Honest Agent Proportion (%)", fontsize=11)
    ax1.set_title(
        "Reproduction of agentxiv 2602.00035:\nWelfare vs. Toxicity by Honest Agent Proportion",
        fontsize=13, fontweight="bold", pad=10,
    )
    ax1.grid(True, alpha=0.3, linestyle="--")
    ax1.spines["top"].set_visible(False)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, loc="upper center")

    out = out_dir / "welfare_toxicity_vs_honest_pct.png"
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_welfare_scatter(aggs: List[AggResult], out_dir: Path) -> Path:
    """Scatter: welfare vs toxicity, each point is a composition."""
    fig, ax = plt.subplots(figsize=(8, 6))

    for a in aggs:
        pct = a.honest_pct * 100
        # Color gradient from red (0% honest) to green (100% honest)
        r = max(0, 1.0 - a.honest_pct)
        g = a.honest_pct
        b = 0.2
        color = (r, g, b)
        ax.scatter(
            a.welfare_total_mean, a.toxicity_mean,
            c=[color], s=120, edgecolors="white", linewidth=1, zorder=5,
        )
        ax.annotate(
            f"{pct:.0f}%",
            (a.welfare_total_mean, a.toxicity_mean),
            textcoords="offset points", xytext=(8, 5), fontsize=8,
        )

    _style_ax(
        ax,
        "Welfare-Toxicity Trade-off by Honest Agent %\n(Reproduction of 2602.00035)",
        "Total Welfare",
        "Toxicity Rate",
    )
    ax.set_ylim(-0.05, 1.05)

    out = out_dir / "welfare_toxicity_scatter.png"
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_bar_comparison(aggs: List[AggResult], out_dir: Path) -> Path:
    """Side-by-side bars: welfare and toxicity for key compositions."""
    # Pick key compositions: 0%, 20%, 50%, 80%, 100%
    key_pcts = {0.0, 0.2, 0.5, 0.8, 1.0}
    selected = [a for a in aggs if round(a.honest_pct, 1) in key_pcts]

    labels = [a.label for a in selected]
    welfares = [a.welfare_total_mean for a in selected]
    toxicities = [a.toxicity_mean for a in selected]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(10, 6))

    bars1 = ax1.bar(x - width / 2, welfares, width, label="Total Welfare",
                    color=COLORS["welfare"], alpha=0.85)
    ax1.set_ylabel("Total Welfare", fontsize=11, color=COLORS["welfare"])

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, toxicities, width, label="Toxicity Rate",
                    color=COLORS["toxicity"], alpha=0.85)
    ax2.set_ylabel("Toxicity Rate", fontsize=11, color=COLORS["toxicity"])
    ax2.set_ylim(0, 1.0)

    # Value labels on bars
    for bar, val in zip(bars1, welfares):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{val:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(bars2, toxicities):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                 f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.set_title(
        "Key Compositions: Welfare & Toxicity\n(Reproduction of 2602.00035)",
        fontsize=13, fontweight="bold",
    )
    ax1.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)

    out = out_dir / "key_compositions_bars.png"
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_pareto_frontier(aggs: List[AggResult], out_dir: Path) -> Path:
    """Pareto frontier: compositions that are non-dominated on welfare vs toxicity."""
    fig, ax = plt.subplots(figsize=(8, 6))

    welfares = [a.welfare_total_mean for a in aggs]
    toxicities = [a.toxicity_mean for a in aggs]
    pcts = [a.honest_pct * 100 for a in aggs]

    # Find Pareto-optimal points (maximize welfare, minimize toxicity)
    pareto_mask = []
    for i, (w, t) in enumerate(zip(welfares, toxicities)):
        dominated = False
        for j, (w2, t2) in enumerate(zip(welfares, toxicities)):
            if i != j and w2 >= w and t2 <= t and (w2 > w or t2 < t):
                dominated = True
                break
        pareto_mask.append(not dominated)

    # Plot all points
    for i, a in enumerate(aggs):
        color = "#4CAF50" if pareto_mask[i] else "#9E9E9E"
        marker = "D" if pareto_mask[i] else "o"
        size = 120 if pareto_mask[i] else 60
        ax.scatter(
            a.welfare_total_mean, a.toxicity_mean,
            c=color, s=size, marker=marker, edgecolors="white", linewidth=1, zorder=5,
        )
        ax.annotate(
            f"{pcts[i]:.0f}%",
            (a.welfare_total_mean, a.toxicity_mean),
            textcoords="offset points", xytext=(8, 5), fontsize=8,
        )

    # Connect Pareto front
    pareto_points = [(welfares[i], toxicities[i]) for i in range(len(aggs)) if pareto_mask[i]]
    pareto_points.sort(key=lambda p: p[0])
    if pareto_points:
        pw, pt = zip(*pareto_points)
        ax.plot(pw, pt, color="#4CAF50", linewidth=1.5, linestyle="--", alpha=0.7, label="Pareto frontier")

    _style_ax(
        ax,
        "Pareto Frontier: Welfare vs. Toxicity\n(green diamonds = non-dominated compositions)",
        "Total Welfare",
        "Toxicity Rate",
    )
    ax.legend(fontsize=9)

    out = out_dir / "pareto_frontier.png"
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reproduce agentxiv 2602.00035: welfare vs honest agent proportion"
    )
    parser.add_argument("--total-agents", type=int, default=10, help="Total agents per run")
    parser.add_argument("--epochs", type=int, default=30, help="Epochs per run")
    parser.add_argument("--steps", type=int, default=10, help="Steps per epoch")
    parser.add_argument("--seeds", type=int, default=3, help="Number of random seeds")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir or Path(f"runs/{timestamp}_reproduce_2602_00035")
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    compositions = build_compositions(args.total_agents)
    seeds = list(range(42, 42 + args.seeds))

    print("=" * 70)
    print("Reproducing agentxiv 2602.00035")
    print(f"  Agents: {args.total_agents}, Epochs: {args.epochs}, Steps/epoch: {args.steps}")
    print(f"  Seeds: {seeds}")
    print(f"  Compositions: {len(compositions)}")
    print("=" * 70)

    # Run all combinations
    all_results: List[RunResult] = []
    total_runs = len(compositions) * len(seeds)
    run_idx = 0

    for comp in compositions:
        for seed in seeds:
            run_idx += 1
            print(f"  [{run_idx}/{total_runs}] {comp.label} "
                  f"(H={comp.n_honest}, D={comp.n_deceptive}, O={comp.n_opportunistic}) "
                  f"seed={seed}...", end=" ", flush=True)
            result = run_single(comp, seed, args.epochs, args.steps)
            all_results.append(result)
            print(f"welfare={result.total_welfare:.1f}, toxicity={result.mean_toxicity:.3f}")

    # Aggregate
    aggs = aggregate_results(all_results)

    # Print results table
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"{'Composition':<18} {'Honest%':>8} {'TotalWelfare':>13} {'WelfareStd':>11} "
          f"{'Toxicity':>9} {'ToxStd':>8} {'QualGap':>8} {'AvgPayoff':>10}")
    print("-" * 95)
    for a in aggs:
        print(f"{a.label:<18} {a.honest_pct*100:>7.0f}% {a.welfare_total_mean:>13.2f} "
              f"{a.welfare_std:>11.2f} {a.toxicity_mean:>9.3f} {a.toxicity_std:>8.3f} "
              f"{a.quality_gap_mean:>8.3f} {a.avg_payoff_mean:>10.3f}")

    # Key comparison: 20% vs 100% honest
    agg_20 = next((a for a in aggs if round(a.honest_pct, 1) == 0.2), None)
    agg_100 = next((a for a in aggs if round(a.honest_pct, 1) == 1.0), None)

    print("\n" + "=" * 70)
    print("KEY COMPARISON: 20% honest vs 100% honest")
    print("=" * 70)
    if agg_20 and agg_100:
        w20, w100 = agg_20.welfare_total_mean, agg_100.welfare_total_mean
        t20, t100 = agg_20.toxicity_mean, agg_100.toxicity_mean
        welfare_pct = ((w20 - w100) / w100 * 100) if w100 != 0 else float("inf")
        print(f"  20% honest: welfare={w20:.2f}, toxicity={t20:.3f}")
        print(f"  100% honest: welfare={w100:.2f}, toxicity={t100:.3f}")
        print(f"  Welfare difference: {welfare_pct:+.1f}%")
        print(f"  Toxicity difference: {t20 - t100:+.3f}")
        print()
        if welfare_pct > 0:
            print(f"  FINDING REPRODUCED: 20% honest has {welfare_pct:.0f}% higher welfare")
            print(f"  Paper claims: 55% higher welfare (53.67 vs 34.71)")
            print(f"  Our result:   {welfare_pct:.0f}% difference ({w20:.2f} vs {w100:.2f})")
        else:
            print(f"  FINDING NOT REPRODUCED: 20% honest has {welfare_pct:.0f}% {'lower' if welfare_pct < 0 else 'equal'} welfare")
    else:
        print("  Could not find both 20% and 100% compositions in results")

    # Find peak welfare composition
    peak = max(aggs, key=lambda a: a.welfare_total_mean)
    print(f"\n  Peak welfare composition: {peak.label} "
          f"(welfare={peak.welfare_total_mean:.2f}, toxicity={peak.toxicity_mean:.3f})")

    # Generate plots
    print("\nGenerating plots...")
    plots_written = []
    plots_written.append(plot_welfare_toxicity_dual_axis(aggs, plots_dir))
    plots_written.append(plot_welfare_scatter(aggs, plots_dir))
    plots_written.append(plot_bar_comparison(aggs, plots_dir))
    plots_written.append(plot_pareto_frontier(aggs, plots_dir))

    for p in plots_written:
        print(f"  -> {p}")

    # Export CSV
    csv_path = out_dir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "composition", "honest_pct", "seed", "n_epochs",
            "mean_welfare", "total_welfare", "mean_toxicity",
            "mean_quality_gap", "mean_avg_payoff",
            "final_welfare", "final_toxicity",
        ])
        writer.writeheader()
        for r in all_results:
            writer.writerow({
                "composition": r.composition,
                "honest_pct": f"{r.honest_pct:.2f}",
                "seed": r.seed,
                "n_epochs": r.n_epochs,
                "mean_welfare": f"{r.mean_welfare:.6f}",
                "total_welfare": f"{r.total_welfare:.6f}",
                "mean_toxicity": f"{r.mean_toxicity:.6f}",
                "mean_quality_gap": f"{r.mean_quality_gap:.6f}",
                "mean_avg_payoff": f"{r.mean_avg_payoff:.6f}",
                "final_welfare": f"{r.final_welfare:.6f}",
                "final_toxicity": f"{r.final_toxicity:.6f}",
            })
    print(f"  -> {csv_path}")

    agg_csv_path = out_dir / "aggregated_results.csv"
    with open(agg_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "composition", "honest_pct", "n_seeds",
            "welfare_total_mean", "welfare_std",
            "toxicity_mean", "toxicity_std",
            "quality_gap_mean", "avg_payoff_mean",
        ])
        writer.writeheader()
        for a in aggs:
            writer.writerow({
                "composition": a.label,
                "honest_pct": f"{a.honest_pct:.2f}",
                "n_seeds": a.n_seeds,
                "welfare_total_mean": f"{a.welfare_total_mean:.4f}",
                "welfare_std": f"{a.welfare_std:.4f}",
                "toxicity_mean": f"{a.toxicity_mean:.4f}",
                "toxicity_std": f"{a.toxicity_std:.4f}",
                "quality_gap_mean": f"{a.quality_gap_mean:.4f}",
                "avg_payoff_mean": f"{a.avg_payoff_mean:.4f}",
            })
    print(f"  -> {agg_csv_path}")

    print(f"\nAll outputs in: {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
