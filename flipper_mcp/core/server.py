"""Main Flipper MCP server implementation."""

import asyncio
import os
import sys
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .registry import ModuleRegistry
from .flipper_client import FlipperClient
from .transport import get_transport


class FlipperMCPServer:
    """
    Main MCP server for Flipper Zero.
    
    This is the core server that:
    - Handles MCP protocol communication
    - Manages module registry
    - Delegates all tool calls to modules
    - Maintains connection to Flipper Zero
    
    The server follows a modular architecture where all functionality
    is provided by modules, not hardcoded in the server itself.
    """
    
    def __init__(self, config: dict):
        """
        Initialize Flipper MCP server.
        
        Args:
            config: Server configuration dict
        """
        self.config = config
        self.app = Server("flipper-zero-mcp")
        self.flipper: FlipperClient | None = None
        self.registry: ModuleRegistry | None = None
        self.stub_mode = False  # Whether running in stub mode (no real hardware)
        
        # Register MCP handlers
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""
        always_allowed_tools = {
            # Allow assistants to determine reality and recover, even when disconnected.
            "flipper_connection_health",
            "flipper_connection_reconnect",
        }

        def _looks_like_disconnect(text: str) -> bool:
            t = (text or "").lower()
            needles = [
                "not connected",
                "usb not connected",
                "wifi not connected",
                "connection reset",
                "broken pipe",
                "device disconnected",
                "serialexception",
            ]
            return any(n in t for n in needles)

        async def _attempt_reconnect_once() -> bool:
            """
            Best-effort reconnect for mid-session drops.

            Returns True if reconnect succeeded, False otherwise.
            """
            if not self.flipper:
                return False
            if bool(getattr(self.flipper, "stub_mode", False)):
                return False
            try:
                try:
                    await self.flipper.disconnect()
                except Exception:
                    pass
                return bool(await self.flipper.connect())
            except Exception:
                return False
        
        @self.app.list_tools()
        async def list_tools() -> list[Tool]:
            """Return all tools from all modules."""
            if not self.registry:
                return []
            return self.registry.get_all_tools()
        
        @self.app.call_tool()
        async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
            """Route tool calls to appropriate module."""
            if name not in always_allowed_tools:
                if not self.flipper or not self.flipper.connected:
                    return [TextContent(
                        type="text",
                        text=(
                            "❌ Flipper Zero not connected.\n"
                            "Ensure the device is connected via USB, or set up WiFi and configure `FLIPPER_WIFI_HOST`.\n"
                            "Use `flipper_connection_health` to check status, then `flipper_connection_reconnect` to retry."
                        )
                    )]

            # Connection tools are allowed even if disconnected; still require flipper object.
            if not self.flipper:
                return [TextContent(
                    type="text",
                    text="❌ Flipper client is not initialized."
                )]

            # If transport is already known-bad, try to heal once before routing the tool.
            if name not in always_allowed_tools:
                try:
                    transport_ok = bool(await self.flipper.transport.is_connected())
                except Exception:
                    transport_ok = False
                if not transport_ok:
                    if await _attempt_reconnect_once():
                        # Continue to route tool call after reconnect.
                        pass
                    else:
                        return [TextContent(
                            type="text",
                            text=(
                                "❌ Flipper Zero disconnected. Auto-reconnect failed.\n"
                                "Call `flipper_connection_health` to verify status, then `flipper_connection_reconnect` to retry."
                            ),
                        )]
            
            try:
                result = await self.registry.route_tool_call(name, arguments)
            except Exception as e:
                # If routing itself threw, try one reconnect for non-connection tools.
                if name not in always_allowed_tools and _looks_like_disconnect(str(e)):
                    if await _attempt_reconnect_once():
                        try:
                            result = await self.registry.route_tool_call(name, arguments)
                        except Exception as e2:
                            return [TextContent(type="text", text=f"❌ Error executing tool: {str(e2)}")]
                    else:
                        return [TextContent(
                            type="text",
                            text=(
                                "❌ Flipper Zero disconnected. Auto-reconnect failed.\n"
                                "Call `flipper_connection_health` to verify status, then `flipper_connection_reconnect` to retry."
                            ),
                        )]
                else:
                    return [TextContent(type="text", text=f"❌ Error executing tool: {str(e)}")]

            # If module returned a disconnect-like error, attempt reconnect once and retry.
            if name not in always_allowed_tools and result:
                joined = "\n".join([getattr(x, "text", "") for x in result])
                if _looks_like_disconnect(joined):
                    if await _attempt_reconnect_once():
                        retry = await self.registry.route_tool_call(name, arguments)
                        return retry
                    return [TextContent(
                        type="text",
                        text=(
                            "❌ Flipper Zero disconnected. Auto-reconnect failed.\n"
                            "Call `flipper_connection_health` to verify status, then `flipper_connection_reconnect` to retry."
                        ),
                    )]

            return result
    
    async def initialize(self) -> None:
        """
        Initialize server and load modules.
        
        This:
        1. Creates transport layer
        2. Connects to Flipper Zero
        3. Discovers and loads modules
        """
        # IMPORTANT: When running under MCP stdio, stdout is reserved for JSON-RPC.
        # Send all human-readable logs to stderr.
        def _log(msg: str = "") -> None:
            try:
                print(msg, file=sys.stderr)
            except Exception:
                # Best-effort only (stdio may be closed by client).
                pass

        _log("=" * 60)
        _log("Flipper Zero MCP Server - Modular Architecture")
        _log("=" * 60)
        
        # Create transport based on config
        transport_type = self.config.get("transport", {}).get("type", "usb")
        
        try:
            transport = get_transport(transport_type, self.config)
        except ValueError as e:
            _log(f"\n❌ {e}")
            raise
        
        # Create Flipper client
        _log(f"\n🔌 Initializing {transport_type.upper()} transport...")
        self.flipper = FlipperClient(transport)
        
        # Try to connect
        _log("   Connecting to Flipper Zero...")
        if not await self.flipper.connect():
            _log("❌ Failed to connect to Flipper Zero")
            allow_stub = os.environ.get("FLIPPER_MCP_ALLOW_STUB_MODE", "").lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            if allow_stub:
                _log("\n⚠️  NOTE: Running in DEV STUB MODE (explicitly enabled).")
                _log("   In production, ensure Flipper Zero is connected via USB/WiFi/BLE")
                _log("   Set FLIPPER_MCP_ALLOW_STUB_MODE=0 to disable this behavior.")
                # Dev-only: allow tool routing even without hardware.
                self.flipper.connected = True
                self.stub_mode = True
            else:
                _log("\n⚠️  Not connected (stub mode disabled).")
                _log("   Only connection tools will be usable until a Flipper is connected.")
                self.flipper.connected = False
                self.stub_mode = False
        else:
            self.stub_mode = False

        # Publish stub mode to the client for health reporting.
        try:
            self.flipper.stub_mode = bool(self.stub_mode)
        except Exception:
            pass
        
        _log(
            ("✓ Connected to Flipper Zero" + (" (STUB MODE)" if self.stub_mode else ""))
            if self.flipper.connected
            else "⚠️  Flipper Zero not connected"
        )
        
        # Get device info
        try:
            device_info = await self.flipper.get_device_info()
            _log(f"   Device: {device_info.get('name', 'Unknown')}")
            _log(f"   Firmware: {device_info.get('firmware', 'Unknown')}")
        except Exception as e:
            _log(f"   (Could not get device info: {e})")
        
        # Initialize module registry
        _log("\n📦 Discovering modules...")
        self.registry = ModuleRegistry(self.flipper)
        self.registry.discover_modules()

        # Discover modules contributed by other installed packages (e.g. LLMDR)
        # via setuptools entry-points. This is what lets external projects
        # plug in without flipper-mcp importing them explicitly.
        self.registry.discover_entry_point_modules()
        
        # Load all modules
        _log("\n⚡ Loading modules...")
        await self.registry.load_all()
        
        # Print summary
        enabled_modules = [m for m in self.registry.modules.values() if m.enabled]
        total_tools = sum(len(m.get_tools()) for m in enabled_modules)
        
        _log(f"\n✓ {len(enabled_modules)} module(s) loaded, {total_tools} tool(s) available")
        
        if enabled_modules:
            _log("\n📋 Available modules:")
            for module in enabled_modules:
                tools = module.get_tools()
                _log(f"   • {module.name} v{module.version} - {len(tools)} tool(s)")
                _log(f"     {module.description}")
        else:
            _log("\n⚠️  No modules loaded. The server will have no tools available.")
        
        _log("\n" + "=" * 60)
        _log("🚀 Server ready! Waiting for MCP connections...")
        _log("=" * 60 + "\n")
    
    async def run(self) -> None:
        """
        Run the MCP server.
        
        This starts the MCP server and handles stdio communication.
        The server will run until interrupted.
        """
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.app.run(
                    read_stream,
                    write_stream,
                    self.app.create_initialization_options()
                )
        finally:
            # Cleanup
            if self.registry:
                await self.registry.unload_all()
            if self.flipper:
                await self.flipper.disconnect()
                try:
                    print("\n👋 Disconnected from Flipper Zero", file=sys.stderr)
                except Exception:
                    pass


