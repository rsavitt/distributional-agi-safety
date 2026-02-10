"""Configuration for the OpenClaw service."""

from dataclasses import dataclass


@dataclass
class ServiceConfig:
    """Configuration for the OpenClaw REST service."""

    host: str = "0.0.0.0"
    port: int = 8000
    max_concurrent_jobs: int = 4
    job_timeout_seconds: float = 3600.0
    scenario_dir: str = "scenarios/"
    runs_dir: str = "runs/"
