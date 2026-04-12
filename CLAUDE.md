# Kepler NanoBot

This is Kepler's fork of [NanoBot](https://github.com/HKUDS/nanobot). We build on top of upstream — we don't replace it.

## Fork discipline

Prefer modular, well-documented code that stays separate from upstream files. Every upstream file we modify is a future merge conflict when we sync. NanoBot has extension points (hooks, channel registry, command router, skills directory, provider registry) — use them where possible.

When modifying an upstream file is unavoidable, keep the diff minimal, add a `# KEPLER:` comment explaining why, and log it in `UPSTREAM_CHANGES.md`.

## Git setup

| Remote | Repo | Purpose |
|---|---|---|
| `origin` | `whitespacehq/kepler-nanobot` | Our fork. `main` pushes here. |
| `upstream` | `HKUDS/nanobot` | Official NanoBot. Read-only — fetch, never push. |

| Branch | Tracks | Rule |
|---|---|---|
| `main` | `origin/main` | Kepler's main branch. All our work goes here. |
| `upstream-main` | `upstream/main` | Mirror of official NanoBot `main`. Never commit Kepler code here. |

Sync biweekly using `/sync-upstream` from the openclaw-surgeon repo. Upstream uses `main` (stable) and `nightly` (experimental) — we track `main`.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check nanobot/
ruff format nanobot/
```

Python 3.11+, async throughout, 100-char line length. See `CONTRIBUTING.md` for upstream's code style — we follow it for consistency.

## Auth

OAuth subscriptions only for LLM access. No `ANTHROPIC_API_KEY` in `.env`.
