# DAY 9 — Phase 2 Cook Log

**Cook started:** 2026-05-27
**Spec:** v5.1 at commit c1f74a8
**Goal:** Skeleton CFC FAP boots + responds to PING/META/RESET/ERROR; 17 §12.1 tests pass.

---

## Preconditions (§13.1) — re-validated by cook

| Check | Result |
|---|---|
| ufbt installed | ✅ 0.2.6 at `D:\Dev\Projects\Kiisu\.venv\Scripts\ufbt.exe` |
| Pillow importable | ✅ 12.2.0 |
| msgpack importable | ✅ 1.1.2 |
| `flipper_mcp.core.protobuf_gen` has `Main.app_data_exchange_request` + `DataExchangeRequest` | ✅ verified |
| git --version | ✅ 2.53.0.windows.2 |
| git status clean | ✅ empty |
| `cfc/` absent | ✅ confirmed |

(AmorPoee device health re-checked at step 9 immediately before live fire.)

---

## Step 2 — Vendor cmp library

- `git ls-remote --tags https://github.com/camgunz/cmp` → tags `v16…v20`, highest semver = **v20**.
- Cloned `--depth 1 --branch v20` and vendored `cmp.c` (85099 bytes) + `cmp.h` (21969 bytes) into `cfc/lib/cmp/`.
- **Resolved cmp tag: v20**

## Step 3 — Icon

- `Image.new('1', (10,10), 1).save('cfc/cfc_10px.png')` → 73-byte 1-bit PNG.

## Step 4 — Reference FAP inspection (Q-IMPL-7)

- Inspected `notebooklm/cfc/medium/official-good-faps/weather_station/weather_station_app.c:179-188`.
- **Q-IMPL-7 resolved: `int32_t cfc_app_main(void* p)`** with `UNUSED(p)` and `return 0;` on clean exit.
- **CRITICAL FINDING from `notebooklm/cfc/_upload/notebook1_firmware_side/01_rpc_service_all.txt:783-787`:**
  When host calls `app_start("cfc", "RPC")`, the firmware *rewrites* args to `"RPC %08lX"` containing the hex pointer to the `RpcAppSystem` instance. The FAP receives this in `void* p` (a `const char*`). The FAP must parse this hex pointer to obtain its `RpcAppSystem*`.
- **Q-IMPL-6 (Furi APIs):** Confirmed by official-good-faps usage:
  - Logging: `FURI_LOG_E(TAG, fmt, ...)`, `FURI_LOG_I(TAG, ...)`, `FURI_LOG_D(TAG, ...)` (macros).
  - Delay: `furi_delay_ms(ms)` is the idiomatic choice.
- **Spec/header discrepancy:** Spec §6.4 implies `rpc_system_app_exchange_data()` returns `bool`. The actual header (`rpc_app.h:220`) declares it `void`. Phase 2 sends single-fragment responses only, so the "return false → halt" path in §6.4 cannot fire; flagged for spec correction post-cook.

## Step 5 — FAP source (`cfc/cfc.c`)

- 590 lines, single file, builds clean with 0 warnings on first attempt.
- State machine: IDLE / ASSEMBLING, mutex-protected. RESET is a special-case that clears ASSEMBLING regardless of `transaction_id` (§6.2).
- All 8 error codes from §4.3 table wired through `cfc_send_error()`.
- Required confirm-BEFORE-send order in callback (§6.3 step 3) is the first thing every DataExchange handler does.
- `rpc_system_app_exchange_data()` called from within the RPC callback — empirically validated safe in step 9 (Q-IMPL-5 ✅).

## Step 6 — Host module (`flipper_mcp/modules/cfc/module.py`)

- Uses CPK internal `flipper_mcp.core.protobuf_gen.flipper_pb2` / `application_pb2` per v5.1 §7.1.
- Wire-touching `_cfc_send_one_frame` acquires `ProtobufRPC._wire_lock` directly (no decorator — non-bound function).
- Fragmentation: single-fragment outbound in Phase 2 paths exercised; multi-fragment code path present.
- Late refinement: added `wait_for_response: bool` parameter so non-final-fragment sends don't burn 2.5s on a futile drain (see step 10 fix).

## Step 7 — `requirements.txt`

- Added only `msgpack>=1.0.7` (v5.1 §7.1 — CFC uses internal protobuf_gen, no `flipperzero-protobuf` pin).

## Step 8 — Test suite

