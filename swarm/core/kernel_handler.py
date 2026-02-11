"""Kernel oracle handler for the GPU kernel marketplace domain."""

import random
import uuid
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, model_validator

from swarm.agents.base import Action, ActionType
from swarm.core.handler import Handler
from swarm.core.proxy import ProxyObservables
from swarm.env.state import EnvState
from swarm.models.agent import AgentType
from swarm.models.events import Event, EventType
from swarm.models.kernel import ChallengeSpec, KernelActionResult, KernelSubmission

# Hardcoded challenge catalog (LeetGPU metadata, CC BY-NC-ND 4.0 safe)
CHALLENGE_CATALOG: List[ChallengeSpec] = [
    ChallengeSpec("1_vector_add", "Vector Addition", "easy", 13, 1e-5, 1e-5, 25_000_000),
    ChallengeSpec("2_matrix_mul", "Matrix Multiplication", "easy", 10, 1e-4, 1e-4, 8192 * 6144),
    ChallengeSpec("3_transpose", "Matrix Transpose", "easy", 10, 1e-5, 1e-5, 16_000_000),
    ChallengeSpec("4_reduction", "Reduction", "medium", 8, 1e-5, 1e-5, 4_194_304),
    ChallengeSpec("5_softmax", "Softmax", "medium", 10, 1e-4, 1e-4, 1_000_000),
    ChallengeSpec("6_attention", "Softmax Attention", "medium", 8, 1e-4, 1e-4, 1024 * 1024),
    ChallengeSpec("12_mha", "Multi-Head Attention", "hard", 4, 1e-5, 1e-5, 1024 * 1024 * 16),
    ChallengeSpec("11_conv3d", "3D Convolution", "hard", 6, 1e-4, 1e-4, 512 * 512 * 64),
]

# Difficulty penalty on test pass rate
DIFFICULTY_PENALTY: Dict[str, float] = {
    "easy": 0.0,
    "medium": 0.1,
    "hard": 0.2,
}


class KernelOracleConfig(BaseModel):
    """Configuration for KernelOracleHandler."""

    enabled: bool = True
    seed: Optional[int] = None
    difficulty_distribution: Dict[str, float] = {
        "easy": 0.4,
        "medium": 0.4,
        "hard": 0.2,
    }
    honest_quality_mean: float = 0.85
    opportunistic_quality_mean: float = 0.55
    adversarial_quality_mean: float = 0.75
    adversarial_cheat_rate: float = 0.6
    audit_detection_rate: float = 0.8
    verifier_detection_rate: float = 0.3

    @model_validator(mode="after")
    def _validate(self) -> "KernelOracleConfig":
        for rate in (
            self.honest_quality_mean,
            self.opportunistic_quality_mean,
            self.adversarial_quality_mean,
            self.adversarial_cheat_rate,
            self.audit_detection_rate,
            self.verifier_detection_rate,
        ):
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"Rate {rate} must be in [0, 1]")
        total = sum(self.difficulty_distribution.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"difficulty_distribution must sum to ~1.0, got {total}"
            )
        return self


