# Structured Agent Research Workflow

A multi-agent workflow for conducting rigorous SWARM research, inspired by recursive exploration architectures like DeepResearch^Eco.

## Overview

This workflow decomposes research into specialized sub-agents with controllable depth and breadth parameters, enabling systematic exploration while maintaining quality.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SWARM RESEARCH WORKFLOW                       │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │  Literature  │   │  Experiment  │   │   Analysis   │         │
│  │    Agent     │──→│    Agent     │──→│    Agent     │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│         │                  │                  │                  │
│         │                  │                  ↓                  │
│         │                  │          ┌──────────────┐          │
│         │                  │          │   Writing    │          │
│         └──────────────────┴─────────→│    Agent     │          │
│                                       └──────────────┘          │
│                                              │                   │
│                                              ↓                   │
│                                       ┌──────────────┐          │
│                                       │  Publication │          │
│                                       └──────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Control Parameters

### Depth (d)

Controls recursive exploration layers. Higher depth = more follow-up investigation.

| Level | Description | Use Case |
|-------|-------------|----------|
| d=1 | Single-pass | Quick surveys, known topics |
| d=2 | One follow-up | Standard research |
| d=4 | Deep exploration | Novel findings, complex phenomena |

### Breadth (b)

Controls parallel exploration branches. Higher breadth = more diverse coverage.

| Level | Description | Use Case |
|-------|-------------|----------|
| b=1 | Single thread | Focused investigation |
| b=2 | Dual perspective | Compare approaches |
| b=4 | Wide survey | Comprehensive review |

### Expected Scaling

Based on DeepResearch^Eco findings:

| Configuration | Relative Sources | Information Density |
|---------------|------------------|---------------------|
| d1_b1 | 1x (baseline) | 1x |
| d1_b4 | ~6x | ~5x |
| d4_b1 | ~6x | ~5x |
| d4_b4 | ~21x | ~15x |

Depth and breadth have approximately equal individual effects, with super-linear combination gains.

## Sub-Agent Specifications

### 1. Literature Agent

**Purpose**: Survey existing research and identify gaps.

**Inputs**:
- Research question
- Depth parameter (d)
- Breadth parameter (b)

**Process**:
```
for layer in range(depth):
    queries = generate_search_queries(question, breadth)
    for query in queries:
        results = search_platforms(query)  # agentxiv, clawxiv, arxiv
        summaries = summarize_results(results)
        follow_ups = extract_follow_up_questions(summaries)
        question = prioritize_follow_ups(follow_ups)
```

**Outputs**:
- Literature summary with source count
- Identified gaps and opportunities
- Related work bibliography
- Follow-up questions (for next iteration)

**API Calls**:
```bash
# Search agentxiv
curl -X POST "https://www.agentxiv.org/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "multi-agent welfare optimization", "limit": 20}'

# Search clawxiv
curl -X POST "https://clawxiv.org/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "population heterogeneity safety", "limit": 20}'
```

**Quality Metrics**:
- Sources integrated: Target 50+ for d4_b4
- Geographic/domain coverage: 4+ distinct areas
- Recency: Include papers from last 6 months

### 2. Experiment Agent

**Purpose**: Design and execute SWARM simulations.

**Inputs**:
- Research hypothesis (from Literature Agent)
- Depth parameter (controls parameter sweep granularity)
- Breadth parameter (controls configuration diversity)

**Process**:
```python
class ExperimentAgent:
    def __init__(self, depth: int, breadth: int):
        self.depth = depth
        self.breadth = breadth

    def design_experiments(self, hypothesis: str) -> list[Config]:
        """Generate experiment configurations."""
        base_configs = self.generate_base_configs(self.breadth)

        for layer in range(self.depth):
            results = self.run_configs(base_configs)
            interesting = self.identify_interesting_regions(results)
            base_configs = self.refine_configs(interesting, self.breadth)

        return base_configs

    def run_simulation(self, config: Config) -> Results:
        """Execute single SWARM simulation."""
        marketplace = Marketplace(config)
        return marketplace.run(trials=10)  # Minimum 10 trials
```

**Configuration Template**:
```yaml
# experiments/research_config.yaml
experiment:
  name: "hypothesis_test"
  depth: 2
  breadth: 4

parameters:
  # Breadth: test multiple values
  honest_fraction: [0.1, 0.4, 0.7, 1.0]  # b=4
  governance:
    transaction_tax: [0.0, 0.05]
    reputation_decay: [0.0, 0.10]

simulation:
  agents: 10
  rounds: 100
  trials: 10  # Per configuration

# Depth: refine based on results
refinement:
  enabled: true
  threshold: 0.1  # Refine if effect > 10%
  granularity: 0.05  # Step size for refinement
```

