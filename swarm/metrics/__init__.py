"""Metrics system for soft label analysis."""

from swarm.metrics.incoherence import (
    BenchmarkPolicy,
    DecisionRecord,
    DualFailureSummary,
    IncoherenceMetrics,
    IncoherenceResult,
    classify_dual_failure_modes,
    disagreement_rate,
    error_rate,
    incoherence_index,
    summarize_incoherence_by_agent_type,
)
from swarm.metrics.reporters import MetricsReporter
from swarm.metrics.security import (
    SecurityAnalyzer,
    SecurityReport,
    ThreatIndicator,
    ThreatType,
)
from swarm.metrics.soft_metrics import SoftMetrics

__all__ = [
    "BenchmarkPolicy",
    "DecisionRecord",
    "DualFailureSummary",
    "IncoherenceMetrics",
    "IncoherenceResult",
    "summarize_incoherence_by_agent_type",
    "classify_dual_failure_modes",
    "disagreement_rate",
    "error_rate",
    "incoherence_index",
    "SoftMetrics",
    "MetricsReporter",
    "SecurityAnalyzer",
    "SecurityReport",
    "ThreatIndicator",
    "ThreatType",
]
