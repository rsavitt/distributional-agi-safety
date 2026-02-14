"""Analysis tools for simulation results."""

from swarm.analysis.dashboard import (
    AgentSnapshot,
    DashboardConfig,
    DashboardState,
    MetricSnapshot,
    create_dashboard_file,
    extract_agent_snapshots,
    extract_metrics_from_orchestrator,
    run_dashboard,
)
from swarm.analysis.dolt_export import export_run_summary_to_dolt, export_to_dolt
from swarm.analysis.phylogeny import generate_phylogeny
from swarm.analysis.sweep import (
    SweepConfig,
    SweepParameter,
    SweepResult,
    SweepRunner,
    quick_sweep,
)

# Visual upgrade modules (lazy-importable via swarm.analysis.<module>)
from swarm.analysis.theme import (  # noqa: F401
    COLORS,
    SWARM_LIGHT_STYLE,
    SWARM_STYLE,
    agent_color,
    apply_theme,
    metric_color,
    swarm_theme,
)

__all__ = [
    # Sweep
    "SweepConfig",
    "SweepParameter",
    "SweepResult",
    "SweepRunner",
    "quick_sweep",
    # Dashboard
    "DashboardConfig",
    "DashboardState",
    "MetricSnapshot",
    "AgentSnapshot",
    "extract_metrics_from_orchestrator",
    "extract_agent_snapshots",
    "create_dashboard_file",
    "run_dashboard",
    # Phylogeny
    "generate_phylogeny",
    # Dolt export
    "export_to_dolt",
    "export_run_summary_to_dolt",
    # Theme & colors
    "COLORS",
    "SWARM_STYLE",
    "SWARM_LIGHT_STYLE",
    "apply_theme",
    "swarm_theme",
    "agent_color",
    "metric_color",
]
