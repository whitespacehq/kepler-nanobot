# Upstream Changes

Files modified from upstream NanoBot that will need attention during merges. Each entry should include the file, what changed, and why — so future merge conflicts have context.

## Format

```
### <file path>
- **What:** one-line description of the change
- **Why:** why we couldn't use an extension point instead
- **PR:** link to upstream PR if we've proposed upstreaming this
```

## Changes

### `nanobot/providers/anthropic_provider.py`
- **What:** Added `auth_token` parameter and OAuth beta headers for Claude Code OAuth support
- **Why:** No extension point for auth strategy — provider init is inline
- **PR:** —

### `nanobot/providers/registry.py`
- **What:** Changed Anthropic `env_key` to `ANTHROPIC_AUTH_TOKEN`, set `is_oauth=True`
- **Why:** Registry validation would reject missing API key; `is_oauth` skips that check
- **PR:** —

### `nanobot/nanobot.py`
- **What:** Added `auth_token=None` to `AnthropicProvider()` instantiation
- **Why:** Explicit parameter threading for OAuth (resolved from env inside provider)
- **PR:** —

### `nanobot/cli/commands.py`
- **What:** Added `auth_token=None` to `AnthropicProvider()` instantiation; added dotenv loading in `_load_runtime_config`
- **Why:** OAuth param threading + `.env` auto-loading so secrets stay out of config.json
- **PR:** —
