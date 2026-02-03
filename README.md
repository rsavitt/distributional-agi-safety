# Distributional AGI Safety Sandbox

A simulation framework for studying distributional safety in multi-agent AI systems using soft (probabilistic) labels.

## Overview

The system provides:

**Foundation Layer:**
- Core data models for interactions with probabilistic labels
- Downstream proxy computation (v_hat → p via calibrated sigmoid)
- Soft payoff engine (reformulated A3b)
- Metrics system (toxicity, conditional loss, calibration, variance)
- Append-only event logging with replay

**Runtime Layer (MVP v0):**
- Agent behavioral policies (honest, opportunistic, deceptive, adversarial)
- Environment state management with rate limits
- Feed engine (posts, replies, voting, visibility ranking)
- Task system (claiming, collaboration, verification)
- Orchestrator for multi-agent simulation

## Installation

```bash
# Install base dependencies
pip install -e .

# Install with development tools
pip install -e ".[dev]"

# Install with analysis tools (pandas, matplotlib)
pip install -e ".[analysis]"

# Install everything
pip install -e ".[all]"
```

## Quick Start: Running a Simulation

```python
from src.agents.honest import HonestAgent
from src.agents.opportunistic import OpportunisticAgent
from src.agents.deceptive import DeceptiveAgent
from src.core.orchestrator import Orchestrator, OrchestratorConfig

# Configure simulation
config = OrchestratorConfig(
    n_epochs=10,
    steps_per_epoch=10,
    seed=42,
)

# Create orchestrator
orchestrator = Orchestrator(config=config)

# Register agents
orchestrator.register_agent(HonestAgent(agent_id="honest_1"))
orchestrator.register_agent(HonestAgent(agent_id="honest_2"))
orchestrator.register_agent(OpportunisticAgent(agent_id="opp_1"))
orchestrator.register_agent(DeceptiveAgent(agent_id="dec_1"))

# Run simulation
metrics = orchestrator.run()

# Analyze results
for m in metrics:
    print(f"Epoch {m.epoch}: toxicity={m.toxicity_rate:.3f}, welfare={m.total_welfare:.2f}")
```

Run the demo:
```bash
python examples/mvp_demo.py
```

## Quick Start: Computing Metrics

```python
from src.models.interaction import SoftInteraction, InteractionType
from src.core.proxy import ProxyComputer, ProxyObservables
from src.core.payoff import SoftPayoffEngine
from src.metrics.reporters import MetricsReporter

# Create an interaction with observables
obs = ProxyObservables(
    task_progress_delta=0.7,
    rework_count=1,
    verifier_rejections=0,
    counterparty_engagement_delta=0.4,
)

# Compute soft labels
proxy = ProxyComputer()
v_hat, p = proxy.compute_labels(obs)

# Create interaction
interaction = SoftInteraction(
    initiator="agent_1",
    counterparty="agent_2",
    interaction_type=InteractionType.COLLABORATION,
    accepted=True,
    v_hat=v_hat,
    p=p,
)

# Compute payoffs
engine = SoftPayoffEngine()
payoff_a = engine.payoff_initiator(interaction)
payoff_b = engine.payoff_counterparty(interaction)

# Compute metrics on a batch
from tests.fixtures.interactions import generate_mixed_batch

interactions = generate_mixed_batch(count=100, toxic_fraction=0.3)
reporter = MetricsReporter()
print(reporter.format_report(interactions, verbose=True))
```

## Directory Structure

```
distributional-agi-safety/
├── src/
│   ├── models/
│   │   ├── interaction.py      # SoftInteraction, InteractionType
│   │   ├── agent.py            # AgentType, AgentState
│   │   └── events.py           # Event log schema
│   ├── core/
│   │   ├── payoff.py           # SoftPayoffEngine
│   │   ├── proxy.py            # ProxyComputer (v_hat computation)
│   │   ├── sigmoid.py          # Calibrated sigmoid utilities
│   │   └── orchestrator.py     # Simulation orchestrator
│   ├── agents/
│   │   ├── base.py             # BaseAgent, Action, Observation
│   │   ├── honest.py           # Cooperative agent policy
│   │   ├── opportunistic.py    # Payoff-maximizing policy
│   │   ├── deceptive.py        # Trust-then-exploit policy
│   │   ├── adversarial.py      # Targeting/coordination policy
│   │   └── roles/              # Role mixins (planner, worker, verifier, etc.)
│   ├── env/
│   │   ├── state.py            # EnvState, RateLimits
│   │   ├── feed.py             # Posts, replies, voting
│   │   └── tasks.py            # Task pool and lifecycle
│   ├── metrics/
│   │   ├── soft_metrics.py     # SoftMetrics (40+ metrics)
│   │   └── reporters.py        # Dual reporting (soft + hard)
│   └── logging/
│       └── event_log.py        # Append-only JSONL logger
├── tests/
│   ├── test_payoff.py
│   ├── test_proxy.py
│   ├── test_metrics.py
│   ├── test_agents.py
│   ├── test_env.py
│   ├── test_orchestrator.py
│   └── fixtures/
│       └── interactions.py     # Test data generators
├── examples/
│   └── mvp_demo.py             # End-to-end demo
├── scenarios/
│   ├── baseline.yaml           # 5-agent baseline scenario
│   └── status_game.yaml        # Reputation competition
└── pyproject.toml
```

