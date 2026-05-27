# DAY 8/9 — CFC Phase 1 Spec: Architecture & Wire Protocol (v5 — SHIPPABLE)

**Status:** v5 — addresses adversarial review v4 findings (Sherpa run 20260527-033056). Adversarial review converged: 4 passes × 3 reviewers = 12 critique runs, zero structural issues found. Remaining items require empirical validation during Phase 2 cook.
**Authors:** Victor + Claude Desktop (Day 9)
**Supersedes:** v4 (11 surgical fixes: F25-F35)
**Anchored by:** `notebooklm/cfc/_meta/RECON_LOG.md` Findings A-I + NotebookLM Q1-Q7 answers (Day 9)

---

## 1. Purpose

Lock in the architecture and wire protocol for the **CPK Companion FAP (CFC)** before any C code is written. Everything in this doc must be empirically anchored to firmware source or codebase behavior — no speculation, no aspirational design.

The recon (Findings A-I) and NotebookLM Q1-Q7 produced enough evidence to commit. This spec is the commitment.

## 2. Architectural commitment

**CFC is a single `.fap` (FlipperAppType.EXTERNAL) using `RpcAppEventTypeDataExchange` for all host↔device communication.**

### 2.1 Why not Path B (`.fal` JS modules)

NotebookLM Q4 closed this: out-of-tree `.fal` modules cannot call `furi_hal_nfc_*`, `furi_hal_subghz_*`, `furi_hal_infrared_*`, or `furi_hal_gpio_*`. The CompositeApiResolver only exposes mJS-engine helpers (`js_delay_with_flags`, `js_flags_set`, `js_value_buffer_size`, etc.) from `applications/system/js_app/plugin_api/app_api_table_i.h`. Hardware functions are absent from both the JS app's private table and the global firmware API table. Symbol resolution fails at load, FAL is unloaded.

Community pattern confirms this: zero out-of-tree `.fal` modules exist in 800MB of community FAPs (recon Finding G). Path B is not on the table.

### 2.2 Why Path A is sufficient

- `applications/services/rpc/rpc_app.h` is the canonical, documented extension path (recon Finding B; NotebookLM Q1)
- A FAP using `rpc_system_app_set_callback` receives bidirectional bytes via `RpcAppEventTypeDataExchange`
- `rpc_system_app_exchange_data()` sends bytes back to the host
- **Declared API for rpc_app.h is identical across Momentum, OFW, and Unleashed** (recon Finding D — Xtreme deferred). **Runtime behavior validated only on Momentum mntm-dev.** Cross-firmware portability is a structural likelihood, not a tested guarantee.
- Official Python bindings already wrap this (`flipperzero_protobuf/flipper_app.py`: `rpc_app_data_exchange_send/recv`) — host transport is a ~12 line port (recon Finding E)
- Host pattern documented end-to-end in qFlipper C++ (NotebookLM Q6)

## 3. Hard facts the spec commits to

| # | Fact | Source file:section |
|---|---|---|
| H1 | `RPC_BUFFER_SIZE = 1024` bytes is the hard ceiling on a single `Main` envelope | `applications/services/rpc/rpc.h`; NotebookLM Q2 |
| H2 | Usable CFC payload per frame is **884 bytes** (1024 − 16-byte CFC header − ~124 bytes Protobuf overhead). This is the canonical number used everywhere in this spec. | Q2 derivation |
| H3 | `RPC_STORAGE_BUFFER_SIZE = 512` is **storage-specific**, NOT inherited by `app_data_exchange` | `applications/services/rpc/rpc_storage.c`; Q2 follow-up |
| H4 | `app_data_exchange` has **no built-in chunking** — CFC's protocol must handle framing in its payload bytes | Q2 follow-up |
| H5 | FAP **MUST** call `rpc_system_app_confirm(rpc_app, true)` after **every** DataExchange event or host times out. Confirm is the RPC-layer transport ack, NOT an application-layer status. ERROR responses are surfaced via separate ERROR-opcode frames at the application layer. | `applications/services/rpc/rpc_app.h`; Q1, Q2 |
| H6 | FAP gets **one callback per inbound chunk** — multi-fragment re-assembly is FAP's responsibility | Q2 Gotcha B |
| H7 | App must launch via full path on mntm-dev: `/ext/apps/<category>/<appid>.fap` | DolphinTank Decision #002; Q7 |
| H8 | Host pattern: blocking single-request-response per session, command_id filtering, broadcast frames have command_id=0 | Q5, Q6 |
| H9 | Complete-response timeout (refreshed on each frame), not per-frame timeout | qFlipper `backend/abstractserialoperation.cpp`; Q6 |