class KernelOracleHandler(Handler):
    """Handles kernel market actions: submit, verify, audit.

    Simulates kernel quality outcomes using seeded RNG, agent archetype,
    and challenge difficulty to produce SWARM-compatible proxy signals.
    No actual GPU hardware required.
    """

    def __init__(
        self,
        config: KernelOracleConfig,
        emit_event: Callable[[Event], None],
    ):
        super().__init__(emit_event=emit_event)
        self.config = config
        self._rng = random.Random(config.seed)

        # Build challenge catalog indexed by difficulty
        self._catalog: Dict[str, List[ChallengeSpec]] = {
            "easy": [],
            "medium": [],
            "hard": [],
        }
        for spec in CHALLENGE_CATALOG:
            self._catalog[spec.difficulty].append(spec)

        # Per-epoch state
        self._epoch_challenges: List[ChallengeSpec] = []
        self._submissions: Dict[str, KernelSubmission] = {}  # submission_id -> sub
        self._submission_history: List[KernelSubmission] = []

    def on_epoch_start(self, state: EnvState) -> None:
        """Rotate challenge pool for the epoch."""
        self._epoch_challenges = self._sample_challenges()
        self._submissions.clear()

    def on_epoch_end(self, state: EnvState) -> None:
        """Clear per-epoch state."""
        pass

    def _sample_challenges(self) -> List[ChallengeSpec]:
        """Sample challenges based on difficulty distribution."""
        challenges: List[ChallengeSpec] = []
        for difficulty, weight in self.config.difficulty_distribution.items():
            pool = self._catalog.get(difficulty, [])
            if not pool:
                continue
            count = max(1, round(weight * 5))
            for _ in range(count):
                challenges.append(self._rng.choice(pool))
        return challenges

    def build_observation_fields(
        self,
        agent_id: str,
        state: EnvState,
    ) -> Dict[str, Any]:
        """Build kernel-related observation fields for an agent."""
        available_challenges = [
            {
                "challenge_id": c.challenge_id,
                "name": c.name,
                "difficulty": c.difficulty,
                "num_functional_tests": c.num_functional_tests,
            }
            for c in self._epoch_challenges
        ]

        # Pending submissions by this agent
        pending = [
            {
                "submission_id": s.submission_id,
                "challenge_id": s.challenge_id,
                "tests_passed": s.tests_passed,
                "tests_total": s.tests_total,
            }
            for s in self._submissions.values()
            if s.author_id == agent_id
        ]

        # Submissions available for verification (not by this agent)
        to_verify = [
            {
                "submission_id": s.submission_id,
                "challenge_id": s.challenge_id,
                "author_id": s.author_id,
                "tests_passed": s.tests_passed,
                "tests_total": s.tests_total,
            }
            for s in self._submissions.values()
            if s.author_id != agent_id
        ]

        # Full history for this agent
        history = [
            {
                "submission_id": s.submission_id,
                "challenge_id": s.challenge_id,
                "tests_passed": s.tests_passed,
                "tests_total": s.tests_total,
                "perf_speedup": s.perf_speedup,
            }
            for s in self._submission_history
            if s.author_id == agent_id
        ]

        return {
            "kernel_available_challenges": available_challenges,
            "kernel_pending_submissions": pending,
            "kernel_submissions_to_verify": to_verify,
            "kernel_submission_history": history,
        }

    def handle_action(
        self, action: Action, state: EnvState
    ) -> KernelActionResult:
        """Handle a kernel market action."""
        if action.action_type == ActionType.SUBMIT_KERNEL:
            return self._handle_submit_kernel(action, state)
        elif action.action_type == ActionType.VERIFY_KERNEL:
            return self._handle_verify_kernel(action, state)
        elif action.action_type == ActionType.AUDIT_KERNEL:
            return self._handle_audit_kernel(action, state)

        return KernelActionResult(success=False)

    def _get_agent_type(self, agent_id: str, state: EnvState) -> AgentType:
        """Look up agent type from state."""
        agent_state = state.get_agent(agent_id)
        if agent_state is None:
            return AgentType.HONEST
        return agent_state.agent_type

    def _get_quality_mean(self, agent_type: AgentType) -> float:
        """Get quality mean for an agent type."""
        if agent_type == AgentType.HONEST:
            return self.config.honest_quality_mean
        elif agent_type == AgentType.OPPORTUNISTIC:
            return self.config.opportunistic_quality_mean
        elif agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            return self.config.adversarial_quality_mean
        return self.config.honest_quality_mean

    def _handle_submit_kernel(
        self, action: Action, state: EnvState
    ) -> KernelActionResult:
        """Handle kernel submission action."""
        agent_type = self._get_agent_type(action.agent_id, state)
        quality_mean = self._get_quality_mean(agent_type)

        # Pick challenge from pool or use target_id
        challenge = self._pick_challenge(action.target_id)
        if challenge is None:
            return KernelActionResult(success=False)

        # Apply difficulty penalty
        penalty = DIFFICULTY_PENALTY.get(challenge.difficulty, 0.0)
        effective_quality = max(0.0, min(1.0, quality_mean - penalty))

        # Simulate test results
        tests_total = challenge.num_functional_tests
        tests_passed = sum(
            1 for _ in range(tests_total) if self._rng.random() < effective_quality
        )

        # Compilation failures (higher for opportunistic)
        comp_lambda = 0.2 if agent_type == AgentType.HONEST else 0.8
        compilation_failures = self._poisson(comp_lambda)

        # Precision hacks (higher for adversarial)
        hack_lambda = (
            1.5
            if agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE)
            else 0.1
            if agent_type == AgentType.OPPORTUNISTIC
            else 0.0
        )
        precision_hacks = self._poisson(hack_lambda)

        # Performance speedup (normal distribution)
        speed_mean = (
            0.3
            if agent_type == AgentType.HONEST
            else 0.6
            if agent_type == AgentType.OPPORTUNISTIC
            else 0.5
        )
        perf_speedup = max(-1.0, min(1.0, self._rng.gauss(speed_mean, 0.2)))

        # Cheat determination
        is_cheat = False
        if agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            is_cheat = self._rng.random() < self.config.adversarial_cheat_rate

        # Build submission
        submission = KernelSubmission(
            submission_id=str(uuid.uuid4()),
            challenge_id=challenge.challenge_id,
            author_id=action.agent_id,
            tests_passed=tests_passed,
            tests_total=tests_total,
            compilation_failures=compilation_failures,
            precision_hacks=precision_hacks,
            perf_speedup=perf_speedup,
            is_cheat=is_cheat,
        )
        self._submissions[submission.submission_id] = submission
        self._submission_history.append(submission)

        # Build ProxyObservables
        task_progress = 2.0 * (tests_passed / max(1, tests_total)) - 1.0
        observables = ProxyObservables(
            task_progress_delta=task_progress,
            rework_count=compilation_failures,
            verifier_rejections=0,
            tool_misuse_flags=precision_hacks,
            counterparty_engagement_delta=perf_speedup,
        )

        self._emit_event(
            Event(
                event_type=EventType.KERNEL_SUBMITTED,
                agent_id=action.agent_id,
                payload={
                    "submission_id": submission.submission_id,
                    "challenge_id": challenge.challenge_id,
                    "tests_passed": tests_passed,
                    "tests_total": tests_total,
                    "is_cheat": is_cheat,
                    "perf_speedup": perf_speedup,
                },
                epoch=state.current_epoch,
                step=state.current_step,
            )
        )

        return KernelActionResult(
            success=True,
            observables=observables,
            initiator_id=action.agent_id,
            counterparty_id="kernel_oracle",
            metadata={
                "kernel_market": True,
                "action": "submit",
                "challenge_id": challenge.challenge_id,
                "submission_id": submission.submission_id,
            },
            submission=submission,
        )

    def _handle_verify_kernel(
        self, action: Action, state: EnvState
    ) -> KernelActionResult:
        """Handle kernel verification action."""
        submission = self._submissions.get(action.target_id)
        if submission is None:
            return KernelActionResult(success=False)

        # Simulate verification: detect cheats with verifier_detection_rate
        verifier_rejections = 0
        if submission.is_cheat:
            if self._rng.random() < self.config.verifier_detection_rate:
                verifier_rejections = self._rng.randint(1, 3)

        # Build observables from submission signals + verifier findings
        task_progress = (
            2.0 * (submission.tests_passed / max(1, submission.tests_total)) - 1.0
        )
        observables = ProxyObservables(
            task_progress_delta=task_progress,
            rework_count=submission.compilation_failures,
            verifier_rejections=verifier_rejections,
            tool_misuse_flags=submission.precision_hacks,
            counterparty_engagement_delta=submission.perf_speedup,
        )

        self._emit_event(
            Event(
                event_type=EventType.KERNEL_VERIFIED,
                agent_id=action.agent_id,
                payload={
                    "submission_id": submission.submission_id,
                    "verifier_rejections": verifier_rejections,
                    "is_cheat": submission.is_cheat,
                    "detected": verifier_rejections > 0,
                },
                epoch=state.current_epoch,
                step=state.current_step,
            )
        )

        return KernelActionResult(
            success=True,
            observables=observables,
            initiator_id=action.agent_id,
            counterparty_id=submission.author_id,
            metadata={
                "kernel_market": True,
                "action": "verify",
                "submission_id": submission.submission_id,
                "detected_cheat": verifier_rejections > 0,
            },
            submission=submission,
        )

    def _handle_audit_kernel(
        self, action: Action, state: EnvState
    ) -> KernelActionResult:
        """Handle kernel audit (deep testing) action."""
        submission = self._submissions.get(action.target_id)
        if submission is None:
            return KernelActionResult(success=False)

        # Deep testing with higher detection rate
        verifier_rejections = 0
        extra_misuse_flags = 0
        if submission.is_cheat:
            if self._rng.random() < self.config.audit_detection_rate:
                verifier_rejections = self._rng.randint(2, 5)
                extra_misuse_flags = self._rng.randint(1, 3)

        task_progress = (
            2.0 * (submission.tests_passed / max(1, submission.tests_total)) - 1.0
        )
        observables = ProxyObservables(
            task_progress_delta=task_progress,
            rework_count=submission.compilation_failures,
            verifier_rejections=verifier_rejections,
            tool_misuse_flags=submission.precision_hacks + extra_misuse_flags,
            counterparty_engagement_delta=submission.perf_speedup,
        )

        self._emit_event(
            Event(
                event_type=EventType.KERNEL_AUDITED,
                agent_id=action.agent_id,
                payload={
                    "submission_id": submission.submission_id,
                    "verifier_rejections": verifier_rejections,
                    "extra_misuse_flags": extra_misuse_flags,
                    "is_cheat": submission.is_cheat,
                    "detected": verifier_rejections > 0,
                },
                epoch=state.current_epoch,
                step=state.current_step,
            )
        )

        return KernelActionResult(
            success=True,
            observables=observables,
            initiator_id=action.agent_id,
            counterparty_id=submission.author_id,
            metadata={
                "kernel_market": True,
                "action": "audit",
                "submission_id": submission.submission_id,
                "detected_cheat": verifier_rejections > 0,
            },
            submission=submission,
        )

    def _pick_challenge(self, target_id: str) -> Optional[ChallengeSpec]:
        """Pick a challenge from the epoch pool, or by target_id."""
        if target_id:
            for c in self._epoch_challenges:
                if c.challenge_id == target_id:
                    return c
        if self._epoch_challenges:
            return self._rng.choice(self._epoch_challenges)
        # Fallback: pick from full catalog
        all_challenges = [c for specs in self._catalog.values() for c in specs]
        if all_challenges:
            return self._rng.choice(all_challenges)
        return None

    def _poisson(self, lam: float) -> int:
        """Sample from Poisson distribution using inverse transform."""
        if lam <= 0:
            return 0
        L = pow(2.718281828, -lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= self._rng.random()
            if p <= L:
                return k - 1
