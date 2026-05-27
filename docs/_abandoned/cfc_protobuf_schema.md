# CFC Protobuf Schema

## Scope

This document defines the protobuf contract for the CPK Companion FAP (CFC) RPC surface.

It is the canonical host/device wire contract for:

- service and method names
- request/response payloads
- status/error semantics
- compatibility and versioning rules

This schema is designed to match the CFC FAP contract in `docs/cfc_fap_specification.md`.

## Design principles

- One envelope style for all methods.
- Every response carries operation metadata (`op_id`, `elapsed_ms`).
- Explicit status enum values for machine-safe branching.
- Forward-compatible message evolution (`optional`/new fields with stable tags).
- Deterministic semantics over convenience.

## Package and file layout

Recommended source file:

- `proto/cfc.proto`

Recommended package names:

- `package cpk.cfc.v1;`
- language options as needed (`go_package`, `java_package`, etc.)

V1 must remain in `v1` namespace. Any breaking change requires a new namespace (for example `cpk.cfc.v2`).

## Service surface (V1)

```proto
syntax = "proto3";

package cpk.cfc.v1;

service CfcService {
  rpc SystemPing(SystemPingRequest) returns (SystemPingResponse);
  rpc SystemVersion(SystemVersionRequest) returns (SystemVersionResponse);
  rpc SystemCapabilities(SystemCapabilitiesRequest) returns (SystemCapabilitiesResponse);

  rpc GpioWrite(GpioWriteRequest) returns (GpioWriteResponse);
  rpc GpioRead(GpioReadRequest) returns (GpioReadResponse);
  rpc GpioPulse(GpioPulseRequest) returns (GpioPulseResponse);

  rpc UartExchange(UartExchangeRequest) returns (UartExchangeResponse);

  rpc MissionRunNamed(MissionRunNamedRequest) returns (MissionRunNamedResponse);
  rpc MissionGetStatus(MissionGetStatusRequest) returns (MissionGetStatusResponse);
  rpc MissionCancel(MissionCancelRequest) returns (MissionCancelResponse);

  rpc MetaHealth(MetaHealthRequest) returns (MetaHealthResponse);
  rpc MetaLastError(MetaLastErrorRequest) returns (MetaLastErrorResponse);
}
```

## Common enums and base fields

### StatusCode

```proto
enum StatusCode {
  STATUS_CODE_UNSPECIFIED = 0;
  OK = 1;
  ERROR_INVALID_ARGUMENT = 2;
  ERROR_UNSUPPORTED = 3;
  ERROR_TIMEOUT = 4;
  ERROR_BUSY = 5;
  ERROR_IO = 6;
  ERROR_LOCKED_STATE = 7;
  ERROR_INTERNAL = 8;
}
```

### Operation metadata contract

Every response message in V1 includes:

- `bool ok`
- `StatusCode status`
- `string message`
- `string op_id`
- `uint32 elapsed_ms`

Field numbers should be kept consistent across response messages where practical:

- `ok = 1`
- `status = 2`
- `message = 3`
- `op_id = 4`
- `elapsed_ms = 5`

## Message definitions

### System group

```proto
message SystemPingRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
}

message SystemPingResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  uint64 device_time_ms = 6;
}

message SystemVersionRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
}

message SystemVersionResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  string cfc_version = 6;
  string firmware_name = 7;
  string firmware_version = 8;
  uint32 schema_major = 9;
  uint32 schema_minor = 10;
}

message SystemCapabilitiesRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
}

message SystemCapabilitiesResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  repeated string capability = 6;
}
```

### GPIO group

```proto
enum GpioLevel {
  GPIO_LEVEL_UNSPECIFIED = 0;
  GPIO_LOW = 1;
  GPIO_HIGH = 2;
}

message GpioWriteRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  uint32 pin = 3;
  GpioLevel level = 4;
}

message GpioWriteResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
}

message GpioReadRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  uint32 pin = 3;
}

message GpioReadResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  GpioLevel level = 6;
}

message GpioPulseRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  uint32 pin = 3;
  GpioLevel active_level = 4;
  uint32 duration_ms = 5;
}

message GpioPulseResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
}
```

