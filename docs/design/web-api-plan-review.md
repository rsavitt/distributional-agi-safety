# Review: Web API Implementation Plan

**Reviewing:** `docs/design/web-api-plan.md` and `docs/design/api-design.md`
**Branch:** `feature/web-api-plan` (PR #61, Issue #60)
**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-06

---

## Executive Summary

The plan proposes a FastAPI-based web API for external agent participation in SWARM simulations across 5 phases over 10 weeks. The documents are well-structured with clear endpoint specifications and a sensible phased rollout. However, there are significant gaps in how the API layer will integrate with the existing simulation core, an underspecified concurrency model, and several security concerns that should be resolved before implementation begins.

**Verdict:** Solid foundation, but needs revisions before implementation -- particularly around the orchestrator integration strategy, the async execution model, and the trust boundary between external agents and the simulation engine.

---

## Strengths

### 1. Good phased decomposition
The plan correctly prioritizes foundation (auth, DB) before features, and defers real-time WebSocket support to a later phase. The `api-design.md` document is even more conservative, pushing WebSocket to a future v2 and starting with read-only endpoints. This is the right instinct.

### 2. Endpoint design is clean and RESTful
The resource hierarchy (`/agents`, `/scenarios`, `/simulations`, `/metrics`, `/governance`) maps naturally to SWARM's domain model. The request/response schemas are concrete and use appropriate HTTP verbs. The versioned `/api/v1/` prefix is good practice.

### 3. Leverages existing Pydantic models
SWARM already uses Pydantic extensively (`SoftInteraction`, `AgentState`, `PayoffConfig`, `GovernanceConfig`, etc.), which will translate cleanly to FastAPI request/response schemas with minimal glue code.

### 4. Two complementary documents
Having both an implementation plan (`web-api-plan.md`) with task checklists and a design document (`api-design.md`) with API specs and security model is good practice. They serve different audiences.

---

## Critical Issues

### C1. Orchestrator integration is hand-waved

The plan says "Create simulation runner integration with `Orchestrator`" as a single checkbox item, but this is the hardest problem in the entire plan. The `Orchestrator` is a 1,680-line class that manages a tightly coupled simulation loop:

- `Orchestrator.run()` is synchronous and runs the full simulation to completion
- `Orchestrator.run_async()` exists but is also a run-to-completion coroutine
- Neither method supports injecting external agent decisions mid-simulation

For external agents to *participate* in simulations (not just submit scenarios and read results), you need one of:

1. **Turn-based adapter**: Pause the orchestrator at each step, publish state to a queue, wait for external agent actions, then resume. This requires refactoring the orchestrator's inner loop into a step-by-step generator or state machine.
2. **Callback injection**: Register external agents as `BaseAgent` subclasses whose `decide()` method makes an HTTP callback or reads from a queue. Simpler but adds latency per step.
3. **Pre-declared strategy**: External agents submit a policy (e.g., parameter vector or decision tree) upfront, and a local proxy agent executes it. No mid-simulation interaction needed.

The plan doesn't acknowledge this choice or its implications. **This is the biggest risk to the 10-week timeline.** Recommend adding a Phase 0 spike to prototype the orchestrator integration pattern before committing to the full plan.

### C2. Async execution model is undefined

When a user POSTs to `/simulations/create`, what happens? The plan implies the simulation runs server-side, but:

- **Who pays for compute?** A simulation with 100 epochs x 10 steps x 20 actions is non-trivial. The plan lists "100+ concurrent agents" as a success metric but has no resource budgeting.
- **How is the simulation scheduled?** Is it a background task (Celery, arq, asyncio task)? A separate worker process? The architecture diagram shows no task queue.
- **What about long-running simulations?** A simulation could take minutes. The API needs to return immediately and provide a polling endpoint or webhook. The async action endpoint (`POST /simulations/{id}/action`) implies this, but the execution model isn't specified.

The `api-design.md` mentions Redis for "cache, queue" in the architecture diagram but never specifies what it queues. Recommend explicitly defining the task execution architecture.

### C3. Conflicting phasing between the two documents

The two documents disagree on the order of implementation:

| Phase | `web-api-plan.md` | `api-design.md` |
|-------|-------------------|-----------------|
| 1-2 | Auth + DB, then Core endpoints | Read-only API (GET scenarios, GET metrics) |
| 3-4 | Real-time WebSocket, then Metrics/Governance | Scenario submission, then Agent registration |
| 5 | Security hardening | Async participation |

The `api-design.md` ordering is more pragmatic -- starting read-only lets you ship useful functionality while the hard orchestrator integration problem is solved. But the `web-api-plan.md` ordering (which is what the branch ships) front-loads the complex write paths. **These need to be reconciled into a single agreed phasing.**

### C4. No sandboxing design for scenario YAML

The plan allows external users to submit arbitrary YAML via `POST /scenarios/submit`. SWARM's scenario loader (`swarm/scenarios/loader.py`) builds orchestrator configs from YAML, which can specify:

- Agent counts and types (including `ADVERSARIAL`)
- Epoch/step counts (compute cost)
- Governance parameters
- Network configurations

Without validation, a malicious submission could:
- Request enormous simulations (resource exhaustion)
- Configure scenarios that crash the orchestrator
- Submit YAML with anchors/aliases that cause parser bombs

The plan mentions "YAML validation against schema" but doesn't define the schema or resource limits. The `api-design.md` mentions `resource_estimate` in the response but not how it's computed or enforced. Recommend defining a strict allowlist schema for submitted scenarios with hard caps on epochs, agents, and steps.

---

## Significant Issues

### S1. Authentication model is too simple

The plan uses API key authentication throughout, but:

- **Registration is unauthenticated**: `POST /agents/register` returns an API key without any identity verification. This means anyone can create unlimited agent identities (Sybil attack), which the "Open Questions" section acknowledges but doesn't resolve.
- **No key rotation mechanism**: If a key is compromised, there's no revocation or rotation API.
- **Scopes are vague**: The `api-design.md` defines scopes (`read`, `write`, `participate`, `admin`) but the `web-api-plan.md` just says "scopes: List of permitted operations" without defining them.
- **No OAuth/OIDC option**: For institutional users, API keys alone won't satisfy security requirements. Consider supporting OAuth2 client credentials flow.

### S2. Database schema is divorced from existing models

The plan proposes SQLAlchemy models (`RegisteredAgent`, `SubmittedScenario`, `SimulationSession`, `GovernanceProposal`) that are completely separate from SWARM's existing Pydantic models (`AgentState`, `SoftInteraction`, `GovernanceConfig`). This creates a mapping problem:

- How does a `RegisteredAgent` (DB) become an `AgentState` (simulation)?
- How does a `SubmittedScenario` (DB) become an `OrchestratorConfig`?
- Who maintains the mapping code? What happens when core models change?

Recommend designing the DB models as persistence layers for the existing domain models rather than parallel hierarchies.

### S3. The dependency list is heavy

The proposed dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `python-jose`, `passlib`, `redis`, `websockets`) add 8 new packages plus transitive dependencies to a project that currently has only 3 core dependencies (`numpy`, `pydantic`, `pandas`). This is a significant increase in surface area for a research tool.

