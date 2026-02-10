"""SWARM-OpenClaw Bridge.

Provides a REST service layer over the SWARM orchestrator,
enabling HTTP-based scenario execution and metrics retrieval.

Architecture:
    HTTP Client (OpenClawSkill)
        └── FastAPI Service (create_app)
                ├── POST /runs     → JobQueue.submit
                ├── GET /runs/{id} → JobQueue.get
                ├── GET /runs/{id}/metrics → Job.metrics
                └── GET /health
"""

from swarm.bridges.openclaw.config import ServiceConfig
from swarm.bridges.openclaw.job_queue import Job, JobQueue, JobState
from swarm.bridges.openclaw.schemas import (
    RunMetrics,
    RunRequest,
    RunResponse,
    RunStatus,
)
from swarm.bridges.openclaw.skill import OpenClawSkill

__all__ = [
    "ServiceConfig",
    "JobQueue",
    "Job",
    "JobState",
    "RunRequest",
    "RunResponse",
    "RunStatus",
    "RunMetrics",
    "OpenClawSkill",
]

# Lazy import for service (requires FastAPI)


def create_app(config: ServiceConfig | None = None):  # type: ignore[return]
    """Create a FastAPI app for the OpenClaw service."""
    from swarm.bridges.openclaw.service import create_app as _create_app

    return _create_app(config)


def start_service(config: ServiceConfig | None = None) -> None:
    """Start the OpenClaw service."""
    from swarm.bridges.openclaw.service import start_service as _start_service

    _start_service(config)
