# CPK STATE — What's True Right Now

> 02-state wins on **"what is true now."**
> If 02-state disagrees with anything else, 02-state is correct.
> If 02-state's timestamp is stale (>7 days old), distrust it and verify.

---

**Last updated:** 2026-05-27 (Day 9 session close — Phase 2 cook complete)
**Updated by:** Victor + Claude Desktop
**Confidence:** HIGH — values verified during this session

---

## Repository state

- **Default branch on GitHub:** `main` at commit `35a9332` (Phase 2 shipped; not pushed to GitHub yet)
- **Active experiment branch:** none
- **Stargazers:** 2
- **Working tree (Day 9 close):** CLEAN. Three Day 9 commits on main, ready to push when Victor wants.
- **Day 9 commits on main:**
  - `35a9332` Phase 2 CFC skeleton ships at 17/18 — architecture VALIDATED
  - `c1f74a8` Day 9 v5.1: CFC spec corrected after Phase 2 precondition discovery
  - `1d5dcca` Day 9: Phase 1 CFC spec shipped (v5) + NotebookLM corpus + decisions

---

## Hardware state

- **Primary device:** AmorPoee — Kiisu V4B clone, serial `5A3DEA0027E18000`
- **Firmware:** Momentum `mntm-dev`
- **Transport:** USB on COM9
- **Auto-lock:** 30 minutes (manually configured)
- **Connection health (last checked Day 9):** ✅ connected, RPC responsive, used heavily during Phase 2 cook for live-fire tests
- **CFC FAP deployed on SD card** at `/ext/apps/Tools/cfc.fap` (Phase 2 build). Persists across reboots. Safe to leave installed.

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

## CFC (CPK Companion FAP) project state — UPDATED Day 9 close

### Phase 1: SHIPPED ✅

- **Spec:** `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` v5.1
- **Architecture:** Path A (single .fap, FlipperAppType.EXTERNAL, AppDataExchange)
- **Wire protocol:** 16-byte CFC header + msgpack payload, 884 bytes/frame, 8KB transaction cap
- **NotebookLM corpus:** 3 notebooks, 70 sources at `notebooklm/cfc/_upload/`
- **Adversarial review:** 4 Sherpa passes × 3 reviewers = 12 critique runs

### Phase 2: SHIPPED at 17/18 ✅

- **Cook log:** `docs/decisions/DAY9_PHASE2_COOK_LOG.md`
- **FAP source:** `cfc/cfc.c` (590 lines, builds clean with 0 warnings)
- **Host module:** `flipper_mcp/modules/cfc/module.py`
- **Tests:** 18 test files at `tests/cfc_phase2/` — **17 passing, 1 halted**
- **Deployed:** `/ext/apps/Tools/cfc.fap` on AmorPoee SD card
- **Cook stats:** ~25 min wall-clock, 1/10 ufbt rebuilds, test suite 4:35 / 5:00

**Q-IMPL findings (resolved at cook time):**
- **Q-IMPL-5:** ✅ `rpc_system_app_exchange_data()` IS safe to call from within the RPC callback — architecture validated by 17 passing tests
- **Q-IMPL-6:** Furi APIs confirmed — `furi_delay_ms()`, `furi_ms_to_ticks()`, `FURI_LOG_E/I/D(TAG, fmt, ...)` macros
- **Q-IMPL-7:** `int32_t cfc_app_main(void* p)` — and CRITICAL: firmware rewrites `app_start("cfc", "RPC")` args to `"RPC %08lX"` containing hex pointer to `RpcAppSystem`. FAP must parse this hex string to get its RPC handle. See cook log §4 and `rpc_service_all.txt:783-787`.

**One halt — `test_stale_transaction` failure (Phase 2.5 investigation):**
- BUSY-during-ASSEMBLING is detected correctly (sub-assertion 1 ✅)
- But the original transaction's resume fragment receives ERROR instead of PING
- Hypothesis: FAP's `rpc_system_app_exchange_data` malloc'd Main has uninitialized command_id causing host-side stale-frame collision
- Fix-attempt budget exhausted per spec §13.2 → halted cleanly

**Known spec discrepancy (correction deferred to Phase 2.5):**
- Spec §6.4 implies `rpc_system_app_exchange_data()` returns `bool`
- Actual header `rpc_app.h:220` declares it `void`
- Phase 2 didn't hit this (single-fragment outbound only); Phase 2.5 chunking will

### Phase 2.5: NEXT

Two items, both small and well-scoped:
1. Investigate `test_stale_transaction` command_id collision (instrument FAP to log outbound Main command_id; consider relaxing host-side command_id matching for app_data_exchange responses)
2. End-to-end chunking validation (>884 byte response roundtrip)
3. Spec §6.4 patch (`bool` → `void`)

### Phase 3: QUEUED

NFC vertical slice + host-listener architecture for async opcodes. See spec §6.5.

---

## Open R-series findings (from cc Phase 1 capability survey, Day 5)

- **R5 (storage_write false-failure):** ✅ FIXED Day 4, re-validated Day 7
- **R6 (large script crash):** ✅ SUBSUMED by R5
- **R7 (orphan flipper-mcp processes):** ⚠️ **Re-observed Day 9 Phase 2 cook** — six stale `flipper_mcp.cli.main` processes were holding COM9 when cook tried to deploy via ufbt. Resolved with `Stop-Process`. Worth a longer-term mitigation: maybe a "kill-stale-flipper-mcp-processes" helper script, or auto-detect and warn in flipper-mcp startup.

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
- **Last session goal achieved:** Phase 1 + Phase 2 both shipped. Architecture validated empirically. 17/18 tests pass on real hardware.
- **Next session goal:** Phase 2.5 — fix `test_stale_transaction`, validate chunking, then move to Phase 3 (NFC vertical slice). OR push the three Day 9 commits to GitHub if not done.
