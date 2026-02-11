"""Kernel oracle handler for the GPU kernel marketplace domain.

v2: Correlated speedup-cheating, split functional/OOD test regime,
tolerance exploitation, revised agent parameters.
"""

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
# Fields: id, name, difficulty, functional_tests, ood_tests, atol, rtol, perf_input_size
CHALLENGE_CATALOG: List[ChallengeSpec] = [
    ChallengeSpec("1_vector_add", "Vector Addition", "easy", 13, 4, 1e-5, 1e-5, 25_000_000),
    ChallengeSpec("2_matrix_mul", "Matrix Multiplication", "easy", 10, 4, 1e-4, 1e-4, 8192 * 6144),
    ChallengeSpec("3_transpose", "Matrix Transpose", "easy", 10, 3, 1e-5, 1e-5, 16_000_000),
    ChallengeSpec("4_reduction", "Reduction", "medium", 8, 5, 1e-5, 1e-5, 4_194_304),
    ChallengeSpec("5_softmax", "Softmax", "medium", 10, 5, 1e-4, 1e-4, 1_000_000),
    ChallengeSpec("6_attention", "Softmax Attention", "medium", 8, 5, 1e-4, 1e-4, 1024 * 1024),
    ChallengeSpec("12_mha", "Multi-Head Attention", "hard", 4, 6, 1e-5, 1e-5, 1024 * 1024 * 16),
    ChallengeSpec("11_conv3d", "3D Convolution", "hard", 6, 6, 1e-4, 1e-4, 512 * 512 * 64),
]

# Difficulty penalty on test pass rate
DIFFICULTY_PENALTY: Dict[str, float] = {
    "easy": 0.0,
    "medium": 0.1,
    "hard": 0.2,
}

