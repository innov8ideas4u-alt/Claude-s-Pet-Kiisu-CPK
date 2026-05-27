# Claude ↔ Kiisu4b on Momentum: Additional Research Brief (2026-05-27)

## Purpose
This note adds high-value external references and implementation guidance for building a reliable Claude-driven control loop for a Kiisu4b running Momentum firmware.

## 1) Control-plane architecture that is most likely to work

### Recommended split
- Host orchestrator (Claude tool layer): plans tasks, validates state, logs outcomes.
- RPC transport client on host: speaks Flipper protobuf RPC over serial.
- Optional on-device JS mission layer: executes short deterministic device-side operations.

### Why this split
- RPC gives direct control of app start/exit, storage, GUI input, and lock state.
- JS modules can simplify timing-sensitive GPIO/serial logic on-device.
- Combining both yields a robust “host supervises, device executes” model.

## 2) Proven RPC session pattern (important)

Across references, the reliable pattern is:
1. Open serial port and clear prompt.
2. Send `start_rpc_session`.
3. Exchange length-delimited protobuf `Main` envelopes.
4. Check status for each command (`command_status`, continuation via `has_next`).
5. Stop session cleanly when done.

Practical implication: your Claude control adapter should enforce this lifecycle and reject command dispatch when session state is not healthy.

## 3) Python control surface you can leverage quickly

`flipperzero_protobuf_py` exposes methods that map directly to orchestration needs:
- Session: `start_rpc_session()`, `rpc_stop_session()`
- Health/version: `rpc_system_ping()`, `rpc_protobuf_version()`
- App control: `rpc_app_start()`, `rpc_app_load_file()`, `rpc_app_exit()`
- UI input: `rpc_gui_send_input(...)`
- Device status: `rpc_lock_status()`
- Storage: `rpc_storage_list()`, `rpc_read()`, `rpc_write()`

Practical implication: implement your first Claude adapter around these methods before attempting lower-level custom protobuf wiring.

## 4) JS runtime capabilities that help Kiisu workflows

Flipper JS module docs and community firmware notes point to useful blocks:
- `serial` for UART interactions
- `gpio` for pin-level control, interrupts/events, and PWM on supported pins
- `storage` for local mission config and logging
- `event_loop` for deterministic event-driven behavior

Important GPIO details:
- `event_loop` must be loaded before `gpio`
- pin mode must be explicitly initialized (`direction`, `outMode` / `inMode` / `edge`)
- PWM requires capability checks (`isPwmSupported()`)

Practical implication: keep JS missions small, stateless, and parameterized by files/args written over RPC.

## 5) Momentum-specific operational notes

Momentum docs/wiki reinforce useful deployment considerations:
- Momentum has protocol and interface settings centralized in MNTM app.
- Release notes include fixes touching CLI/qFlipper and serial behavior; version pinning matters.
- Some install/update failures are SD-card/host state related; keep recovery steps in your runbook.

Practical implication: when debugging Claude control failures, include firmware version + channel (mainline/dev) + SD health in telemetry.

## 6) Suggested implementation contract for Claude tooling

### Host adapter contract
- `connect()`
- `start_session()`
- `assert_ready()` (ping + protobuf version + lock check)
- `run_rpc(op, args)`
- `run_js(script_path, wait, cleanup)`
- `stop_session()`

### Safety/reliability guards
- single-flight command queue per device
- operation timeouts + retries only for idempotent ops
- structured command logs (command_id, status, latency)
- always send app-exit/back cleanup for mission-style runs

### Data flow pattern
1. Claude chooses action.
2. Host writes mission config/file (if needed).
3. Host launches app/script.
4. Host waits/polls logs.
5. Host performs cleanup and returns structured result.

## 7) Gaps still worth filling next

- Device-specific Kiisu4b pin mapping and electrical constraints as a canonical profile.
- A tested matrix of Momentum versions vs RPC/protobuf compatibility.
- Deterministic JS mission templates for your top recurring tasks.
- Fault-injection tests: cable disconnect, lockscreen present, stale app state, SD read/write faults.

## 8) Source links (for deeper extraction into NotebookLM)

- Flipper protobuf schema repo: https://github.com/flipperdevices/flipperzero-protobuf
- Python protobuf bindings: https://github.com/flipperdevices/flipperzero_protobuf_py
- Python API docs page (doc.md): https://github.com/flipperdevices/flipperzero_protobuf_py/blob/main/doc.md
- Flipper JS docs index: https://developer.flipper.net/flipperzero/doxygen/js.html
- Flipper JS GPIO module docs: https://developer.flipper.net/flipperzero/doxygen/js_gpio.html
- Momentum firmware repo: https://github.com/Next-Flip/Momentum-Firmware
- Momentum wiki home (GitHub): https://github.com/Next-Flip/Momentum-Firmware/wiki
- Momentum wiki site: https://momentum-fw.dev/wiki
- qFlipper protobuf RPC PR history: https://github.com/flipperdevices/qFlipper/pull/34
- Rust reference transport notes (community): https://github.com/elijah629/flipper-rpc

## 9) Quick “first milestone” checklist

- Build a minimal Python adapter using `flipperzero_protobuf_py`.
- Enforce session lifecycle and status checks.
- Add one JS mission (GPIO or serial) with file-based params.
- Implement log + timeout + cleanup policy.
- Test against your current Momentum build and freeze known-good versions.
