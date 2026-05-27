# CPK STATE — What's True Right Now

> 02-state wins on **"what is true now."**
> If 02-state disagrees with anything else, 02-state is correct.
> If 02-state's timestamp is stale (>7 days old), distrust it and verify.

---

**Last updated:** 2026-05-27 (Day 10 session close — Phase 2.5 SHIPPED at 27/27)
**Updated by:** Victor + Claude Desktop
**Confidence:** HIGH — values verified during this session

---

## Repository state

- **Default branch on GitHub:** `main` at commit `6bf1d32` (Phase 2.5 shipped, pushed to GitHub)
- **Active experiment branch:** none
- **Stargazers:** 2
- **Working tree (Day 10 close):** CLEAN. Phase 2.5 commit pushed to origin/main.
- **Day 10 commit on main (pushed):**
  - `6bf1d32` Phase 2.5: CFC multi-fragment outbound + wire-layer hardening
- **Day 9 commits on main (already pushed):**
  - `35a9332` Phase 2 CFC skeleton ships at 17/18 — architecture VALIDATED
  - `c1f74a8` Day 9 v5.1: CFC spec corrected after Phase 2 precondition discovery
  - `1d5dcca` Day 9: Phase 1 CFC spec shipped (v5) + NotebookLM corpus + decisions

---

## Hardware state

- **Primary device:** AmorPoee — Kiisu V4B clone, serial `5A3DEA0027E18000`
- **Firmware:** Momentum `mntm-dev`
- **Transport:** USB on COM9
- **Auto-lock:** 30 minutes (manually configured)
- **Connection health (last checked Day 10):** ✅ connected, RPC responsive, used heavily during Phase 2.5 cook for live-fire tests including 10× test_stale_transaction loop
- **CFC FAP deployed on SD card** at `/ext/apps/Tools/cfc.fap` (Phase 2.5 v8.3 build, 15,932 bytes — multi-fragment outbound enabled). Persists across reboots. Safe to leave installed.

---

## Tooling state

