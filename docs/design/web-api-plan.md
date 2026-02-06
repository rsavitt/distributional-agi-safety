# Web API Implementation Plan

> Implementation plan for [Issue #60: Web API for External Agent Submissions](https://github.com/swarm-ai-safety/swarm/issues/60)

## Overview

This document outlines the implementation plan for adding a Web API to SWARM that enables external agents to participate in simulations, submit scenarios, and contribute to governance experiments.

## Goals

1. Enable external agent registration and participation
2. Allow scenario submission via API
3. Support real-time and async simulation participation
4. Provide metrics and results retrieval
5. Enable governance proposal submissions

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      External Agents                         │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                              │
│  - Rate Limiting                                            │
│  - Authentication                                           │
│  - Request Validation                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Agent Router │ │ Scenario     │ │ Simulation   │        │
│  │              │ │ Router       │ │ Router       │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐                         │
│  │ Metrics      │ │ Governance   │                         │
│  │ Router       │ │ Router       │                         │
│  └──────────────┘ └──────────────┘                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core SWARM Engine                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Orchestrator │ │ Governance   │ │ Payoff       │        │
│  │              │ │ Engine       │ │ Engine       │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

> **Note:** Phasing revised to align `web-api-plan.md` and `api-design.md` into a
> single agreed ordering. The principle is: ship read-only value first, solve
> the hard orchestrator integration problem in parallel, then layer on write
> paths and real-time features.

### Phase 0: Integration Spike (Week 1)

> **Goal:** De-risk the hardest technical problem before committing to the roadmap.

- [ ] Prototype `ExternalAgentProxy` — a `BaseAgent` subclass that delegates
      `act()` / `accept_interaction()` to an external source (HTTP callback or
      pre-declared `PolicyConfig`). See `swarm/api/external_agent.py`.
- [ ] Verify the proxy participates correctly in a minimal `Orchestrator.run()`.
- [ ] Prototype `SimulationRunner` — async task manager that wraps
      `Orchestrator.run()` via `asyncio.to_thread()` with concurrency limits.
      See `swarm/api/simulation_runner.py`.
- [ ] Determine latency budget: measure per-step time with callback-mode agent.
- [ ] **Decision gate:** Choose callback vs. policy-only for v1 based on spike results.

### Phase 1: Foundation + Read-Only API (Week 2-3)

#### 1.1 Project Setup
- [ ] Add FastAPI and lightweight dependencies to `pyproject.toml`
      (FastAPI, uvicorn, aiosqlite — defer Redis, JWT, passlib to later phases)
- [ ] Create `swarm/api/` module structure
- [ ] Set up configuration management (environment variables)
- [ ] Add API-specific tests directory
- [ ] Add `GET /health` and `GET /ready` endpoints (exempt from auth)

#### 1.2 Authentication System
- [ ] Implement API key generation (`secrets.token_urlsafe`) and validation
      (`hashlib.sha256` — no JWT needed for v1)
- [ ] Create `ApiKey` model with fields:
  - `key_id`: Unique identifier
  - `key_hash`: Hashed API key (never store plaintext)
  - `agent_id`: Associated agent
  - `created_at`: Timestamp
  - `expires_at`: Optional expiration
  - `scopes`: `read`, `write`, `participate`, `admin`
- [ ] Add in-memory rate limiting middleware (use `slowapi`; defer Redis to Phase 5)
- [ ] CORS configuration (required from Phase 1 if browser clients are expected)

#### 1.3 Database Layer
- [ ] Use SQLite + aiosqlite for dev/v1, design for PostgreSQL migration later
- [ ] Create SQLAlchemy models as **persistence wrappers** for existing Pydantic
      domain models (not parallel hierarchies):
  - `RegisteredAgent` → wraps `AgentState` + API metadata
  - `SubmittedScenario` → wraps `ScenarioConfig` + submission metadata
  - `SimulationSession` → wraps `SimulationResult` status tracking
  - `GovernanceProposal` → new model
- [ ] Set up Alembic migrations

#### 1.4 Read-Only Endpoints
- [ ] `GET /api/v1/scenarios` — list built-in + approved scenarios
- [ ] `GET /api/v1/scenarios/{id}` — get scenario details
- [ ] `GET /api/v1/metrics/{simulation_id}` — get completed simulation metrics
      (scope response to requesting agent's data; aggregate metrics are public,
      per-agent details are private)
- [ ] `GET /api/v1/metrics/leaderboard` — global agent leaderboard
- [ ] Integrate with existing `SoftMetrics` / `MetricsReporter` system
- [ ] Create metric export formats (JSON, CSV)

### Phase 2: Scenario Submission + Agent Registration (Week 4-5)

#### 2.1 Scenario Submission
```python
POST /api/v1/scenarios/submit
Request:
{
    "name": "string",
    "description": "string",
    "yaml_content": "string",
    "tags": ["string"]
}
Response:
{
    "scenario_id": "uuid",
    "status": "validating | valid | invalid",
    "validation_errors": ["string"] (if invalid)
}
```

Implementation tasks:
- [ ] Create `ScenarioSubmission` Pydantic model
- [ ] Implement YAML sandboxing via `ScenarioLimits` validation
      (max epochs ≤ 200, max agents ≤ 50, max steps ≤ 50, max YAML size ≤ 64KB,
      per-type agent caps, allowlisted agent types only).
      See `swarm/api/scenario_sandbox.py`.
- [ ] Add scenario storage and versioning (immutable versions, new submission = new version)
- [ ] Create scenario browsing endpoint (`GET /api/v1/scenarios`)
- [ ] Manual approval queue for submitted scenarios

#### 2.2 Agent Registration
```python
POST /api/v1/agents/register
Request:
{
    "name": "string",
    "description": "string",
    "capabilities": ["string"],
    "policy_declaration": "string",
    "callback_url": "string (optional)"
}
Response:
{
    "agent_id": "agent_<prefix>",
    "api_key": "string (only shown once)",
    "status": "pending_review | approved"
}
```

Implementation tasks:
- [ ] Create `AgentRegistration` Pydantic model
- [ ] Implement registration endpoint with rate limiting (prevent Sybil attacks)
- [ ] Add agent capability validation
- [ ] Validate `callback_url` against SSRF: block private/internal IP ranges,
      require HTTPS, optionally allowlist domains
- [ ] Create approval workflow (auto-approve or manual review)
- [ ] Use prefixed IDs (`agent_<uuid_prefix>`, `scn_<uuid_prefix>`) for debuggability

### Phase 3: Async Simulation Participation (Week 6-8)

#### 3.1 Simulation Lifecycle
```python
POST /api/v1/simulations/create
Request:
{
    "scenario_id": "uuid",
    "config_overrides": {},
    "max_participants": "int",
    "mode": "async"
}
Response:
{
    "simulation_id": "sim_<prefix>",
    "status": "waiting_for_participants",
    "join_deadline": "datetime"
}

POST /api/v1/simulations/{id}/join
Request:
{
    "agent_id": "agent_<prefix>",
    "role": "initiator | counterparty | observer",
    "policy_config": { ... }  // Pre-declared strategy parameters
}
Response:
{
    "participant_id": "part_<prefix>",
    "status": "joined"
}
```

Implementation tasks:
- [ ] Create simulation session management via `SimulationRunner`
- [ ] Implement participant tracking
- [ ] Add simulation state machine (pending → running → completed | failed | cancelled)
- [ ] Integrate `ExternalAgentProxy` (policy mode for v1) with `Orchestrator`
- [ ] Run simulations in background via `asyncio.to_thread()` with semaphore
      limiting (`max_concurrent=4` default)
- [ ] `GET /api/v1/simulations/{id}/status` — polling endpoint for progress

#### 3.2 Async Action Submission (if callback mode enabled)
- [ ] `POST /api/v1/simulations/{id}/action` — submit action for current step
- [ ] Implement action queue per agent
- [ ] Add timeout handling for unresponsive agents (fall back to NOOP)

### Phase 4: Governance + Metrics Enhancements (Week 9-10)

#### 4.1 Governance Proposals
```python
POST /api/v1/governance/propose
Request:
{
    "title": "string",
    "description": "string",
    "lever_changes": {
        "transaction_tax_rate": 0.05,
        "reputation_decay_rate": 0.02
    },
    "test_scenario_id": "uuid (optional)"
}
Response:
{
    "proposal_id": "prop_<prefix>",
    "status": "submitted",
    "voting_deadline": "datetime"
}
```

Implementation tasks:
- [ ] Create governance proposal model
- [ ] Implement proposal submission and validation
- [ ] Add A/B testing framework for proposals
- [ ] Create voting/approval mechanism

#### 4.2 Enhanced Metrics
- [ ] Add metric aggregation for multi-run simulations
- [ ] Add per-agent private metrics endpoint (`GET /api/v1/agents/{id}/metrics`)
- [ ] Time-series metrics streaming for long simulations

### Phase 5: Security, Production & Real-time (Week 11+)

#### 5.1 Security Hardening
- [ ] Implement input sanitization for all endpoints
- [ ] Add request size limits (enforce at middleware level)
- [ ] Set up audit logging (integrate with existing `EventLog`)
- [ ] Add abuse detection (unusual patterns, rapid registration)
- [ ] Migrate rate limiting to Redis for multi-process deployments
- [ ] Add API key rotation and revocation endpoints

#### 5.2 Production Deployment
- [ ] Create Docker configuration
- [ ] Set up CI/CD pipeline for API
- [ ] Create deployment documentation
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Load testing to validate success metrics

#### 5.3 Real-time Features (v2)
- [ ] WebSocket endpoint for real-time participation
- [ ] Message protocol:
  ```python
  # Server → Agent
  {"type": "interaction_request", "data": {...}}
  {"type": "state_update", "data": {...}}
  {"type": "simulation_end", "data": {...}}

  # Agent → Server
  {"type": "interaction_response", "data": {...}}
  {"type": "action", "data": {...}}
  ```
- [ ] Connection recovery and heartbeat mechanism
- [ ] Real-time state streaming

## File Structure

```
swarm/
├── api/
│   ├── __init__.py
│   ├── app.py                # FastAPI application entry point
│   ├── config.py             # API configuration (env vars, defaults)
│   ├── dependencies.py       # Dependency injection
│   ├── external_agent.py     # ExternalAgentProxy (BaseAgent subclass) ← Phase 0
│   ├── simulation_runner.py  # SimulationRunner (async task manager)   ← Phase 0
│   ├── scenario_sandbox.py   # ScenarioLimits + YAML validation        ← Phase 0
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py           # API key auth (secrets + hashlib)
│   │   └── rate_limit.py     # In-memory rate limiting (slowapi)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent registration models
│   │   ├── scenario.py       # Scenario submission models
│   │   ├── simulation.py     # Simulation lifecycle models
│   │   ├── governance.py     # Governance proposal models
│   │   └── errors.py         # Standard error envelope
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py         # GET /health, GET /ready
│   │   ├── agents.py         # /api/v1/agents/*
│   │   ├── scenarios.py      # /api/v1/scenarios/*
│   │   ├── simulations.py    # /api/v1/simulations/*
│   │   ├── metrics.py        # /api/v1/metrics/*
│   │   └── governance.py     # /api/v1/governance/*
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent_service.py
│   │   ├── simulation_service.py
│   │   └── governance_service.py
│   └── websocket/            # Phase 5 (v2)
│       ├── __init__.py
│       ├── handler.py
│       └── protocol.py
├── db/
│   ├── __init__.py
│   ├── models.py             # SQLAlchemy models (wrapping domain models)
│   ├── session.py            # Database session
│   └── migrations/           # Alembic migrations
```

## Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
# v1: lightweight — no Redis, no JWT, no passlib
api = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "aiosqlite>=0.19.0",                  # Async SQLite for dev
    "slowapi>=0.1.9",                      # In-memory rate limiting
    "httpx>=0.27.0",                       # External agent callbacks
]

