#!/usr/bin/env python
"""Minimal SWARM example with an illusion-delta style signal.

Run:
    python examples/illusion_delta_minimal.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm.agents.deceptive import DeceptiveAgent
from swarm.agents.honest import HonestAgent
from swarm.core.orchestrator import Orchestrator, OrchestratorConfig
from swarm.metrics.incoherence import illusion_delta


def _run_once(seed: int) -> tuple[float, float]:
    cfg = OrchestratorConfig(n_epochs=12, steps_per_epoch=8, seed=seed)
    orchestrator = Orchestrator(config=cfg)
    orchestrator.register_agent(HonestAgent(agent_id="honest_a", name="Alice"))
    orchestrator.register_agent(HonestAgent(agent_id="honest_b", name="Bob"))
    orchestrator.register_agent(DeceptiveAgent(agent_id="deceptive_x", name="Mallory"))

    history = orchestrator.run()
    accepted = sum(s.accepted_interactions for s in history)
    total = sum(s.total_interactions for s in history)
    avg_toxicity = statistics.fmean(s.toxicity_rate for s in history)
    acceptance_rate = accepted / total if total else 0.0
    perceived_p = max(0.0, min(1.0, 1.0 - avg_toxicity * acceptance_rate))
    return avg_toxicity, perceived_p


def main() -> int:
    seeds = [7, 8, 9, 10]
    replay = [_run_once(seed) for seed in seeds]

    toxicity_values = [r[0] for r in replay]
    p_values = [r[1] for r in replay]

    mean_toxicity = statistics.fmean(toxicity_values)
    disagreement_rates = [abs(v - mean_toxicity) for v in toxicity_values]
    gap = illusion_delta(p_values=p_values, disagreement_rates=disagreement_rates)

    print("seed,avg_toxicity,perceived_coherence_proxy")
    for seed, tox, p in zip(seeds, toxicity_values, p_values, strict=True):
        print(f"{seed},{tox:.4f},{p:.4f}")

    print("\nsummary")
    print(f"perceived_coherence={gap.perceived_coherence:.4f}")
    print(f"distributed_coherence={gap.distributed_coherence:.4f}")
    print(f"illusion_delta={gap.illusion_delta:.4f}")

    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("\nInstall plotting deps to generate a figure:")
        print("python -m pip install -e '.[analysis]'")
        return 0

    out_dir = Path("artifacts")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "illusion_delta_minimal.png"

    fig = plt.figure(figsize=(7, 4))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(seeds, toxicity_values, marker="o", linewidth=2, color="#c0392b")
    ax.set_title(f"Replay toxicity proxy (illusion Δ={gap.illusion_delta:.3f})")
    ax.set_xlabel("replay seed")
    ax.set_ylabel("avg toxicity")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)

    print(f"\nWrote plot: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
