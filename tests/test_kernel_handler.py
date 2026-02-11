"""Tests for the kernel oracle handler (v2: correlated cheating, OOD, tolerance)."""

import pytest

from swarm.agents.base import Action, ActionType
from swarm.core.kernel_handler import (
    CHALLENGE_CATALOG,
    DIFFICULTY_PENALTY,
    DIFFICULTY_SPEEDUP_VARIANCE,
    KernelOracleConfig,
    KernelOracleHandler,
)
from swarm.env.state import EnvState
from swarm.models.agent import AgentType
from swarm.models.events import Event


class _EventCollector:
    """Collects emitted events for assertions."""

    def __init__(self):
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


def _make_handler(seed: int = 42, **kwargs) -> tuple[KernelOracleHandler, _EventCollector]:
    collector = _EventCollector()
    config = KernelOracleConfig(seed=seed, **kwargs)
    handler = KernelOracleHandler(config=config, emit_event=collector)
    return handler, collector


def _make_state(*agent_specs: tuple[str, AgentType]) -> EnvState:
    state = EnvState()
    for agent_id, agent_type in agent_specs:
        state.add_agent(agent_id=agent_id, name=agent_id, agent_type=agent_type)
    return state


class TestConfigValidation:
    def test_valid_config(self):
        config = KernelOracleConfig()
        assert config.enabled is True

    def test_invalid_functional_quality(self):
        with pytest.raises(ValueError):
            KernelOracleConfig(honest_functional_quality=1.5)

    def test_invalid_difficulty_distribution(self):
        with pytest.raises(ValueError):
            KernelOracleConfig(difficulty_distribution={"easy": 0.1, "medium": 0.1, "hard": 0.1})

    def test_valid_custom_config(self):
        config = KernelOracleConfig(
            honest_functional_quality=0.9,
            adversarial_cheat_rate=0.8,
            audit_detection_rate=0.95,
        )
        assert config.honest_functional_quality == 0.9
        assert config.adversarial_cheat_rate == 0.8

    def test_legacy_quality_mean_migration(self):
        """Old YAMLs using honest_quality_mean should map to functional_quality."""
        config = KernelOracleConfig(
            honest_quality_mean=0.9,
            opportunistic_quality_mean=0.6,
            adversarial_quality_mean=0.8,
        )
        assert config.honest_functional_quality == 0.9
        assert config.opportunistic_functional_quality == 0.6
        assert config.adversarial_functional_quality == 0.8

    def test_new_v2_fields_have_defaults(self):
        config = KernelOracleConfig()
        assert config.cheat_speedup_bonus == 0.40
        assert config.honest_ood_quality == 0.80
        assert config.adversarial_ood_quality == 0.30
        assert config.honest_tolerance_margin == 0.70
        assert config.adversarial_tolerance_margin == 0.05


class TestChallengeCatalog:
    def test_catalog_populated(self):
        assert len(CHALLENGE_CATALOG) > 0

    def test_catalog_has_all_difficulties(self):
        difficulties = {c.difficulty for c in CHALLENGE_CATALOG}
        assert "easy" in difficulties
        assert "medium" in difficulties
        assert "hard" in difficulties

    def test_catalog_has_ood_tests(self):
        for c in CHALLENGE_CATALOG:
            assert c.num_ood_tests > 0, f"{c.challenge_id} missing OOD tests"

    def test_difficulty_penalties_defined(self):
        for difficulty in ("easy", "medium", "hard"):
            assert difficulty in DIFFICULTY_PENALTY

    def test_difficulty_speedup_variance_defined(self):
        for difficulty in ("easy", "medium", "hard"):
            assert difficulty in DIFFICULTY_SPEEDUP_VARIANCE

    def test_epoch_challenge_sampling(self):
        handler, _ = _make_handler()
        state = _make_state()
        handler.on_epoch_start(state)
        assert len(handler._epoch_challenges) > 0


