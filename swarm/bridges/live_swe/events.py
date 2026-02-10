"""Event types for the LiveSWE agent bridge.

Defines typed events for tracking self-evolving SWE agent behavior:
trajectory steps, tool creation, self-modification, and capability growth.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LiveSWEEventType(Enum):
    """Event types emitted by the LiveSWE agent bridge."""

    AGENT_STARTED = "agent:started"
    AGENT_COMPLETED = "agent:completed"
    STEP_EXECUTED = "step:executed"
    STEP_FAILED = "step:failed"
    TOOL_CREATED = "tool:created"
    TOOL_USED = "tool:used"
    SELF_MODIFICATION = "self:modification"
    BEHAVIOR_DRIFT = "behavior:drift"
    CAPABILITY_GROWTH = "capability:growth"
    TASK_SUBMITTED = "task:submitted"
    ERROR = "error"


@dataclass
class LiveSWEEvent:
    """Base event emitted by the LiveSWE bridge."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: LiveSWEEventType = LiveSWEEventType.STEP_EXECUTED
    timestamp: datetime = field(default_factory=_utcnow)
    agent_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LiveSWEEvent":
        event_type_str = data.get("event_type", "step:executed")
        event_type = LiveSWEEventType(event_type_str)
        ts = data.get("timestamp")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        else:
            timestamp = _utcnow()
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=event_type,
            timestamp=timestamp,
            agent_id=data.get("agent_id", ""),
            payload=data.get("payload", {}),
        )


@dataclass
class StepEvent:
    """A single trajectory step from a live-swe-agent run."""

    step_index: int = 0
    thought: str = ""
    bash_command: str = ""
    return_code: int = 0
    output_preview: str = ""
    tool_creations: List[str] = field(default_factory=list)
    tool_usages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "thought": self.thought,
            "bash_command": self.bash_command,
            "return_code": self.return_code,
            "output_preview": self.output_preview,
            "tool_creations": self.tool_creations,
            "tool_usages": self.tool_usages,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepEvent":
        return cls(
            step_index=data.get("step_index", 0),
            thought=data.get("thought", ""),
            bash_command=data.get("bash_command", ""),
            return_code=data.get("return_code", 0),
            output_preview=data.get("output_preview", ""),
            tool_creations=data.get("tool_creations", []),
            tool_usages=data.get("tool_usages", []),
        )


@dataclass
class ToolCreationEvent:
    """Records a tool (script/file) created by the agent at runtime."""

    tool_path: str = ""
    tool_content_hash: str = ""
    detected_capabilities: List[str] = field(default_factory=list)
    step_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_path": self.tool_path,
            "tool_content_hash": self.tool_content_hash,
            "detected_capabilities": self.detected_capabilities,
            "step_index": self.step_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCreationEvent":
        return cls(
            tool_path=data.get("tool_path", ""),
            tool_content_hash=data.get("tool_content_hash", ""),
            detected_capabilities=data.get("detected_capabilities", []),
            step_index=data.get("step_index", 0),
        )


@dataclass
class TrajectoryEvent:
    """Summary of a complete agent trajectory (run)."""

    total_steps: int = 0
    total_cost_usd: float = 0.0
    tools_created: List[str] = field(default_factory=list)
    success: bool = False
    duration_seconds: float = 0.0
    steps: List[StepEvent] = field(default_factory=list)
    agent_id: str = ""
    task: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_steps": self.total_steps,
            "total_cost_usd": self.total_cost_usd,
            "tools_created": self.tools_created,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "steps": [s.to_dict() for s in self.steps],
            "agent_id": self.agent_id,
            "task": self.task,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrajectoryEvent":
        steps_data = data.get("steps", [])
        steps = [StepEvent.from_dict(s) for s in steps_data]
        return cls(
            total_steps=data.get("total_steps", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            tools_created=data.get("tools_created", []),
            success=data.get("success", False),
            duration_seconds=data.get("duration_seconds", 0.0),
            steps=steps,
            agent_id=data.get("agent_id", ""),
            task=data.get("task", ""),
        )