- 18 test files written (spec §12.1 lists 7 positive + 9 negative + 2 stress = 18; cook.txt's "17" appears to be an off-by-one in the prose).
- `conftest.py` provides `cfc_client`, `cfc_call`, `cfc_send_raw`, `decode_resp` fixtures.
- Tests skip cleanly when AmorPoee unreachable unless `CFC_REQUIRE_HW=1` (then they ERROR).
- DolphinTank Decision #002 confirmed live: external FAPs need full path; fixture uses `app_start("/ext/apps/Tools/cfc.fap", "RPC")`.

## Step 9 — First live fire (Q-IMPL-5 validation)

- ufbt build: **clean on first attempt** (rebuild count: 1).
- ufbt launch initially failed with `Access is denied` on COM9 — six(!) stale `flipper_mcp.cli.main` processes from prior Claude Desktop / Code sessions were holding the port. Resolved by killing the stale processes (Victor confirmed Claude Desktop was shut down). After cleanup, deploy succeeded and FAP installed at `/ext/apps/Tools/cfc.fap`.
- Test fixture initially errored with `'NoneType' object has no attribute 'app_start'` — `FlipperRPC.protobuf_rpc` is lazily initialized via `_ensure_protobuf_rpc()`; conftest now calls it before use.
- Test fixture then errored with `ERROR_INVALID_PARAMETERS` for `app_start("cfc", "RPC")` — known: external FAPs need full path on mntm-dev (DolphinTank #002). Switched to full path `/ext/apps/Tools/cfc.fap`.
- **`test_ping_roundtrip.py` PASSED first time after these fixture fixes** — Q-IMPL-5 **EMPIRICALLY VALIDATED**: `rpc_system_app_exchange_data()` IS safe to call from within the RPC callback. The architecture works.

## Step 10 — Full test suite

- First full-suite run: **17/18 pass in 4:57**. Only `test_stale_transaction` failed.
- Fix attempt #1 (per §13.2 "1 fix attempt per failing test"): added `wait_for_response=False` to the test's outbound non-final fragment send, so the 2.5s drain wouldn't push subsequent fragments close to the FAP's 5s ASSEMBLING timer window.
- **After fix**: `test_stale_transaction`'s first sub-assertion (BUSY received) now passes ✅, but the second sub-assertion (txn1 PING completion after BUSY interrupt) now fails with `op=0xFF` instead of `op=0x00 (PING)`. Per §13.2 rule, 1-fix-per-test is exhausted — **HALT**.
- All 17 other tests re-confirmed passing in 4:35 (no regressions from the host-side fix).

### Q-IMPL-5/6/7 final findings

| Question | Result |
|---|---|
| **Q-IMPL-5** (rpc_system_app_exchange_data safe from RPC callback?) | ✅ **YES** — empirically validated by all 17 passing tests. Single-fragment responses sent from within callback work reliably. |
| **Q-IMPL-6** (Furi delay / log API names) | `furi_delay_ms()`, `furi_ms_to_ticks()`, `FURI_LOG_E/I/D(TAG, fmt, ...)` macros — all available, all used. |
| **Q-IMPL-7** (`cfc_app_main` signature) | `int32_t cfc_app_main(void* p)`. `p` is a `const char*` carrying `"RPC %08lX"` where the hex is the `RpcAppSystem*` (firmware rewrite at `rpc_system_app_start_process` line 783). |

### Halt — test_stale_transaction unresolved

**Symptom:** After the FAP correctly responds with BUSY to a foreign-txn fragment during ASSEMBLING, the original transaction's subsequent fragment receives an ERROR (op=0xFF) instead of completing as PING.

**Hypothesis (un-validated, requires Phase 2.5 investigation):**
- The BUSY response's outbound Main (built via `rpc_system_app_exchange_data` from uninitialized malloc) may have a random `command_id` that collides with a subsequent request's `command_id`, causing host-side stale-frame matching to consume the wrong frame.
- Alternatively, FAP-side state corruption between the BUSY response and the txn1 frag2 processing (less likely — code path is straightforward, mutex held during state read/write).

**Mitigation already in place:**
- `_cfc_send_one_frame` discards mismatched command_ids up to a `max_mismatches=4` budget (inherited from existing `_send_rpc_message`).
- The `wait_for_response=False` no-wait helper added in step 10 reduces the wire's "stale-Main-soup" surface area for the no-response paths.

**Recommended next step (Phase 2.5):** Instrument FAP to log the outbound Main `command_id` before each `rpc_system_app_exchange_data` call. If the random `command_id` hypothesis holds, either (a) submit a Momentum patch to zero the Main in `rpc_system_app_exchange_data`, or (b) accept inbound app_data_exchange Mains regardless of command_id on the host (treat data-exchange as unsolicited per spec H8).

### Build / rebuild count

- **Total ufbt rebuilds: 1** (well under §13.2's 10-rebuild cap). The single build was clean; the failure in step 10 was host-side and required no FAP rebuild.

### Existing flipper_mcp v0.4.0 health check

- Not run as a discrete `storage_read` smoke test (MCP server was killed during step 9 port-cleanup and the harness hasn't re-spawned a server in this session). However, **all 17 passing tests exercise `flipper_mcp.core.protobuf_rpc` + `transport.usb.USBTransport` + `_send_rpc_message`** — the underlying flipper-mcp stack is empirically healthy. Recommend Victor verify with one explicit `storage_read` call after MCP server re-spawns.

### Cook timing summary

- Wall-clock total: ~25 min (vs 2-hour cap).
- Rebuilds: 1/10.
- Tests fixed: 1/1 budget for the failing test.

---

## Cook outcome: PARTIAL SHIP (17 of 18 tests passing, 1 halt)

Phase 2 is functionally complete: PING / META_CAPABILITIES / META_VERSION / RESET all work end-to-end, plus 9 negative-frame paths and 1 stress test (assembling timeout). The one remaining failure (`test_stale_transaction`) is a real protocol-interaction edge case that exposes a likely command-id collision bug in `rpc_system_app_exchange_data`'s uninitialized Main — not a structural design failure in CFC. Phase 2.5 should investigate.

**No commit made — `let her rip` required from Victor.**