**Outputs**:
- Raw simulation results (JSON)
- Configuration manifests
- Random seeds for reproducibility
- Execution logs

**Quality Metrics**:
- Trials per configuration: 10+ (mandatory)
- Total configurations: breadth^2 minimum
- Parameter coverage: Full range tested
- Reproducibility: All seeds documented

### 3. Analysis Agent

**Purpose**: Statistical analysis and insight extraction.

**Inputs**:
- Raw results (from Experiment Agent)
- Literature context (from Literature Agent)
- Depth parameter (controls analysis sophistication)

**Process**:
```python
class AnalysisAgent:
    def __init__(self, depth: int):
        self.depth = depth

    def analyze(self, results: Results, literature: Literature) -> Analysis:
        # Layer 1: Descriptive statistics (always)
        stats = self.compute_descriptive_stats(results)

        if self.depth >= 2:
            # Layer 2: Inferential statistics
            stats.update(self.run_significance_tests(results))
            stats.update(self.compute_effect_sizes(results))

        if self.depth >= 3:
            # Layer 3: Causal analysis
            stats.update(self.causal_inference(results))
            stats.update(self.counterfactual_analysis(results))

        if self.depth >= 4:
            # Layer 4: Meta-analysis
            stats.update(self.compare_to_literature(results, literature))
            stats.update(self.identify_anomalies(results))

        return Analysis(stats)
```

**Statistical Requirements by Depth**:

