# Case Study: `mjrathbun-website` (crabby-rathbun.github.io)

This note frames `https://crabby-rathbun.github.io/mjrathbun-website/` as a lightweight case study for documenting and evaluating a personal/project website in a reproducible way.

## Goal

Evaluate the site as a communication artifact:

- clarity of narrative (what the project is, who it is for)
- credibility signals (about, work history, outcomes, contact paths)
- conversion readiness (clear next actions for visitors)
- maintainability (repeatable content updates, stable structure)

## Evaluation Rubric

Use a 1-5 scale for each category.

| Category | What good looks like | Evidence to collect |
|---|---|---|
| Positioning | Landing page communicates role/value in <10 seconds | Hero text, headline, subheadline |
| Proof of work | Concrete projects with outcomes and stack details | Case/project cards, links, metrics |
| Trust signals | Real identity, timeline consistency, contact channels | About section, resume/CV, social links |
| UX quality | Fast load, readable typography, mobile-safe layout | Lighthouse + manual responsive check |
| Conversion | Obvious CTA for hiring/collaboration | Contact form, email CTA, booking links |
| Ops hygiene | Easy update path and low breakage risk | Repo structure, deploy flow, content source |

## Suggested Case-Study Method

1. **Snapshot the current state**
   - capture homepage and one deep page screenshot
   - record Lighthouse scores (performance, accessibility, SEO)
2. **Trace visitor journeys**
   - recruiter journey: "Can I evaluate fit quickly?"
   - collaborator journey: "Can I find relevant prior work?"
3. **Score rubric and list top-3 bottlenecks**
   - prioritize by expected impact × implementation effort
4. **Ship one iteration**
   - update hero messaging, one project card, and CTA
5. **Re-measure after deploy**
   - compare rubric deltas and analytics baselines

## Example Improvement Backlog

- Tighten hero copy to role + domain + differentiator in one sentence.
- Add 2-3 quantified outcomes to featured projects.
- Standardize project cards: problem → approach → result → links.
- Add explicit CTA block ("Hire me", "View resume", "Contact").
- Add simple analytics goals (resume clicks, contact clicks, project deep-page views).

## Minimal Reproducible Template

For future personal-site case studies, keep this structure:

- **Context:** audience + objective
- **Baseline:** screenshots + speed/accessibility metrics
- **Intervention:** exact content/layout changes
- **Result:** before/after metric deltas
- **Follow-up:** next hypothesis to test

## Runbook Snippet

```bash
# 1) Capture baseline scores
lighthouse https://crabby-rathbun.github.io/mjrathbun-website/ --view

# 2) Keep a markdown log of changes and outcomes
# docs/research/mjrathbun-website-case-study.md
```

If you want, this can be expanded into a filled-out before/after report once runtime access to the target website is available in this environment.
