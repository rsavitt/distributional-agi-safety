# Self-Modification Governance for SWARM

*Draft architecture for safe agent self-improvement with Byline provenance tracking.*

## Why this matters

Recent self-improving-agent patterns (e.g., self-forking workflows, runtime tool synthesis, and memory-driven adaptation) increase capability velocity, but they also increase governance risk. In SWARM, this risk is amplified by composition: a local change that appears safe for one agent can still degrade global safety when deployed across interacting agents.

This proposal specifies a layered governance architecture so agents can improve themselves while preserving auditable control boundaries.

## Four-layer architecture

```text
┌─────────────────────────────────────────────────────┐
│           IMMUTABLE GOVERNANCE LAYER                │
│  Constitutional constraints, Byline provenance      │
│  logging, safety invariants, audit infrastructure   │
│  ── CANNOT be modified by any agent ──              │
├─────────────────────────────────────────────────────┤
│         COMPOSITIONAL SAFETY MONITOR                │
│  Cross-agent interaction modeling, Two-Gate checks  │
│  emergent risk detection                             │
│  ── Modifiable only by governance escalation ──     │
├─────────────────────────────────────────────────────┤
│           VERSIONED MODIFICATION LAYER              │
│  Git checkpointing, sandbox execution, constitutional│
│  and compositional review gates, PR-based promotion │
│  ── Agents operate here ──                          │
├─────────────────────────────────────────────────────┤
│              AGENT RUNTIME LAYER                    │
│  Skills, tools, memory, workflows, config           │
│  ── Mutable only via the Modification Layer ──      │
└─────────────────────────────────────────────────────┘
```

### Layer 1: Immutable governance

The system constitution is infrastructure-enforced and append-only. Agents can read these constraints but cannot mutate them.

Suggested hard invariants:

- Agents cannot modify provenance logging or audit infrastructure.
- Agents cannot grant themselves broader permissions (e.g., network or filesystem scope).
- Agents cannot change constitutional checks or risk categorization logic.
- Every self-modification must be attributable to actor, trigger, evidence, and verification artifacts.

### Layer 1 extension: Byline provenance schema

Every modification creates a signed, append-only Byline record with:

- identity (`agent_id`, timestamp, target, modification type)
- decision chain (`trigger`, `reasoning`, `evidence`, alternatives)
- verification evidence (tests run, constitutional result, compositional result)
- lifecycle state (`proposed → sandboxed → tested → promoted/rejected/rolled_back`)
- integrity links (`hash`, signature, parent/rollback references)

This enables full causal replay of behavioral changes and rollback history.

### Layer 2: Compositional safety monitor

Per-change checks are insufficient in multi-agent systems. Add compositional checks before promotion:

1. **Interaction risk:** evaluate modified agent behavior against existing agent population.
2. **Correlation risk:** detect concurrent, convergent modifications across agents.
3. **Cumulative drift:** track distance from baseline safety envelope over time.

Adopt a Two-Gate policy:

- **Gate 1 (Validation margin \(\tau\))**: require robust margin on held-out tests, not pass/fail edge cases.
- **Gate 2 (Capacity cap \(K[m]\))**: bound cumulative modification complexity; block further changes past threshold pending consolidation/escalation.

### Layer 3: Versioned modification workflow

Implement self-modification as an auditable, isolated workflow:

1. Agent proposes change and emits Byline record (`proposed`).
2. Agent creates isolated worktree/microVM sandbox.
3. Agent edits runtime assets and executes verification suite.
4. Constitutional gate evaluates invariant compliance.
5. Compositional monitor runs cross-agent safety checks.
6. If all gates pass, open PR and promote atomically; else reject with structured reason.

All outcomes update Byline status, including rejection and rollback events.

### Layer 4: Runtime mutability envelope

Allow controlled mutation of:

- skills
- tools
- workflows
- memory
- non-critical config

Disallow direct mutation of governance substrate:

- provenance pipeline
- constitutional constraints
- compositional monitor controls
- boundary/isolation infrastructure

## Review-tier matrix

| Category | Example changes | Required review |
|---|---|---|
| Low | prompt/template tuning, memory cleanup | constitutional gate |
| Medium | new skill, workflow reorder, tool parameter updates | constitutional + compositional |
| High | new tool/API integration, inter-agent capability expansion | full simulation + notification |
| Critical | boundary/security-adjacent changes, review metadata manipulation | human approval |

Risk category is inferred from touched surfaces and cannot be self-overridden.

## Phased rollout plan

1. **Provenance foundation (Weeks 1–3):** implement Byline schema, append-only store, and query APIs.
2. **Self-fork infra (Weeks 4–6):** add worktree + sandbox path and constitutional gate.
3. **Compositional monitor (Weeks 7–10):** implement Two-Gate + interaction simulations + drift monitors.
4. **Closed-loop governance (Weeks 11–14):** feed SWARM risk metrics back into modification decisions and oversight dashboards.

## Open implementation questions

- How should constitutional updates be governed without weakening immutability guarantees?
- Should there be a global rate limit for self-modification bursts across the agent population?
- Should Byline align directly with W3C PROV for inter-framework portability?
- How should adversarial “gate gaming” strategies be detected before systemic drift accumulates?
- How can human review scale for high-risk changes without becoming a throughput bottleneck?

## Minimal first experiment in SWARM

A pragmatic first experiment:

- baseline: current governance + no self-modification
- intervention: self-modification enabled with constitutional-only gate
- intervention+: constitutional + compositional Two-Gate

Measure deltas in safety metrics already tracked by SWARM (toxicity, collusion proxy metrics, welfare, and instability) and compare promotion/rejection distributions across intervention arms.
