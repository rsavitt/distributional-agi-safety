"""Async simulation execution model for the SWARM web API.

Provides a SimulationRunner that manages simulation lifecycle:
submit, run (in background), poll status, cancel.

Simulations run in background asyncio tasks with concurrency limiting
via a semaphore.  The orchestrator's synchronous ``run()`` is offloaded
to a thread executor via ``asyncio.to_thread()``.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from swarm.scenarios.loader import build_orchestrator, load_scenario


class SimulationStatus(str, Enum):
    """Lifecycle states for a simulation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationResult(BaseModel):
    """Tracks a simulation's lifecycle and results."""

    simulation_id: str
    status: SimulationStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    epoch_metrics: list = Field(default_factory=list)
    error: Optional[str] = None


class SimulationRunner:
    """Manages async simulation execution with concurrency limits.

    Usage::

        runner = SimulationRunner(max_concurrent=4)
        result = await runner.submit(yaml_str)
        # ... poll later ...
        result = runner.get_status(result.simulation_id)
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self._max_concurrent = max_concurrent
        self._simulations: dict[str, SimulationResult] = {}
        self._tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)

    async def submit(
        self,
        scenario_yaml: str,
        simulation_id: str | None = None,
    ) -> SimulationResult:
        """Submit a simulation for background execution.

        Creates a :class:`SimulationResult` with ``PENDING`` status,
        launches ``_run_simulation`` as a background asyncio task, and
        returns immediately with the pending result.

        Args:
            scenario_yaml: YAML string defining the scenario.
            simulation_id: Optional explicit ID.  A UUID is generated
                if not provided.

        Returns:
            The initial ``PENDING`` :class:`SimulationResult`.
        """
        if simulation_id is None:
            simulation_id = str(uuid.uuid4())

        result = SimulationResult(
            simulation_id=simulation_id,
            status=SimulationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._simulations[simulation_id] = result

        task = asyncio.create_task(
            self._run_simulation(simulation_id, scenario_yaml)
        )
        self._tasks[simulation_id] = task

        return result

    async def _run_simulation(
        self, simulation_id: str, scenario_yaml: str
    ) -> None:
        """Execute a simulation in the background with semaphore limiting.

        Acquires the semaphore, updates status to RUNNING, parses the
        YAML, builds an orchestrator, and calls ``orchestrator.run()``
        in a thread executor.  On success the epoch metrics are stored
        and status is set to COMPLETED.  On exception the error message
        is stored and status is set to FAILED.  The semaphore is always
        released.
        """
        result = self._simulations[simulation_id]
        try:
            async with self._semaphore:
                result.status = SimulationStatus.RUNNING
                result.started_at = datetime.now(timezone.utc)

                # Write YAML to a temp file so the existing loader can
                # parse it without duplicating its logic.
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as f:
                    f.write(scenario_yaml)
                    tmp_path = Path(f.name)

                try:
                    scenario = load_scenario(tmp_path)
                    orchestrator = build_orchestrator(scenario)

                    # Offload the synchronous run to a thread so the
                    # event loop stays responsive.
                    epoch_metrics_list = await asyncio.to_thread(
                        orchestrator.run
                    )

                    result.epoch_metrics = [
                        asdict(m) for m in epoch_metrics_list
                    ]
                    result.status = SimulationStatus.COMPLETED
                    result.completed_at = datetime.now(timezone.utc)
                finally:
                    tmp_path.unlink(missing_ok=True)

        except asyncio.CancelledError:
            result.status = SimulationStatus.CANCELLED
            result.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            result.status = SimulationStatus.FAILED
            result.error = str(exc)
            result.completed_at = datetime.now(timezone.utc)

    def get_status(self, simulation_id: str) -> SimulationResult | None:
        """Return the result for a simulation, or ``None`` if unknown."""
        return self._simulations.get(simulation_id)

    async def cancel(self, simulation_id: str) -> bool:
        """Cancel a running or pending simulation.

        Cancels the underlying asyncio task and sets the result status
        to ``CANCELLED``.

        Returns:
            ``True`` if the simulation was successfully cancelled,
            ``False`` if it was already done or not found.
        """
        task = self._tasks.get(simulation_id)
        if task is None or task.done():
            return False

        task.cancel()

        result = self._simulations[simulation_id]
        result.status = SimulationStatus.CANCELLED
        result.completed_at = datetime.now(timezone.utc)
        return True

    def list_simulations(
        self, status: SimulationStatus | None = None
    ) -> list[SimulationResult]:
        """List simulations, optionally filtered by status.

        Args:
            status: If provided, only return simulations with this status.

        Returns:
            List of matching :class:`SimulationResult` instances.
        """
        if status is None:
            return list(self._simulations.values())
        return [
            r for r in self._simulations.values() if r.status == status
        ]
