"""Stream adapter — translates broadcaster events into channel-appropriate output.

Each inbound message gets a StreamAdapter that handles the response lifecycle:
- For channels with STREAMING + edit support (Telegram): sends a placeholder,
  accumulates tokens, edits periodically, sends final edit on "done".
- For channels without STREAMING: accumulates everything, sends once on "done".
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nerve.channels.base import (
    BaseChannel,
    ChannelCapability,
    OutboundMessage,
)

logger = logging.getLogger(__name__)


class StreamAdapter:
    """Translates StreamBroadcaster events into channel-specific output.

    Created per inbound message by the ChannelRouter, registered as a
    broadcaster listener, and torn down after the agent run completes.
    """

    def __init__(
        self,
        channel: BaseChannel,
        target: str,
        session_id: str,
    ):
        self.channel = channel
        self.target = target
        self.session_id = session_id

        # Streaming state
        self._buffer: str = ""
        self._placeholder_id: str | None = None
        self._last_edit: float = 0.0
        self._edit_lock = asyncio.Lock()

        # Tool label grouping (collapse consecutive same-tool calls)
        self._last_tool_name: str | None = None
        self._tool_run_count: int = 0
        self._tool_label_start: int = 0

        # Precompute capability checks
        self._supports_streaming = (
            ChannelCapability.STREAMING in channel.capabilities
        )
        self._supports_edit = channel.constraints.supports_message_edit
        self._edit_interval = channel.constraints.min_edit_interval
        self._max_len = channel.constraints.max_message_length
        self._supports_interactive = (
            ChannelCapability.INTERACTIVE in channel.capabilities
        )

    async def initialize(self) -> None:
        """Set up streaming — send placeholder if appropriate."""
        if self._supports_streaming and self._supports_edit:
            self._placeholder_id = await self.channel.send_placeholder(
                self.target, self.session_id,
            )

    async def on_event(self, session_id: str, message: dict[str, Any]) -> None:
        """Handle a broadcaster event. Registered as a broadcaster callback."""
        msg_type = message.get("type")

        if msg_type == "token":
            await self._handle_token(message.get("content", ""))

        elif msg_type == "tool_use":
            tool_name = message.get("tool", "unknown")
            if self._supports_streaming and self._supports_edit:
                if tool_name == self._last_tool_name:
                    self._tool_run_count += 1
                    self._buffer = self._buffer[:self._tool_label_start]
                    self._buffer += f"\n`[tool: {tool_name}] x{self._tool_run_count}`\n"
                else:
                    self._last_tool_name = tool_name
                    self._tool_run_count = 1
                    self._tool_label_start = len(self._buffer)
                    self._buffer += f"\n`[tool: {tool_name}]`\n"

        elif msg_type == "done":
            await self._handle_done()

        elif msg_type == "error":
            await self._handle_error(message.get("error", "unknown"))

        elif msg_type == "interaction":
            await self._handle_interaction(message)

        # Other event types (thinking, tool_result, subagent_*, session_*,
        # file_changed, plan_update) are silently consumed for non-web channels.
        # The web channel handles those via its direct broadcaster callback.

    # ------------------------------------------------------------------ #
    #  Event handlers                                                      #
    # ------------------------------------------------------------------ #

    async def _handle_token(self, content: str) -> None:
        self._last_tool_name = None  # Reset tool grouping
        self._buffer += content

        if not self._supports_streaming or not self._supports_edit:
            return  # Accumulate for final send

        if not self._placeholder_id:
            return

        now = asyncio.get_event_loop().time()
        if now - self._last_edit < self._edit_interval:
            return  # Rate limited

        if not self._buffer.strip():
            return

        async with self._edit_lock:
            try:
                display = self._truncate(self._buffer)
                await self.channel.edit_message(
                    self.target, self._placeholder_id, display,
                )
                self._last_edit = now
            except Exception:
                pass  # Edit failures are non-fatal

    async def _handle_done(self) -> None:
        if self._supports_streaming and self._supports_edit and self._placeholder_id:
            # Final edit with complete text
            async with self._edit_lock:
                try:
                    text = self._truncate(self._buffer).strip() or "(no response)"
                    await self.channel.edit_message(
                        self.target, self._placeholder_id, text,
                    )
                except Exception:
                    pass
        elif not self._supports_streaming:
            # Non-streaming channel: send the accumulated response as one message
            if self._buffer.strip():
                formatted = self.channel.format_response(self._buffer)
                await self.channel.send(OutboundMessage(
                    target=self.target,
                    text=formatted,
                    session_id=self.session_id,
                ))

    async def _handle_error(self, error: str) -> None:
        error_text = f"Error: {error}"
        if self._supports_streaming and self._supports_edit and self._placeholder_id:
            async with self._edit_lock:
                try:
                    await self.channel.edit_message(
                        self.target, self._placeholder_id, error_text,
                    )
                except Exception:
                    pass
        else:
            await self.channel.send(OutboundMessage(
                target=self.target,
                text=error_text,
                session_id=self.session_id,
            ))

    async def _handle_interaction(self, message: dict[str, Any]) -> None:
        if self._supports_interactive:
            await self.channel.send_interaction(
                target=self.target,
                session_id=self.session_id,
                interaction_id=message.get("interaction_id", ""),
                interaction_type=message.get("interaction_type", ""),
                tool_name=message.get("tool_name", ""),
                tool_input=message.get("tool_input", {}),
            )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _truncate(self, text: str) -> str:
        """Truncate text to max message length if constrained."""
        if self._max_len and len(text) > self._max_len:
            return text[:self._max_len]
        return text