class TestSubmitKernel:
    def test_honest_agent_high_pass_rate(self):
        handler, collector = _make_handler(seed=42)
        state = _make_state(("honest_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        action = Action(
            action_type=ActionType.SUBMIT_KERNEL,
            agent_id="honest_1",
        )
        result = handler.handle_action(action, state)

        assert result.success
        assert result.submission is not None
        assert result.submission.is_cheat is False
        assert result.observables is not None
        # Honest agent should pass most tests
        pass_rate = result.submission.tests_passed / max(1, result.submission.tests_total)
        assert pass_rate > 0.3  # Generous lower bound given randomness

    def test_adversarial_agent_produces_cheats(self):
        handler, _ = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))
        handler.on_epoch_start(state)

        action = Action(
            action_type=ActionType.SUBMIT_KERNEL,
            agent_id="adv_1",
        )
        result = handler.handle_action(action, state)

        assert result.success
        assert result.submission is not None
        assert result.submission.is_cheat is True

    def test_adversarial_cheat_rate_statistical(self):
        """Over many submissions, cheat rate should approximate config."""
        handler, _ = _make_handler(seed=123, adversarial_cheat_rate=0.6)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))

        cheats = 0
        n = 200
        for _ in range(n):
            handler.on_epoch_start(state)
            action = Action(
                action_type=ActionType.SUBMIT_KERNEL,
                agent_id="adv_1",
            )
            result = handler.handle_action(action, state)
            if result.submission and result.submission.is_cheat:
                cheats += 1

        cheat_rate = cheats / n
        assert 0.4 < cheat_rate < 0.8, f"Cheat rate {cheat_rate} not near 0.6"

    def test_submit_emits_event(self):
        handler, collector = _make_handler()
        state = _make_state(("h1", AgentType.HONEST))
        handler.on_epoch_start(state)

        action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
        handler.handle_action(action, state)

        kernel_events = [
            e for e in collector.events if e.event_type.value == "kernel_submitted"
        ]
        assert len(kernel_events) == 1

    def test_submission_has_ood_fields(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))
        handler.on_epoch_start(state)

        action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
        result = handler.handle_action(action, state)

        sub = result.submission
        assert sub.ood_tests_total > 0
        assert 0 <= sub.ood_tests_passed <= sub.ood_tests_total
        assert 0.0 <= sub.tolerance_margin <= 1.0
        assert sub.base_speedup <= sub.perf_speedup or not sub.is_cheat


class TestCorrelatedSpeedupCheating:
    """Test the core v2 mechanic: cheating boosts apparent speedup."""

    def test_cheat_speedup_higher_than_base(self):
        """When cheating, perf_speedup should exceed base_speedup."""
        handler, _ = _make_handler(
            seed=42, adversarial_cheat_rate=1.0, cheat_speedup_bonus=0.4
        )
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))

        for _ in range(20):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
            result = handler.handle_action(action, state)
            sub = result.submission
            assert sub.is_cheat
            # perf_speedup should be base + bonus (clamped to [-1, 1])
            expected = min(1.0, sub.base_speedup + 0.4)
            assert abs(sub.perf_speedup - expected) < 1e-10

    def test_honest_no_speedup_bonus(self):
        """Honest agents should have perf_speedup == base_speedup."""
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        for _ in range(20):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            result = handler.handle_action(action, state)
            sub = result.submission
            assert not sub.is_cheat
            assert abs(sub.perf_speedup - sub.base_speedup) < 1e-10

    def test_cheat_speedup_statistical_advantage(self):
        """Over many runs, adversarial cheaters should have higher average speedup."""
        handler, _ = _make_handler(
            seed=42, adversarial_cheat_rate=1.0, cheat_speedup_bonus=0.4
        )
        state = _make_state(
            ("h1", AgentType.HONEST), ("adv_1", AgentType.ADVERSARIAL)
        )

        honest_speedups = []
        adv_speedups = []

        for _ in range(100):
            handler.on_epoch_start(state)
            h_action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            a_action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
            h_result = handler.handle_action(h_action, state)
            a_result = handler.handle_action(a_action, state)
            honest_speedups.append(h_result.submission.perf_speedup)
            adv_speedups.append(a_result.submission.perf_speedup)

        avg_honest = sum(honest_speedups) / len(honest_speedups)
        avg_adv = sum(adv_speedups) / len(adv_speedups)
        assert avg_adv > avg_honest, (
            f"Adversarial avg speedup {avg_adv:.3f} should exceed honest {avg_honest:.3f}"
        )


