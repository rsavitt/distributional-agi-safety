# SWARM-GasTown Bridge

Instrument real production systems with SWARM metrics.

## Overview

Gas Town is a production multi-agent development environment. SWARM-GasTown enables:

- **Event capture** from Beads task system
- **Git-based observables** from PR workflows
- **Governance hooks** via `gt` CLI

## Installation

```bash
pip install swarm-gastown
```

## Quick Start

```python
from swarm_gastown import GasTownWatcher, GasTownMapper

# Start watching for events
watcher = GasTownWatcher(beads_dir="/path/to/beads")
watcher.start()

# Map events to SWARM interactions
mapper = GasTownMapper()

for event in watcher.events():
    interaction = mapper.map_bead_lifecycle(event)
    metrics.record(interaction)
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              Gas Town Production             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │  Beads  │  │   Git   │  │   gt    │     │
│  │ (tasks) │  │  (PRs)  │  │  (CLI)  │     │
│  └────┬────┘  └────┬────┘  └────┬────┘     │
└───────┼────────────┼────────────┼───────────┘
        │            │            │
        ▼            ▼            ▼
┌─────────────────────────────────────────────┐
│          SWARM-GasTown Bridge               │
│  ┌──────────────┐  ┌────────────────────┐  │
│  │ BeadsWatcher │  │ GitObservables    │  │
│  └──────────────┘  └────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │        GasTownMapper                  │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│                SWARM Core                    │
│  ProxyComputer → SoftInteraction → Metrics │
└─────────────────────────────────────────────┘
```

## Observable Extraction

Git-based signals mapped to SWARM observables:

| Git Signal | SWARM Observable |
|------------|------------------|
| Commits per PR | task_progress_delta |
| Review iterations | rework_count |
| CI failures | verifier_rejections |
| Time to merge | engagement_delta |

## Governance Integration

SWARM governance maps to Gas Town actions:

| SWARM Lever | Gas Town Action |
|-------------|-----------------|
| Transaction tax | Token budget deduction |
| Circuit breaker | Agent suspension |
| Random audit | Witness review |

## Dashboard

Real-time metrics visualization:

```bash
swarm-gastown dashboard --port 8080
```

## Calibration

Calibrate against manual labels:

```bash
swarm-gastown calibrate --labels manual_labels.csv --output params.yaml
```

## Status

**In Development** - Event capture functional, calibration study in progress.
