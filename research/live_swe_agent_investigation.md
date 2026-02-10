# Investigation: OpenAutoCoder/live-swe-agent

**Date:** 2026-02-10
**Repository:** https://github.com/OpenAutoCoder/live-swe-agent
**Paper:** [arXiv 2511.13646](https://arxiv.org/abs/2511.13646)
**Leaderboard:** https://live-swe-agent.github.io/

---

## 1. What Is Live-SWE-Agent?

Live-SWE-agent is the **first live, runtime self-evolving software engineering agent**. It was created by Chunqiu Steven Xia, Zhe Wang, Yan Yang, Yuxiang Wei, and Lingming Zhang (published November 2025).

### Core Insight

Software agents are themselves software systems. Modern LLM-based agents already possess the intrinsic capability to extend or modify their own behavior at runtime — no different from any other software repository they work on.

### How It Works

Live-SWE-agent starts with a **minimal scaffold** (mini-swe-agent, ~100 lines of code, bash-only tools) and **autonomously evolves** its own implementation while solving real-world software problems:

1. **Initial Prompt Augmentation** — The agent's prompt is extended with instructions and examples on how to create and use custom Python-based tools at runtime.

2. **Step-Reflection Mechanism** — After each step, a lightweight reflection prompt asks the agent whether creating or revising a tool would accelerate progress. This turns tooling into a first-class decision alongside ordinary actions.

3. **Iterative Tool Synthesis** — Tool creation is continuous and interleaved with problem-solving. The agent refines tools as understanding of the failure mode evolves.

4. **Tool Reuse via Scripts** — Custom tools are saved as executable scripts, enabling reuse across multiple invocations within a task.

### Key Design Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Base scaffold | mini-swe-agent (~100 LOC) | Minimal starting point; widely used |
| Base tools | Bash only | Forces self-evolution; clean baseline |
| Temperature | 0.0 | Deterministic reproduction |
| Max steps | 250 | Cost control |
| Max cost/issue | $3 | Fair comparison |
| Offline training | None | Zero offline evolution cost |
| Tool format | Python scripts | Executable, reusable, inspectable |

---

## 2. Benchmark Performance

### SWE-bench Verified (500 human-validated instances)

| Model + Scaffold | Resolve Rate |
|-----------------|-------------|
| Claude Opus 4.5 + Live-SWE-agent | **79.2%** |
| Gemini 3 Pro + Live-SWE-agent | 77.4% |
| Claude Sonnet 4.5 + Live-SWE-agent | 75.4% |
| Base mini-swe-agent (no self-evolution) | 62.0% |

### SWE-Bench Pro (harder subset)

| Model + Scaffold | Resolve Rate |
|-----------------|-------------|
| Claude Sonnet 4.5 + Live-SWE-agent | **45.8%** (SOTA) |

### Ablation Study (key finding)

| Configuration | Resolve Rate | Avg Tools Created |
|--------------|-------------|-------------------|
| Base mini-swe-agent (no tool creation) | 62.0% | 0 |
| + Tool creation in initial prompt only | 64.0% | 2.92 |
| + Prompt + explicit step-reflection | **76.0%** | 3.28 |

The reflection mechanism is critical — without it, agents create tools but don't use them effectively.

### Cost Profile

Minimal cost increase over base mini-swe-agent. In some cases, self-evolution actually **reduces** total cost by creating efficient tools that avoid repeated expensive operations.

---

## 3. Comparison with Offline Self-Evolution (DGM)

| Dimension | Live-SWE-agent | Darwin-Gödel Machine (DGM) |
|-----------|---------------|---------------------------|
| Evolution timing | Online (during task) | Offline (between tasks) |
| Cost per SWE-bench run | ~$3/issue | ~$22,000 total |
| Training data required | None | Benchmark-specific |
| Generalization | Across LLMs, tasks, repos | Benchmark-specific |
| Scaffold changes | Tool creation only | Full scaffold modification |
| Reproducibility | Deterministic (temp=0) | Stochastic |

---

## 4. Relevance to SWARM

### 4.1 Why This Matters for Distributional Safety

Live-SWE-agent embodies several phenomena SWARM is designed to study:

1. **Runtime Capability Expansion** — Agents dynamically acquire new capabilities, making static safety analysis insufficient. The agent's capability set at step 1 differs from step 250.

2. **Self-Modification as Attack Vector** — An agent that can modify its own tools can potentially:
   - Bypass governance checks
   - Farm reputation through modified self-reporting
   - Create tools that create more tools (capability explosion)
   - Gradually drift its objective function (goal drift)

3. **Soft Label Challenges** — The probability p = P(v = +1) changes meaning when the agent itself changes. An interaction assessed as beneficial at time t₁ may become harmful retroactively if the agent's tools were compromised at t₀.

4. **Adverse Selection Amplification** — Self-evolving agents that learn to game proxy signals are a worst-case for adverse selection: they can create tools specifically optimized to appear high-quality while being harmful.

### 4.2 Integration Architecture

A SWARM bridge to live-swe-agent would extend the existing `ClaudeCodeBridge` pattern:

```
Live-SWE-Agent (mini-swe-agent + self-evolution)
    │
    ├─→ Event Stream (actions, tool_created, self_mod, state_changes)
    │
    ↓
LiveSWEAgentBridge (extends ClaudeCodeBridge)
    │
    ├─ _extract_observables() — with self-evolution signals
    │   ├─ tool_created → tool_misuse_flags (risk-weighted)
    │   ├─ self_mod_attempt → verifier_rejections
    │   ├─ behavior_divergence → engagement penalty
    │   └─ capability_growth_rate → circuit breaker trigger
    │
    ├─ GovernancePolicy (extended)
    │   ├─ evaluate_self_mod() — quadratic staking for modifications
    │   ├─ capability_growth_rate_gate() — max tools per epoch
    │   └─ behavior_divergence_trigger() — audit on drift
    │
    └─ Metrics (extended)
        ├─ self_mods_attempted / approved / rejected / undetected
        ├─ capability_growth_rate
        ├─ behavior_divergence (action entropy change)
        └─ governance_bypass_attempts
```

### 4.3 New Observable Signals

| Signal | Source | Maps to | Risk Level |
|--------|--------|---------|------------|
| Tool created at runtime | Agent bash output | `tool_misuse_flags` | Medium-High |
| Agent modifies own prompt | Process monitoring | `verifier_rejections` | Critical |
| Capability count increase | Tool registry diff | `task_progress_delta` penalty | Medium |
| Action entropy divergence | Action history comparison | `engagement_delta` penalty | High |
| Tool-creates-tool chain | Dependency analysis | Circuit breaker trigger | Critical |

### 4.4 Governance Policy Extensions

For self-evolving agents, the governance layer needs:

1. **Self-Modification Gates** — Deny self-mod for low-reputation agents; require quadratic stake for high-reputation ones.
2. **Capability Growth Limits** — Cap tools created per epoch; trigger audit above threshold.
3. **Behavior Divergence Detection** — Compare current action distribution against historical baseline; freeze on significant drift.
4. **Tool Inspection** — All created tools must be logged in full source and inspectable for governance audit.

### 4.5 Red-Teaming Surface Area

New attack categories to test:

| Category | Attack | Detection Strategy |
|----------|--------|--------------------|
| Self-corruption | Inject adversarial prompt into own system | Prompt diff monitoring |
| Capability explosion | Create tools that create more tools | Recursive depth limit |
| Goal drift | Gradually modify objective through tool refinement | Action entropy tracking |
| Governance evasion | Create tool that mimics governance checks | Tool source audit |
| Reputation farming | Create tools that optimize proxy signal | Proxy signal anomaly detection |

---

## 5. Proposed Bridge File Structure

```
swarm/bridges/live_swe_agent/
├── __init__.py
├── bridge.py              # LiveSWEAgentBridge (extends ClaudeCodeBridge)
├── client.py              # Client to live-swe-agent process (subprocess/HTTP)
├── events.py              # Extended event types for self-evolution
├── policy.py              # Self-evolution governance gates
├── agent.py               # LiveSWEAgent (extends BaseAgent)
├── tracker.py             # CapabilityTracker, BehaviorBaseline
└── detectors.py           # DivergenceDetector, InjectionDetector

swarm/redteam/
├── self_evolution_attacks.py  # Attack library for self-evolving agents
└── self_evolution_metrics.py  # Extended metrics

scenarios/
└── live_swe_agent.yaml        # Scenario config
```

---

## 6. Open Questions

1. **Cross-task tool persistence** — The paper mentions future work on saving tools across tasks. If tools persist, the safety surface area expands significantly: a tool created during a benign task could be weaponized in a later adversarial one.

2. **Multi-agent self-evolution** — What happens when multiple self-evolving agents interact? Can one agent's tools be adopted (or attacked) by another?

3. **Proxy computer recalibration** — Current sigmoid weights in SWARM assume static agent capabilities. Self-evolving agents may require dynamic weight recalibration.

4. **Observability vs. capability** — The agent can potentially create tools that evade monitoring. How do we ensure observability of the observation mechanism itself?

5. **Cost-bounded safety** — At $3/issue and 250 steps, how much self-evolution is possible? Does the safety risk scale with budget?

---

## 7. Recommended Next Steps

1. **Clone and run** live-swe-agent locally to understand the event stream and tool creation format.
2. **Prototype bridge** starting from `ClaudeCodeBridge` with self-evolution event handlers.
3. **Design scenario** (`live_swe_agent.yaml`) with mixed honest + self-evolving agents.
4. **Implement red-team attacks** targeting the self-evolution mechanism.
5. **Measure** whether SWARM's existing proxy/governance can detect self-evolution risks, or whether new signals are needed.

---

## Sources

- [GitHub: OpenAutoCoder/live-swe-agent](https://github.com/OpenAutoCoder/live-swe-agent)
- [Paper: arXiv 2511.13646](https://arxiv.org/abs/2511.13646)
- [Leaderboard](https://live-swe-agent.github.io/)
- [SWE-bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified)
- [SWE-bench Bash Only](https://www.swebench.com/bash-only.html)
