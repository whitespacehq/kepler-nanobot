"""Kepler's Slack channel — extends upstream with reaction handling."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from loguru import logger
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.websockets import SocketModeClient

from nanobot.bus.events import OutboundMessage
from nanobot.channels.slack import SlackChannel

_MAX_TS_CACHE = 1000


class KeplerSlackChannel(SlackChannel):
    """Slack channel with reaction send/receive support.

    Outbound: intercepts ``_reaction`` metadata to call ``reactions_add`` /
    ``reactions_remove`` instead of posting a message.

    Inbound: optionally delivers ``reaction_added`` / ``reaction_removed``
    events to the agent (controlled by ``reaction_events`` config key,
    default ``"off"``).
    """

    display_name = "Slack (Kepler)"

    async def _handle_message(self, sender_id, chat_id, content, media=None,
                               metadata=None, session_key=None):
        """Inject Slack message ts as message_id for tool context routing."""
        meta = metadata or {}
        slack_event = meta.get("slack", {}).get("event", {})
        ts = slack_event.get("ts", "")
        if ts:
            meta["message_id"] = ts
        await super()._handle_message(
            sender_id=sender_id, chat_id=chat_id, content=content,
            media=media, metadata=meta, session_key=session_key,
        )

    def __init__(self, config: Any, bus: Any) -> None:
        super().__init__(config, bus)
        # ts → thread_ts cache for routing reaction events back to the
        # correct session.  Bounded via FIFO eviction.
        self._ts_to_thread: OrderedDict[str, str | None] = OrderedDict()
        # Config extension — read from raw config dict since the upstream
        # Pydantic model doesn't know about this field.
        raw = config if isinstance(config, dict) else config.model_dump(by_alias=True)
        self._reaction_events: str = raw.get("reactionEvents", "off")

    # ------------------------------------------------------------------
    # Outbound — intercept _reaction metadata
    # ------------------------------------------------------------------

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message or reaction through Slack."""
        if msg.metadata and msg.metadata.get("_reaction"):
            await self._send_reaction(msg)
            return
        await super().send(msg)

    async def _send_reaction(self, msg: OutboundMessage) -> None:
        """Execute a reaction add/remove via the Slack Web API."""
        if not self._web_client:
            logger.warning("Slack client not running, cannot send reaction")
            return
        r = msg.metadata["_reaction"]
        emoji = r["emoji"]
        message_ts = r["message_ts"]
        action = r.get("action", "add")
        channel = msg.chat_id

        try:
            if action == "remove":
                await self._web_client.reactions_remove(
                    channel=channel, name=emoji, timestamp=message_ts,
                )
            else:
                await self._web_client.reactions_add(
                    channel=channel, name=emoji, timestamp=message_ts,
                )
            logger.debug("Slack reaction {}: :{}: on {} in {}", action, emoji, message_ts, channel)
        except Exception as e:
            logger.warning("Slack reaction {} failed: {}", action, e)

    # ------------------------------------------------------------------
    # Inbound — intercept reaction events, cache ts→thread
    # ------------------------------------------------------------------

    async def _on_socket_request(
        self,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle incoming Socket Mode requests with reaction support."""
        if req.type != "events_api":
            return

        payload = req.payload or {}
        event = payload.get("event") or {}
        event_type = event.get("type")

        # Intercept reaction events before the base class (which ignores them).
        if event_type in ("reaction_added", "reaction_removed"):
            await client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )
            await self._handle_reaction_event(event, event_type)
            return

        # Delegate to base class for normal message handling.
        await super()._on_socket_request(client, req)

        # After base class processes: cache ts → thread_ts for future
        # reaction event routing.
        if event_type in ("message", "app_mention") and not event.get("subtype"):
            ts = event.get("ts")
            if ts:
                thread_ts = event.get("thread_ts") or (
                    ts if self.config.reply_in_thread else None
                )
                self._cache_ts(ts, thread_ts)

    def _cache_ts(self, ts: str, thread_ts: str | None) -> None:
        """Cache a message ts → thread_ts mapping, evicting oldest if full."""
        if ts in self._ts_to_thread:
            self._ts_to_thread.move_to_end(ts)
        self._ts_to_thread[ts] = thread_ts
        while len(self._ts_to_thread) > _MAX_TS_CACHE:
            self._ts_to_thread.popitem(last=False)

    async def _handle_reaction_event(self, event: dict, event_type: str) -> None:
        """Process an inbound reaction event."""
        if self._reaction_events == "off":
            return

        user = event.get("user", "")
        reaction = event.get("reaction", "")
        item = event.get("item", {})
        item_ts = item.get("ts", "")
        item_channel = item.get("channel", "")

        if not user or not item_ts or not item_channel:
            return

        # Ignore bot's own reactions
        if self._bot_user_id and user == self._bot_user_id:
            return

        # Look up thread context — drop if we don't know this message
        thread_ts = self._ts_to_thread.get(item_ts)
        if thread_ts is None and item_ts not in self._ts_to_thread:
            logger.debug("Reaction on unknown message {}, dropping", item_ts)
            return

        # Infer channel_type from channel ID prefix (Slack convention)
        channel_type = "im" if item_channel.startswith("D") else "channel"

        if not self._is_allowed(user, item_channel, channel_type):
            return

        # Build session key matching the message handling pattern
        session_key = (
            f"slack:{item_channel}:{thread_ts}"
            if thread_ts and channel_type != "im"
            else None
        )

        action = "added" if event_type == "reaction_added" else "removed"
        content = f"[reaction] :{reaction}: {action} by <@{user}> on message {item_ts}"

        try:
            await self._handle_message(
                sender_id=user,
                chat_id=item_channel,
                content=content,
                metadata={
                    "slack": {
                        "event": event,
                        "event_type": event_type,
                        "thread_ts": thread_ts,
                        "channel_type": channel_type,
                        "reaction": {
                            "emoji": reaction,
                            "user": user,
                            "item_ts": item_ts,
                            "item_channel": item_channel,
                        },
                    },
                },
                session_key=session_key,
            )
        except Exception:
            logger.exception("Error handling Slack reaction event")
