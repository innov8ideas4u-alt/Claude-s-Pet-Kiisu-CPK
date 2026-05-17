# Day 1 BLE Capability Probe — Decision Document

**Date:** 2026-04-30
**Hardware:** AmorPoee (Kiisu V4B + Momentum mntm-dev), MAC `80:E1:26:EA:3D:5A`
**Adapter:** OnTopDesk built-in MB Bluetooth
**Library:** bleak 3.0.1 on Python 3.13.7 (Windows WinRT backend)
**Branch:** `experiment/ble-capability-proof`

---

## TL;DR

**The strategic question is answered: BLE is RPC-only on Flipper. The CLI text-shell is not exposed over Bluetooth.**

This means JS missions (`mission_freq_analyzer`, `mission_rf_rssi_log`) — which currently launch via `js /ext/...` through the firmware CLI — **cannot run over BLE without architecture changes**. Pure-RPC missions (`mission_nfc_capture`, storage operations, device info) work fine.

We answered this in one evening instead of discovering it on Day 5 after building a phone relay. Win.

---

## Probe results

| # | Question | Status | Finding |
|---|---|---|---|
| Q0 | Does AmorPoee advertise over BLE? | ✅ PASS | Discovered at -72 dBm. Required BT toggle on Kiisu screen to start. |
| Q1 | Can we connect & enumerate GATT? | ✅ PASS | All 4 expected Flipper characteristics present on Momentum mntm-dev. UUIDs match research. |
| Q2 | Can we send a protobuf ping? | ✅ PASS | PONG echoed back instantly. **No `start_rpc_session` handshake needed over BLE** — channel comes up RPC-ready. |
| Q3 | Can we do storage R/W? | ⚠️ PARTIAL | Channel works (ping works); OVERFLOW reports 256KB credit and fires correctly; backpressure functional. **High-level `storage_write` returns False** — software bug in chunked-message ack handling, not a BLE limitation. Deferred. |
| Q4 | Is CLI prompt accessible over BLE? | ❌ **FAIL** | Sent `stop_session` RPC, received 5-byte protobuf ack, then **dead silence**. CR press → no prompt. `help\\r` → no listing. **Zero printable ASCII produced.** |
| Q5 | Can we run `js /ext/...`? | ⏭️ SKIPPED | Q4 made it moot. |
| Q6 | Can we recover RPC after CLI? | ⏭️ SKIPPED | Q4 made it moot. |

---

## Critical findings, plain English

### Finding 1 — UUID labels in last chat were perspective-flipped

The "TX" and "RX" labels in research were from the *firmware writer's* point of view, not ours. From the GATT property dump:

| UUID | Properties | Direction (from our POV) |
|---|---|---|
| `19ed82ae-...62fe0000` | `read, write, write-without-response` | **WE WRITE HERE** (TO_FLIPPER) |
| `19ed82ae-...61fe0000` | `read, indicate` | **FLIPPER WRITES TO US** (FROM_FLIPPER) |
| `19ed82ae-...63fe0000` | `notify, read` | OVERFLOW — Flipper announces RX-buffer free space |
| `19ed82ae-...64fe0000` | `notify, read, write` | RPC_STATE — bidirectional state flag |

Note: read direction uses **indicate** (per-packet ACK), not notify. Bleak handles this transparently.

### Finding 2 — OVERFLOW protocol confirmed

The OVERFLOW characteristic carries a little-endian uint32 = "bytes the Flipper is ready to receive." We seed initial credit by reading the characteristic on connect (returned 262144 = 256 KB). Subsequent notifications update the credit. We must pace writes against this number.

For reference: Q3 sent 1 KB into a 256 KB buffer — backpressure was not the bottleneck on this test, but the mechanism is now proven and instrumented.

### Finding 3 — MTU is variable

First connection: MTU=23 (default, 20-byte payload). Second connection: MTU=414 briefly. Bleak/Windows BT stack negotiates upward when the link is stable. **Plan for 20-byte fragments worst-case but expect better.**

### Finding 4 — Flipper rate-limits BLE re-advertising

After every disconnect, AmorPoee stops advertising for 30-90 seconds. Sometimes a screen-side BT toggle is needed to re-prime. This will be a UX consideration in the eventual transport.

### Finding 5 — Q4's silence is definitive

Sending `stop_session` produced a 5-byte protobuf acknowledgment (`0408642200`) and then nothing. Compare to USB, where the same command produces ~500 ms of "Welcome to Flipper Zero" banner + `>: ` prompt within 250 ms. The BLE serial-RPC characteristic is a sealed protobuf channel — the firmware never wires the CLI text-shell to it.

---

## Architectural implications

### What works over BLE today
- Every `_with_wire_lock` RPC method in `protobuf_rpc.py`: ping, system_*, storage_*, app_start, app_load, gui_*, etc.
- Pure-RPC missions: `mission_nfc_capture`, `mission_subghz_capture`
- Status/health checks, device info, file listings

