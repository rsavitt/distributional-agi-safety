"""SWARM Worktree Sandbox Bridge.

Provides sandboxed git worktree environments for agents with full
boundary enforcement (command allowlisting, leakage detection,
information flow tracking, and policy gating).
"""

from swarm.bridges.worktree.bridge import WorktreeBridge
from swarm.bridges.worktree.config import WorktreeConfig
from swarm.bridges.worktree.policy import WorktreePolicy
from swarm.bridges.worktree.sandbox import SandboxManager

__all__ = [
    "WorktreeBridge",
    "WorktreeConfig",
    "WorktreePolicy",
    "SandboxManager",
]