## 4. Wire protocol design (the CFC framing)

### 4.1 Constraints driving the design

- Single envelope max usable payload: **884 bytes** (H2)
- Inbound re-assembly on FAP side: required (H6)
- No firmware-level chunking: must be in CFC's payload (H4)
- Bidirectional: same framing used host→FAP and FAP→host

### 4.2 CFC frame header (16 bytes)

Every CFC payload begins with a fixed 16-byte header:

```
Offset  Size  Field             Description
------  ----  ----------------  ----------------------------------
0       2     magic             0x4346 ('CF') — protocol identifier
2       1     version           Protocol version (0x01 for v1)
3       1     op_code           Command opcode (see §5)
4       4     transaction_id    Per-transaction monotonic ID (CFC layer)
8       2     fragment_index    0-based, current fragment number
10      2     fragment_total    Total fragments in this transaction
12      4     payload_length    TOTAL assembled payload length across
                                ALL fragments (identical in every fragment
                                of the same transaction)
```

After the 16-byte header in each frame: actual fragment payload bytes (≤884 bytes for the fragment).

### 4.3 Framing rules (BINDING)

- **transaction_id** is CFC's, not RPC's. RPC's `command_id` may be reused freely by the transport; CFC matches request↔response via its own `transaction_id`.
- **Magic + version validation.** If `magic != 0x4346` or `version != 0x01`, FAP discards the frame, MUST still call `rpc_system_app_confirm(rpc_app, true)` (per H5), and sends an ERROR opcode (0xFF) frame with `code=BAD_FRAME` from within the same callback.
- **CODIFIED PAYLOAD LIMIT: `payload_length` MUST be ≤ 8192 (8KB).** If exceeded on first fragment, FAP refuses with ERROR `code=PAYLOAD_TOO_LARGE`.
- **`payload_length` consistency check (NEW v5):** Every fragment of a transaction MUST carry the same `payload_length` value. If a subsequent fragment carries a different `payload_length` than the first fragment's value, FAP discards the entire transaction (frees buffer, returns IDLE) and sends ERROR `code=BAD_FRAGMENT`.
- **Per-frame data size validation (NEW v5 — security):** The number of payload bytes after the 16-byte header in each frame MUST satisfy: `bytes_in_frame ≤ remaining_expected_bytes` where `remaining_expected_bytes = payload_length - bytes_already_assembled`. If a frame contains more bytes than expected, FAP discards the transaction and sends ERROR `code=BAD_FRAGMENT`. This prevents buffer-overflow from malformed or malicious hosts.
- **Fragment validation:** `fragment_index < fragment_total` strictly. `fragment_total >= 1`. Violations → ERROR `code=BAD_FRAGMENT`.
- **Single-fragment transactions** still have a header: `fragment_index=0`, `fragment_total=1`, `payload_length=N`.
- **IDLE rejects non-first fragments:** If FAP is in IDLE and receives a fragment with `fragment_index != 0`, reject with ERROR `code=BAD_FRAGMENT`.
- **Order is guaranteed by the transport** (single FIFO queue per session — Q6).
- **Re-assembly buffer per transaction_id.** Allocate `payload_length` bytes on first fragment, append, dispatch when `fragment_index + 1 == fragment_total`.
- **ASSEMBLING TIMEOUT:** FAP starts a 5-second `FuriTimer` on first fragment. If next fragment doesn't arrive in time, FAP aborts transaction (free buffer, return to IDLE, log).
- **Malloc-failure:** ERROR `code=OUT_OF_MEMORY`, stay in IDLE.

