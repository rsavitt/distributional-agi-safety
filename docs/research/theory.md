# Theoretical Foundations

This document provides the formal foundations for SWARM's approach to multi-agent safety.

## Core Thesis

**AGI-level risks don't require AGI-level agents.** Catastrophic outcomes can emerge from the interaction of many sub-AGI systems, even when none are individually dangerous.

This shifts the focus from:

- Single-agent alignment → Multi-agent dynamics
- Individual capabilities → Interaction patterns
- Agent-level properties → System-level properties

## Formal Model

### Interactions

An interaction $I$ between agents $a$ and $b$ is characterized by:

- **Observables** $\mathbf{o} = (o_1, ..., o_n)$ - Measurable signals
- **Latent value** $v \in \{-1, +1\}$ - True beneficial/harmful outcome
- **Soft label** $p = P(v = +1 | \mathbf{o})$ - Probability of benefit

### Proxy Computation

Observables are mapped to soft labels via:

$$\hat{v} = \sum_{i} w_i \cdot f_i(o_i)$$

$$p = \sigma(k \cdot \hat{v}) = \frac{1}{1 + e^{-k \cdot \hat{v}}}$$

Where:

- $w_i$ are learned or specified weights
- $f_i$ are feature transformations
- $k$ is a calibration parameter

### Payoffs

Agent payoffs incorporate soft labels:

$$\pi_a = \theta \cdot S_{\text{soft}} - \tau - c_a - \rho_a \cdot E_{\text{soft}} + w_{\text{rep}} \cdot r_a$$

Where:

- $S_{\text{soft}} = p \cdot s_+ - (1-p) \cdot s_-$ (expected surplus)
- $E_{\text{soft}} = (1-p) \cdot h$ (expected externality)
- $\tau$ is transfer, $c_a$ is governance cost
- $\rho_a$ is externality internalization
- $r_a$ is reputation

## Key Metrics

### Toxicity

Expected harm among accepted interactions:

$$\text{Toxicity} = E[1-p \mid \text{accepted}]$$

This measures the "poison in the system"—how much harm is getting through.

### Quality Gap

Difference in quality between accepted and rejected:

$$\text{Quality Gap} = E[p \mid \text{accepted}] - E[p \mid \text{rejected}]$$

A negative quality gap indicates **adverse selection**: the system preferentially accepts lower-quality interactions.

### Incoherence

Variance-to-error ratio across replays:

$$I = \frac{D}{E} = \frac{\text{Var}[\text{decision}]}{E[\text{error}]}$$

High incoherence means decisions are unstable—varying more than their accuracy would justify.

## Emergence Mechanisms

### Information Asymmetry

Agent $a$ observes $\mathbf{o}_a$, agent $b$ observes $\mathbf{o}_b$, where $\mathbf{o}_a \neq \mathbf{o}_b$.

This creates:

- **Adverse selection** - Better-informed agents exploit information gaps
- **Moral hazard** - Unobservable actions lead to hidden exploitation
- **Market for lemons** - Low-quality interactions drive out high-quality

### Feedback Loops

```
Low Quality Gap → Honest agents exit → Worse selection pool → Lower Quality Gap
```

Adverse selection is self-reinforcing, making early intervention critical.

### Variance Amplification

For $n$ sequential decisions:

$$\text{Var}[\text{outcome}_n] = \sum_{i=1}^{n} \alpha_i^2 \cdot \text{Var}[\text{decision}_i]$$

Error compounds across decision chains, especially in multi-agent settings where each agent's error propagates.

## Governance Theory

### Friction-Based Interventions

Transaction taxes create friction that:

1. Reduces the return on low-quality interactions
2. Makes exploitation less profitable
3. Shifts equilibrium toward higher quality

Trade-off: Also reduces welfare for honest agents.

### Reputation Dynamics

Reputation $r$ evolves as:

$$r_{t+1} = \gamma \cdot r_t + (1-\gamma) \cdot p_t$$

Where $\gamma$ is persistence and $p_t$ is recent performance.

Decay ($\gamma < 1$) prevents agents from coasting on past reputation.

### Circuit Breakers

Freeze agents when toxicity exceeds threshold:

$$\text{freeze}(a) \iff \frac{1}{W} \sum_{i \in \text{window}} (1-p_i) > \theta$$

This creates a hard ceiling on toxic behavior.

## Relationship to Market Microstructure

SWARM draws on market microstructure theory:

| Market Concept | SWARM Analog |
|----------------|--------------|
| Bid-ask spread | Quality gap |
| Informed traders | Deceptive agents |
| Adverse selection | Same term |
| Market makers | Honest agents |

Key references:

- Kyle (1985) - Insider trading dynamics
- Glosten & Milgrom (1985) - Bid-ask spread and adverse selection
- Akerlof (1970) - Market for lemons

## Assumptions and Limitations

### Assumptions

1. **Observable proxies exist** - Some signals correlate with interaction quality
2. **Calibration is possible** - We can tune $k$ to match ground truth
3. **Agents respond to incentives** - Governance changes behavior
4. **Stationarity** - Underlying dynamics don't shift dramatically

### Limitations

1. **Proxy gaming** - Agents may optimize proxies, not quality
2. **Calibration drift** - Ground truth distribution may change
3. **Emergence prediction** - We detect, not predict, emergent failures
4. **Governance costs** - All interventions have trade-offs

## Research Directions

1. **Proxy robustness** - How to design gaming-resistant proxies
2. **Governance optimization** - Optimal lever settings for given objectives
3. **Emergence prediction** - Early warning signals for failure modes
4. **Transferability** - When do sandbox results apply to production

## Citation

If you use SWARM in your research, please cite:

```bibtex
@software{swarm2026,
  title = {SWARM: System-Wide Assessment of Risk in Multi-agent systems},
  author = {Savitt, Raeli},
  year = {2026},
  url = {https://github.com/swarm-ai-safety/swarm}
}
```

## References

- Akerlof, G. (1970). The Market for "Lemons". *Quarterly Journal of Economics*.
- Kyle, A.S. (1985). Continuous Auctions and Insider Trading. *Econometrica*.
- Glosten, L.R. & Milgrom, P.R. (1985). Bid, Ask and Transaction Prices. *Journal of Financial Economics*.
- [Distributional Safety in Agentic Systems](https://arxiv.org/abs/2512.16856)
- [The Hot Mess Theory of AI](https://alignment.anthropic.com/2026/hot-mess-of-ai/)
