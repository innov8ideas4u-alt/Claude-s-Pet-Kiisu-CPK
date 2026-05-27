# CFC FAP Specification

## Scope

This document defines the implementation contract for the CPK Companion FAP (CFC): an on-device Flipper app that exposes a stable RPC-facing control surface for Claude-driven missions.

Primary objective:

- Provide deterministic, first-class operations for mission-critical primitives that are fragile through UI-driving alone.

## Goals

- Replace UI-navigation-heavy mission paths with explicit RPC verbs where possible.
- Preserve existing MCP transport and session model in `flipper_mcp`.
- Keep behavior deterministic, bounded, and auditable.
- Work on Momentum `mntm-dev` first, then broaden compatibility.

## Non-goals (V1)

- Replacing every stock app feature.
- Background daemon behavior outside normal app lifecycle.
- Any hidden or implicit retry loops for non-idempotent operations.

## System context

Host side:

- `flipper_mcp` receives MCP tool calls and sends protobuf RPC over transport.
- Current RPC implementation and framing behavior are in `flipper_mcp/core/protobuf_rpc.py`.

Device side:

- CFC is a `.fap` built with `ufbt` and launched like other external apps.
- CFC registers RPC handlers for a CFC-specific message surface.

## Runtime model

1. Host ensures session readiness.
2. Host launches CFC app.
3. Host sends CFC RPC requests.
4. CFC executes operation and returns structured result.
5. Host performs cleanup and logs mission outcome.

## V1 operation groups

### 1) system

- `system.ping`
- `system.version`
- `system.capabilities`

### 2) gpio

- `gpio.write`
- `gpio.read`
- `gpio.pulse`

### 3) uart

- `uart.exchange`

### 4) mission

- `mission.run_named`
- `mission.get_status`
- `mission.cancel`

### 5) meta

- `meta.health`
- `meta.last_error`

## Determinism and safety requirements

- Single-flight command execution within CFC.
- Explicit timeout on every operation.
- No automatic retries for non-idempotent operations.
- All errors must return a classified status code and message.
- Every operation response must include operation id and elapsed time.

## Error contract

All responses include:

- `ok` boolean
- `status` enum
- `message` string
- `op_id` string
- `elapsed_ms` uint32

Minimum status enum set:

- `OK`
- `ERROR_INVALID_ARGUMENT`
- `ERROR_UNSUPPORTED`
- `ERROR_TIMEOUT`
- `ERROR_BUSY`
- `ERROR_IO`
- `ERROR_LOCKED_STATE`
- `ERROR_INTERNAL`

## Host integration contract

`flipper_mcp/modules/cfc/module.py` will map MCP tools to CFC RPCs:

- `flipper_cfc_ping`
- `flipper_cfc_version`
- `flipper_cfc_gpio_write`
- `flipper_cfc_gpio_read`
- `flipper_cfc_gpio_pulse`
- `flipper_cfc_uart_exchange`
- `flipper_cfc_mission_run`
- `flipper_cfc_mission_status`
- `flipper_cfc_mission_cancel`
- `flipper_cfc_health`

## V1 acceptance criteria

A V1 build is acceptable only when all are true:

- CFC launches reliably on target device/firmware row.
- `system.ping`, `system.version`, and `meta.health` pass 3 consecutive runs.
- `gpio.pulse` and `uart.exchange` pass with bounded latency and structured logs.
- `mission.run_named` and cancel/status lifecycle works without stale state.
- Failure cases return classified statuses, not generic failures.

## Required test vectors

- Locked desktop present before launch.
- Reconnect after transport drop.
- Operation timeout path.
- Invalid argument path for each verb.
- Busy-state rejection path.

## Open implementation decisions

- Exact app start name/path strategy for all target firmware rows.
- Whether mission operations execute inline or via short worker queue.
- Final capability bitset layout for `system.capabilities`.

## References

- `docs/decisions/DAY8_FAP_VISION.md`
- `docs/SETUP_REQUIREMENTS_mntm-dev.md`
- `docs/protobuf_rpc.md`
- `docs/KIISU_DEEP_KNOWLEDGE.md`
- https://github.com/flipperdevices/flipperzero-protobuf
- https://github.com/flipperdevices/flipperzero-firmware
- https://github.com/Next-Flip/Momentum-Firmware
- https://github.com/flipperdevices/flipper-ufbt