### What does NOT work over BLE today
- Anything routed through `cli_command()`
- `JsRunnerModule._run()` — the entire JS launch pipeline
- `mission_freq_analyzer`, `mission_rf_rssi_log` — both depend on JS launching
- `_try_launch_js` cascade in `library.py` — the CLI fallback path

### Mission impact on the CompTIA roadmap
- TPMS sniffing (planned, JS-based) — would need rewrite or stay USB
- POCSAG decoder (planned) — depends on implementation choice
- Smart-meter capture — same
- Mifare clone demo — pure RPC, **works over BLE today**

---

## Architecture options (ranked)

### Option 1 — Split-mode (recommended starting point)
**Effort:** ~1 day. **Risk:** low.

Tag every mission with capability metadata:
```python
class Mission:
    requires_cli: bool         # True for JS missions
    requires_rpc: bool = True  # ~always True
    safe_over_ble: bool        # derived from requires_cli
    expected_duration_s: int
```

`BLERelayTransport` (or future `BLEDirectTransport`) refuses to launch missions with `requires_cli=True`, returns clear error message. USB transport launches everything.

**CompTIA demo:** "Kiisu off-cable doing NFC capture from across the classroom" — already a strong demo. RF missions still cabled.

### Option 2 — `app_start` RPC route (high leverage if it works)
**Effort:** 1–2 days probe + integration. **Risk:** medium-high.

The Flipper firmware exposes `application_start_request` as an RPC. JS scripts run inside a `.fap` (JS Runner). If we can `app_start("JS Runner", args=path_to_script)` and have the script execute, we bypass the CLI entirely and **every JS mission works over BLE**.

**Test plan for Day 2:**
1. Probe `app_start("JS Runner", args="/ext/apps_data/mcp_missions/test.js")` over USB first (known-good baseline)
2. If it runs the script: same probe over BLE
3. If both pass: refactor `JsRunnerModule._run()` to prefer `app_start` over `cli_command` when transport is BLE
4. If app_start doesn't accept the JS path argument cleanly, fall back to Option 1

### Option 3 — Custom Flipper FAP launcher
**Effort:** 1–2 weeks. **Risk:** high (new toolchain).

Write a tiny C app on Flipper that listens on a custom GATT service or registers as an RPC plugin, accepts JS path, launches it. Most flexible long-term but big learning curve.

### Option 4 — Rewrite JS missions as pure-RPC
**Effort:** per-mission, weeks total. **Risk:** may not be possible — some signal-processing primitives only exist in the JS layer.

---

## Day 2 recommended path

1. **Pin Q3 software bug** (~1 hr) — the storage_write returning False is a chunked-message ack issue (almost certainly indicate-vs-notify timing in our receive_exact reassembly). Fix in the BLE probe transport, then `BLERelayTransport`/`BLEDirectTransport` inherits a working pattern.
2. **Probe `app_start` JS launching over USB first** (~1 hr) — if `app_start("JS Runner", args="...")` runs scripts on USB, it almost certainly will over BLE too.
3. **If Option 2 works:** great, JS missions get BLE. If not: ship Option 1, plan Option 2 as a follow-up.
4. **Mission capability metadata** (~2 hr regardless) — must be added either way; gates Option 1 and is good hygiene.

---

## What we're NOT doing

- Not building `BLERelayTransport` yet. Architecture choice (Option 1 vs 2) drives the transport's contract.
- Not adding phone-as-relay tonight — laptop-direct probing is the cleanest place to learn the BLE channel, and we've now learned what we need.
- Not pivoting to Kotlin Android relay yet — Option 2 might make Android relay unnecessary entirely (RPC-only relay is much simpler than CLI-tunneling).

---

## Files in this experiment

| File | Purpose |
|---|---|
| `experiments/ble_probe/probe_q0_q1.py` | Q0/Q1 — discovery + GATT enumeration |
| `experiments/ble_probe/probe_q2.py` | Q2 — protobuf ping over BLE |
| `experiments/ble_probe/probe_q3.py` | Q3v1 — storage round-trip without OVERFLOW |
| `experiments/ble_probe/probe_q3_v2.py` | Q3v2 — storage round-trip with OVERFLOW backpressure |
| `experiments/ble_probe/probe_q4.py` | Q4 — CLI prompt reachability test (the strategic one) |
| `experiments/ble_probe/reconnect_check.py` | utility — quick scan + enumerate, used during debugging |
| `experiments/ble_probe/PROBE_RESULTS.md` | raw probe output logs |
| `experiments/ble_probe/DAY1_DECISION.md` | this file |

All probes are **deliberately throwaway code**. They prove the channel; they are not the eventual transport.

---

## Acknowledgements

GPT-5.5-Pro's review (`C:\Temp\llmdr_review_gpt55.md`) called Q4 the "biggest technical miss" before any code was written. **They were right.** Probing capability before architecture saved us 4–5 days of phone-relay work that would have hit the same wall.
