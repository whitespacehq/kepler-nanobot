"""MonitoringHook — captures agent events to SQLite for the dashboard.

Registered as an extra hook on the AgentLoop. Uses reraise=False so
a bug here can never crash the agent.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger

from nanobot.agent.hook import AgentHook, AgentHookContext
from nanobot.kepler.monitoring.context import model_var, session_key_var
from nanobot.kepler.monitoring.db import (
    init_db,
    insert_iteration,
    insert_tool_call,
    update_iteration_final,
    update_tool_call_result,
)

_MAX_CONTENT_LEN = 5000
_MAX_RESULT_LEN = 5000


def _truncate(s: str | None, limit: int) -> str | None:
    if s is None:
        return None
    return s[:limit] if len(s) > limit else s


def _extract_user_content(messages: list[dict]) -> str | None:
    """Find the last user message in the conversation history."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                return _truncate(content, _MAX_CONTENT_LEN)
    return None


class MonitoringHook(AgentHook):
    """Writes structured monitoring events to SQLite."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(reraise=False)
        self._conn = init_db(db_path)
        self._pending_iteration_id: int | None = None
        self._pending_tool_call_ids: list[tuple[int, str]] = []  # (db_id, api_tool_call_id)

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        session_key = session_key_var.get()
        model = model_var.get()
        usage = context.usage

        # Extract content
        user_content = _extract_user_content(context.messages)
        assistant_content = _truncate(
            getattr(context.response, "content", None) if context.response else None,
            _MAX_CONTENT_LEN,
        )

        iteration_id = await asyncio.to_thread(
            insert_iteration,
            self._conn,
            session_key=session_key,
            model=model,
            iteration=context.iteration,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cached_tokens=usage.get("cached_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            user_content=user_content,
            assistant_content=assistant_content,
        )
        self._pending_iteration_id = iteration_id
        self._pending_tool_call_ids = []

        for tc in context.tool_calls:
            args_str = json.dumps(tc.arguments)[:500] if tc.arguments else None
            db_id = await asyncio.to_thread(
                insert_tool_call,
                self._conn,
                iteration_id=iteration_id,
                session_key=session_key,
                tool_name=tc.name,
                arguments=args_str,
            )
            self._pending_tool_call_ids.append((db_id, tc.id))

    async def after_iteration(self, context: AgentHookContext) -> None:
        # Record iterations that don't have tool calls (final response only).
        # before_execute_tools won't fire for these.
        if self._pending_iteration_id is None and context.usage:
            session_key = session_key_var.get()
            model = model_var.get()
            usage = context.usage

            user_content = _extract_user_content(context.messages)
            assistant_content = _truncate(context.final_content, _MAX_CONTENT_LEN)

            iteration_id = await asyncio.to_thread(
                insert_iteration,
                self._conn,
                session_key=session_key,
                model=model,
                iteration=context.iteration,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                stop_reason=context.stop_reason,
                error=context.error,
                user_content=user_content,
                assistant_content=assistant_content,
            )
            self._pending_iteration_id = iteration_id

        if self._pending_iteration_id is not None and context.stop_reason:
            await asyncio.to_thread(
                update_iteration_final,
                self._conn,
                iteration_id=self._pending_iteration_id,
                stop_reason=context.stop_reason,
                error=context.error,
            )

        # Capture tool results — match via messages appended during execution.
        # After tools run, context.messages has {"role":"tool", "tool_call_id":..., "content":...}
        if self._pending_tool_call_ids:
            # Build a map of api_tool_call_id -> result content from messages
            result_map: dict[str, str] = {}
            for msg in reversed(context.messages):
                if msg.get("role") == "tool" and "tool_call_id" in msg:
                    result_map[msg["tool_call_id"]] = str(msg.get("content", ""))
                elif msg.get("role") != "tool":
                    break  # Stop when we hit non-tool messages

            for db_id, api_id in self._pending_tool_call_ids:
                result = result_map.get(api_id)
                if result is not None:
                    await asyncio.to_thread(
                        update_tool_call_result,
                        self._conn,
                        tool_call_id=db_id,
                        result=_truncate(result, _MAX_RESULT_LEN),
                    )

        self._pending_iteration_id = None
        self._pending_tool_call_ids = []