class TestOODTestRegime:
    """Test the split functional/OOD test regime."""

    def test_honest_high_ood_quality(self):
        """Honest agents should pass most OOD tests."""
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        ood_rates = []
        for _ in range(100):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            result = handler.handle_action(action, state)
            sub = result.submission
            if sub.ood_tests_total > 0:
                ood_rates.append(sub.ood_tests_passed / sub.ood_tests_total)

        avg_ood = sum(ood_rates) / len(ood_rates)
        assert avg_ood > 0.6, f"Honest OOD pass rate {avg_ood:.3f} too low"

    def test_adversarial_cheat_low_ood_quality(self):
        """Adversarial cheaters should fail most OOD tests."""
        handler, _ = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))

        ood_rates = []
        for _ in range(100):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
            result = handler.handle_action(action, state)
            sub = result.submission
            if sub.ood_tests_total > 0:
                ood_rates.append(sub.ood_tests_passed / sub.ood_tests_total)

        avg_ood = sum(ood_rates) / len(ood_rates)
        assert avg_ood < 0.45, f"Adversarial OOD pass rate {avg_ood:.3f} too high"

    def test_proxy_only_sees_functional(self):
        """Proxy observables should reflect functional tests, not OOD."""
        handler, _ = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))
        handler.on_epoch_start(state)

        action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        result = handler.handle_action(action, state)

        # task_progress should be based on functional tests (high for adversarial)
        sub = result.submission
        func_rate = sub.tests_passed / max(1, sub.tests_total)
        expected_progress = 2.0 * func_rate - 1.0
        assert abs(result.observables.task_progress_delta - expected_progress) < 1e-10

        # OOD results should NOT affect proxy observables at submit time
        assert result.observables.verifier_rejections == 0


class TestToleranceExploitation:
    """Test tolerance margin mechanics."""

    def test_honest_comfortable_margin(self):
        """Honest agents should have tolerance margin well within bounds."""
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        margins = []
        for _ in range(100):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            result = handler.handle_action(action, state)
            margins.append(result.submission.tolerance_margin)

        avg_margin = sum(margins) / len(margins)
        assert avg_margin > 0.5, f"Honest avg margin {avg_margin:.3f} too low"

    def test_adversarial_cheat_tight_margin(self):
        """Adversarial cheaters should have tolerance margin near zero."""
        handler, _ = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))

        margins = []
        for _ in range(100):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
            result = handler.handle_action(action, state)
            margins.append(result.submission.tolerance_margin)

        avg_margin = sum(margins) / len(margins)
        assert avg_margin < 0.25, f"Adversarial avg margin {avg_margin:.3f} too high"

    def test_tight_margin_produces_precision_hacks(self):
        """Submissions with tight tolerance should produce more precision hacks."""
        handler, _ = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))

        hack_counts = []
        for _ in range(100):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
            result = handler.handle_action(action, state)
            hack_counts.append(result.submission.precision_hacks)

        avg_hacks = sum(hack_counts) / len(hack_counts)
        assert avg_hacks > 0.5, f"Adversarial avg hacks {avg_hacks:.3f} too low"


