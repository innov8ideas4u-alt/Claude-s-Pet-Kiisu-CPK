# API Reference

This document describes the public Python interfaces and runtime configuration points used by this project.

## CLI

### `flipper-mcp`

Installed via `pip install -e .` (entry point: `flipper_mcp.cli.main:main`).

### `python -m flipper_mcp.cli.main`

Runs the same entry point via Python module execution.

## Environment variables

The default server entry point (`flipper_mcp.core.server.main`) reads:

- `FLIPPER_TRANSPORT`: transport type (`auto` default, `usb`, `wifi`, `bluetooth`/`ble`)
- `FLIPPER_PORT`: override USB serial device path (only used when `FLIPPER_TRANSPORT=usb`)
- `FLIPPER_WIFI_HOST`: WiFi Dev Board host/IP (only used when `FLIPPER_TRANSPORT=wifi`, or when `auto` falls back to WiFi)
- `FLIPPER_WIFI_PORT`: WiFi Dev Board TCP port (only used when `FLIPPER_TRANSPORT=wifi`, or when `auto` falls back to WiFi)
- `FLIPPER_DEBUG`: enable protobuf RPC debug logs (`1`, `true`, `yes`, `on`)
- `FLIPPER_FORCE_START_RPC_SESSION`: always send the CLI command `start_rpc_session` before protobuf RPC (`1`, `true`, `yes`, `on`)
- `FLIPPER_MCP_ALLOW_STUB_MODE`: DEV ONLY. If enabled (`1`, `true`, `yes`, `on`), the server will route tools even without hardware (useful for module dev).

### Auto transport selection

When `FLIPPER_TRANSPORT` is unset (default `auto`):

- USB is tried first
- WiFi is only attempted if `FLIPPER_WIFI_HOST` is set

## Core API

### `flipper_mcp.core.server.FlipperMCPServer`

The MCP server implementation. It registers MCP handlers to:

- expose module tools via `list_tools`
- route tool calls via `call_tool` to the owning module

Key methods:

- `__init__(config: dict)`
- `async initialize()`
- `async run()`

### `flipper_mcp.core.registry.ModuleRegistry`

Discovers and manages modules.

Key methods:

- `discover_modules(search_paths: list[str] | None = None) -> None`
- `register_module(module_class: type[FlipperModule]) -> None`
- `async load_all() -> None`
- `async unload_all() -> None`
- `get_all_tools() -> list[Tool]`
- `async route_tool_call(tool_name: str, arguments: Any) -> Sequence[TextContent]`
- `get_module(name: str) -> FlipperModule | None`
- `list_modules() -> list[dict[str, Any]]`

### `flipper_mcp.core.flipper_client.FlipperClient`

High-level client injected into modules. Provides:

- `storage`: `FlipperStorage` wrapper
- `app`: `FlipperApp` wrapper (note: app launching is currently a stub that returns `True`)
- `rpc`: `FlipperRPC` instance once connected

Key methods:

- `async connect() -> bool`
- `async disconnect() -> None`
- `async get_device_info() -> dict[str, Any]`
- `async get_firmware_version() -> str`
- `async check_sd_card_available(force_check: bool = False) -> bool`

### `flipper_mcp.core.rpc.FlipperRPC`

RPC wrapper that prefers protobuf RPC (via `ProtobufRPC`) and falls back to simplified methods.

Key methods:

- `async get_device_info() -> dict[str, Any]`
- `async storage_list(path: str) -> list[str]`
- `async storage_read(path: str) -> str`
- `async storage_write(path: str, content: str) -> bool`
- `async storage_delete(path: str, recursive: bool = False) -> bool`
- `async storage_mkdir(path: str) -> bool`
- `async storage_info(path: str) -> dict[str, int] | None`

### `flipper_mcp.core.protobuf_rpc.ProtobufRPC`

Implements protobuf RPC using generated protobuf code in `flipper_mcp.core.protobuf_gen`.

This implementation expects nanopb-delimited framing:

- each message is encoded as `[varint length][protobuf bytes]`

See `docs/protobuf_rpc.md` for details.

## Transport API

### `flipper_mcp.core.transport.base.FlipperTransport`

Abstract interface implemented by all transports:

- `async connect() -> bool`
- `async disconnect() -> None`
- `async send(data: bytes) -> None`
- `async receive(timeout: float | None = None) -> bytes`
- `async receive_exact(n: int, timeout: float | None = None) -> bytes`
- `clear_receive_buffer() -> None`
- `async is_connected() -> bool`
- `get_name() -> str`

### Implementations

- `flipper_mcp.core.transport.usb.USBTransport`
- `flipper_mcp.core.transport.wifi.WiFiTransport`
- `flipper_mcp.core.transport.bluetooth.BluetoothTransport` (stub)

### Factory

- `flipper_mcp.core.transport.get_transport(transport_type: str, config: dict) -> FlipperTransport`

## Module API

### `flipper_mcp.modules.base_module.FlipperModule`

Base class for all modules.

Required:

- `name: str` (property)
- `version: str` (property)
- `description: str` (property)
- `get_tools() -> list[Tool]`
- `async handle_tool_call(tool_name: str, arguments: Any) -> Sequence[TextContent]`

Optional:

- `async on_load() -> None`
- `async on_unload() -> None`
- `get_dependencies() -> list[str]`
- `validate_environment() -> tuple[bool, str]`
- `requires_sd_card() -> bool`


