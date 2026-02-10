"""Job queue for managing simulation runs."""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from swarm.bridges.openclaw.config import ServiceConfig

logger = logging.getLogger(__name__)

# Type for simulation function: (scenario_dict, seed) -> metrics_dict
SimulationFn = Callable[[dict[str, Any], int], dict[str, Any]]


class JobState(Enum):
    """State of a simulation job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """A simulation job."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request: dict[str, Any] = field(default_factory=dict)
    state: JobState = JobState.QUEUED
    epochs_completed: int = 0
    total_epochs: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metrics: dict[str, Any] = field(default_factory=dict)
    run_dir: str = ""

    def to_status_dict(self) -> dict[str, Any]:
        """Convert to status dict."""
        return {
            "job_id": self.job_id,
            "status": self.state.value,
            "epochs_completed": self.epochs_completed,
            "total_epochs": self.total_epochs,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class JobQueue:
    """Thread-safe job queue for simulation runs."""

    def __init__(
        self,
        config: Optional[ServiceConfig] = None,
        simulation_fn: Optional[SimulationFn] = None,
    ):
        self._config = config or ServiceConfig()
        self._simulation_fn = simulation_fn
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=self._config.max_concurrent_jobs
        )

    def submit(self, request: dict[str, Any]) -> Job:
        """Submit a new simulation job."""
        job = Job(
            request=request,
            total_epochs=request.get("epochs", 10),
        )

        with self._lock:
            self._jobs[job.job_id] = job

        # Submit to thread pool
        self._executor.submit(self._run_job, job)

        return job

    def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> list[Job]:
        """List recent jobs."""
        with self._lock:
            jobs = list(self._jobs.values())
        return jobs[-limit:]

    def _run_job(self, job: Job) -> None:
        """Execute a simulation job."""
        with self._lock:
            job.state = JobState.RUNNING
            job.started_at = datetime.now(timezone.utc)

        try:
            scenario_name = job.request.get("scenario", "")
            seed = job.request.get("seed", 42)

            scenario_dict = self._load_scenario(scenario_name)

            # Apply overrides
            epochs = job.request.get("epochs")
            if epochs is not None:
                scenario_dict.setdefault("simulation", {})["n_epochs"] = epochs
                job.total_epochs = epochs

            steps = job.request.get("steps_per_epoch")
            if steps is not None:
                scenario_dict.setdefault("simulation", {})["steps_per_epoch"] = steps

            gov_overrides = job.request.get("governance_overrides")
            if gov_overrides:
                scenario_dict.setdefault("governance", {}).update(gov_overrides)

            if self._simulation_fn is None:
                raise RuntimeError("No simulation function configured")

            result = self._simulation_fn(scenario_dict, seed)

            with self._lock:
                job.metrics = result
                job.epochs_completed = job.total_epochs
                job.state = JobState.COMPLETED
                job.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.exception("Job %s failed", job.job_id)
            with self._lock:
                job.state = JobState.FAILED
                job.error = self._sanitize_error(e)
                job.completed_at = datetime.now(timezone.utc)

    @staticmethod
    def _sanitize_error(exc: Exception) -> str:
        """Return a safe error message without leaking internal paths."""
        if isinstance(exc, FileNotFoundError):
            return "Scenario not found"
        if isinstance(exc, ValueError):
            return f"Invalid request: {exc}"
        if isinstance(exc, RuntimeError):
            return str(exc)
        return f"Job failed: {type(exc).__name__}"

    def _load_scenario(self, name: str) -> dict[str, Any]:
        """Load a scenario YAML file by name.

        Only loads files from the configured scenario_dir. Path traversal
        sequences are rejected to prevent reading arbitrary files.
        """
        # Reject path separators and traversal sequences in the name
        if "/" in name or "\\" in name or "\0" in name:
            raise ValueError("Invalid scenario name: must not contain path separators")

        scenario_dir = Path(self._config.scenario_dir).resolve()
        candidates = [
            scenario_dir / name,
            scenario_dir / f"{name}.yaml",
            scenario_dir / f"{name}.yml",
        ]

        for candidate in candidates:
            resolved = candidate.resolve()
            # Ensure the resolved path is within the scenario directory
            if not resolved.is_relative_to(scenario_dir):
                raise ValueError("Invalid scenario name: path escapes scenario directory")
            if resolved.exists() and resolved.is_file():
                with open(resolved) as f:
                    data: dict[str, Any] = yaml.safe_load(f)
                    return data

        raise FileNotFoundError(f"Scenario not found: {name}")

    def shutdown(self) -> None:
        """Shut down the executor."""
        self._executor.shutdown(wait=False)
