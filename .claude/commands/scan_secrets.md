# /scan_secrets

Scan the working tree for hardcoded API keys, tokens, and secrets.

## Usage

`/scan_secrets [path]`

- `/scan_secrets` — scan all tracked + untracked files
- `/scan_secrets scripts/` — scan a specific directory
- `/scan_secrets swarm/bridges/gastown/bridge.py` — scan a single file

## Behavior

1) Run the secrets scanner script:
   ```
   bash .claude/hooks/scan_secrets.sh [path]
   ```

2) The scanner checks for:
   - Platform API keys: agentxiv (`ax_`), clawxiv (`clx_`), moltbook (`moltbook_sk_`), moltipedia, wikimolt (`wm_`), clawchan, clawk
   - Cloud provider keys: OpenAI (`sk-`), AWS (`AKIA`), GitHub (`ghp_`, `gho_`), Anthropic (`sk-ant-`)
   - Generic patterns: hardcoded `API_KEY = "..."`, `Bearer` tokens, private keys (`-----BEGIN`)
   - High-entropy strings assigned to key/token/secret variables

3) Report results:
   - If clean: print confirmation with count of files scanned
   - If secrets found: list each match with file, line number, matched pattern, and a redacted preview of the line
   - Suggest remediation: use `os.environ.get()`, `~/.config/<platform>/credentials.json`, or `${VAR}` interpolation

## When to use

- Before committing (`/scan_secrets` then `/commit`)
- After writing new bridge code or submission scripts
- Periodically during development as a health check
- When onboarding a new platform integration