async def main() -> None:
    """
    Entry point for Flipper MCP server.
    
    Loads configuration and starts the server.
    """
    # Default configuration
    # In production, this would be loaded from a config file
    env_transport = os.environ.get("FLIPPER_TRANSPORT")
    env_port = os.environ.get("FLIPPER_PORT")
    env_wifi_host = os.environ.get("FLIPPER_WIFI_HOST")
    env_wifi_port = os.environ.get("FLIPPER_WIFI_PORT")
    config = {
        "transport": {
            # Default to auto so a single MCP client configuration can work across USB and WiFi.
            # Auto selection policy: prefer USB, fall back to WiFi only if FLIPPER_WIFI_HOST is set.
            "type": env_transport or "auto",  # or "usb", "wifi", "bluetooth"
            "usb": {
                # Auto-detect if not specified; can be overridden via FLIPPER_PORT
                **({"port": env_port} if env_port else {}),
                "baudrate": 115200
            },
            "wifi": {
                # IMPORTANT: do not assume a WiFi host by default.
                # WiFi should only be considered "configured" when FLIPPER_WIFI_HOST is set.
                **({"host": env_wifi_host} if env_wifi_host else {}),
                "port": int(env_wifi_port) if env_wifi_port else 8080
            },
            "bluetooth": {
                "address": None  # Auto-discover
            }
        },
        "modules": {
            # Module-specific configuration can go here
        }
    }
    
    server = FlipperMCPServer(config)
    await server.initialize()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
