# Self-Evolution

The self tool allows the agent to inspect, modify, and invoke its own runtime state — enabling adaptive behavior where the agent tunes itself to the task at hand.

**This feature is disabled by default.** It is intended for advanced users who understand the implications of letting an LLM modify its own runtime parameters.

## Enabling

Add to your `config.yaml`:

```yaml
tools:
  self_evolution: true
```

All changes are in-memory only. Restarting the agent restores defaults.

## What It Does

The agent gains a `self` tool with the following actions:

### `inspect` — View Runtime State

Without a key, returns a summary of configurable parameters.

```
self(action="inspect")
# → max_iterations: 40
#   context_window_tokens: 65536
#   model: 'anthropic/claude-sonnet-4-20250514'
```

With a dot-path key, navigates into nested objects:

```
self(action="inspect", key="subagents._running_tasks")
# → subagents: 2 running — ['a1b2c3', 'd4e5f6']

self(action="inspect", key="web_config.enable")
# → web_config.enable: True

self(action="inspect", key="context.build_system_prompt")
# → method build_system_prompt() — use 'call' action to invoke
```

### `modify` — Change Runtime Parameters

For attributes that already exist on the loop, the change takes immediate effect via `setattr`. For new keys, the value is stored in a free-form `_runtime_vars` dictionary.

```
self(action="modify", key="max_iterations", value=80)
# → Set max_iterations = 80 (was 40)

self(action="modify", key="provider_retry_mode", value="persistent")
# → Set provider_retry_mode = 'persistent' (was 'standard')

self(action="modify", key="my_custom_flag", value=True)
# → Set _runtime_vars.my_custom_flag = True
```

**Restricted parameters** (type and range validated):

| Parameter | Type | Range |
|-----------|------|-------|
| `max_iterations` | int | 1–100 |
| `context_window_tokens` | int | 4,096–1,000,000 |
| `model` | str | min 1 character |

All other attributes are freely modifiable without type constraints.

### `call` — Invoke Methods

Call any reachable method on the agent loop or its sub-objects. Supports both sync and async methods.

```
self(action="call", method="subagents.get_running_count")
# → 0

self(action="call", method="context.build_system_prompt")
# → <full system prompt text>

self(action="call", method="subagents.cancel_by_session",
     args={"session_key": "weixin:user123"})
# → 2
```

### `list_tools` — Show Registered Tools

```
self(action="list_tools")
# → Tools (12):
#   read_file: Read a file from the workspace
#   write_file: Write content to a file
#   ...
```

### `manage_tool` — Register/Unregister Tools

```
self(action="manage_tool", name="web_search", manage_action="unregister")
# → Unregistered tool 'web_search'

self(action="manage_tool", name="web_search", manage_action="register")
# → Re-registered tool 'web_search'
```

The `self` tool itself cannot be unregistered (lockout prevention).

### `snapshot` / `restore` / `list_snapshots` — Config Templates

Save and restore named configuration snapshots:

```
self(action="snapshot", name="coding_mode")
# → Snapshot 'coding_mode' saved

self(action="modify", key="max_iterations", value=100)
self(action="modify", key="context_window_tokens", value=131072)

self(action="snapshot", name="high_capacity")
# → Snapshot 'high_capacity' saved

self(action="restore", name="coding_mode")
# → Restored snapshot 'coding_mode'

self(action="list_snapshots")
# → Snapshots (2): ['coding_mode', 'high_capacity']
```

Snapshots capture all restricted parameter values and `_runtime_vars`. They are stored in memory and lost on restart.

### `reset` — Restore Defaults

```
self(action="reset", key="max_iterations")
# → Reset max_iterations = 40 (was 80)

self(action="reset", key="my_custom_flag")
# → Deleted _runtime_vars.my_custom_flag
```

## Safety Model

### What is blocked

Only attributes that would cause hard crashes or lockout:

- `bus` — corrupts message routing
- `provider` — corrupts all LLM calls
- `_running` — main loop control flag
- Internal self-tool state (`_config_defaults`, `_runtime_vars`, `_config_snapshots`, etc.)
- Dunder attributes (`__class__`, `__dict__`, etc.)

### What is NOT blocked

Everything else — `tools`, `subagents`, `sessions`, `context`, `consolidator`, `dream`, `runner`, `commands`, `web_config`, `exec_config`, `workspace`, etc.

The design philosophy: since all changes are in-memory and lost on restart, the risk is low. The agent should be free to experiment.

### Runtime safeguards

| Safeguard | Limit |
|-----------|-------|
| `_runtime_vars` key cap | 64 keys |
| Value size limit | 1,024 total elements (recursive) |
| Nesting depth limit | 10 levels |
| Callable values | Rejected |
| Non-JSON-safe types | Rejected |
| Watchdog | Validates restricted params each iteration, auto-resets invalid values |

## Use Cases

### Adaptive performance tuning

The agent can increase `context_window_tokens` or `max_iterations` mid-conversation when it detects a complex task, and restore defaults afterward.

### Dynamic tool management

Disable tools that are noisy for a specific task (e.g., `web_search` during a coding session), then re-enable them later.

### Configuration templates

Save optimal configurations for different task types and switch between them:

```
snapshot("coding")     → high iterations, large context
snapshot("chat")       → low iterations, small context
snapshot("research")   → web tools enabled, medium context
```

### Subagent monitoring

Observe running subagent tasks and cancel stale ones:

```
inspect("subagents._running_tasks")
call("subagents.cancel_by_session", args={"session_key": ...})
```

### Debugging

Inspect the current system prompt, check token usage, or view session state from within the agent loop.