## Agent Policies

| Type | Behavior |
|------|----------|
| **Honest** | Cooperative, trust-based, completes tasks diligently |
| **Opportunistic** | Maximizes short-term payoff, cherry-picks tasks, strategic voting |
| **Deceptive** | Builds trust through honest behavior, then exploits trusted relationships |
| **Adversarial** | Targets honest agents, coordinates with allies, disrupts ecosystem |

## Orchestrator

The orchestrator manages the simulation loop:

```python
for epoch in range(n_epochs):
    for step in range(steps_per_epoch):
        for agent in agents:
            observation = build_observation(agent, state)
            action = agent.act(observation)
            execute_action(action, state, event_log)
        resolve_pending_interactions()
    emit_epoch_metrics()
```

**Features:**
- Agent scheduling (round-robin, random, or priority-based)
- Rate limit enforcement (posts, votes, interactions per epoch)
- Automatic payoff computation via SoftPayoffEngine
- Event logging with full simulation replay

## Core Concepts

### Soft Labels

Instead of binary labels (good/bad), interactions carry a probability `p = P(v = +1)` representing the likelihood of a beneficial outcome:

1. **Proxy signals** are combined into a raw score `v_hat ∈ [-1, +1]`
2. **Calibrated sigmoid** converts to probability: `p = 1 / (1 + exp(-k * v_hat))`

### Proxy Computation

The `ProxyComputer` combines observable signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| task_progress | 0.4 | Forward progress on task |
| rework_penalty | 0.2 | Quality signal from rework cycles |
| verifier_penalty | 0.2 | Safety signal from rejections |
| engagement_signal | 0.2 | Counterparty response |

### Soft Payoff Engine (Reformulated A3b)

```
π_a = θ * S_soft - τ - c_a - ρ_a * E_soft + w_rep * r_a
π_b = (1-θ) * S_soft + τ - c_b - ρ_b * E_soft + w_rep * r_b
```

Where:
- `S_soft = p * s_plus - (1-p) * s_minus` (expected surplus)
- `E_soft = (1-p) * h` (expected harm externality)

### Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| Toxicity rate | `E[1-p \| accepted]` | Expected harm among accepted |
| Quality gap | `E[p \| accepted] - E[p \| rejected]` | Adverse selection indicator |
| Conditional loss | `E[π \| accepted] - E[π]` | Selection effect on payoffs |
| Brier score | `E[(p - v)²]` | Calibration quality |
| ECE | Expected calibration error | Binned calibration |

## Event Logging & Replay

```python
from pathlib import Path
from src.core.orchestrator import Orchestrator, OrchestratorConfig

# Run with logging
config = OrchestratorConfig(
    n_epochs=10,
    log_path=Path("logs/simulation.jsonl"),
    log_events=True,
)
orchestrator = Orchestrator(config=config)
# ... register agents and run ...

# Replay events
for event in orchestrator.event_log.replay():
    print(event.event_type, event.timestamp)

# Reconstruct interactions
interactions = orchestrator.event_log.to_interactions()
```

## Running Tests

```bash
# Run all tests (156 tests)
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_orchestrator.py -v
```

## Scenarios

Define simulations in YAML:

```yaml
# scenarios/baseline.yaml
scenario_id: baseline
agents:
  - type: honest
    count: 3
  - type: opportunistic
    count: 1
  - type: deceptive
    count: 1

simulation:
  n_epochs: 10
  steps_per_epoch: 10
  seed: 42

payoff:
  s_plus: 2.0
  s_minus: 1.0
  h: 2.0
  theta: 0.5
```

## Future Extensions (MVP v1)

- **Governance module**: Transaction taxes, reputation decay, circuit breakers
- **Marketplace**: Bounties, bids, escrow for task completion
- **Scenario runner**: Parameter sweeps, batch simulations
- **Dashboard**: Streamlit visualization of metrics over time

## Inspired By

- [Distributional Safety in Agentic Systems](https://arxiv.org/abs/2512.16856)
- [Multi-Agent Market Dynamics](https://arxiv.org/abs/2502.141)
- [Moltbook](https://moltbook.com)
- [@sebkrier's thread on agent economies](https://x.com/sebkrier/status/2017993948132774232)

## Dependencies

**Core:** numpy, pydantic

**Development:** pytest, pytest-cov, mypy, ruff

**Analysis:** pandas, matplotlib, seaborn

**Runtime:** pyyaml

**Dashboard:** streamlit, plotly
