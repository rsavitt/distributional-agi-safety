"""Event schemas for the SWARM-Worktree sandbox bridge.

Defines typed event structures for sandbox lifecycle, command execution,
env propagation blocking, leakage detection, and policy violations.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class WorktreeEventType(Enum):
    """Event types in the Worktree bridge protocol."""

    # Sandbox lifecycle
    SANDBOX_CREATED = "sandbox:created"
    SANDBOX_DESTROYED = "sandbox:destroyed"
    SANDBOX_GC_COLLECTED = "sandbox:gc_collected"

    # Command lifecycle
    COMMAND_REQUESTED = "command:requested"
    COMMAND_ALLOWED = "command:allowed"
    COMMAND_DENIED = "command:denied"
    COMMAND_COMPLETED = "command:completed"
    COMMAND_TIMEOUT = "command:timeout"

    # Security events
    ENV_PROPAGATION_BLOCKED = "security:env_propagation_blocked"
    LEAKAGE_DETECTED = "security:leakage_detected"
    RESOURCE_LIMIT_HIT = "security:resource_limit_hit"
    POLICY_VIOLATION = "security:policy_violation"


@dataclass
class WorktreeEvent:
    """An event observed from a Worktree sandbox."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: WorktreeEventType = WorktreeEventType.SANDBOX_CREATED
    timestamp: datetime = field(default_factory=_utcnow)
    agent_id: str = ""
    sandbox_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON transport."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "sandbox_id": self.sandbox_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorktreeEvent":
        """Deserialize from dict with safe type handling."""
        try:
            event_type = WorktreeEventType(data["event_type"])
        except (ValueError, KeyError):
            event_type = WorktreeEventType.POLICY_VIOLATION
        raw_ts = data.get("timestamp")
        if raw_ts is not None:
            try:
                ts = datetime.fromisoformat(str(raw_ts))
            except (ValueError, TypeError):
                ts = _utcnow()
        else:
            ts = _utcnow()
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=event_type,
            timestamp=ts,
            agent_id=str(data.get("agent_id", "")),
            sandbox_id=data.get("sandbox_id"),
            payload=data.get("payload", {}),
        )
