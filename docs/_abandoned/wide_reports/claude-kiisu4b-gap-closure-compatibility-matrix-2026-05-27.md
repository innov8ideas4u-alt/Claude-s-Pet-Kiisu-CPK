# Claude ↔ Kiisu4b Gap Closure: Compatibility Matrix and Validation Plan (2026-05-27)

## Why this file exists
This closes the second major gap: known-good compatibility combinations across firmware, protobuf schema, host client stack, and operating environment.

## 1) Matrix dimensions to track

Track and lock these dimensions per test row:

- Momentum firmware version/channel
- Flipper protobuf schema commit/branch
- Host client implementation (Python/Rust/custom)
- Host OS and serial driver stack
- RPC feature subset used
- JS mission subset used
- Pass/fail and failure signature

## 2) Compatibility matrix template

| Matrix ID | Momentum Version | Protobuf Schema Ref | Host Client | Host OS | Transport | Core RPC Tests | JS Mission Tests | Result | Notes |
|---|---|---|---|---|---|---|---|---|---|
| M001 | Momentum mntm-dev (AmorPoee baseline) | flipperzero-protobuf dev branch (exact commit TBD) | cpk flipper_mcp ProtobufRPC (pyproject cpk 0.4.0) | Windows 11 | USB serial | PASS (connect/session/ping/protobuf/storage/app/gui) | PASS (`flipper_js_run` ping + multi-call mission) | CANDIDATE_KNOWN_GOOD | Requires exact firmware/protobuf commit capture |
| M002 | TBD | dev@TBD | flipper-rpc@TBD | Windows 11 | USB serial | TBD | TBD | TBD | alt client |
| M003 | TBD | dev@TBD | custom adapter@TBD | Windows 11 | USB serial | TBD | TBD | TBD | target stack |
| M004 | TBD | dev@TBD | custom adapter@TBD | Linux TBD | USB serial | TBD | TBD | TBD | portability check |

## 3) Minimal compatibility test suite

Run these in order, fail fast on first break:

1. Connect/disconnect
2. Start/stop RPC session
3. Ping + protobuf version
4. Storage list/read/write roundtrip
5. App start/load/exit cycle
6. GUI input injection cycle
7. JS mission run + log retrieval + cleanup
8. Re-run suite 3x for stability

## 4) Version pinning policy

- Pin Momentum version for each release of your adapter.
- Pin protobuf schema ref used to generate/parity-check client behavior.
- Pin Python package versions if using `flipperzero_protobuf_py`.
- Record hash/version in every test report.

## 5) Failure signatures to classify

Standardize these buckets:

- `SERIAL_PORT_ACCESS_DENIED`
- `RPC_SESSION_START_FAILED`
- `PROTOBUF_VERSION_MISMATCH`
- `COMMAND_STATUS_ERROR`
- `HAS_NEXT_DRAIN_INCOMPLETE`
- `APP_CANNOT_START`
- `LOCKED_DESKTOP_BLOCK`
- `STORAGE_TIMEOUT_OR_IO`
- `MISSION_TIMEOUT`

## 6) Pass criteria for "known-good"

A matrix row is known-good only if:

- Full minimal suite passes 3 consecutive runs.
- No unclassified error signatures.
- Median latency and p95 latency recorded for key operations.
- Session cleanup always succeeds.

## 6b) First baseline row evidence trail (M001)

Evidence in this repo that supports M001 as a candidate-known-good row:

- `docs/decisions/DAY2_APP_RPC_AND_INPUT.md`: validated app launch path on mntm-dev using full FAP path and successful mission loop.
- `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md`: validated storage write fix and successful `flipper_js_run` mission execution.
- `docs/decisions/DAY7_LIVE_FIRE_MORNING_KIT.md`: 4/6 live-fire missions passed on AmorPoee mntm-dev, including JS mission and Sub-GHz scan workflows.
- `docs/SETUP_REQUIREMENTS_mntm-dev.md`: required lockscreen/RPC settings captured for repeatability.

Promotion rule from CANDIDATE_KNOWN_GOOD to KNOWN_GOOD:

- Capture exact Momentum build identifier and protobuf schema commit hash.
- Re-run minimal suite 3 consecutive times with zero unclassified errors.
- Record median and p95 latency for ping, storage roundtrip, app start, and JS mission execution.

## 7) Immediate first fill recommendation

Fill these first to de-risk quickly:

- One known-good Momentum mainline build on your primary host OS.
- One known-good dev build on same OS.
- One alternate client implementation row (Python or Rust) for differential diagnosis.

## 8) Reporting format (store with each run)

```json
{
  "matrix_id": "M001",
  "momentum_version": "TBD",
  "protobuf_ref": "dev@TBD",
  "host_client": "flipperzero_protobuf_py@TBD",
  "host_os": "Windows 11",
  "tests": {
    "session_lifecycle": "pass",
    "ping_version": "pass",
    "storage_roundtrip": "pass",
    "app_cycle": "pass",
    "gui_input": "pass",
    "js_mission": "pass"
  },
  "runs": 3,
  "status": "known_good",
  "errors": []
}
```

## 8b) Pre-filled M001 run template (candidate baseline)

```json
{
  "matrix_id": "M001",
  "device": "AmorPoee / Kiisu V4B",
  "momentum_version": "mntm-dev (exact build id TBD)",
  "protobuf_ref": "flipperzero-protobuf dev (exact commit TBD)",
  "host_client": "cpk flipper_mcp ProtobufRPC (cpk 0.4.0)",
  "host_os": "Windows 11",
  "transport": "USB serial",
  "suite": {
    "connect_disconnect": "pass",
    "session_lifecycle": "pass",
    "ping_protobuf_version": "pass",
    "storage_roundtrip": "pass",
    "app_cycle": "pass",
    "gui_input_cycle": "pass",
    "js_mission_run_and_cleanup": "pass"
  },
  "runs": 3,
  "latency_ms": {
    "ping": {"median": "TBD", "p95": "TBD"},
    "storage_roundtrip": {"median": "TBD", "p95": "TBD"},
    "app_start": {"median": "TBD", "p95": "TBD"},
    "js_mission": {"median": "TBD", "p95": "TBD"}
  },
  "status": "CANDIDATE_KNOWN_GOOD",
  "errors": [],
  "evidence_refs": [
    "docs/decisions/DAY2_APP_RPC_AND_INPUT.md",
    "docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md",
    "docs/decisions/DAY7_LIVE_FIRE_MORNING_KIT.md",
    "docs/SETUP_REQUIREMENTS_mntm-dev.md"
  ],
  "promotion_checks": {
    "exact_firmware_id_captured": false,
    "exact_protobuf_commit_captured": false,
    "three_consecutive_clean_runs": false,
    "latency_median_p95_filled": false
  }
}
```

## Sources

- https://github.com/flipperdevices/flipperzero-protobuf
- https://github.com/flipperdevices/flipperzero_protobuf_py
- https://github.com/elijah629/flipper-rpc
- https://github.com/Next-Flip/Momentum-Firmware/releases
- https://developer.flipper.net/flipperzero/doxygen/expansion_protocol.html
