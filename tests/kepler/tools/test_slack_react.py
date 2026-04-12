"""Tests for the Slack reaction tool."""


import pytest

from nanobot.kepler.tools.slack_react import SlackReactTool, _normalize_emoji

# -- Emoji normalization -----------------------------------------------------


@pytest.mark.parametrize(
    "input_emoji, expected",
    [
        ("thumbsup", "thumbsup"),
        (":thumbsup:", "thumbsup"),
        ("\U0001f44d", "thumbsup"),
        ("\u2764\ufe0f", "heart"),
        ("\u2764", "heart"),
        ("eyes", "eyes"),
        (":eyes:", "eyes"),
        ("\U0001f440", "eyes"),
        ("custom_emoji", "custom_emoji"),
        (":custom_emoji:", "custom_emoji"),
        ("  thumbsup  ", "thumbsup"),
    ],
)
def test_normalize_emoji(input_emoji, expected):
    assert _normalize_emoji(input_emoji) == expected


# -- Tool execution ----------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_add_reaction():
    """Tool sends an OutboundMessage with _reaction metadata."""
    sent = []

    async def mock_send(msg):
        sent.append(msg)

    tool = SlackReactTool(send_callback=mock_send)
    tool.set_context("slack", "C12345")

    result = await tool.execute(emoji="thumbsup", message_ts="1234567890.123456")

    assert len(sent) == 1
    msg = sent[0]
    assert msg.metadata["_reaction"]["emoji"] == "thumbsup"
    assert msg.metadata["_reaction"]["message_ts"] == "1234567890.123456"
    assert msg.metadata["_reaction"]["action"] == "add"
    assert msg.chat_id == "C12345"
    assert "Added" in result


@pytest.mark.asyncio
async def test_execute_remove_reaction():
    sent = []

    async def mock_send(msg):
        sent.append(msg)

    tool = SlackReactTool(send_callback=mock_send)
    tool.set_context("slack", "C12345")

    result = await tool.execute(
        emoji=":heart:", message_ts="1234567890.123456", action="remove",
    )

    assert sent[0].metadata["_reaction"]["emoji"] == "heart"
    assert sent[0].metadata["_reaction"]["action"] == "remove"
    assert "Removed" in result


@pytest.mark.asyncio
async def test_execute_unicode_emoji():
    sent = []

    async def mock_send(msg):
        sent.append(msg)

    tool = SlackReactTool(send_callback=mock_send)
    tool.set_context("slack", "C12345")

    await tool.execute(emoji="\U0001f525", message_ts="123.456")

    assert sent[0].metadata["_reaction"]["emoji"] == "fire"


@pytest.mark.asyncio
async def test_execute_no_callback():
    tool = SlackReactTool(send_callback=None)
    tool.set_context("slack", "C12345")

    result = await tool.execute(emoji="thumbsup", message_ts="123.456")
    assert "Error" in result


@pytest.mark.asyncio
async def test_execute_no_channel():
    sent = []

    async def mock_send(msg):
        sent.append(msg)

    tool = SlackReactTool(send_callback=mock_send)
    # No set_context called

    result = await tool.execute(emoji="thumbsup", message_ts="123.456")
    assert "Error" in result


@pytest.mark.asyncio
async def test_set_context_updates_routing():
    sent = []

    async def mock_send(msg):
        sent.append(msg)

    tool = SlackReactTool(send_callback=mock_send)
    tool.set_context("slack", "C_FIRST")
    await tool.execute(emoji="thumbsup", message_ts="1.0")

    tool.set_context("slack", "C_SECOND")
    await tool.execute(emoji="thumbsup", message_ts="2.0")

    assert sent[0].chat_id == "C_FIRST"
    assert sent[1].chat_id == "C_SECOND"


# -- create_tool factory -----------------------------------------------------


def test_create_tool_factory():
    from nanobot.kepler.tools.slack_react import create_tool

    class FakeBus:
        async def publish_outbound(self, msg):
            pass

    tool = create_tool(bus=FakeBus())
    assert tool.name == "slack_react"