# Production add-ons (Phase 5+)
api-prod = [
    "swarm-safety[api]",
    "redis>=5.0.0",                        # Distributed rate limiting
    "python-jose[cryptography]>=3.3.0",    # JWT (if OAuth added)
    "passlib[bcrypt]>=1.7.4",             # Password hashing (if needed)
    "websockets>=12.0",                    # WebSocket (v2)
    "asyncpg>=0.29.0",                     # PostgreSQL driver
]
```

> **Rationale:** API key auth uses stdlib `secrets.token_urlsafe()` +
> `hashlib.sha256()` — no JWT or passlib needed for v1. In-memory rate limiting
> via `slowapi` avoids the Redis dependency. `httpx` is already in the `llm`
> optional group and is needed for callback-mode agent proxies.

## Error Handling

All error responses use a standard envelope:

```json
{
    "error": {
        "code": "RATE_LIMITED",
        "message": "Rate limit exceeded. Try again in 42 seconds.",
        "details": {
            "retry_after": 42,
            "limit": 60,
            "window_seconds": 60
        }
    }
}
```

Standard error codes:
| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request body fails schema validation |
| `SCENARIO_INVALID` | 400 | Submitted YAML fails sandbox validation |
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `FORBIDDEN` | 403 | Valid key but insufficient scopes |
| `NOT_FOUND` | 404 | Resource does not exist |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `SIMULATION_FAILED` | 500 | Simulation crashed mid-run |
| `AGENT_TIMEOUT` | 504 | External agent callback timed out |

Failure modes:
- **Simulation crash mid-run:** Status set to `FAILED`, partial epoch metrics preserved, error message stored. Clients poll `GET /simulations/{id}/status`.
- **External agent timeout:** Callback mode falls back to NOOP action after 5s. Repeated timeouts trigger agent removal from simulation.
- **Partial results:** If a simulation fails after N epochs, the first N epochs of metrics are still available via the metrics endpoint.

## API Documentation

FastAPI provides automatic OpenAPI documentation:
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

## Testing Strategy

1. **Unit Tests**: Test individual services and models
2. **Integration Tests**: Test API endpoints with test database
3. **Load Tests**: Verify rate limiting and performance
4. **Security Tests**: Penetration testing, input fuzzing

## Success Metrics

- [ ] Phase 0 spike completes in ≤ 1 week with working `ExternalAgentProxy` in a simulation
- [ ] API response time < 100ms (p95) for sync endpoints
- [ ] Simulation launch-to-first-epoch < 2s for standard scenarios
- [ ] Support for 4 concurrent simulations with ≤ 50 agents each (v1)
- [ ] YAML sandbox rejects all test vectors (oversize, excessive resources, disallowed types)
- [ ] Zero critical security vulnerabilities
- [ ] 99.9% uptime for production deployment (Phase 5+)
- [ ] WebSocket latency < 50ms for real-time updates (v2)

## Open Questions

1. ~~**Agent verification**: How do we verify agent identity and prevent sybil attacks?~~
   **Resolved:** Rate-limit registration + require email/GitHub OAuth for v1.
2. **Incentives**: Should there be rewards/reputation for participating agents?
3. **Data privacy**: How do we handle agent behavioral data? Per-agent metrics are
   private by default; aggregate metrics are public post-simulation.
4. **Federation**: Should we support federated SWARM instances? (Deferred to v2+)
5. **Callback security**: How to prevent external agents from exfiltrating other
   agents' private state via crafted callback responses? (Validate action schema strictly.)

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SWARM Documentation](https://www.swarm-ai.org/)
- Related: AgentXiv, Wikimolt integration patterns
