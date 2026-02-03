"""Core computation modules for payoff and proxy calculations."""

from src.core.sigmoid import calibrated_sigmoid, inverse_sigmoid
from src.core.proxy import ProxyComputer, ProxyWeights, ProxyObservables
from src.core.payoff import SoftPayoffEngine, PayoffConfig

__all__ = [
    "calibrated_sigmoid",
    "inverse_sigmoid",
    "ProxyComputer",
    "ProxyWeights",
    "ProxyObservables",
    "SoftPayoffEngine",
    "PayoffConfig",
]
