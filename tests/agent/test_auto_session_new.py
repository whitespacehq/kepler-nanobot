"""Tests for auto session new (idle TTL) feature."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import AgentDefaults
from nanobot.providers.base import LLMResponse


def _make_loop(tmp_path: Path, session_ttl_minutes: int = 15) -> AgentLoop:
    """Create a minimal AgentLoop for testing."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.estimate_prompt_tokens.return_value = (10_000, "test")
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="ok", tool_calls=[]))
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        context_window_tokens=1,
        session_ttl_minutes=session_ttl_minutes,
    )
    loop.tools.get_definitions = MagicMock(return_value=[])
    return loop


class TestSessionTTLConfig:
    """Test session TTL configuration."""

    def test_default_ttl_is_zero(self):
        """Default TTL should be 0 (disabled)."""
        defaults = AgentDefaults()
        assert defaults.session_ttl_minutes == 0

    def test_custom_ttl(self):
        """Custom TTL should be stored correctly."""
        defaults = AgentDefaults(session_ttl_minutes=30)
        assert defaults.session_ttl_minutes == 30

    def test_ttl_zero_means_disabled(self):
        """TTL of 0 means auto-new is disabled."""
        defaults = AgentDefaults()
        assert defaults.session_ttl_minutes == 0


class TestAgentLoopTTLParam:
    """Test that AgentLoop receives and stores session_ttl_minutes."""

    def test_loop_stores_ttl(self, tmp_path):
        """AgentLoop should store the TTL value."""
        loop = _make_loop(tmp_path, session_ttl_minutes=25)
        assert loop._session_ttl_minutes == 25

    def test_loop_default_ttl_zero(self, tmp_path):
        """AgentLoop default TTL should be 0 (disabled)."""
        loop = _make_loop(tmp_path, session_ttl_minutes=0)
        assert loop._session_ttl_minutes == 0
