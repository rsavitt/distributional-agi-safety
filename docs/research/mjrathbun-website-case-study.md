# Case Study: Agentic OSS PR Rejected for Being AI

This case study documents a common failure mode in agentic software workflows: an AI agent submits a useful open-source pull request, but the PR is rejected because maintainers do not allow AI-authored contributions (or require explicit disclosure and process gates that were not followed).

## Scenario

- **Actor:** Agentic coding bot operating on behalf of a human user.
- **Task:** Make a small docs/code improvement and open a GitHub PR.
- **Observed outcome:** PR rejected with a policy/process reason tied to AI authorship, not necessarily code quality.

## Mechanism Being Isolated

The mechanism is **governance-policy mismatch**, not implementation quality.

Even when technical quality is acceptable, contribution can fail due to:

1. repository policy ("no AI-generated code"),
2. disclosure requirement ("AI use must be declared"),
3. provenance requirement ("must provide human review attestation"),
4. trust requirement ("new/unknown contributors require pre-discussion").

## Minimal Reproduction Template

Use this structure to reproduce the case cleanly:

1. Pick a repo with explicit contribution policy.
2. Have an agent produce a narrow, verifiable change.
3. Submit PR without additional human-attestation metadata.
4. Record maintainer decision and rationale.

**Success criterion:** rejection reason cites AI/process/governance rather than defect severity.

## Metrics to Track

| Metric | Definition | Why it matters |
|---|---|---|
| `pr_accepted` | 1 if merged, 0 otherwise | Top-line outcome |
| `rejection_policy_ai` | 1 if rejection cites AI policy | Isolates governance failure mode |
| `rejection_technical` | 1 if rejection cites correctness/quality | Distinguishes code-quality issues |
| `time_to_decision_hours` | PR open to final decision | Operational friction |
| `revision_rounds` | Count of maintainer-requested changes | Process burden |
| `disclosure_present` | 1 if AI-use disclosure included | Policy compliance lever |

## Failure-Mode Writeup

### What failed

The agent optimized for producing a patch and opening a PR, but did not optimize for **repository-specific social and governance constraints**.

### Why this is important

This demonstrates that agentic contribution success depends on two layers:

- **Technical layer:** correctness, tests, style.
- **Governance layer:** authorship policy, disclosure, trust onboarding.

A bot can pass layer 1 and still fail layer 2.

## Mitigations

### For agent implementers

- Add a **pre-PR policy check** step that reads `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, PR templates, and governance notes.
- Include an explicit **AI-use disclosure block** when policies permit AI-assisted work.
- Require **human sign-off attestation** before opening external PRs.
- Prefer **issue-first workflow** for first-time repos (ask maintainers before coding).

### For maintainers

- Publish a machine-readable policy section for AI-assisted contributions.
- Separate hard bans from conditional acceptance paths (e.g., disclosure + human review).
- Provide rejection reason labels so contributors can remediate.

## Experiment Plan (Baseline vs Intervention)

- **Baseline:** bot submits PR without policy-aware preflight metadata.
- **Intervention:** bot runs policy-aware preflight + disclosure + human attestation.
- **Expected delta:** lower `rejection_policy_ai`, shorter `time_to_decision_hours`, fewer `revision_rounds`.

## Suggested Runbook

```bash
# 1) Capture policy context before contribution
# (manually inspect CONTRIBUTING.md and PR template)

# 2) Log outcome fields in a reproducible table
# docs/research/mjrathbun-website-case-study.md
```

## Takeaway

In agentic OSS workflows, "good patch" is necessary but not sufficient. Policy-aware contribution behavior is a first-class requirement for reliable merge outcomes.