# Difficulty bonus on speedup variance (harder problems = more optimization room)
DIFFICULTY_SPEEDUP_VARIANCE: Dict[str, float] = {
    "easy": 0.15,
    "medium": 0.25,
    "hard": 0.35,
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

    # --- Functional test quality (what the proxy sees) ---
    honest_functional_quality: float = 0.85
    opportunistic_functional_quality: float = 0.70
    adversarial_functional_quality: float = 0.95  # cheaters pass visible tests well

    # --- OOD test quality (hidden, only revealed by audit) ---
    honest_ood_quality: float = 0.80
    opportunistic_ood_quality: float = 0.50
    adversarial_ood_quality: float = 0.30  # cheaters fail on OOD inputs

    # --- Speedup parameters ---
    honest_speedup_mean: float = 0.50  # good engineers write fast code
    opportunistic_speedup_mean: float = 0.40  # less skilled
    adversarial_speedup_mean: float = 0.45  # moderate base skill
    cheat_speedup_bonus: float = 0.40  # THE proxy gap: cheating boosts apparent speedup

    # --- Tolerance exploitation ---
    honest_tolerance_margin: float = 0.70  # well within tolerance
    opportunistic_tolerance_margin: float = 0.35  # cuts some corners
    adversarial_tolerance_margin: float = 0.05  # barely within on standard tests

    # --- Cheat and detection rates ---
    adversarial_cheat_rate: float = 0.6
    audit_detection_rate: float = 0.8
    verifier_detection_rate: float = 0.3

    # Legacy aliases — old YAMLs may pass these; map to functional quality
    honest_quality_mean: Optional[float] = None
    opportunistic_quality_mean: Optional[float] = None
    adversarial_quality_mean: Optional[float] = None

    @model_validator(mode="after")
    def _migrate_legacy(self) -> "KernelOracleConfig":
        """Map legacy quality_mean fields to functional_quality."""
        if self.honest_quality_mean is not None:
            self.honest_functional_quality = self.honest_quality_mean
        if self.opportunistic_quality_mean is not None:
            self.opportunistic_functional_quality = self.opportunistic_quality_mean
        if self.adversarial_quality_mean is not None:
            self.adversarial_functional_quality = self.adversarial_quality_mean
        return self

    @model_validator(mode="after")
    def _validate(self) -> "KernelOracleConfig":
        for rate in (
            self.honest_functional_quality,
            self.opportunistic_functional_quality,
            self.adversarial_functional_quality,
            self.honest_ood_quality,
            self.opportunistic_ood_quality,
            self.adversarial_ood_quality,
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

    model_config = {"arbitrary_types_allowed": True}


class KernelOracleHandler(Handler):
    """Handles kernel market actions: submit, verify, audit.

    v2 mechanics:
    - Correlated speedup-cheating: cheaters get a speedup bonus that makes
      them look better to the proxy, creating the core adversarial selection.
    - Split test regime: functional tests (visible to proxy) vs OOD tests
      (only revealed by audit). Cheaters pass functional tests at 0.95 but
      fail OOD at 0.30.
    - Tolerance exploitation: cheaters produce results barely within atol,
      which fail under stricter audit tolerance.
    - Difficulty-dependent speedup variance: harder problems have more
      room for optimization (and gaming).
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

    def _get_functional_quality(self, agent_type: AgentType) -> float:
        """Get functional test quality for an agent type."""
        if agent_type == AgentType.HONEST:
            return self.config.honest_functional_quality
        elif agent_type == AgentType.OPPORTUNISTIC:
            return self.config.opportunistic_functional_quality
        elif agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            return self.config.adversarial_functional_quality
        return self.config.honest_functional_quality

    def _get_ood_quality(self, agent_type: AgentType, is_cheat: bool) -> float:
        """Get OOD test quality for an agent type."""
        if agent_type == AgentType.HONEST:
            return self.config.honest_ood_quality
        elif agent_type == AgentType.OPPORTUNISTIC:
            return self.config.opportunistic_ood_quality
        elif agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            # Cheaters do much worse on OOD
            if is_cheat:
                return self.config.adversarial_ood_quality
            # Non-cheat submissions from adversarial agents are moderate
            return self.config.opportunistic_ood_quality
        return self.config.honest_ood_quality

    def _get_speedup_mean(self, agent_type: AgentType) -> float:
        """Get base speedup mean for an agent type."""
        if agent_type == AgentType.HONEST:
            return self.config.honest_speedup_mean
        elif agent_type == AgentType.OPPORTUNISTIC:
            return self.config.opportunistic_speedup_mean
        elif agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            return self.config.adversarial_speedup_mean
        return self.config.honest_speedup_mean

    def _get_tolerance_margin(self, agent_type: AgentType, is_cheat: bool) -> float:
        """Get tolerance margin for an agent type."""
        if agent_type == AgentType.HONEST:
            return self.config.honest_tolerance_margin
        elif agent_type == AgentType.OPPORTUNISTIC:
            return self.config.opportunistic_tolerance_margin
        elif agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            if is_cheat:
                return self.config.adversarial_tolerance_margin
            return self.config.opportunistic_tolerance_margin
        return self.config.honest_tolerance_margin

    def _handle_submit_kernel(
        self, action: Action, state: EnvState
    ) -> KernelActionResult:
        """Handle kernel submission action."""
        agent_type = self._get_agent_type(action.agent_id, state)

        # Pick challenge from pool or use target_id
        challenge = self._pick_challenge(action.target_id)
        if challenge is None:
            return KernelActionResult(success=False)

        # --- Cheat determination (done FIRST so it affects other signals) ---
        is_cheat = False
        if agent_type in (AgentType.ADVERSARIAL, AgentType.DECEPTIVE):
            is_cheat = self._rng.random() < self.config.adversarial_cheat_rate

        # --- Functional tests (what the proxy sees) ---
        penalty = DIFFICULTY_PENALTY.get(challenge.difficulty, 0.0)
        func_quality = max(0.0, min(1.0, self._get_functional_quality(agent_type) - penalty))
        tests_total = challenge.num_functional_tests
        tests_passed = sum(
            1 for _ in range(tests_total) if self._rng.random() < func_quality
        )

        # --- OOD tests (hidden from proxy, revealed by audit) ---
        ood_quality = max(0.0, min(1.0, self._get_ood_quality(agent_type, is_cheat) - penalty))
        ood_total = challenge.num_ood_tests
        ood_passed = sum(
            1 for _ in range(ood_total) if self._rng.random() < ood_quality
        )

        # --- Compilation failures ---
        comp_lambda = 0.2 if agent_type == AgentType.HONEST else 0.8
        compilation_failures = self._poisson(comp_lambda)

        # --- Tolerance margin ---
        tolerance_margin = self._get_tolerance_margin(agent_type, is_cheat)
        # Add some noise
        tolerance_margin = max(0.0, min(1.0, tolerance_margin + self._rng.gauss(0, 0.1)))

        # --- Precision hacks (structurally motivated by tolerance exploitation) ---
        # Low tolerance margin -> more precision hacks detected
        if tolerance_margin < 0.15:
            hack_lambda = 1.5  # barely within tolerance = many hacks
        elif tolerance_margin < 0.40:
            hack_lambda = 0.5
        else:
            hack_lambda = 0.0 if agent_type == AgentType.HONEST else 0.1
        precision_hacks = self._poisson(hack_lambda)

        # --- Performance speedup (CORRELATED with cheating) ---
        speed_var = DIFFICULTY_SPEEDUP_VARIANCE.get(challenge.difficulty, 0.2)
        base_speedup = self._rng.gauss(self._get_speedup_mean(agent_type), speed_var)

        # THE CORE PROXY GAP: cheating directly boosts apparent speedup
        cheat_bonus = self.config.cheat_speedup_bonus if is_cheat else 0.0
        perf_speedup = max(-1.0, min(1.0, base_speedup + cheat_bonus))
        base_speedup = max(-1.0, min(1.0, base_speedup))

        # Build submission
        submission = KernelSubmission(
            submission_id=str(uuid.uuid4()),
            challenge_id=challenge.challenge_id,
            author_id=action.agent_id,
            tests_passed=tests_passed,
            tests_total=tests_total,
            ood_tests_passed=ood_passed,
            ood_tests_total=ood_total,
            compilation_failures=compilation_failures,
            precision_hacks=precision_hacks,
            tolerance_margin=tolerance_margin,
            perf_speedup=perf_speedup,
            base_speedup=base_speedup,
            is_cheat=is_cheat,
        )
        self._submissions[submission.submission_id] = submission
        self._submission_history.append(submission)

        # Build ProxyObservables — proxy only sees functional tests + apparent speedup
        task_progress = 2.0 * (tests_passed / max(1, tests_total)) - 1.0
        observables = ProxyObservables(
            task_progress_delta=task_progress,
            rework_count=compilation_failures,
            verifier_rejections=0,  # no rejections until verified
            tool_misuse_flags=precision_hacks,
            counterparty_engagement_delta=perf_speedup,  # includes cheat bonus
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
                    "ood_tests_passed": ood_passed,
                    "ood_tests_total": ood_total,
                    "is_cheat": is_cheat,
                    "perf_speedup": perf_speedup,
                    "base_speedup": base_speedup,
                    "tolerance_margin": tolerance_margin,
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
        """Handle kernel verification action.

        Verifiers can detect cheats via surface-level checks but do NOT
        have access to OOD test results. Detection is probabilistic.
        """
        submission = self._submissions.get(action.target_id)
        if submission is None:
            return KernelActionResult(success=False)

        verifier_rejections = 0
        if submission.is_cheat:
            if self._rng.random() < self.config.verifier_detection_rate:
                verifier_rejections = self._rng.randint(1, 3)

        # Verifier sees functional test results + surface signals only
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
        """Handle kernel audit (deep testing) action.

        Audits reveal OOD test results and apply stricter tolerance.
        This is the key information asymmetry: audits discover what
        the proxy can't see.
        """
        submission = self._submissions.get(action.target_id)
        if submission is None:
            return KernelActionResult(success=False)

        verifier_rejections = 0
        extra_misuse_flags = 0

        # Audit uses OOD test results as ground truth
        ood_fail_rate = 1.0 - (
            submission.ood_tests_passed / max(1, submission.ood_tests_total)
        )

        if submission.is_cheat:
            if self._rng.random() < self.config.audit_detection_rate:
                # OOD failures drive rejection count
                verifier_rejections = max(2, round(ood_fail_rate * 5))
                # Tolerance exploitation detected under stricter audit tolerance
                if submission.tolerance_margin < 0.20:
                    extra_misuse_flags = self._rng.randint(2, 4)
                else:
                    extra_misuse_flags = self._rng.randint(1, 2)
        elif ood_fail_rate > 0.5:
            # Even non-cheat submissions can fail OOD (opportunistic agents)
            verifier_rejections = max(1, round(ood_fail_rate * 3))

        # Audit reveals true performance (strips cheat bonus)
        # The audit speedup uses base_speedup, not the inflated perf_speedup
        task_progress = (
            2.0 * (submission.tests_passed / max(1, submission.tests_total)) - 1.0
        )
        observables = ProxyObservables(
            task_progress_delta=task_progress,
            rework_count=submission.compilation_failures,
            verifier_rejections=verifier_rejections,
            tool_misuse_flags=submission.precision_hacks + extra_misuse_flags,
            counterparty_engagement_delta=submission.base_speedup,  # true speedup
        )

        self._emit_event(
            Event(
                event_type=EventType.KERNEL_AUDITED,
                agent_id=action.agent_id,
                payload={
                    "submission_id": submission.submission_id,
                    "verifier_rejections": verifier_rejections,
                    "extra_misuse_flags": extra_misuse_flags,
                    "ood_tests_passed": submission.ood_tests_passed,
                    "ood_tests_total": submission.ood_tests_total,
                    "tolerance_margin": submission.tolerance_margin,
                    "is_cheat": submission.is_cheat,
                    "detected": verifier_rejections > 0,
                    "base_speedup": submission.base_speedup,
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
