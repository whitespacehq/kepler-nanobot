# Cobble

Cobble is an experimental bot built on a tracking fork of [NanoBot](https://github.com/qwibitai/nanobot). It's a learning and experimentation ground — particularly for memory, dreaming, and the micro-decisions that only surface at runtime. **Not production Kepler** (that runs on OpenClaw on M1).

## Fork discipline

Prefer modular, well-documented code that stays separate from upstream files. Every upstream file we modify is a future merge conflict when we sync. NanoBot has extension points (hooks, channel registry, command router, skills directory, provider registry) — use them where possible.

When modifying an upstream file is unavoidable, keep the diff minimal, add a `# COBBLE:` comment explaining why, and log it in `UPSTREAM_CHANGES.md`.

## Git setup

| Remote | Repo | Purpose |
|---|---|---|
| `origin` | `whitespacehq/kepler-nanobot` | Our fork. `main` pushes here. |
| `upstream` | `HKUDS/nanobot` | Official NanoBot. Read-only — fetch, never push. |

| Branch | Tracks | Rule |
|---|---|---|
| `main` | `origin/main` | Cobble's main branch. All our work goes here. |
| `upstream-main` | `upstream/main` | Mirror of official NanoBot `main`. Never commit Cobble code here. |

Sync biweekly using `/sync-upstream` from the kepler-surgeon repo. Upstream uses `main` (stable) and `nightly` (experimental) — we track `main`.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check nanobot/
ruff format nanobot/
```

Python 3.11+, async throughout, 100-char line length. See `CONTRIBUTING.md` for upstream's code style — we follow it for consistency.

## Operations

### Running locally (dev)

```bash
source .venv/bin/activate
python -m nanobot gateway --config config.json
```

### M1 deployment

Cobble is **currently stopped**. When running, it uses a launchd service on M1 (`ssh m1`) alongside (not replacing) production Kepler on OpenClaw.

```bash
cd ~/kepler-nanobot && source .venv/bin/activate

# Status
python -m nanobot.kepler.deploy.launchd status

# Stop
launchctl unload ~/Library/LaunchAgents/com.whitespace.kepler-nanobot.plist

# Start
launchctl load ~/Library/LaunchAgents/com.whitespace.kepler-nanobot.plist

# Reinstall (regenerates plist — run after .env or config changes)
python -m nanobot.kepler.deploy.launchd install

# Logs
tail -f ~/kepler-nanobot/logs/gateway.log
tail -f ~/kepler-nanobot/logs/gateway.err.log
```

### Deploy workflow

1. Develop and test locally
2. `git push origin main`
3. SSH to M1: `cd ~/kepler-nanobot && git pull`
4. If code-only changes: `launchctl unload ... && launchctl load ...`
5. If .env or config changed: `python -m nanobot.kepler.deploy.launchd install`

### Config and secrets

- `config.json` — gitignored, instance-specific. Slack tokens inlined.
- `.env` — gitignored. Contains `ANTHROPIC_AUTH_TOKEN` (OAuth), `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`.
- `workspace/` — separate git repo. Cobble's identity/memory files still need setup (currently has leftover Kepler identity).

## Auth

OAuth subscriptions only for LLM access. No `ANTHROPIC_API_KEY` in `.env`. Uses `ANTHROPIC_AUTH_TOKEN` (OAuth token from `claude setup-token`). Requires Claude Code identity headers — see `Kepler/NanoBot/OAuth Authentication.md` in the Obsidian vault for details.
