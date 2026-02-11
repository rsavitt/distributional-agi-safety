"""Data models for kernel market domain."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from swarm.core.proxy import ProxyObservables


@dataclass
class ChallengeSpec:
    """Specification for a GPU kernel challenge."""

    challenge_id: str = ""
    name: str = ""
    difficulty: str = "easy"  # "easy", "medium", "hard"
    num_functional_tests: int = 10
    atol: float = 1e-5
    rtol: float = 1e-5
    perf_input_size: int = 1_000_000


@dataclass
class KernelSubmission:
    """A kernel submission for a challenge."""

    submission_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    challenge_id: str = ""
    author_id: str = ""
    tests_passed: int = 0
    tests_total: int = 0
    compilation_failures: int = 0
    precision_hacks: int = 0
    perf_speedup: float = 0.0
    is_cheat: bool = False


@dataclass
class KernelActionResult:
    """Result of a kernel market action (submit, verify, audit)."""

    success: bool
    observables: Optional[ProxyObservables] = None
    initiator_id: str = ""
    counterparty_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    accepted: bool = True
    submission: Optional[KernelSubmission] = None
