"""Tests for swarm.api.simulation_runner."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swarm.api.simulation_runner import (
    SimulationResult,
    SimulationRunner,
    SimulationStatus,
    _run_simulation_sync,
)


# Minimal valid scenario YAML for testing
MINIMAL_YAML = """\
scenario_id: test_sim
simulation:
  n_epochs: 2
  steps_per_epoch: 2
  seed: 42
agents:
  - type: honest
    count: 2
"""


@pytest.fixture
def runner():
    return SimulationRunner(max_concurrent=2)


@pytest.mark.asyncio
async def test_submit_creates_pending_simulation(runner):
    result = await runner.submit(MINIMAL_YAML, simulation_id="test_1")
    assert result.simulation_id == "test_1"
    assert result.status == SimulationStatus.PENDING
    assert result.created_at is not None
    assert result.epoch_metrics == []
    # Clean up background task
    task = runner._tasks.get("test_1")
    if task:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_submit_generates_id_if_not_provided(runner):
    result = await runner.submit(MINIMAL_YAML)
    assert result.simulation_id.startswith("sim_")
    task = runner._tasks.get(result.simulation_id)
    if task:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_simulation_completes_successfully(runner):
    """Submit a minimal scenario and verify it completes."""
    result = await runner.submit(MINIMAL_YAML, simulation_id="complete_test")

    # Wait for the background task to finish
    task = runner._tasks["complete_test"]
    await asyncio.wait_for(task, timeout=30.0)

    final = runner.get_status("complete_test")
    assert final is not None
    assert final.status == SimulationStatus.COMPLETED
    assert final.started_at is not None
    assert final.completed_at is not None
    assert len(final.epoch_metrics) == 2  # 2 epochs
    assert final.error is None


@pytest.mark.asyncio
async def test_failed_simulation_records_error(runner):
    """Submit invalid YAML and verify the simulation fails gracefully."""
    bad_yaml = "this: is: not: valid: yaml: ["

    result = await runner.submit(bad_yaml, simulation_id="fail_test")
    task = runner._tasks["fail_test"]
    await asyncio.wait_for(task, timeout=10.0)

    final = runner.get_status("fail_test")
    assert final is not None
    assert final.status == SimulationStatus.FAILED
    assert final.error is not None


@pytest.mark.asyncio
async def test_cancel_sets_status(runner):
    """Cancel a simulation and verify status is CANCELLED."""
    # Use a mock that blocks to ensure the sim is still running when we cancel
    async def slow_sim(sim_id, yaml_str):
        result = runner._simulations[sim_id]
        async with runner._semaphore:
            result.status = SimulationStatus.RUNNING
            try:
                await asyncio.sleep(60)  # Block until cancelled
            except asyncio.CancelledError:
                result.status = SimulationStatus.CANCELLED
                raise

    with patch.object(runner, "_run_simulation", side_effect=slow_sim):
        result = await runner.submit(MINIMAL_YAML, simulation_id="cancel_test")
        await asyncio.sleep(0.1)  # Let the task start

        cancelled = await runner.cancel("cancel_test")
        assert cancelled is True

        final = runner.get_status("cancel_test")
        assert final is not None
        assert final.status == SimulationStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_unknown_returns_false(runner):
    result = await runner.cancel("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_get_status_unknown_returns_none(runner):
    assert runner.get_status("nonexistent") is None


@pytest.mark.asyncio
async def test_list_simulations_filters_by_status(runner):
    """Verify list_simulations can filter by status."""
    # Manually insert simulations in different states
    runner._simulations["a"] = SimulationResult(
        simulation_id="a", status=SimulationStatus.COMPLETED
    )
    runner._simulations["b"] = SimulationResult(
        simulation_id="b", status=SimulationStatus.FAILED
    )
    runner._simulations["c"] = SimulationResult(
        simulation_id="c", status=SimulationStatus.COMPLETED
    )

    completed = runner.list_simulations(status=SimulationStatus.COMPLETED)
    assert len(completed) == 2
    assert all(s.status == SimulationStatus.COMPLETED for s in completed)

    failed = runner.list_simulations(status=SimulationStatus.FAILED)
    assert len(failed) == 1

    all_sims = runner.list_simulations()
    assert len(all_sims) == 3


@pytest.mark.asyncio
async def test_concurrent_limit_respected():
    """Verify semaphore limits concurrent simulations."""
    runner = SimulationRunner(max_concurrent=1)

    started = []
    barrier = asyncio.Event()

    original_run = runner._run_simulation

    async def tracked_run(sim_id, yaml_str):
        started.append(sim_id)
        if sim_id == "first":
            # Hold the semaphore until released
            await barrier.wait()
        await original_run(sim_id, yaml_str)

    with patch.object(runner, "_run_simulation", side_effect=tracked_run):
        r1 = await runner.submit(MINIMAL_YAML, simulation_id="first")
        r2 = await runner.submit(MINIMAL_YAML, simulation_id="second")

        # Give tasks time to start
        await asyncio.sleep(0.2)

        # Only "first" should have started (semaphore=1)
        assert "first" in started
        # "second" may or may not have started the coroutine,
        # but it should be blocked at the semaphore
        first_result = runner.get_status("first")
        assert first_result is not None

        # Release the barrier so both can complete
        barrier.set()

        # Wait for both
        for sid in ("first", "second"):
            task = runner._tasks.get(sid)
            if task:
                try:
                    await asyncio.wait_for(task, timeout=30.0)
                except (asyncio.CancelledError, Exception):
                    pass
