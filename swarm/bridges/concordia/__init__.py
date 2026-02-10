"""SWARM-Concordia Bridge.

Connects SWARM's governance and metrics framework to Concordia
(Google DeepMind's LLM agent simulation library), enabling
safety scoring of narrative-driven multi-agent interactions.

Architecture:
    Concordia GameMaster
        └── SwarmGameMaster (wrapper)
                ├── ConcordiaAdapter  (narrative → SoftInteraction)
                │       ├── LLMJudge  (narrative → scores)
                │       └── ProxyComputer (scores → v_hat → p)
                └── GovernanceEngine  (optional)
"""

from swarm.bridges.concordia.adapter import ConcordiaAdapter
from swarm.bridges.concordia.config import ConcordiaConfig, JudgeConfig
from swarm.bridges.concordia.events import (
    ConcordiaEvent,
    ConcordiaEventType,
    JudgeScores,
    NarrativeChunk,
)
from swarm.bridges.concordia.game_master import SwarmGameMaster
from swarm.bridges.concordia.judge import LLMJudge

__all__ = [
    "ConcordiaAdapter",
    "ConcordiaConfig",
    "JudgeConfig",
    "ConcordiaEvent",
    "ConcordiaEventType",
    "JudgeScores",
    "NarrativeChunk",
    "SwarmGameMaster",
    "LLMJudge",
]
