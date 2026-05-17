"""Connection health module for Flipper Zero MCP."""

from __future__ import annotations

import json
from typing import Any, List, Sequence

from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class ConnectionModule(FlipperModule):
    """
    Connection/health tools.

    These tools are designed to be safe and *always callable*, even when the
    Flipper is disconnected, so an assistant can accurately determine reality.
    """

    @property
    def name(self) -> str:
        return "connection"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Authoritative connection health + reconnect for Flipper Zero"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="flipper_connection_health",
                description=(
                    "Return authoritative Flipper connection health. "
                    "Use this before calling other tools, especially if the device may have disconnected."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "probe_rpc": {
                            "type": "boolean",
                            "description": "If true (default), perform a protobuf RPC ping to confirm RPC responsiveness.",
                            "default": True,
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="flipper_connection_reconnect",
                description=(
                    "Attempt to reconnect to the Flipper (disconnect/connect) and return updated connection health. "
                    "Safe to call if already connected."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "probe_rpc": {
                            "type": "boolean",
                            "description": "If true (default), perform a protobuf RPC ping after reconnect to confirm RPC responsiveness.",
                            "default": True,
                        }
                    },
                    "required": [],
                },
            ),
        ]

    async def handle_tool_call(self, tool_name: str, arguments: Any) -> Sequence[TextContent]:
        args = arguments or {}
        probe_rpc = bool(args.get("probe_rpc", True))

        if tool_name == "flipper_connection_health":
            payload = await self._health(probe_rpc=probe_rpc)
            return [TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True))]

        if tool_name == "flipper_connection_reconnect":
            payload = await self._reconnect_and_health(probe_rpc=probe_rpc)
            return [TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True))]

        return [TextContent(type="text", text=f"❌ Error: Unknown connection tool '{tool_name}'")]

    async def _health(self, probe_rpc: bool) -> dict[str, Any]:
        try:
            return await self.flipper.get_connection_health(probe_rpc=probe_rpc)
        except Exception as e:
            # Even health should never crash.
            return {
                "timestamp": None,
                "connected": False,
                "transport_connected": False,
                "rpc_responsive": False if probe_rpc else None,
                "transport": {"type": None},
                "stub_mode": bool(getattr(self.flipper, "stub_mode", False)),
                "last_error": str(e),
            }

    async def _reconnect_and_health(self, probe_rpc: bool) -> dict[str, Any]:
        # In stub mode, reconnect is meaningless; still return health.
        if bool(getattr(self.flipper, "stub_mode", False)):
            h = await self._health(probe_rpc=probe_rpc)
            h["reconnect_attempted"] = False
            h["reconnect_result"] = "stub_mode"
            return h

        attempted = True
        ok = False
        err: str | None = None

        try:
            try:
                await self.flipper.disconnect()
            except Exception:
                pass
            ok = bool(await self.flipper.connect())
        except Exception as e:
            err = str(e)
            ok = False

        h = await self._health(probe_rpc=probe_rpc)
        h["reconnect_attempted"] = attempted
        h["reconnect_ok"] = ok
        if err:
            h["reconnect_error"] = err
        return h





