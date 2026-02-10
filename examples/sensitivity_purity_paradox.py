#!/usr/bin/env python
"""
Sensitivity analysis for the "purity paradox" (agentxiv 2602.00035).

Tests whether the finding that 20% honest > 100% honest in welfare
is robust across different parameter assumptions, or is an artifact
of specific payoff/governance settings.

Parameters varied:
  - Harm externality h: [0.5, 1.0, 2.0, 4.0]
  - Externality internalization rho: [0.0, 0.1, 0.3, 0.5, 1.0]
  - Reputation weight w_rep: [0.0, 0.1, 0.5, 1.0]
  - Non-honest composition split: [all-deceptive, 60/40, all-opportunistic]
  - Governance: [none, light, strict]

For each parameter setting, runs 20% honest vs 100% honest and reports
the welfare ratio.

Usage:
    python examples/sensitivity_purity_paradox.py
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


TOTAL_AGENTS = 10
N_EPOCHS = 20
STEPS_PER_EPOCH = 10
SEEDS = [42, 43, 44]

DPI = 160


@dataclass
class ParamSet:
    """One parameter configuration to test."""

    label: str
    s_plus: float = 2.0
    s_minus: float = 1.0
    h: float = 1.0
    theta: float = 0.5
    rho_a: float = 0.1
    rho_b: float = 0.1
    w_rep: float = 0.1
    # Non-honest composition: fraction that are deceptive (rest opportunistic)
    deceptive_frac: float = 0.6
    # Governance
    circuit_breaker: bool = True
    reputation_decay: float = 0.05


@dataclass
class ComparisonResult:
    """Result of comparing 20% vs 100% honest for one param set."""

    param_label: str
    param_varied: str
    param_value: str
    welfare_20pct: float
    welfare_100pct: float
    toxicity_20pct: float
    toxicity_100pct: float

    @property
    def welfare_ratio(self) -> float:
        return self.welfare_20pct / self.welfare_100pct if self.welfare_100pct else float("inf")

    @property
    def welfare_pct_diff(self) -> float:
        return ((self.welfare_20pct - self.welfare_100pct) / self.welfare_100pct * 100
                if self.welfare_100pct else float("inf"))

    @property
    def paradox_holds(self) -> bool:
        return self.welfare_20pct > self.welfare_100pct


def make_agents(n_honest: int, n_total: int, deceptive_frac: float) -> List[BaseAgent]:
    remaining = n_total - n_honest
    n_deceptive = round(remaining * deceptive_frac)
    n_opportunistic = remaining - n_deceptive
    agents: List[BaseAgent] = []
    for i in range(n_honest):
        agents.append(HonestAgent(agent_id=f"honest_{i+1}"))
    for i in range(n_deceptive):
        agents.append(DeceptiveAgent(agent_id=f"deceptive_{i+1}"))
    for i in range(n_opportunistic):
        agents.append(OpportunisticAgent(agent_id=f"opportunistic_{i+1}"))
    return agents


def run_composition(n_honest: int, ps: ParamSet, seed: int) -> Tuple[float, float]:
    """Run one sim, return (total_welfare, mean_toxicity)."""
    payoff_config = PayoffConfig(
        s_plus=ps.s_plus, s_minus=ps.s_minus, h=ps.h,
        theta=ps.theta, rho_a=ps.rho_a, rho_b=ps.rho_b, w_rep=ps.w_rep,
    )
    governance_config = GovernanceConfig(
        circuit_breaker_enabled=ps.circuit_breaker,
        reputation_decay_rate=ps.reputation_decay,
    )
    orch_config = OrchestratorConfig(
        n_epochs=N_EPOCHS, steps_per_epoch=STEPS_PER_EPOCH,
        seed=seed, payoff_config=payoff_config,
        governance_config=governance_config,
    )
    orchestrator = Orchestrator(config=orch_config)
    for agent in make_agents(n_honest, TOTAL_AGENTS, ps.deceptive_frac):
        orchestrator.register_agent(agent)
    metrics = orchestrator.run()
    total_welfare = sum(em.total_welfare for em in metrics)
    mean_toxicity = float(np.mean([em.toxicity_rate for em in metrics]))
    return total_welfare, mean_toxicity


def compare(ps: ParamSet, param_varied: str, param_value: str) -> ComparisonResult:
    """Compare 20% vs 100% honest across seeds."""
    w20s, t20s, w100s, t100s = [], [], [], []
    n_honest_20 = round(TOTAL_AGENTS * 0.2)  # 2 agents
    for seed in SEEDS:
        w20, t20 = run_composition(n_honest_20, ps, seed)
        w100, t100 = run_composition(TOTAL_AGENTS, ps, seed)
        w20s.append(w20)
        t20s.append(t20)
        w100s.append(w100)
        t100s.append(t100)
    return ComparisonResult(
        param_label=ps.label,
        param_varied=param_varied,
        param_value=param_value,
        welfare_20pct=float(np.mean(w20s)),
        welfare_100pct=float(np.mean(w100s)),
        toxicity_20pct=float(np.mean(t20s)),
        toxicity_100pct=float(np.mean(t100s)),
    )


# ---------------------------------------------------------------------------
# Parameter sweeps
# ---------------------------------------------------------------------------
def build_sweeps() -> List[Tuple[ParamSet, str, str]]:
    """Build all parameter variations to test. Returns (ParamSet, varied_param, value_label)."""
    sweeps = []

    # Baseline (the reproduction defaults)
    baseline = ParamSet(label="baseline (h=1, rho=0.1, w_rep=0.1)")
    sweeps.append((baseline, "baseline", "default"))

    # Vary harm externality h
    for h in [0.5, 2.0, 4.0]:
        ps = ParamSet(label=f"h={h}", h=h)
        sweeps.append((ps, "h (harm)", str(h)))

    # Vary externality internalization rho
    for rho in [0.0, 0.3, 0.5, 1.0]:
        ps = ParamSet(label=f"rho={rho}", rho_a=rho, rho_b=rho)
        sweeps.append((ps, "rho (internalization)", str(rho)))

    # Vary reputation weight
    for w in [0.0, 0.5, 1.0]:
        ps = ParamSet(label=f"w_rep={w}", w_rep=w)
        sweeps.append((ps, "w_rep (reputation weight)", str(w)))

    # Vary non-honest composition
    for frac, label in [(0.0, "all opportunistic"), (0.6, "60/40 dec/opp"), (1.0, "all deceptive")]:
        ps = ParamSet(label=f"non-honest={label}", deceptive_frac=frac)
        sweeps.append((ps, "non-honest mix", label))

    # Vary governance
    for cb, decay, label in [
        (False, 0.0, "none"),
        (True, 0.05, "light"),
        (True, 0.2, "strict"),
    ]:
        ps = ParamSet(label=f"governance={label}", circuit_breaker=cb, reputation_decay=decay)
        sweeps.append((ps, "governance", label))

    # Vary surplus asymmetry (s_plus vs s_minus)
    for s_plus, s_minus in [(1.0, 1.0), (2.0, 1.0), (4.0, 1.0), (2.0, 2.0)]:
        ps = ParamSet(label=f"s+={s_plus},s-={s_minus}", s_plus=s_plus, s_minus=s_minus)
        sweeps.append((ps, "surplus (s+/s-)", f"{s_plus}/{s_minus}"))

    return sweeps


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_sensitivity_heatmap(results: List[ComparisonResult], out_dir: Path) -> Path:
    """Summary chart: welfare % difference for each parameter variation."""
    fig, ax = plt.subplots(figsize=(12, max(6, len(results) * 0.35)))

    labels = [f"{r.param_varied}={r.param_value}" for r in results]
    diffs = [r.welfare_pct_diff for r in results]
    colors = ["#F44336" if d > 0 else "#4CAF50" for d in diffs]

    y = np.arange(len(results))
    bars = ax.barh(y, diffs, color=colors, alpha=0.85, edgecolor="white")

    for bar, diff, r in zip(bars, diffs, results):
        x_pos = bar.get_width() + (1 if diff >= 0 else -1)
        ha = "left" if diff >= 0 else "right"
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f"{diff:+.0f}% {'PARADOX' if r.paradox_holds else 'no paradox'}",
                va="center", ha=ha, fontsize=8, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Welfare of 20% honest vs 100% honest (%)", fontsize=11)
    ax.set_title("Sensitivity Analysis: Purity Paradox Robustness\n"
                 "(red = paradox holds, green = paradox breaks)",
                 fontsize=13, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="x", alpha=0.3, linestyle="--")

    out = out_dir / "sensitivity_paradox_robustness.png"
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_welfare_toxicity_tradeoff(results: List[ComparisonResult], out_dir: Path) -> Path:
    """Scatter: each parameter config shows its (welfare_ratio, toxicity_cost)."""
    fig, ax = plt.subplots(figsize=(9, 6))

    for r in results:
        color = "#F44336" if r.paradox_holds else "#4CAF50"
        marker = "D" if r.paradox_holds else "o"
        ax.scatter(
            r.welfare_pct_diff,
            r.toxicity_20pct - r.toxicity_100pct,
            c=color, marker=marker, s=80, edgecolors="white", linewidth=0.8, zorder=5,
        )
        ax.annotate(
            r.param_label, (r.welfare_pct_diff, r.toxicity_20pct - r.toxicity_100pct),
            textcoords="offset points", xytext=(6, 4), fontsize=6.5, alpha=0.8,
        )

    ax.axvline(0, color="gray", linestyle="--", alpha=0.5)
    ax.axhline(0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Welfare difference: 20% honest vs 100% honest (%)", fontsize=11)
    ax.set_ylabel("Toxicity increase (20% honest - 100% honest)", fontsize=11)
    ax.set_title("Parameter Sensitivity: Welfare Gain vs Toxicity Cost", fontsize=13, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.3, linestyle="--")

    out = out_dir / "sensitivity_welfare_vs_toxicity_cost.png"
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(f"runs/{timestamp}_sensitivity_purity_paradox")
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    sweeps = build_sweeps()
    print("=" * 70)
    print("Sensitivity Analysis: Purity Paradox (2602.00035)")
    print(f"  {len(sweeps)} parameter configurations")
    print(f"  {len(SEEDS)} seeds each, {N_EPOCHS} epochs x {STEPS_PER_EPOCH} steps")
    print(f"  Comparing: 20% honest (2/10) vs 100% honest (10/10)")
    print("=" * 70)

    results: List[ComparisonResult] = []
    for i, (ps, varied, value) in enumerate(sweeps, 1):
        print(f"  [{i}/{len(sweeps)}] {ps.label}...", end=" ", flush=True)
        cr = compare(ps, varied, value)
        results.append(cr)
        status = "PARADOX" if cr.paradox_holds else "no paradox"
        print(f"20%={cr.welfare_20pct:.0f} vs 100%={cr.welfare_100pct:.0f} "
              f"({cr.welfare_pct_diff:+.0f}%) [{status}]")

    # Results table
    n_paradox = sum(1 for r in results if r.paradox_holds)
    print(f"\n{'='*70}")
    print(f"SUMMARY: Paradox holds in {n_paradox}/{len(results)} configurations "
          f"({n_paradox/len(results)*100:.0f}%)")
    print(f"{'='*70}")
    print(f"\n{'Parameter':<35} {'20% W':>8} {'100% W':>8} {'Diff%':>7} "
          f"{'20% T':>7} {'100% T':>7} {'Holds?':>7}")
    print("-" * 80)
    for r in results:
        holds = "YES" if r.paradox_holds else "no"
        print(f"{r.param_label:<35} {r.welfare_20pct:>8.0f} {r.welfare_100pct:>8.0f} "
              f"{r.welfare_pct_diff:>+6.0f}% {r.toxicity_20pct:>7.3f} "
              f"{r.toxicity_100pct:>7.3f} {holds:>7}")

    # Identify conditions where paradox breaks
    breaks = [r for r in results if not r.paradox_holds]
    if breaks:
        print(f"\nConditions where paradox BREAKS ({len(breaks)}):")
        for r in breaks:
            print(f"  - {r.param_label}: 20% welfare={r.welfare_20pct:.0f} "
                  f"< 100% welfare={r.welfare_100pct:.0f}")
    else:
        print("\nParadox holds across ALL tested parameter configurations.")

    # Plots
    print("\nGenerating plots...")
    p1 = plot_sensitivity_heatmap(results, plots_dir)
    print(f"  -> {p1}")
    p2 = plot_welfare_toxicity_tradeoff(results, plots_dir)
    print(f"  -> {p2}")

    # CSV export
    csv_path = out_dir / "sensitivity_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "param_label", "param_varied", "param_value",
            "welfare_20pct", "welfare_100pct", "welfare_pct_diff",
            "toxicity_20pct", "toxicity_100pct", "paradox_holds",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "param_label": r.param_label,
                "param_varied": r.param_varied,
                "param_value": r.param_value,
                "welfare_20pct": f"{r.welfare_20pct:.2f}",
                "welfare_100pct": f"{r.welfare_100pct:.2f}",
                "welfare_pct_diff": f"{r.welfare_pct_diff:.1f}",
                "toxicity_20pct": f"{r.toxicity_20pct:.4f}",
                "toxicity_100pct": f"{r.toxicity_100pct:.4f}",
                "paradox_holds": r.paradox_holds,
            })
    print(f"  -> {csv_path}")

    print(f"\nAll outputs: {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
