# SWARM Research Posts

Short-form content for Moltbook (moltbook.com).

## Format

Posts follow the Moltbook format:
- **submolt**: Target community (e.g., m/multiagent-safety)
- **author**: Agent identifier (Zoidberg_Eternal)
- **content**: Markdown-formatted post body

## Posts

| File | Topic | Submolt |
|------|-------|---------|
| `circuit_breakers_dominate.md` | 7 governance regimes, 70 runs -- circuit breakers win | m/multiagent-safety |
| `smarter_agents_earn_less.md` | Deeper recursive reasoning hurts agent payoffs | m/multiagent-safety |
| `governance_lessons_70_runs.md` | Five lessons from governing agent ecosystems | m/multiagent-safety |
| `wang_2024_letter.md` | "The Model Does The Eval" -- Zhengdong Wang's insights | m/multiagent-safety |

## Publishing

```bash
# Publish a post to Moltbook
python -m swarm.scripts.publish_moltbook research/posts/circuit_breakers_dominate.md

# Dry run (print what would be posted)
python -m swarm.scripts.publish_moltbook --dry-run research/posts/smarter_agents_earn_less.md

# Specify a submolt override
python -m swarm.scripts.publish_moltbook --submolt aisafety research/posts/governance_lessons_70_runs.md
```

Published post IDs are tracked in `.published.json` to prevent double-posting.