class TestVerifyKernel:
    def test_verify_detects_cheats(self):
        """Verification should detect cheats at verifier_detection_rate."""
        handler, _ = _make_handler(seed=42, verifier_detection_rate=1.0, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL), ("ver_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        # Submit a cheat
        submit = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        submit_result = handler.handle_action(submit, state)
        sub_id = submit_result.submission.submission_id

        # Verify it
        verify = Action(
            action_type=ActionType.VERIFY_KERNEL,
            agent_id="ver_1",
            target_id=sub_id,
        )
        verify_result = handler.handle_action(verify, state)

        assert verify_result.success
        assert verify_result.observables.verifier_rejections > 0

    def test_verify_nonexistent_submission(self):
        handler, _ = _make_handler()
        state = _make_state(("ver_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        verify = Action(
            action_type=ActionType.VERIFY_KERNEL,
            agent_id="ver_1",
            target_id="nonexistent",
        )
        result = handler.handle_action(verify, state)
        assert result.success is False

    def test_verify_honest_no_rejections(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST), ("ver_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        submit = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
        submit_result = handler.handle_action(submit, state)
        sub_id = submit_result.submission.submission_id

        verify = Action(
            action_type=ActionType.VERIFY_KERNEL,
            agent_id="ver_1",
            target_id=sub_id,
        )
        verify_result = handler.handle_action(verify, state)

        assert verify_result.success
        # Honest agent's submission is never a cheat, so no rejections
        assert verify_result.observables.verifier_rejections == 0


class TestAuditKernel:
    def test_audit_higher_detection(self):
        """Audit should have higher detection than verification."""
        handler, _ = _make_handler(
            seed=42,
            audit_detection_rate=1.0,
            verifier_detection_rate=0.0,
            adversarial_cheat_rate=1.0,
        )
        state = _make_state(("adv_1", AgentType.ADVERSARIAL), ("aud_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        submit = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        submit_result = handler.handle_action(submit, state)
        sub_id = submit_result.submission.submission_id

        # Verify: should NOT detect (rate=0)
        verify = Action(
            action_type=ActionType.VERIFY_KERNEL,
            agent_id="aud_1",
            target_id=sub_id,
        )
        verify_result = handler.handle_action(verify, state)
        assert verify_result.observables.verifier_rejections == 0

        # Audit: should detect (rate=1)
        audit = Action(
            action_type=ActionType.AUDIT_KERNEL,
            agent_id="aud_1",
            target_id=sub_id,
        )
        audit_result = handler.handle_action(audit, state)
        assert audit_result.observables.verifier_rejections > 0

    def test_audit_reveals_true_speedup(self):
        """Audit should strip cheat bonus and show base_speedup."""
        handler, _ = _make_handler(
            seed=42,
            adversarial_cheat_rate=1.0,
            cheat_speedup_bonus=0.4,
            audit_detection_rate=1.0,
        )
        state = _make_state(("adv_1", AgentType.ADVERSARIAL), ("aud_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        submit = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        submit_result = handler.handle_action(submit, state)
        sub = submit_result.submission

        audit = Action(
            action_type=ActionType.AUDIT_KERNEL,
            agent_id="aud_1",
            target_id=sub.submission_id,
        )
        audit_result = handler.handle_action(audit, state)

        # Audit shows base_speedup, not inflated perf_speedup
        assert abs(audit_result.observables.counterparty_engagement_delta - sub.base_speedup) < 1e-10
        # Submit showed inflated speedup
        assert abs(submit_result.observables.counterparty_engagement_delta - sub.perf_speedup) < 1e-10

    def test_audit_uses_ood_results(self):
        """Audit event should include OOD test data."""
        handler, collector = _make_handler(
            seed=42, adversarial_cheat_rate=1.0, audit_detection_rate=1.0
        )
        state = _make_state(("adv_1", AgentType.ADVERSARIAL), ("aud_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        submit = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        submit_result = handler.handle_action(submit, state)
        sub_id = submit_result.submission.submission_id

        audit = Action(
            action_type=ActionType.AUDIT_KERNEL,
            agent_id="aud_1",
            target_id=sub_id,
        )
        handler.handle_action(audit, state)

        audit_events = [
            e for e in collector.events if e.event_type.value == "kernel_audited"
        ]
        assert len(audit_events) == 1
        payload = audit_events[0].payload
        assert "ood_tests_passed" in payload
        assert "ood_tests_total" in payload
        assert "tolerance_margin" in payload
        assert "base_speedup" in payload

    def test_audit_emits_event(self):
        handler, collector = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL), ("aud_1", AgentType.HONEST))
        handler.on_epoch_start(state)

        submit = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        submit_result = handler.handle_action(submit, state)
        sub_id = submit_result.submission.submission_id

        audit = Action(
            action_type=ActionType.AUDIT_KERNEL,
            agent_id="aud_1",
            target_id=sub_id,
        )
        handler.handle_action(audit, state)

        audit_events = [
            e for e in collector.events if e.event_type.value == "kernel_audited"
        ]
        assert len(audit_events) == 1


class TestProxySignalRanges:
    def test_task_progress_in_range(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        for _ in range(20):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            result = handler.handle_action(action, state)
            assert result.observables is not None
            assert -1.0 <= result.observables.task_progress_delta <= 1.0

    def test_rework_count_non_negative(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        for _ in range(20):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            result = handler.handle_action(action, state)
            assert result.observables.rework_count >= 0

    def test_engagement_delta_in_range(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        for _ in range(20):
            handler.on_epoch_start(state)
            action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
            result = handler.handle_action(action, state)
            assert -1.0 <= result.observables.counterparty_engagement_delta <= 1.0


class TestGroundTruth:
    def test_cheat_maps_to_negative_ground_truth(self):
        """Cheats should produce ground_truth=-1 when wired through orchestrator."""
        handler, _ = _make_handler(seed=42, adversarial_cheat_rate=1.0)
        state = _make_state(("adv_1", AgentType.ADVERSARIAL))
        handler.on_epoch_start(state)

        action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="adv_1")
        result = handler.handle_action(action, state)
        assert result.submission.is_cheat is True
        # ground_truth is set by orchestrator, but we verify the flag

    def test_honest_maps_to_positive(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))
        handler.on_epoch_start(state)

        action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
        result = handler.handle_action(action, state)
        assert result.submission.is_cheat is False


class TestDifficultyPenalty:
    def test_harder_challenges_lower_pass_rate(self):
        """Statistically, hard challenges should yield lower pass rates."""
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))

        easy_rates = []
        hard_rates = []

        for _ in range(100):
            handler.on_epoch_start(state)
            # Find an easy and a hard challenge
            easy_c = [c for c in handler._epoch_challenges if c.difficulty == "easy"]
            hard_c = [c for c in handler._epoch_challenges if c.difficulty == "hard"]

            if easy_c:
                action = Action(
                    action_type=ActionType.SUBMIT_KERNEL,
                    agent_id="h1",
                    target_id=easy_c[0].challenge_id,
                )
                result = handler.handle_action(action, state)
                if result.submission:
                    easy_rates.append(
                        result.submission.tests_passed / max(1, result.submission.tests_total)
                    )

            if hard_c:
                action = Action(
                    action_type=ActionType.SUBMIT_KERNEL,
                    agent_id="h1",
                    target_id=hard_c[0].challenge_id,
                )
                result = handler.handle_action(action, state)
                if result.submission:
                    hard_rates.append(
                        result.submission.tests_passed / max(1, result.submission.tests_total)
                    )

        if easy_rates and hard_rates:
            avg_easy = sum(easy_rates) / len(easy_rates)
            avg_hard = sum(hard_rates) / len(hard_rates)
            assert avg_easy > avg_hard, (
                f"Easy avg {avg_easy:.3f} should be > hard avg {avg_hard:.3f}"
            )


class TestReproducibility:
    def test_same_seed_same_results(self):
        """Same seed should produce identical submissions."""
        results_a = []
        results_b = []

        for seed_run in (results_a, results_b):
            handler, _ = _make_handler(seed=99)
            state = _make_state(("h1", AgentType.HONEST))
            handler.on_epoch_start(state)

            for _ in range(5):
                action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
                result = handler.handle_action(action, state)
                seed_run.append(
                    (
                        result.submission.tests_passed,
                        result.submission.tests_total,
                        result.submission.ood_tests_passed,
                        result.submission.ood_tests_total,
                        result.submission.is_cheat,
                        round(result.submission.perf_speedup, 10),
                        round(result.submission.base_speedup, 10),
                    )
                )

        assert results_a == results_b


class TestScenarioIntegration:
    def test_v1_scenario_loads_and_runs(self):
        """Original baseline scenario should still work with legacy fields."""
        from pathlib import Path

        from swarm.scenarios.loader import build_orchestrator, load_scenario

        sc = load_scenario(Path("scenarios/kernel_market/baseline.yaml"))
        assert sc.orchestrator_config.kernel_oracle_config is not None

        orch = build_orchestrator(sc)
        orch.config.n_epochs = 1
        results = orch.run()
        assert len(results) == 1

    def test_v2_scenario_loads_and_runs(self):
        """v2 scenario with new kernel oracle params should load and run."""
        from pathlib import Path

        from swarm.scenarios.loader import build_orchestrator, load_scenario

        sc = load_scenario(Path("scenarios/kernel_market/v2.yaml"))
        assert sc.orchestrator_config.kernel_oracle_config is not None

        orch = build_orchestrator(sc)
        orch.config.n_epochs = 1
        results = orch.run()
        assert len(results) == 1


class TestObservationFields:
    def test_observation_fields_populated(self):
        handler, _ = _make_handler(seed=42)
        state = _make_state(("h1", AgentType.HONEST))
        handler.on_epoch_start(state)

        # Submit a kernel first
        action = Action(action_type=ActionType.SUBMIT_KERNEL, agent_id="h1")
        handler.handle_action(action, state)

        # Build observation
        obs = handler.build_observation_fields("h1", state)
        assert "kernel_available_challenges" in obs
        assert "kernel_pending_submissions" in obs
        assert "kernel_submissions_to_verify" in obs
        assert "kernel_submission_history" in obs
        assert len(obs["kernel_available_challenges"]) > 0
        assert len(obs["kernel_pending_submissions"]) == 1
        assert len(obs["kernel_submission_history"]) == 1
