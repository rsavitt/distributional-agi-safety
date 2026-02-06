"""Agent module with behavioral policies and roles."""

from swarm.agents.adaptive_adversary import (
    AdaptiveAdversary,
    AttackStrategy,
)
from swarm.agents.adversarial import AdversarialAgent
from swarm.agents.base import (
    Action,
    ActionType,
    BaseAgent,
    Observation,
)
from swarm.agents.deceptive import DeceptiveAgent
from swarm.agents.honest import HonestAgent
from swarm.agents.opportunistic import OpportunisticAgent

__all__ = [
    # Base classes
    "BaseAgent",
    "Action",
    "ActionType",
    "Observation",
    # Agent types
    "HonestAgent",
    "OpportunisticAgent",
    "DeceptiveAgent",
    "AdversarialAgent",
    "AdaptiveAdversary",
    # Attack strategies
    "AttackStrategy",
]
