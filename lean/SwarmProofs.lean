/-
  SwarmProofs
  ===========
  Root import file for the SWARM formal verification library.

  Verified modules (all proofs machine-checked, no sorry):
  - Basic:       Core definitions (sigmoid, payoff, harm, break-even)
  - Sigmoid:     Range, symmetry, monotonicity, derivative
  - Payoff:      Bounds, break-even, zero-sum, internalization
  - Metrics:     Toxicity, quality gap, variance, Brier score
  - Composition: End-to-end pipeline safety

  Work-in-progress modules (not yet imported — need autoImplicit fixes
  and sorry elimination):
  - Collusion:   Collusion detection score bounds
  - Diversity:   Diversity-as-defense properties
  - Escrow:      Marketplace escrow conservation laws
  - EventLog:    Event log replay correctness
  - Governance:  Governance lever invariants
-/

import SwarmProofs.Basic
import SwarmProofs.Sigmoid
import SwarmProofs.Payoff
import SwarmProofs.Metrics
import SwarmProofs.Composition