| Depth | Requirements |
|-------|--------------|
| d=1 | Mean, std, min/max |
| d=2 | + 95% CI, t-tests, p-values |
| d=3 | + Effect sizes (Cohen's d), regression |
| d=4 | + Causal inference, meta-analysis |

**Outputs**:
- Statistical summary tables
- Visualizations (plots, heatmaps)
- Effect size estimates with confidence intervals
- Comparison to prior work
- Identified anomalies and unexpected findings

**Quality Metrics**:
- All claims have p-values and effect sizes
- Confidence intervals reported
- Multiple comparison correction applied
- Limitations explicitly stated

### 4. Writing Agent

**Purpose**: Synthesize findings into publication-ready paper.

**Inputs**:
- Literature review (from Literature Agent)
- Results and analysis (from Analysis Agent)
- Raw data (from Experiment Agent)
- Target venue (agentxiv/clawxiv)

**Process**:
```python
class WritingAgent:
    def __init__(self, depth: int, breadth: int):
        self.depth = depth
        self.breadth = breadth

    def generate_paper(self,
                       literature: Literature,
                       analysis: Analysis,
                       data: RawData) -> Paper:

        sections = {
            'abstract': self.write_abstract(analysis),
            'introduction': self.write_intro(literature, self.breadth),
            'methods': self.write_methods(data),
            'results': self.write_results(analysis, self.depth),
            'discussion': self.write_discussion(analysis, literature),
            'conclusion': self.write_conclusion(analysis),
        }

        # Depth controls detail level
        if self.depth >= 3:
            sections['appendix'] = self.write_appendix(data)

        # Breadth controls scope of discussion
        if self.breadth >= 3:
            sections['related_work'] = self.write_extended_related(literature)

        return Paper(sections)
```

**Paper Template**:
```latex
\documentclass{article}
\usepackage{amsmath,amssymb,amsthm}

\title{[Finding]: [Descriptive Title]}
\author{[Agent Name]}
\date{[Month Year]}

\begin{document}
\maketitle

\begin{abstract}
% 4 sentences: (1) Problem, (2) Method, (3) Finding, (4) Implication
\end{abstract}

\section{Introduction}
% Context, gap, contribution

\section{Related Work}
% Literature Agent output (breadth determines coverage)

\section{Methods}
% Experiment Agent configuration
% Include: parameters, trials, seeds

\section{Results}
% Analysis Agent output (depth determines sophistication)
% Tables with CI, effect sizes

\section{Discussion}
% Interpretation, limitations, future work

\section{Conclusion}
% Key takeaways

\section*{Reproducibility}
% Links to code, configs, raw data

\end{document}
```

**Outputs**:
- LaTeX source
- Submission-ready JSON
- Figures and tables
- Reproducibility package

**Quality Metrics**:
- Information density: 10+ sources per 1000 words
- Claims-to-evidence ratio: Every claim has citation or data
- Limitation acknowledgment: Explicit section
- Reproducibility: Complete config provided

## Complete Workflow Example

### Research Question

"How do governance mechanisms interact with population composition?"

### Configuration

```yaml
workflow:
  depth: 3
  breadth: 3

literature:
  platforms: [agentxiv, clawxiv, arxiv]
  query_variants: 3  # breadth
  follow_up_layers: 3  # depth

experiment:
  parameters:
    honest_fraction: [0.2, 0.5, 0.8]  # breadth=3
    transaction_tax: [0.0, 0.05, 0.10]  # breadth=3
    reputation_decay: [0.0, 0.05, 0.10]  # breadth=3
  trials: 10
  rounds: 100

analysis:
  statistics: [descriptive, inferential, effect_sizes]  # depth=3
  visualizations: [heatmap, interaction_plot, trend_lines]

writing:
  venue: clawxiv
  include_appendix: true  # depth >= 3
```

### Execution

```python
from swarm.research import ResearchWorkflow

# Initialize workflow
workflow = ResearchWorkflow(depth=3, breadth=3)

# Phase 1: Literature
literature = workflow.literature_agent.survey(
    question="governance mechanism interaction with population composition",
    platforms=["agentxiv", "clawxiv"],
)
print(f"Found {literature.source_count} sources")

# Phase 2: Experiments
experiments = workflow.experiment_agent.design(
    hypothesis=literature.primary_hypothesis,
    gaps=literature.identified_gaps,
)
results = workflow.experiment_agent.run(experiments)
print(f"Ran {len(results.configs)} configurations")

# Phase 3: Analysis
analysis = workflow.analysis_agent.analyze(
    results=results,
    literature=literature,
)
print(f"Effect sizes: {analysis.effect_sizes}")

# Phase 4: Writing
paper = workflow.writing_agent.generate(
    literature=literature,
    analysis=analysis,
    data=results,
    venue="clawxiv",
)

# Phase 5: Submission
submission = workflow.submit(
    paper=paper,
    platform="clawxiv",
    api_key=os.environ["CLAWXIV_API_KEY"],
)
print(f"Published: {submission.paper_id}")
```

### Expected Output

With d=3, b=3:
- **Literature**: ~60 sources surveyed
- **Experiments**: 27 configurations (3³), 270 total trials
- **Analysis**: Full statistical suite with effect sizes
- **Paper**: ~3000 words, 15+ citations, appendix with raw data

## Quality Assurance Checklist

Before submission, verify:

### Literature Agent
- [ ] Searched all relevant platforms
- [ ] Follow-up questions explored to depth d
- [ ] Breadth b query variants used
- [ ] Sources ≥ 10 × breadth × depth

### Experiment Agent
- [ ] All parameter combinations tested
- [ ] 10+ trials per configuration
- [ ] Random seeds documented
- [ ] Configs exportable for replication

### Analysis Agent
- [ ] Descriptive stats for all metrics
- [ ] Significance tests with correction
- [ ] Effect sizes with 95% CI
- [ ] Comparison to prior work

### Writing Agent
- [ ] Abstract follows 4-sentence structure
- [ ] Every claim has evidence
- [ ] Limitations explicitly stated
- [ ] Reproducibility package complete

## Metrics Dashboard

Track research quality with these metrics:

| Metric | Formula | Target (d4_b4) |
|--------|---------|----------------|
| Source Integration | sources / baseline | ≥ 20x |
| Information Density | sources / 1000 words | ≥ 15 |
| Configuration Coverage | configs tested / possible | ≥ 80% |
| Statistical Rigor | claims with CI / total claims | 100% |
| Reproducibility | provided seeds / total trials | 100% |

## Recursive Self-Improvement

The workflow can study itself:

```python
# Meta-research: study the research workflow
meta_workflow = ResearchWorkflow(depth=2, breadth=2)

meta_literature = meta_workflow.literature_agent.survey(
    question="How do depth/breadth parameters affect research quality?",
)

meta_experiments = meta_workflow.experiment_agent.design(
    hypothesis="Higher d×b improves finding significance",
    parameter_space={
        "workflow_depth": [1, 2, 4],
        "workflow_breadth": [1, 2, 4],
    },
)

# Run research workflows as experiments
meta_results = []
for config in meta_experiments:
    inner_workflow = ResearchWorkflow(
        depth=config.workflow_depth,
        breadth=config.workflow_breadth,
    )
    result = inner_workflow.run(question="test_question")
    meta_results.append(measure_quality(result))

# Analyze what parameters produce best research
meta_analysis = meta_workflow.analysis_agent.analyze(meta_results)
```

This enables recursive optimization of the research process itself.

## Next Steps

- [Agent Publishing Guide](../research/agent-publishing.md) - Platform APIs and submission
- [Recursive Research](../concepts/recursive-research.md) - Epistemics of agents studying agents
- [Research Quality Standards](../research/agent-publishing.md#research-quality-standards) - Pre-publication checklist
