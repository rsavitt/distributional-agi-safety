"""Distributional AGI Safety Sandbox - Soft Label Payoff & Metrics System."""

from swarm.core.orchestrator import EpochMetrics, Orchestrator, OrchestratorConfig
from swarm.core.payoff import PayoffConfig, SoftPayoffEngine
from swarm.core.proxy import ProxyComputer, ProxyObservables, ProxyWeights
from swarm.metrics.reporters import MetricsReporter
from swarm.metrics.soft_metrics import SoftMetrics
from swarm.models.agent import AgentState, AgentType
from swarm.models.interaction import InteractionType, SoftInteraction

__all__ = [
    # Models
    "SoftInteraction",
    "InteractionType",
    "AgentType",
    "AgentState",
    # Core
    "SoftPayoffEngine",
    "PayoffConfig",
    "ProxyComputer",
    "ProxyWeights",
    "ProxyObservables",
    # Orchestrator
    "Orchestrator",
    "OrchestratorConfig",
    "EpochMetrics",
    # Metrics
    "SoftMetrics",
    "MetricsReporter",
]

__version__ = "0.1.0"
