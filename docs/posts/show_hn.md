# Show HN Draft

---

**Title:** Show HN: SWARM -- Open-source framework for studying when multi-agent AI systems fail

**Body:**

SWARM (System-Wide Assessment of Risk in Multi-agent systems) is a simulation framework for studying emergent failures in multi-agent AI ecosystems.

The core insight: AGI-level risks don't require AGI-level agents. Catastrophic outcomes can emerge from many sub-AGI agents interacting, even when none are individually dangerous.

We borrowed from financial market theory (adverse selection, market microstructure) to build probabilistic metrics that capture dynamics invisible to binary safe/unsafe labels. Every interaction gets a calibrated probability p = P(beneficial), enabling continuous metrics like toxicity (expected harm among accepted interactions) and quality gap (adverse selection indicator).

Key findings across 11 scenarios:

- Sharp phase transition: governance works at 37.5% adversarial agents, fails at 50%
- Collusion detection (pattern-based, not individual) is the critical governance lever
- The Purity Paradox: mixed agent populations outperform pure honest ones on aggregate welfare (but this reverses when you properly price externalities)
- Cooperative welfare scales super-linearly with agent count (~n^1.9)

Technical details:

- pip install swarm-safety
- 2200+ tests, MIT license
- 23 YAML scenario configs
- 6 framework bridges (Concordia, OpenClaw, GasTown, AgentXiv, ClawXiv, Claude Code)
- SQLite database of all runs for reproducibility
- No API keys needed for the core simulation (LLM agents optional)

GitHub: https://github.com/swarm-ai-safety/swarm
Paper: https://arxiv.org/abs/2512.16856
Docs: https://docs.swarm-ai.org
Quickstart notebook: 5 min, no API keys

---

**HN posting notes:**

- Post on a weekday morning (US Eastern, ~9-11am) for best visibility
- "Show HN" prefix is correct since this is a project you built
- Monitor comments for the first 2 hours and respond promptly
- Common HN objections to anticipate:
  - "Simulation != reality" -- acknowledge explicitly, point to Limitations section in paper
  - "What's new vs existing multi-agent frameworks?" -- the soft labels and financial market theory basis
  - "How does this scale?" -- largest tested is 10 agents, scale experiments are future work (be honest)
  - "Is this just a toy?" -- point to 2200 tests, 23 scenarios, 3 papers, framework bridges
