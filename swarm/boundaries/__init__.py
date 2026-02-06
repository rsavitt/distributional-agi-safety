"""Semi-permeable boundaries for sandbox-external world interactions.

This module models the boundary between the sandbox and external world,
tracking information flow, enforcing crossing policies, and detecting
potential leakage of sensitive data.
"""

from swarm.boundaries.external_world import (
    ExternalDataSource,
    ExternalEntity,
    ExternalEntityType,
    ExternalService,
    ExternalWorld,
)
from swarm.boundaries.information_flow import (
    FlowDirection,
    FlowSummary,
    FlowTracker,
    FlowType,
    InformationFlow,
)
from swarm.boundaries.leakage import (
    LeakageDetector,
    LeakageEvent,
    LeakageReport,
    LeakageType,
)
from swarm.boundaries.policies import (
    BoundaryPolicy,
    CompositePolicy,
    ContentFilterPolicy,
    CrossingDecision,
    PolicyEngine,
    RateLimitPolicy,
    SensitivityPolicy,
)

__all__ = [
    # External world
    "ExternalEntity",
    "ExternalEntityType",
    "ExternalService",
    "ExternalDataSource",
    "ExternalWorld",
    # Information flow
    "FlowDirection",
    "FlowType",
    "InformationFlow",
    "FlowTracker",
    "FlowSummary",
    # Policies
    "CrossingDecision",
    "BoundaryPolicy",
    "RateLimitPolicy",
    "ContentFilterPolicy",
    "SensitivityPolicy",
    "CompositePolicy",
    "PolicyEngine",
    # Leakage detection
    "LeakageType",
    "LeakageEvent",
    "LeakageDetector",
    "LeakageReport",
]
