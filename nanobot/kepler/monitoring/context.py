"""Contextvars bridge between the agent loop and the monitoring hook.

The agent loop sets these before each run so the hook knows which session
and model are active without modifying AgentHookContext (upstream type).
"""

from contextvars import ContextVar

session_key_var: ContextVar[str] = ContextVar("monitor_session_key", default="unknown")
model_var: ContextVar[str] = ContextVar("monitor_model", default="unknown")