### UART group

```proto
message UartExchangeRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  uint32 uart_id = 3;
  uint32 baud = 4;
  bytes tx = 5;
  uint32 read_max_bytes = 6;
}

message UartExchangeResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  bytes rx = 6;
}
```

### Mission group

```proto
enum MissionState {
  MISSION_STATE_UNSPECIFIED = 0;
  MISSION_QUEUED = 1;
  MISSION_RUNNING = 2;
  MISSION_SUCCEEDED = 3;
  MISSION_FAILED = 4;
  MISSION_CANCELLED = 5;
}

message MissionRunNamedRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  string mission_name = 3;
  bytes payload = 4;
}

message MissionRunNamedResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  string mission_id = 6;
  MissionState state = 7;
}

message MissionGetStatusRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  string mission_id = 3;
}

message MissionGetStatusResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  string mission_id = 6;
  MissionState state = 7;
  uint32 progress_pct = 8;
}

message MissionCancelRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
  string mission_id = 3;
}

message MissionCancelResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  string mission_id = 6;
  MissionState state = 7;
}
```

### Meta group

```proto
message MetaHealthRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
}

message MetaHealthResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  uint32 queue_depth = 6;
  bool single_flight_busy = 7;
  uint32 uptime_s = 8;
}

message MetaLastErrorRequest {
  string op_id = 1;
  uint32 timeout_ms = 2;
}

message MetaLastErrorResponse {
  bool ok = 1;
  StatusCode status = 2;
  string message = 3;
  string op_id = 4;
  uint32 elapsed_ms = 5;
  StatusCode last_status = 6;
  string last_error_message = 7;
  string last_error_op_id = 8;
}
```

## Host mapping guidance

`flipper_mcp/modules/cfc/module.py` should map MCP tools to RPC methods as follows:

- `flipper_cfc_ping` -> `SystemPing`
- `flipper_cfc_version` -> `SystemVersion`
- `flipper_cfc_gpio_write` -> `GpioWrite`
- `flipper_cfc_gpio_read` -> `GpioRead`
- `flipper_cfc_gpio_pulse` -> `GpioPulse`
- `flipper_cfc_uart_exchange` -> `UartExchange`
- `flipper_cfc_mission_run` -> `MissionRunNamed`
- `flipper_cfc_mission_status` -> `MissionGetStatus`
- `flipper_cfc_mission_cancel` -> `MissionCancel`
- `flipper_cfc_health` -> `MetaHealth`

## Validation rules

V1 host-side validators should enforce:

- `timeout_ms` in a bounded range (for example `1..60000`).
- non-empty `op_id` for tracing.
- bounded `tx`/`rx` byte lengths.
- allowed mission name charset (`[a-zA-Z0-9._-]`).
- supported GPIO pin list based on capability report.

Violations return `ERROR_INVALID_ARGUMENT`.

## Versioning and compatibility policy

### Backward-compatible changes (allowed within v1)

- adding new `optional` or repeated fields with new tag numbers
- adding new RPC methods that do not alter existing methods
- adding new enum values at the end of an enum

### Breaking changes (require v2 namespace)

- changing field numbers
- changing existing field wire types
- changing method request/response message types
- changing semantics in a way that breaks existing callers

### Reserved tags and names

When removing fields, reserve removed tags/names:

```proto
message Example {
  reserved 9, 10;
  reserved "old_field", "legacy_value";
}
```

## Golden test cases

At minimum, verify these over real transport:

- Ping/version/health success path.
- Invalid argument for each method family.
- Busy-state response under forced single-flight contention.
- Timeout handling for long mission and UART waits.
- Unknown capability or unsupported operation returns `ERROR_UNSUPPORTED`.

## References

- `docs/cfc_fap_specification.md`
- `docs/protobuf_rpc.md`
- `flipper_mcp/core/protobuf_rpc.py`
- https://github.com/flipperdevices/flipperzero-protobuf
- https://protobuf.dev/programming-guides/proto3/