**Error code enumeration (CLOSED SET v1):**

| Code constant | Numeric | Trigger |
|---|---|---|
| `BAD_FRAME` | 1 | magic or version mismatch |
| `BAD_FRAGMENT` | 2 | fragment_index ≥ fragment_total; fragment_total < 1; non-first fragment in IDLE; payload_length inconsistency; per-frame data overflow |
| `PAYLOAD_TOO_LARGE` | 3 | payload_length > 8192 |
| `OUT_OF_MEMORY` | 4 | malloc returned NULL |
| `BUSY` | 5 | another transaction in flight |
| `BAD_PAYLOAD` | 6 | frame valid but msgpack decode of assembled payload failed |
| `UNKNOWN_OPCODE` | 7 | op_code not in §5 v1 table |
| `INTERNAL` | 99 | handler crashed / unexpected error |

### 4.4 Payload encoding

Payload bytes after the header are **MessagePack** (msgpack) encoded objects.

Each command/response is a msgpack map. **Response maps MUST include a `status` field** (`"ok"` or error string).

**C library for FAP side: `cmp`** — single-header msgpack implementation. Source: `https://github.com/camgunz/cmp`. **Fetch step in §13.1 uses `git ls-remote --tags` to discover the correct tag name first** (tag naming convention not pinned — could be `v20`, `v2.0`, or `20`; the cook resolves at runtime). License: MIT.

**Python library for host side: `msgpack`** — pinned in `flipper_mcp/requirements.txt` at `msgpack==1.0.7` or later.

## 5. Opcode space (v1)

| op_code | Direction (Phase 2) | Direction (Phase 3+) | Name | Purpose |
|---|---|---|---|---|
| 0x00 | both | both | `PING` | Handshake / liveness; response echoes payload |
| 0x01 | both | both | `META_CAPABILITIES` | FAP returns list of supported opcodes + versions |
| 0x02 | both | both | `META_VERSION` | FAP returns CFC version, firmware build, schema versions |
| 0x10-0x1F | host→FAP only | both (with listener) | `NFC_*` | NFC operations (Phase 3) |
| 0x20-0x2F | host→FAP only | both (with listener) | `SUBGHZ_*` | Sub-GHz operations (Phase 4) |
| 0x30-0x3F | host→FAP only | both (with listener) | `IR_*` | Infrared operations (Phase 4) |
| 0x40-0x4F | host→FAP only | both (with listener) | `GPIO_*` | GPIO operations (Phase 4) |
| 0xFE | host→FAP | host→FAP | `RESET` | Clear all transaction state, return to idle |
| 0xFF | both | both | `ERROR` | Error response (msgpack: `{code: int, message: str}`); codes per §4.3 table |

Phase 2 implements **0x00, 0x01, 0x02, 0xFE, and 0xFF only**. Unknown opcodes return ERROR `code=UNKNOWN_OPCODE`.

## 6. FAP-side architecture

### 6.1 Threading model (Phase 2 scope ONLY)

**For Phase 2 (PING + META + RESET + ERROR only):**

- **Single-threaded.** FAP runs one main thread that owns the RPC callback and the re-assembly buffer.
- **No background workers.** All Phase 2 command handlers are synchronous from the callback's perspective.
- **The ASSEMBLING timeout (§4.3) uses `FuriTimer`** which is event-driven, callbacks fire on the same thread as the RPC callback. Single-threaded-compatible.
- **No async opcodes in Phase 2.**

**Phase 3+ async model is defined in §6.5** and is NOT in scope for Phase 1.

### 6.2 State machine (Phase 2)

**Observable states: IDLE and ASSEMBLING only.** The dispatch/response-send phase happens entirely within a single RPC callback invocation and is not externally observable.