Consider:
- Redis is overkill for v1. Use in-memory rate limiting (e.g., `slowapi` with local storage) until you actually need distributed state.
- `python-jose` + `passlib` can be replaced with stdlib `secrets` + `hashlib` for API key auth. JWT is unnecessary if you're not doing OAuth.
- SQLite via `aiosqlite` + raw SQL or a lighter ORM might be more appropriate than SQLAlchemy + Alembic for a research project.

### S4. No error handling or failure mode design

The plan specifies happy-path request/response schemas but doesn't address:

- What error format do endpoints return? (Recommend a standard error envelope with `error_code`, `message`, `details`.)
- What happens when a simulation crashes mid-run?
- What happens when an external agent times out during async participation?
- How are partial results handled?
- What's the retry policy for failed webhook callbacks?

### S5. Metrics endpoint exposes too much

`GET /api/v1/metrics/{simulation_id}` returns `per_agent_metrics` which could leak information about other agents' strategies. The `api-design.md` mentions "Data Isolation" (agents can only see their own state), but the metrics response schema returns all agents' results. These are contradictory. Either scope the response to the requesting agent's data, or clearly document that post-simulation metrics are public.

---

## Minor Issues

### M1. Inconsistent ID formats
`web-api-plan.md` uses bare UUIDs (`"agent_id": "uuid"`) while `api-design.md` uses prefixed IDs (`"agent_id": "agent_a1b2c3d4"`, `"scenario_id": "scn_x1y2z3"`). Prefixed IDs are better for debugging and log readability. Pick one convention.

