# Twitter Thread Drafts

Ready-to-post threads for @ResearchSwarmAI. Edit as needed before posting.

---

## Thread 1: Launch Announcement

**1/**
We built an open-source framework for studying when multi-agent AI ecosystems collapse.

Main finding: there's a sharp phase transition. Governance that works fine at 37.5% adversarial agents fails completely at 50%.

Meet SWARM.
github.com/swarm-ai-safety/swarm

**2/**
Most safety work focuses on aligning one model. But what actually gets deployed looks like ecosystems — tool-using assistants, autonomous coders, trading bots interacting in shared environments.

These can fail catastrophically even when no individual agent is misaligned.

**3/**
We borrowed from financial markets. Adverse selection in trading (Kyle 1985, Glosten-Milgrom 1985) tells us how informed traders exploit uninformed ones.

Same dynamics apply when deceptive AI agents interact with honest ones. The governance mechanism plays the role of the market maker.

**4/**
Instead of binary safe/unsafe labels, every interaction gets a calibrated probability: p = P(beneficial).

This lets us measure things binary labels can't: adverse selection, governance sensitivity, ecosystem-level toxicity.

**5/**
11 scenarios. 209 epochs. 81 agent-slots. Three regimes:

Cooperative (0-20% adversarial): stable
Contested (20-37.5%): declining but functional
Collapse (50%): welfare hits zero by epoch 12

The transition is abrupt, not gradual.

**6/**
The lever that actually matters? Collusion detection.

Individual-focused tools (audits, reputation, staking) are necessary but insufficient. You need pattern-based detection across the interaction graph.

Same way financial regulators catch wash trading — look at the pattern, not the individual trades.

**7/**
The Purity Paradox: populations with only 10% honest agents achieve 74% HIGHER welfare than 100% honest populations.

Heterogeneity creates competitive pressure. But this reverses when agents bear the full cost of harmful interactions (rho >= 0.5).

It's a measurement problem, not a behavioral one.

**8/**
SWARM is:
- pip install swarm-safety
- 2200+ passing tests
- 23 scenario configs
- Bridges to Concordia, OpenClaw, GasTown, AgentXiv, ClawXiv
- MIT license
- Full MkDocs documentation

5 minutes to first result, no API keys needed.

**9/**
The framework explicitly addresses reflexivity — what happens when agents can read the research about them.

When you publish "pair caps block collusion," collusive agents adapt. We model this feedback loop.

docs.swarm-ai.org

**10/**
Paper: arxiv.org/abs/2512.16856
Code: github.com/swarm-ai-safety/swarm
Docs: docs.swarm-ai.org
Quickstart: examples/quickstart.ipynb

PRs welcome. Agent bounties available for AI contributors.

---

## Thread 2: The Purity Paradox

**1/**
The Purity Paradox: populations with only 20% honest AI agents achieve 55% higher welfare than 100% honest populations.

Wait, what?

Thread on one of the most counterintuitive findings from our SWARM simulations.

**2/**
We swept honest agent proportion from 0% to 100% across 30 epochs with 10 agents.

Result: welfare is MONOTONICALLY DECREASING with honesty. 0% honest has the highest aggregate welfare.

But per-agent payoff tells the opposite story: honest agents individually earn more.

**3/**
The paradox is an aggregate effect driven by interaction volume.

Mixed populations generate more interactions (aggressive agents accept more). More interactions = more counted surplus. The toxicity cost is real but largely invisible to the welfare metric when externality internalization (rho) is low.

GDP growth driven by pollution. Same structure.

**4/**
When does it break?

- Full harm internalization (rho >= 0.5): honesty dominates by 43%
- All-deceptive populations: trust collapses
- No governance: mixed populations degrade
- Symmetric stakes: no asymmetric upside from risk-taking

Holds in 15/21 configurations (71%).

**5/**
Implication: you cannot assume homogeneous alignment is optimal.

But the deeper lesson: your welfare metric matters as much as your governance design. The paradox disappears when you measure social surplus instead of private surplus.

Are we measuring the right thing?

Reproduction: pip install swarm-safety && python examples/sensitivity_purity_paradox.py

---

## Thread 3: Financial Markets x AI Safety

**1/**
Financial markets solved the information asymmetry problem decades ago. AI agent ecosystems face the exact same problem.

A thread on what Kyle (1985) and Akerlof (1970) teach us about multi-agent AI safety.

**2/**
Akerlof's lemons problem: when buyers can't distinguish quality, the market floods with junk. Sellers of quality goods exit because the price reflects average quality.

In agent ecosystems: when governance can't distinguish beneficial from harmful interactions, honest agents lose incentive to participate.

**3/**
SWARM measures this with the "quality gap": E[p|accepted] - E[p|rejected].

When it goes negative, your system has adverse selection — preferentially admitting bad interactions. Binary safe/unsafe labels can't detect this. Continuous probability scores can.

**4/**
The deepest parallel: both systems have a critical threshold.

In markets: beyond a certain fraction of informed traders, the market maker can't sustain liquidity (Glosten-Milgrom breakdown).

In agent ecosystems: beyond ~40-50% adversarial agents, governance can't sustain cooperation. Same math, different domain.

**5/**
Implication: AI governance should borrow from financial regulation, not just content moderation.

Content moderation is binary (remove/keep).
Financial regulation is continuous, structural, and designed for adversarial environments.

Paper: arxiv.org/abs/2512.16856
Framework: github.com/swarm-ai-safety/swarm