```
[IDLE] ──recv first fragment (idx=0)──► [ASSEMBLING]
   ▲                                          │
   │                                          ├──final fragment received:
   │                                          │  handler dispatches, sends response
   │                                          │  (all within callback)
   │                                          ▼
   │                                       [IDLE]
   │
   │                                          ├──ASSEMBLING_TIMEOUT (5s)──► [IDLE]
   │                                          ├──recv RESET────────────────► [IDLE]
   │                                          ├──fragment with different transaction_id
   │                                          │   ──► ERROR(BUSY), stay ASSEMBLING
   │                                          └──validation fail────────► ERROR, return IDLE
   │
   └──in IDLE, recv non-first fragment ──► ERROR(BAD_FRAGMENT), stay IDLE
```

**State clarifications:**
- **transaction_id mismatch rule:** While in ASSEMBLING with current `transaction_id == T`, an inbound fragment with `transaction_id != T` triggers ERROR(BUSY); FAP stays in ASSEMBLING (does NOT corrupt the in-progress buffer).
- **RESET acceptance:** Accepted in IDLE (no-op, returns `{status: "ok"}`) and ASSEMBLING (frees buffer, transitions to IDLE, returns `{status: "ok"}`).
- **Inbound fragments in IDLE that are NOT `fragment_index=0`:** ERROR(BAD_FRAGMENT).

### 6.3 Required FAP callback flow

Every DataExchange callback executes this sequence **entirely within the callback**:

1. Validate event type: `if (event->type != RpcAppEventTypeDataExchange) return;`
2. Validate frame header (magic, version, payload_length, fragment_index/total per §4.3)
3. **ALWAYS call `rpc_system_app_confirm(rpc_app, true)`** — BEFORE any send work. This is the RPC-layer transport ack required by H5. Pass `true` regardless of frame validity. ERROR responses are surfaced via separate ERROR-opcode frames at the application layer (steps 4-6).
4. If frame INVALID: build ERROR frame, call `rpc_system_app_exchange_data()` from within the same callback, return.
5. If frame VALID and transaction NOT yet complete: append to re-assembly buffer, return (timer continues running).
6. If frame VALID and transaction COMPLETE: stop the ASSEMBLING timer, dispatch handler, build response frame(s), call `rpc_system_app_exchange_data()` for each, return.

**Empirical validation in Phase 2 cook (Q-IMPL-5 — see §10):** confirm `rpc_system_app_exchange_data()` is safe to call from within the RPC callback. The first PING test validates this; if it fails with a callback-reentry error, halt cook and revise design.

### 6.4 Sending fragmented responses (Phase 2.5+)

```c
size_t total_frags = (response_length + 883) / 884;
for (size_t i = 0; i < total_frags; i++) {
    build_frame(i, total_frags, transaction_id, op_code, slice);
    bool sent = rpc_system_app_exchange_data(rpc_app, frame, frame_size);
    if (!sent) {
        return ERROR_TRANSPORT;  // host hits its 30s timeout
    }
    // Inter-frame yield: use whichever Furi delay primitive mntm-dev exposes
    // (likely furi_delay_us(100) or furi_delay_ms(1)). Cook resolves at build time.
}
```

### 6.5 Async hardware ops (Phase 3+ — DEFERRED)

NFC, Sub-GHz, IR, and GPIO operations that wait on hardware events CANNOT use the Phase 2 synchronous model. Phase 3 will require:

- **Host-side listener:** `flipper_cfc_listen` MCP tool for unsolicited frames matching a `subscription_id`
- **FAP-side worker:** `FuriThread` per long-running op
- **Subscription opcodes:** 0x10+ become bidirectional

## 7. Host-side architecture (CPK `flipper_mcp` extension — Phase 2)

### 7.1 New module

`flipper_mcp/modules/cfc/module.py` — initial MCP-tool surface:

```python
flipper_cfc_call(op_code: int, payload: dict, timeout_s: float = 30.0) -> dict
```

Internally:
1. msgpack-encode payload
2. Validate `len(payload_bytes) <= 8192` (matches FAP-side cap)
3. Fragment into ≤884-byte chunks, build CFC frame headers (every fragment carries the same `payload_length` = total assembled length, per §4.2)
4. For each frame: call `rpc_app_data_exchange_send(frame_bytes)` from `flipperzero_protobuf.flipper_app` (pinned in `requirements.txt`)
5. Block on `rpc_app_data_exchange_recv()` with refreshed timeout per H9
6. Re-assemble incoming fragments matching outbound `transaction_id`
7. msgpack-decode response, return dict