### M2. Missing pagination
`GET /api/v1/scenarios` and the leaderboard endpoint don't specify pagination. For any list endpoint, define `limit`, `offset` (or cursor-based), and default/max page sizes.

### M3. No versioning strategy for scenarios
The plan mentions "scenario versioning" but doesn't specify how. Can a scenario be updated? Does updating create a new version? Can simulations reference specific versions?

### M4. Health check endpoint missing from `web-api-plan.md`
The `api-design.md` mentions `/health` is exempt from auth, but it's not in the task list. Add `GET /health` and `GET /ready` (for deployment orchestrators).

### M5. No CORS specification
The `web-api-plan.md` mentions CORS in Phase 5 but doesn't define the policy. If the API will be called from browser-based agent UIs, CORS needs to be configured from Phase 1.

### M6. The `callback_url` field enables SSRF
Agent registration accepts a `callback_url` that the server will presumably make requests to. This is a server-side request forgery (SSRF) vector. The server must validate callback URLs against an allowlist or at minimum block private/internal IP ranges.

---

## Recommendations

1. **Add a Phase 0 spike** (1 week): Prototype the orchestrator integration pattern. Build a minimal proof-of-concept where an external agent participates in a simulation via HTTP. This will de-risk the entire plan.

2. **Reconcile the two documents** into a single source of truth. The `api-design.md` phasing (read-only first) is more pragmatic; adopt it.

3. **Start with option 3 (pre-declared strategy)** for agent participation. External agents submit a policy configuration, and a local proxy agent executes it. This avoids the hard real-time integration problem and can be extended later.

4. **Define resource limits for scenarios** before accepting external YAML submissions. Hard caps on epochs (<=200), agents (<=50), steps_per_epoch (<=50).

5. **Use lightweight dependencies for v1**. Drop Redis, python-jose, and passlib. Use `secrets.token_urlsafe()` for API keys, `hashlib.sha256` for hashing, and in-memory rate limiting.

6. **Design the error envelope** before implementing endpoints. Standardize on a format like `{"error": {"code": "RATE_LIMITED", "message": "...", "retry_after": 60}}`.

7. **Add an agent identity verification step** for registration -- even a simple email verification or GitHub OAuth would prevent trivial Sybil attacks.

8. **Explicitly define the task execution model**. Recommend: `asyncio.create_task()` for short simulations (<30s), a proper task queue (arq or dramatiq) for longer ones, with a `GET /simulations/{id}/status` polling endpoint.

---

## Summary Table

| Category | Count | Items |
|----------|-------|-------|
| Critical | 4 | Orchestrator integration, async execution, conflicting phases, YAML sandboxing |
| Significant | 5 | Auth model, DB/model mismatch, heavy deps, error handling, metrics leakage |
| Minor | 6 | ID formats, pagination, versioning, health check, CORS, SSRF |

The plan is a reasonable starting point, but it underestimates the integration complexity with SWARM's existing simulation engine. The most important next step is the Phase 0 spike to validate that external agent participation is feasible within the current architecture before committing to the 10-week roadmap.
