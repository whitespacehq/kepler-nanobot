"""Tests for KeplerSlackChannel reaction handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.kepler.channels.slack import KeplerSlackChannel


def _make_channel(reaction_events="off", **extra_config):
    """Create a KeplerSlackChannel with mocked bus and minimal config."""
    config = {
        "enabled": True,
        "mode": "socket",
        "botToken": "xoxb-test",
        "appToken": "xapp-test",
        "replyInThread": True,
        "reactEmoji": "eyes",
        "doneEmoji": "white_check_mark",
        "allowFrom": ["*"],
        "groupPolicy": "mention",
        "reactionEvents": reaction_events,
        "dm": {"enabled": True, "policy": "open", "allowFrom": []},
        **extra_config,
    }
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    channel = KeplerSlackChannel(config, bus)
    channel._web_client = AsyncMock()
    channel._bot_user_id = "U_BOT"
    return channel


# -- ts→thread cache --------------------------------------------------------


def test_cache_ts_bounded():
    channel = _make_channel()
    for i in range(1100):
        channel._cache_ts(str(i), f"thread_{i}")
    assert len(channel._ts_to_thread) == 1000
    # Oldest should be evicted
    assert "0" not in channel._ts_to_thread
    assert "1099" in channel._ts_to_thread


def test_cache_ts_move_to_end():
    channel = _make_channel()
    channel._cache_ts("a", "thread_a")
    channel._cache_ts("b", "thread_b")
    channel._cache_ts("a", "thread_a_updated")
    keys = list(channel._ts_to_thread.keys())
    assert keys == ["b", "a"]
    assert channel._ts_to_thread["a"] == "thread_a_updated"


# -- Inbound reaction events -------------------------------------------------


@pytest.mark.asyncio
async def test_reaction_event_off_by_default():
    """reaction_events='off' means reaction events are silently dropped."""
    channel = _make_channel(reaction_events="off")
    channel._ts_to_thread["1.0"] = "1.0"

    event = {
        "type": "reaction_added",
        "user": "U_USER",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C12345", "ts": "1.0"},
    }
    await channel._handle_reaction_event(event, "reaction_added")

    # _handle_message should NOT have been called
    channel.bus.publish_inbound.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_event_cache_miss():
    """Reactions on unknown messages are dropped."""
    channel = _make_channel(reaction_events="all")
    # Don't populate cache

    event = {
        "type": "reaction_added",
        "user": "U_USER",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C12345", "ts": "unknown.ts"},
    }
    await channel._handle_reaction_event(event, "reaction_added")

    channel.bus.publish_inbound.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_event_bot_ignored():
    """Bot's own reactions are ignored."""
    channel = _make_channel(reaction_events="all")
    channel._ts_to_thread["1.0"] = "1.0"

    event = {
        "type": "reaction_added",
        "user": "U_BOT",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C12345", "ts": "1.0"},
    }
    await channel._handle_reaction_event(event, "reaction_added")

    channel.bus.publish_inbound.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_event_all_mode():
    """reaction_events='all' delivers reaction to the agent."""
    channel = _make_channel(reaction_events="all")
    channel._ts_to_thread["1.0"] = "thread_1.0"

    event = {
        "type": "reaction_added",
        "user": "U_USER",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C12345", "ts": "1.0"},
    }

    # Mock _handle_message to capture the call
    channel._handle_message = AsyncMock()

    await channel._handle_reaction_event(event, "reaction_added")

    channel._handle_message.assert_called_once()
    call_kwargs = channel._handle_message.call_args[1]
    assert call_kwargs["sender_id"] == "U_USER"
    assert call_kwargs["chat_id"] == "C12345"
    assert ":thumbsup:" in call_kwargs["content"]
    assert "added" in call_kwargs["content"]
    assert call_kwargs["metadata"]["slack"]["reaction"]["emoji"] == "thumbsup"
