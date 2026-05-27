# Claude ↔ Kiisu4b Gap Closure: Failure Runbooks and Recovery SOPs (2026-05-27)

## Why this file exists
This closes the third major gap: repeatable operational runbooks for common failures in host-driven control.

## 1) Runbook: serial port cannot open

### Symptoms
- Access denied / busy port
- Session cannot start

### Actions
1. Ensure no other tool is attached (qFlipper, WebUpdater, serial monitors).
2. Re-enumerate serial device and verify expected port.
3. Reconnect cable and retry once.
4. If still blocked, reboot host-side serial stack (or system reboot as last resort).

### Exit criteria
- Port opens and ping succeeds.

## 2) Runbook: RPC session start fails

### Symptoms
- `start_rpc_session` rejected or timeout

### Actions
1. Drain serial prompt and retry session start once.
2. Verify device not in conflicting app/update state.
3. Check desktop lock/app lock status and clear blocking UI/app.
4. Reconnect transport and retry session bootstrap.

### Exit criteria
- Session enters ready state and version check succeeds.

## 3) Runbook: desktop locked / UI blocked

### Symptoms
- App start/input commands fail due to lockscreen/active app state

### Actions
1. Query lockscreen status.
2. Unlock via canonical RPC path where supported.
3. If unsupported, send safe GUI input sequence to clear lockscreen.
4. Ensure no stale app remains open; send app-exit/back once.

### Exit criteria
- Lockscreen absent and app start succeeds.

## 4) Runbook: command status errors

### Symptoms
- Non-OK `command_status`

### Actions
1. Capture full command envelope metadata (command_id, op, status).
2. Classify into known signature bucket.
3. Retry only if operation is idempotent.
4. For non-idempotent ops, abort and surface structured error.

### Exit criteria
- Retry succeeds for idempotent op or deterministic failure captured.

## 5) Runbook: storage I/O timeouts or write failures

### Symptoms
- Write/read timeout, partial transfer, missing files

### Actions
1. Check `/ext` availability and storage info.
2. Validate destination directory existence.
3. Re-attempt with smaller payload if read/write chunking is used.
4. Verify SD health and free space.
5. Abort mission launch on unresolved storage errors.

### Exit criteria
- Read/write roundtrip passes with checksum/length verification.

## 6) Runbook: mission timeout

### Symptoms
- JS mission launched but no completion/log in timeout window

### Actions
1. Attempt graceful app cleanup (app-exit/back).
2. Read partial log tail for progress marker.
3. Classify as hung startup vs hung runtime.
4. If hung runtime repeats, disable mission in scheduler until fixed.

### Exit criteria
- Device returns to ready state and next health check passes.

## 7) Runbook: unexpected disconnect mid-operation

### Symptoms
- Serial read/write failures, broken stream

### Actions
1. Mark operation as interrupted.
2. Close transport handle.
3. Reconnect and rebuild session from scratch.
4. Reconcile operation status by verifying post-state on device.

### Exit criteria
- Session restored and post-state known-good.

## 8) Runbook: protobuf/schema mismatch

### Symptoms
- Decode failures, missing fields, version mismatch checks fail

### Actions
1. Query protobuf version from device.
2. Compare against pinned adapter expectations.
3. Switch to a known-good matrix row.
4. Regenerate/update client bindings only after controlled validation.

### Exit criteria
- Version parity confirmed or fallback matrix row in use.

## 9) Operational safety rules

- Single-flight command queue per device.
- Always cleanup app/UI state after mission runs.
- Never auto-retry non-idempotent operations.
- Every failure must emit a classified signature.
- Promote unknown signatures to backlog immediately.

## 10) Incident record template

```json
{
  "incident_id": "INC-YYYYMMDD-001",
  "timestamp_utc": "2026-05-27T12:00:00Z",
  "matrix_id": "M001",
  "signature": "RPC_SESSION_START_FAILED",
  "operation": "start_session",
  "attempts": 2,
  "resolution": "reconnect_and_rebootstrap",
  "status": "resolved"
}
```

## Sources

- https://github.com/flipperdevices/flipperzero_protobuf_py
- https://github.com/flipperdevices/flipperzero-protobuf
- https://github.com/Next-Flip/Momentum-Firmware/wiki/Frequently-Asked-Questions
- https://github.com/Next-Flip/Momentum-Firmware/releases
- https://developer.flipper.net/flipperzero/doxygen/expansion_protocol.html