- **MCP server:** `flipper-mcp` v0.4.0 — unchanged this session
- **Editable install:** `D:\Dev\Projects\Kiisu\.venv\Lib\site-packages\__editable__.flipper_mcp-0.1.0.pth` points to `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\` (Day 4 band-aid; works)
- **flipper-mcp version:** v0.4.0 (8 tools in `app_lifecycle` module)
- **Sherpa adversarial review pipeline:** validated working (used 4× for Phase 1 spec)
- **Phase 2 deps installed in CPK venv:** ufbt 0.2.6, Pillow 12.2.0, msgpack 1.1.2, setuptools 82.0.1, wheel 0.47.0

---

## Mission framework state

**Unchanged from Day 8** — no missions executed this session (all work was CFC FAP).

Validated working end-to-end on real hardware (Day 7 live-fire):
- ping, radio_handshake (v2), subghz_quick_scan, flipper_info, device_inventory

Built but not validated end-to-end: gpio_full_read (F1), ble_passive_scan (no-op), storage_health_check (unit tests only)

Not yet built: NFC capture (subsumed by CFC Phase 3), red-team missions

---

## Known firmware/MCP bugs (open, prioritized)

Unchanged from Day 8 (CFC Phase 3 will subsume F1 and F4):

- **F1:** `require("gpio")` fails on mntm-dev (Medium — subsumed by CFC Phase 4)
- **F2:** `storage_info` MCP tool returns SD card stats for `/int` requests (small, ~30min fix)
- **F3:** `storage_list` returns empty for `/ext/apps_data` even when files exist
- **F4:** `require("nfc")` fails on mntm-dev (subsumed by CFC Phase 3)

---

## CFC (CPK Companion FAP) project state — UPDATED Day 10 close

### Phase 1: SHIPPED ✅

- **Spec:** `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` v5.1 (§6.4 corrected to `void` in Phase 2.5)
- **Architecture:** Path A (single .fap, FlipperAppType.EXTERNAL, AppDataExchange)
- **Wire protocol:** 16-byte CFC header + msgpack payload, 884 bytes/frame, 8KB transaction cap
- **NotebookLM corpus:** 3 notebooks, 70 sources at `notebooklm/cfc/_upload/`
- **Adversarial review:** 4 Sherpa passes × 3 reviewers = 12 critique runs

### Phase 2: SHIPPED at 17/18 ✅

- **Cook log:** `docs/decisions/DAY9_PHASE2_COOK_LOG.md`
- **FAP source:** `cfc/cfc.c` (was 590 lines after Phase 2; ~650 lines after Phase 2.5 v8.3 multi-fragment outbound)
- **Host module:** `flipper_mcp/modules/cfc/module.py`
- **Tests:** 18 test files at `tests/cfc_phase2/` — **17 passing, 1 halted at end of Phase 2** (closed in Phase 2.5)

### Phase 2.5: SHIPPED at 27/27 ✅ (Day 10, commit `6bf1d32`)

- **Design doc:** `docs/decisions/DAY10_PHASE2_5_DESIGN.md` v8.4 (1464 lines)
- **Cook stats:** 4 attempts, 6 halts (all caught correctly), ~60 min wall-clock total
- **Test results:** 27/27 full suite (253s), test_stale_transaction 10/10 deterministic (~13.5s each)
- **Review pipeline:** 8 rounds — Sherpa ×2, Gemini ×2, NotebookLM ×3, Arena.ai ×2 (random model pool)

**What shipped:**
- **Host-side route-by-tag drain pattern** in `_cfc_send_one_frame` matching qFlipper's canonical implementation. 5 known frame types in allowlist: `app_data_exchange_request` (CFC data), `empty` (sync RPC ack), `app_state_response`, `gui_screen_frame`, `desktop_status`. Unknown content tags raise `CfcProtocolDesyncError`.
- **New `_send_main_raw` method** on `ProtobufRPC` — bypasses strict command_id matcher for CFC's drain loop.
- **New `cfc_recv_response_assembled` helper** — takes first fragment, reads remaining fragments, returns reassembled payload. Reusable for Phase 3 integration tests.
- **FAP-side multi-fragment outbound** per spec §6.4: new `cfc_send_response_multi` fragments payloads up to 8KB into 884-byte chunks with inter-frame `furi_delay_ms(1)` yield. PING handler refactored to use heap-allocated output buffer.
- **`MOMENTUM_RPC_EXCHANGE_DATA_FIXED=False` constant** + one-shot import warning. Forward-declaration for Phase 3 strict-matching gate; not consulted in Phase 2.5 (workaround unconditional).
- **5 new test files:** `test_chunked_ping_roundtrip`, `test_broadcast_path_mock`, `test_cfc_timeout_returns_none`, `test_non_cfc_frame_raises_desync`, `test_async_event_consumed_during_drain` (parametrized ×4).
- **Spec §6.4 corrected:** `bool` → `void` return type.

**Major discoveries during Phase 2.5 (folded into doc):**
- `rpc_system_app_send_state_response` has the same uninit-malloc bug as `rpc_system_app_exchange_data` (NotebookLM Round 2 Q5). Momentum PR drafted at `D:\Dev\scratch\day10_momentum_pr_draft.md` patches both — deferred, not submitted.
- The Flipper RPC dispatcher emits a per-request `empty` Main as a sync ack for EVERY host RPC request. Invisibly absorbed by `_send_rpc_message`'s strict matcher in all existing flipper-mcp tools; exposed for the first time when CFC bypassed strict matching. Added to Q6 allowlist as a 5th frame type.
- The PING handler had a hardcoded 884-byte stack-buffer ceiling — Phase 2 never reached this code path because the wire-layer desync blocked fragment-2 assembly. Phase 2.5's wire fix exposed it; v8.3 lifted it via multi-fragment outbound.

### Phase 3: QUEUED

NFC vertical slice + host-listener architecture for async opcodes. See spec §6.5 and DAY10 design doc §6 for forward-compat notes. The route-by-tag pattern and `cfc_recv_response_assembled` helper are both reusable for Phase 3 integration tests.

---

## Open R-series findings (from cc Phase 1 capability survey, Day 5)

- **R5 (storage_write false-failure):** ✅ FIXED Day 4, re-validated Day 7
- **R6 (large script crash):** ✅ SUBSUMED by R5
- **R7 (orphan flipper-mcp processes):** ⚠️ **Re-observed Day 9 + Day 10 cooks** — Day 9: six stale `flipper_mcp.cli.main` processes were holding COM9. Day 10: orphan python.exe (likely pyserial reader thread) held COM9 after deploy script; physical USB unplug/replug freed it cleanly within ~5 seconds. Pattern confirmed across two cooks. Mitigation candidates: helper script `python -m flipper_mcp.tools.kill_stale`, or auto-detect at MCP startup. **Operational learning:** when COM9 hangs ≥30 sec, unplug/replug is faster than process-hunting.

---

## Tool ecosystem this Claude session has access to

- `flipper-mcp` (live RPC to AmorPoee) — used for connection health checks
- `claude-memory` (hybrid search over Victor's pgvector_load memory store) — not exercised
- `anythingllm` 15-specialist fleet — not exercised
- Desktop Commander / Windows-MCP (Windows filesystem + shell) — extensively used
- Sherpa tooling at `E:\Sherpa\tools\` — used for Phase 1 adversarial review
- Standard web tools (web_search, web_fetch) — used for Hermes/NotebookLM recon and flipperzero-protobuf investigation

---

## Current AI session context

- **Plan:** Pro plan
- **Last session goal achieved:** Phase 2.5 SHIPPED at 27/27. Multi-fragment outbound working end-to-end. test_stale_transaction passes deterministically 10/10. Commit `6bf1d32` pushed to origin/main.
- **Next session goal:** Phase 3 — NFC vertical slice + host-listener architecture. OR pick a side-task (Momentum PR submission, F2 fix, R7 mitigation script).
