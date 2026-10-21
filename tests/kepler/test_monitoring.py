"""Monitoring must keep each concurrent agent run's records together."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.runner import AgentRunner, AgentRunSpec
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.kepler.monitoring.context import model_var, session_key_var
from nanobot.kepler.monitoring.hook import MonitoringHook
from nanobot.providers.base import LLMResponse, ToolCallRequest


class PausedTool(Tool):
    name = "lookup"
    description = "Return a synthetic result after release."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, session, started, release):
        self.session = session
        self.started = started
        self.release = release

    async def execute(self, **kwargs):
        self.started.set()
        await self.release.wait()
        return f"result-{self.session}"


async def run_session(hook, session, started, release, shared_call_id):
    tools = ToolRegistry()
    tools.register(PausedTool(session, started, release))
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        side_effect=[
            LLMResponse(
                content=f"lookup-{session}",
                tool_calls=[
                    ToolCallRequest(
                        id="call-1" if shared_call_id else f"call-{session}",
                        name="lookup",
                        arguments={},
                    )
                ],
                usage={"prompt_tokens": 11, "completion_tokens": 2},
            ),
            LLMResponse(
                content=f"done-{session}",
                usage={"prompt_tokens": 17, "completion_tokens": 3},
            ),
        ]
    )
    session_token = session_key_var.set(session)
    model_token = model_var.set("synthetic-model")
    try:
        return await AgentRunner(provider).run(
            AgentRunSpec(
                initial_messages=[{"role": "user", "content": f"request-{session}"}],
                tools=tools,
                model="synthetic-model",
                max_iterations=3,
                max_tool_result_chars=5000,
                hook=hook,
                session_key=session,
            )
        )
    finally:
        session_key_var.reset(session_token)
        model_var.reset(model_token)


@pytest.mark.parametrize("shared_call_id", [False, True])
@pytest.mark.parametrize("schedule", ["sequential", "a-first", "b-first"])
@pytest.mark.asyncio
async def test_monitoring_keeps_overlapping_sessions_separate(tmp_path, schedule, shared_call_id):
    hook = MonitoringHook(tmp_path / "monitor.db")
    started = {name: asyncio.Event() for name in ("a", "b")}
    release = {name: asyncio.Event() for name in ("a", "b")}
    tasks = []

    async def start(name):
        task = asyncio.create_task(
            run_session(
                hook,
                name,
                started[name],
                release[name],
                shared_call_id,
            )
        )
        tasks.append(task)
        await asyncio.wait_for(started[name].wait(), timeout=5)
        return task

    try:
        a = await start("a")
        if schedule == "sequential":
            release["a"].set()
            assert (await asyncio.wait_for(a, timeout=5)).final_content == "done-a"
        b = await start("b")
        order = ("b", "a") if schedule == "b-first" else ("a", "b")
        for name in order:
            release[name].set()
            task = a if name == "a" else b
            assert (await asyncio.wait_for(task, timeout=5)).final_content == f"done-{name}"

        rows = hook._conn.execute(
            "SELECT i.session_key, i.iteration, t.result "
            "FROM tool_calls t JOIN iterations i ON i.id = t.iteration_id "
            "ORDER BY i.session_key"
        ).fetchall()
        assert rows == [("a", 0, "result-a"), ("b", 0, "result-b")]
        iterations = hook._conn.execute(
            "SELECT session_key, iteration, user_content, assistant_content, stop_reason "
            "FROM iterations ORDER BY session_key, iteration"
        ).fetchall()
        assert iterations == [
            ("a", 0, "request-a", "lookup-a", None),
            ("a", 1, "request-a", "done-a", "completed"),
            ("b", 0, "request-b", "lookup-b", None),
            ("b", 1, "request-b", "done-b", "completed"),
        ]
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        hook._conn.close()


@pytest.mark.asyncio
async def test_monitoring_records_response_without_tools(tmp_path):
    hook = MonitoringHook(tmp_path / "monitor.db")
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content="done",
            usage={"prompt_tokens": 5, "completion_tokens": 1},
        )
    )
    try:
        result = await AgentRunner(provider).run(
            AgentRunSpec(
                initial_messages=[{"role": "user", "content": "hello"}],
                tools=ToolRegistry(),
                model="synthetic-model",
                max_iterations=1,
                max_tool_result_chars=5000,
                hook=hook,
            )
        )
        assert result.final_content == "done"
        assert hook._conn.execute(
            "SELECT user_content, assistant_content, stop_reason FROM iterations"
        ).fetchall() == [("hello", "done", "completed")]
    finally:
        hook._conn.close()
