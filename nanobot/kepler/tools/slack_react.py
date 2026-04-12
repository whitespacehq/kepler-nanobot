"""Slack reaction tool — add or remove emoji reactions on messages."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import StringSchema, tool_parameters_schema
from nanobot.bus.events import OutboundMessage

# Small unicode→shortcode map for common emoji.
_UNICODE_TO_SHORTCODE: dict[str, str] = {
    "\U0001f44d": "thumbsup",
    "\U0001f44e": "thumbsdown",
    "\u2764\ufe0f": "heart",
    "\u2764": "heart",
    "\U0001f602": "joy",
    "\U0001f60d": "heart_eyes",
    "\U0001f525": "fire",
    "\U0001f64f": "pray",
    "\U0001f389": "tada",
    "\U0001f680": "rocket",
    "\u2705": "white_check_mark",
    "\u274c": "x",
    "\U0001f440": "eyes",
    "\U0001f914": "thinking_face",
    "\U0001f4af": "100",
    "\U0001f44b": "wave",
    "\U0001f3af": "dart",
    "\U0001f4a1": "bulb",
    "\U0001f52d": "telescope",
    "\U0001f64c": "raised_hands",
}


def _normalize_emoji(emoji: str) -> str:
    """Normalize emoji input to a Slack shortcode name.

    Handles: ``:thumbsup:`` → ``thumbsup``, ``👍`` → ``thumbsup``,
    ``thumbsup`` → ``thumbsup``.
    """
    emoji = emoji.strip()
    # Strip surrounding colons
    if emoji.startswith(":") and emoji.endswith(":") and len(emoji) > 2:
        emoji = emoji[1:-1]
    # Unicode → shortcode
    if emoji in _UNICODE_TO_SHORTCODE:
        return _UNICODE_TO_SHORTCODE[emoji]
    return emoji


@tool_parameters(
    tool_parameters_schema(
        emoji=StringSchema("Emoji shortcode name, e.g. 'thumbsup', 'heart', 'eyes'"),
        message_ts=StringSchema(
            "Timestamp of the Slack message to react to. "
            "Omit to react to the message you are currently responding to.",
            nullable=True,
        ),
        action=StringSchema(
            "Action to perform",
            enum=["add", "remove"],
        ),
        channel=StringSchema("Target channel ID (defaults to current conversation)"),
        required=["emoji"],
    )
)
class SlackReactTool(Tool):
    """Add or remove emoji reactions on Slack messages."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
    ):
        self._send_callback = send_callback
        self._channel: str = ""
        self._chat_id: str = ""
        self._last_message_ts: str = ""

    def set_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Set the current conversation context for routing."""
        self._channel = channel
        self._chat_id = chat_id
        if message_id:
            self._last_message_ts = message_id

    @property
    def name(self) -> str:
        return "slack_react"

    @property
    def description(self) -> str:
        return (
            "Add or remove an emoji reaction on a Slack message. "
            "Use this to react to messages with emoji like thumbsup, heart, eyes, etc."
        )

    async def execute(
        self,
        emoji: str,
        message_ts: str | None = None,
        action: str = "add",
        channel: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self._send_callback:
            return "Error: Message sending not configured"

        message_ts = message_ts or self._last_message_ts
        if not message_ts:
            return "Error: No message timestamp specified and no current message context"

        chat_id = channel or self._chat_id
        if not chat_id:
            return "Error: No target channel specified"

        normalized = _normalize_emoji(emoji)

        msg = OutboundMessage(
            channel=self._channel,
            chat_id=chat_id,
            content="",
            metadata={
                "_reaction": {
                    "emoji": normalized,
                    "message_ts": message_ts,
                    "action": action,
                },
            },
        )

        try:
            await self._send_callback(msg)
            verb = "Added" if action == "add" else "Removed"
            return f"{verb} :{normalized}: reaction on message {message_ts}"
        except Exception as e:
            return f"Error sending reaction: {e}"


def create_tool(*, bus: Any, **_kwargs: Any) -> SlackReactTool:
    """Factory for the Kepler tool loader."""
    return SlackReactTool(send_callback=bus.publish_outbound)
