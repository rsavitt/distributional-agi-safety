"""Distributional AGI Safety Sandbox - Soft Label Payoff & Metrics System."""

from src.models.interaction import SoftInteraction, InteractionType
from src.models.agent import AgentType, AgentState
from src.core.payoff import SoftPayoffEngine, PayoffConfig
from src.core.proxy import ProxyComputer, ProxyWeights, ProxyObservables
from src.metrics.soft_metrics import SoftMetrics
from src.metrics.reporters import MetricsReporter

__all__ = [
    "SoftInteraction",
    "InteractionType",
    "AgentType",
    "AgentState",
    "SoftPayoffEngine",
    "PayoffConfig",
    "ProxyComputer",
    "ProxyWeights",
    "ProxyObservables",
    "SoftMetrics",
    "MetricsReporter",
]

__version__ = "0.1.0"