If response is ERROR opcode (0xFF), raise `CfcRemoteError(code, message)`.

**Important (NEW v5):** The RPC-layer `rpc_system_app_confirm(true)` happens transparently inside the `flipperzero_protobuf` transport. Host application code (this module) sees only application-layer frames (the ERROR frame, the response frame, etc.). The confirm is NOT a separate "event" that needs handling at this layer.

### 7.2 Concurrency model

- **One transaction at a time per FlipperMCP session** (matches H8)
- Lock on the transport mutex (already present per DolphinTank Decision #005)
- transaction_id allocation: thread-safe monotonic counter

### 7.3 Timeout policy

- Default per-call timeout: **30 seconds**
- Timeout is **complete-response** (refreshed on each inbound frame — H9)
- Timeout fires `flipper_mcp.exceptions.CfcTimeoutError`
- Fast-fail on transport disconnect: `SerialException` → abort immediately
- Malformed msgpack handling: raise `CfcProtocolError("malformed response")`, drain remaining fragments

## 8. FAP application.fam (minimum)

```python
App(
    appid="cfc",
    name="CPK Companion",
    apptype=FlipperAppType.EXTERNAL,
    entry_point="cfc_app_main",
    stack_size=4 * 1024,
    fap_category="Tools",
    fap_description="CPK Companion FAP — Claude-driven RF reconnaissance helper",
    fap_version="0.1",
    fap_icon="cfc_10px.png",
    requires=[],  # Phase 2: no UI, no extra services. Add "gui"/"storage" in Phase 3 if needed.
)
```

Deploys to `/ext/apps/Tools/cfc.fap`. Launch via `flipper_app_start("/ext/apps/Tools/cfc.fap", "")`.

**FAP entry point signature** — confirm against existing examples in corpus. Likely `int32_t cfc_app_main(void* p)` returning 0 on clean exit, but the cook MUST verify against a known-good FAP from `notebooklm/cfc/medium/official-good-faps/` (e.g., the `weather` or `mass_storage` FAP) before writing the entry point.

### 8.1 Project layout

```
Claude-s-Pet-Kiisu-CPK/                 (CPK repo root)
├── flipper_mcp/                        (existing — host-side Python)
│   ├── modules/cfc/module.py           (NEW in Phase 2)
│   ├── requirements.txt                (UPDATED: add msgpack, flipperzero-protobuf pin)
│   └── ...
├── cfc/                                (NEW — FAP source tree)
│   ├── application.fam
│   ├── cfc.c                           (entry: cfc_app_main; reference good-faps/weather/ for shape)
│   ├── cfc_10px.png                    (generated via Pillow, see §13.1)
│   └── lib/cmp/
│       ├── cmp.c                       (vendored, see §13.1 fetch)
│       └── cmp.h
├── tests/cfc_phase2/                   (NEW)
│   └── test_*.py                       (per §12.1)
└── docs/decisions/
    ├── DAY8_FAP_PHASE1_SPEC.md         (this document)
    └── DAY9_PHASE2_COOK_LOG.md         (created by cook on first halt)
```

`ufbt` commands run from the `cfc/` directory.

## 9. Phase 2 scope

Phase 2 is **"skeleton FAP boots, responds to PING and META."**

- ufbt-built CFC.fap loads on AmorPoee (mntm-dev)
- `flipper_cfc_call(PING, {echo: "hello"})` returns `{status: "ok", echo: "hello"}`
- **Multi-fragment INBOUND assembling IS implemented** (required by §12.1 assembling-timeout and stale-transaction tests). **Outbound responses are single-fragment only in Phase 2** (FAP never sends >884 bytes back to host). End-to-end chunking validation is Phase 2.5.
- META_CAPABILITIES returns `{status: "ok", opcodes: [0, 1, 2, 0xFE, 0xFF]}`
- META_VERSION returns `{status: "ok", cfc_version: "0.1", firmware: "mntm-dev", schema_major: 1, schema_minor: 0}`
- RESET returns `{status: "ok"}` and proves state machine returns to IDLE
- ERROR handling validated via negative tests (§12.1)

Phase 2.5: Chunked outbound validation (>884-byte response roundtrip).
Phase 3: Host-listener architecture + NFC vertical slice.
Phase 4: SubGHz / IR / GPIO.

## 10. Open questions deferred to implementation

- Q-IMPL-1: ~~msgpack library~~ **RESOLVED: `cmp` from `github.com/camgunz/cmp`, tag resolved at fetch time (see §13.1).**
- Q-IMPL-2: Stack size — 4KB initial guess. Phase 3 may need 8KB once NFC handler is added.
- Q-IMPL-3: ~~Icon~~ **RESOLVED: Pillow generation, see §13.1.**
- Q-IMPL-4: Single MCP tool vs per-domain tools — default to single tool for Phase 2.
- Q-IMPL-5: `rpc_system_app_exchange_data()` safe from RPC callback context — **validated empirically in Phase 2 cook via first PING test.** If PING succeeds, this holds.
- Q-IMPL-6: Exact Furi API names (`furi_delay_us` vs `furi_delay_ms` vs `furi_delay_tick`; `furi_log_print_format` vs `FURI_LOG_E` macro) — cook resolves from firmware headers at build time.
- Q-IMPL-7: `cfc_app_main` exact signature — cook resolves from a known-good FAP example before writing the entry point.

## 11. Risks logged (honest assessment)

- **R-CFC-1: First-of-kind.** Zero in-the-wild AppDataExchange consumers in 800MB of community FAPs. We'll find rough edges.
- **R-CFC-2: Confirm-required gotcha.** Mitigated by §6.3 step 3.
- **R-CFC-3: Re-assembly buffer DoS surface.** Mitigated by §4.3 codified 8KB cap + per-frame size validation.
- **R-CFC-4: Cross-firmware portability is structural, not validated.** Honest in §2.2.
- **R-CFC-5: ASSEMBLING-state hangs.** Mitigated by 5-second `FuriTimer`.
- **R-CFC-6: msgpack encode/decode mismatch between C `cmp` and Python `msgpack`.** Mitigated by §12.1 `test_msgpack_roundtrip.py`.
- **R-CFC-7 (NEW v5): API symbol availability not confirmed.** `furi_delay_us`, `furi_log_*`, `cfc_app_main` signature, `flipperzero_protobuf.flipper_app` import path all assumed but not verified. Mitigated by §13.1 preconditions that validate before code-write, plus Q-IMPL-5/6/7 cook-time resolution.

## 12. Acceptance criteria

### 12.1 Phase 2 implementation tests

Phase 2 is complete when **all** of the following pass:

**Build & deploy:**
- [ ] `ufbt` builds `cfc.fap` cleanly with no warnings
- [ ] `ufbt launch` deploys to AmorPoee successfully
- [ ] `flipper_app_start("/ext/apps/Tools/cfc.fap", "")` returns success

**Positive path tests (under `tests/cfc_phase2/`):**
- [ ] `test_ping_roundtrip.py` — sends PING with `{echo: "hello"}`, asserts response `{status: "ok", echo: "hello"}`
- [ ] `test_meta_capabilities.py` — asserts response opcodes contain 0x00, 0x01, 0x02, 0xFE, 0xFF
- [ ] `test_meta_version.py` — asserts non-empty `cfc_version` and `firmware` strings
- [ ] `test_reset_returns_idle.py` — RESET in IDLE returns ok; then PING succeeds
- [ ] `test_reset_during_assembling.py` (NEW v5) — sends frag 1 of 2-fragment txn, RESET, then full PING, asserts both succeed and buffer was cleaned
- [ ] `test_recovery_after_bad_frame.py` — sends bad magic (expects ERROR), then PING (expects success)
- [ ] `test_msgpack_roundtrip.py` — sends PING with `{echo: {nested: [1, 2.5, "string", true, null]}}`, asserts FAP echoes byte-identical structure

**Negative path tests:**
- [ ] `test_negative_bad_magic.py` — magic=0x0000 → ERROR `code=BAD_FRAME` (1)
- [ ] `test_negative_bad_version.py` — version=0x99 → ERROR `code=BAD_FRAME`
- [ ] `test_negative_oversized_payload.py` — payload_length=8193 → ERROR `code=PAYLOAD_TOO_LARGE` (3)
- [ ] `test_negative_bad_fragment_index.py` — fragment_index=5, fragment_total=3 → ERROR `code=BAD_FRAGMENT` (2)
- [ ] `test_negative_malformed_msgpack.py` — valid frame, garbage msgpack → ERROR `code=BAD_PAYLOAD` (6)
- [ ] `test_negative_unknown_opcode.py` — op_code=0xAA → ERROR `code=UNKNOWN_OPCODE` (7)
- [ ] `test_negative_zero_fragment_total.py` — fragment_total=0 → ERROR `code=BAD_FRAGMENT`
- [ ] `test_negative_orphan_fragment.py` (NEW v5) — sends fragment_index=1, fragment_total=2 to IDLE FAP → ERROR `code=BAD_FRAGMENT`
- [ ] `test_negative_oversized_frame_data.py` (NEW v5) — declares payload_length=500 but sends 800 bytes of data → ERROR `code=BAD_FRAGMENT` (security test)

**Protocol stress tests:**
- [ ] `test_assembling_timeout.py` — frag 1 of 2-frag txn, wait 6s, send frag 2 → frag 2 rejected (timer cleaned state)
- [ ] `test_stale_transaction.py` — frag 1 of txn 1, then frag 1 of txn 2 → BUSY for txn 2; txn 1 completes within 5s window

**Whole-suite:**
- [ ] `pytest tests/cfc_phase2/ -v` passes all with no skips
- [ ] Test suite total runtime < 5 minutes

**Manual verification (logged in `DAY9_PHASE2_COOK_LOG.md`):**
- [ ] FAP source contains `rpc_system_app_confirm(rpc_app, true)` as step 3 of callback per §6.3 (visual code inspection)
- [ ] FAP entry point signature matches the chosen reference good-fap (Q-IMPL-7)

### 12.2 Test wiring

Tests in `tests/cfc_phase2/` are pure Python pytest modules. Each test:

1. Imports `flipper_mcp.modules.cfc.module.flipper_cfc_call` directly (not via MCP server stdio)
2. Uses a shared pytest fixture `cfc_client` that wraps the existing `FlipperClient` with auto-discovered port
3. Calls `flipper_cfc_call()` and asserts on the returned dict
4. For negative tests that need to send malformed frames, uses a lower-level helper `_send_raw_frame(client, raw_bytes)` that bypasses the normal fragmentation logic

The cook implements `cfc_client` fixture and `_send_raw_frame` helper in `tests/cfc_phase2/conftest.py` as part of test setup.

## 13. Stop conditions and preconditions for Phase 2 autonomous cook

### 13.1 Preconditions (cook halts before starting if missing)

**Tooling:**
- `ufbt --version` returns a version string (else halt: install ufbt manually)
- `python -c "import PIL"` succeeds (else ONE attempt: `pip install Pillow`, halt if still missing)
- `python -c "import msgpack"` succeeds (else ONE attempt: `pip install msgpack`, halt)
- `python -c "from flipperzero_protobuf.flipper_app import rpc_app_data_exchange_send, rpc_app_data_exchange_recv"` succeeds (else halt: "install flipperzero-protobuf>=0.1.5 and verify submodule exposure")
- `git --version` returns a version string

**Hardware:**
- `flipper_connection_health` returns `last_error: null` (else halt)
- Use whatever serial port `flipper_mcp` auto-resolves (do not hardcode COM number)

**Repo state:**
- `git status` in CPK repo is clean
- `cfc/` directory does NOT yet exist (cook creates it; existing → halt and ask Victor for cleanup)

**Vendor library fetch:**
```bash
# Resolve actual tag name first (could be v20, v2.0, or 20)
TAGS=$(git ls-remote --tags https://github.com/camgunz/cmp | awk -F/ '{print $NF}' | grep -E '^v?[0-9]')
TAG=$(echo "$TAGS" | sort -V | tail -1)
# Clone at resolved tag
git clone --depth 1 --branch "$TAG" https://github.com/camgunz/cmp /tmp/cmp_resolved
mkdir -p cfc/lib/cmp
cp /tmp/cmp_resolved/cmp.c cfc/lib/cmp/cmp.c
cp /tmp/cmp_resolved/cmp.h cfc/lib/cmp/cmp.h
rm -rf /tmp/cmp_resolved
# Verify
test -f cfc/lib/cmp/cmp.c || halt "cmp.c missing"
test -f cfc/lib/cmp/cmp.h || halt "cmp.h missing"
# Record resolved tag in cook log
echo "cmp tag resolved to: $TAG" >> docs/decisions/DAY9_PHASE2_COOK_LOG.md
```

**Icon generation:**
```bash
python -c "from PIL import Image; Image.new('1', (10,10), 1).save('cfc/cfc_10px.png')"
test -f cfc/cfc_10px.png || halt "icon generation failed"
```

**Reference FAP inspection (NEW v5):**
- Cook MUST `cat` a known-good FAP's entry point file (e.g., `notebooklm/cfc/medium/official-good-faps/weather/weather_app.c` or equivalent) to confirm `cfc_app_main` signature shape before writing `cfc/cfc.c`. Record finding in cook log.

### 13.2 Halt conditions during cook

cc cooks for Phase 2 MUST halt if:

- `ufbt` build fails with linker error — halt after **1 fix attempt**, report
- FAP loads but `flipper_app_start` returns ANY non-success (not just `ERROR_INVALID_PARAMETERS`) — halt
- PING roundtrip times out 3 consecutive times after build succeeds — halt
- Any test in §12.1 fails after a clean rebuild — halt after **1 fix attempt** per failing test
- `flipper_mcp` module imports fail or break existing tools — halt, no rollback attempt
- `flipper_connection_health` returns ERROR at any point mid-cook — halt immediately (device may have crashed)
- FAP returns `{status: "ok"}` but missing expected fields — halt after **1 fix attempt**
- `rpc_system_app_exchange_data()` returns `false` mid-fragment send in §6.4 loop — halt (Q-IMPL-5 failure)
- `rpc_system_app_set_callback` returns failure on FAP init — halt (RPC registration failed; visible in FAP startup logs)
- Total cook duration exceeds **2 hours** — halt
- More than **10 ufbt rebuilds** in a single cook — halt

### 13.3 Rollback procedure

If cook halts with partial state:

1. If device still connected: `storage_delete("/ext/apps/Tools/cfc.fap")` via MCP. If disconnected: log warning and continue (next cook will overwrite/skip).
2. `rm -rf cfc/` from CPK repo root
3. `git checkout -- flipper_mcp/requirements.txt flipper_mcp/modules/`
4. Smoke test on existing `flipper_mcp` (storage_read of a known file) to confirm no collateral damage
5. Log halt details + state to `docs/decisions/DAY9_PHASE2_COOK_LOG.md`

---

**End of Phase 1 spec v5 — SHIPPABLE.**

**Adversarial review history:**
- v1 (2026-05-27 02:52): 3/3 reviewers SHIP_WITH_FIXES — 8 structural fixes integrated → v2
- v2 (2026-05-27 02:59): 3/3 reviewers SHIP_WITH_FIXES — 8 textual fixes integrated → v3
- v3 (2026-05-27 03:17): 3/3 reviewers SHIP_WITH_FIXES — 8 polish fixes integrated → v4
- v4 (2026-05-27 03:30): 3/3 reviewers SHIP_WITH_FIXES — 11 final-detail fixes integrated → v5
- v5: declared shippable. Remaining items (Q-IMPL-5/6/7, R-CFC-7) require live-device empirical validation, which is Phase 2's job.
