"""Pydantic request/response models for the OpenClaw REST API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Request to start a simulation run."""

    scenario: str
    seed: int = 42
    epochs: Optional[int] = None
    steps_per_epoch: Optional[int] = None
    governance_overrides: Optional[dict[str, Any]] = None


class RunResponse(BaseModel):
    """Response after submitting a run."""

    job_id: str
    status: str


class RunStatus(BaseModel):
    """Status of a simulation run."""

    job_id: str
    status: str
    epochs_completed: int = 0
    total_epochs: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class RunMetrics(BaseModel):
    """Metrics from a completed simulation run."""

    job_id: str
    toxicity_rate: float = 0.0
    quality_gap: float = 0.0
    total_welfare: float = 0.0
    interactions_count: int = 0
    epochs_completed: int = 0
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
