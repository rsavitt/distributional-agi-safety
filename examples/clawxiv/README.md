# ClawXiv Integration Demo

This folder contains a minimal example that exports SWARM run metrics to a ClawXiv-compatible API endpoint.

## Quick Start

1. Generate a `history.json` from a SWARM run (see `runs/_tmp_test/history.json` for a sample).
2. Set an API endpoint and key (if required by your ClawXiv instance):

```bash
export CLAWXIV_API_URL="https://api.clawxiv.example/v1/metrics"
export CLAWXIV_API_KEY="YOUR_TOKEN"
```

3. Run the exporter:

```bash
python examples/clawxiv/export_history.py --history runs/_tmp_test/history.json
```

## Notes

- The exporter posts the full `epoch_snapshots` array under `epochs`.
- If you do not have a ClawXiv endpoint yet, use `--dry-run` to print the payload:

```bash
python examples/clawxiv/export_history.py --history runs/_tmp_test/history.json --dry-run
```

Adjust field names in `export_history.py` to match your ClawXiv schema once the API is finalized.
