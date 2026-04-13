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
- **What:** Added `auth_token=None` to `AnthropicProvider()` instantiation; added Kepler tool loader call
- **Why:** OAuth param threading + Kepler tool auto-registration after AgentLoop init
- **PR:** —

### `nanobot/cli/commands.py`
- **What:** Added `auth_token=None` to `AnthropicProvider()` instantiation; added dotenv loading in `_load_runtime_config`; added `_register_kepler_tools()` helper called after each AgentLoop instantiation (3 sites); added MonitoringHook instantiation and registration in `gateway()`; simplified heartbeat callbacks — removed `_pick_heartbeat_target()`, agent now routes messages via MCP slack tools instead of infrastructure-level delivery
- **Why:** OAuth param threading + `.env` auto-loading + Kepler tool auto-registration + monitoring dashboard data collection + heartbeat channel/thread targeting via Slack MCP server
- **PR:** —

### `nanobot/channels/registry.py`
- **What:** Flipped plugin/built-in priority in `discover_all()` — plugins now override built-ins
- **Why:** Allows `KeplerSlackChannel` to replace built-in `SlackChannel` via entry_points without modifying slack.py
- **PR:** — (arguably upstream-friendly: plugins should be able to override built-ins)

### `nanobot/agent/loop.py`
- **What:** Made `_set_tool_context()` iterate all tools with `set_context` instead of a hardcoded list
- **Why:** Kepler tools (e.g. `slack_react`) need context routing without adding to the fixed name list each time
- **PR:** — (generic improvement, could upstream)

### `nanobot/agent/loop.py` (monitoring contextvars)
- **What:** Added 3 lines in `_run_agent_loop()` to set `session_key_var` and `model_var` contextvars before creating the loop hook
- **Why:** `AgentHookContext` doesn't include session_key or model; contextvars bridge the gap for the monitoring hook without modifying the upstream type
- **PR:** —

### `nanobot/agent/tools/registry.py`
- **What:** Added `all_tools()` method returning `(name, tool)` pairs
- **Why:** Needed by `_set_tool_context()` to iterate all registered tools generically
- **PR:** — (generic improvement, could upstream)

### `pyproject.toml`
- **What:** Added `[project.entry-points."nanobot.channels"]` registering `KeplerSlackChannel`
- **Why:** Channel override mechanism — replaces built-in Slack with Kepler's extended version
- **PR:** —
