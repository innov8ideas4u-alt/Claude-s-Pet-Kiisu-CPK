# CPK STATE — What's True Right Now

> 02-state wins on **"what is true now."**
> If 02-state disagrees with anything else, 02-state is correct.
> If 02-state's timestamp is stale (>7 days old), distrust it and verify.

---

**Last updated:** 2026-05-27 (Day 11 session close — PHASE 3 GREEN, real NFC capture live-fired)
**Updated by:** Victor + Claude Desktop
**Confidence:** HIGH — Phase 3 live-fire PASSED on hardware; commit verified

---

## Repository state

- **Default branch on GitHub:** `main` at commit `6bf1d32` (Phase 2.5 shipped, pushed to GitHub)
- **Active branch:** `phase3-cook1-host-refactor` at commit `425b62e` (Phase 3 Cook 1→3.3, NOT pushed/merged — operator review pending)
- **Stargazers:** 2
- **Working tree (Day 11 close):** CLEAN. Phase 3 stack committed at 425b62e (Cook 3+3.1+3.2+3.3 squashed into one commit; per-cook story lives in scratch cook log).
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

### Phase 3: GREEN ✅ (Day 11, commit `425b62e`)

Real NFC capture live-fired on AmorPoee. NFC vertical slice + host-listener async opcodes complete. The route-by-tag pattern and `cfc_recv_response_assembled` helper carried forward from Phase 2.5. See "Phase 3 Cook 3→3.3 — GREEN" section at bottom for full detail.

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


---

## Phase 3 Cook 1 — SHIPPED (2026-05-27, commit aa5a1c8, branch phase3-cook1-host-refactor)

**Status:** Cook 1 complete, 33/33 tests green. NOT yet pushed/merged (operator review pending). NOT yet on main.

**What's true now:**
- Host-side reader-task infrastructure exists in `flipper_mcp/core/protobuf_rpc.py` — ADDITIVE ONLY, dormant. Existing RPC traffic still uses the legacy `_send_rpc_message → _receive_main_message` direct path. The reader is wired but not engaged.
- Two parallel pending maps live: `_pending` (cmd_id-keyed, non-CFC) and `_cfc_pending` (transaction_id-keyed, CFC; outer cmd_id ignored per Momentum uninit-malloc bug).
- Multi-fragment reassembly (`_cfc_assembling`, `_broadcast_assembling`) implemented and tested.
- Subscription dispatcher (`_subscriptions`, `_Subscription` dataclass with overflow-drops-oldest) is STUBBED — no public subscribe/listen/unsubscribe MCP tools yet (Cook 2).
- 6 new reader-isolation tests in `tests/phase3/` (synthesized frames, no hardware). All 27 Phase 2.5 live-hardware tests unchanged and green.

**Environment fact (NOT committed, but baseline-blocking):**
- protobuf runtime MUST be >=6.x on this machine. Generated code in `flipper_mcp/core/protobuf_gen/` is gencode 6.33.2. Machine was bumped 5.29.5 → 6.33.6 during Cook 1. Anyone reproducing baseline needs `pip install protobuf==6.33.6` (or any 6.x).

**Backup:** `protobuf_rpc.py.bak` in working dir (scratch, not committed).

**NOT engaged until Cook 1.5:** the reader does not auto-start at connect(). Engaging it before migrating existing paths = racing readers = red suite.


---

## Phase 3 Cook 1.5 — SHIPPED (2026-05-27, reader LIVE)

**Status:** Cook 1.5 complete, 33/33 green on live hardware across 4 gates + 11/11 hardware smoke + cli_command. NOT pushed/merged (operator review pending). Same branch (phase3-cook1-host-refactor).

**What's true now — the host genuinely listens:**
- Reader is ENGAGED. Auto-starts via `_ensure_session_and_reader()`. It is the SOLE caller of `_receive_main_message` (except the reader loop itself + pre-reader session probe).
- All 19 public methods migrated off `@_with_wire_lock` to the reader path. Wire lock is now SEND-ONLY.
- §16.1 has_next streams → per-cmd_id asyncio.Queue (`_send_rpc_stream`). device_info/storage_list/storage_read drain until has_next==False.
- §16.2 storage_write → one cmd_id, one Future, all chunks under one lock hold, single terminal ack, popped only in finally.
- §16.3 cli_command → stop reader → CLI text I/O under wire lock → restart session+reader (chose stop/restart over bypass).
- CFC migrated: `_cfc_send_one_frame` registers a txn future, awaits reader reassembly. 4 mock tests rewritten to inject via reader.
- Runtime DROPPED 4:13 → ~1:56 (old CFC path wasted ~2.5s/fragment draining; reader model removed it).

**Two bugs cc fixed going live (NOT predicted by spec):**
1. CFC assembly must key on txn ONLY, not cmd_id==0. FAP sends each fragment via separate exchange_data with independently-garbage command_id, so multi-fragment responses would NEVER reassemble once live. Unified on `_cfc_assembling`. (Would have passed all mocks, failed first real card tap in Cook 3.)
2. conftest self-deadlock — `async with _wire_lock: _send_rpc_message(...)` deadlocked against now-lock-acquiring `_send_rpc_message`. Switched to public `app_exit()`.

**Removed dead code:** `@_with_wire_lock`, `_send_main_raw`, functools import.

**Env fact:** NO .venv. System C:\Python313, protobuf 6.33.6.

**Changed files:** flipper_mcp/core/protobuf_rpc.py, flipper_mcp/modules/cfc/module.py, flipper_mcp/core/flipper_client.py, tests/cfc_phase2/conftest.py, 4 rewritten test mocks. Backup: protobuf_rpc.py.cook15.bak.

**Cook 2 flags (from log):** subscription dispatcher still stubbed (Cook 2 first task); no session-start lock (add asyncio.Lock if Cook 2 has concurrent first-callers); `_broadcast_assembling` now unused (broadcasts will use unified `_cfc_assembling`); broadcasts route via `_deliver_cfc` → tries `_cfc_pending[txn]` then `_subscriptions[op]`.


---

## Reference resource — Momentum firmware local mirror (2026-05-27)

**Location:** D:\Dev\Projects\_reference\Momentum-dev\ (sibling to _reference\Bruce\)
**Commit:** d3ba597 (branch dev, mntm-dev family, dated 2026-05-12), recursive w/ all submodules. 497MB, 22k files.
**Why:** Full local checkout of the firmware AmorPoee runs. Claude greps/reads real firmware source instantly via Desktop Commander — no re-cloning per recon question. Saves tokens + tool calls.
**RULE:** READ-ONLY reference mirror. Never commit/push/treat as a project repo. Never confuse with the CPK project repo. When recon needs firmware files: grep here → copy needed file(s) into the relevant notebookN_* upload folder as .txt → curate (never bulk-dump into NotebookLM).
**NotebookLM notebook5_nfc_firmware** was sourced from THIS commit, so the mirror and the uploaded NFC corpus are version-matched (no drift).


---

## Phase 3 Cook 2 — SHIPPED (2026-05-27, 48/48, FIRST "ALIVE" MILESTONE)

**Status:** Cook 2 complete. 48/48 on live AmorPoee (27 Phase-2 hardware no-regression + 21 phase3). FAP builds clean (uvx ufbt, Target 7, API 87.1), deployed to /ext/apps/Tools/cfc.fap. NOT committed/pushed.

**THE PIPE IS ALIVE:** subscribe(0x42) → FAP armed worker → listen got a broadcast in ~2s with txn 0x80000000 (M3 high bit correct), uid=DEADBEEF, type="iso14443a-4", real timestamp_ms → unsubscribe disarmed. Only the card data is mock; every moving part real.

**Mandates VERIFIED in source (not just claimed):**
- M1+M2: _Subscription buffer = deque(maxlen=SUBSCRIPTION_QUEUE_DEPTH), atomic evict-oldest, NO await put in delivery path. Live-hang + drop-race designed out.
- M3: txn high-bit partition (CFC_BROADCAST_TXN_BIT=0x80000000) asserted BOTH directions in _deliver_cfc; host allocator masks 0x7FFFFFFF. Broadcast-resolves-wrong-Future is now structurally impossible.
- M4: guarded stale-subscriber push. M5: chaos tests present.
- Q2 exclusive subscribe → CFC_ERR_BUSY; idempotent unsubscribe; listener wake-on-close.
- FAP: CfcWorker FuriThread + 2 queues (stack 2048), ack→delay(20)→arm (Q1), worker never touches wire (Q3), PHASE4-UI-HOOK marker placed, 5-min idle=disarm, clean shutdown.

**Flags:**
1. 5 pre-M3 tests used high-bit request txns (now illegal) → updated to host namespace. Conformance, not behavior. (Proves M3 assertion fires.)
2. §5.5 idle = disarm (not full teardown) — avoids re-creation churn, intent preserved.
3. Wire-interleaving single-writer mutex DEFERRED to Cook 3 — temporally separated in mock; becomes REAL when a tap coincides with a response. = Cook 3 MUST-DO #1.

**⚠️ GIT HYGIENE:** Cook 1.5 is UNCOMMITTED in working tree. HEAD still = Cook 1 (aa5a1c8). Cook 2 layered on top of uncommitted 1.5. Commit before Cook 3.

**Backups:** cfc/cfc.c.cook2.bak, protobuf_rpc.py.cook2.bak.
**Cook 3 spec draft ready:** D:\Dev\scratch\day11_cook3_spec_DRAFT.md (NFC recon COMPLETE, all sigs verified vs mirror commit d3ba597).


---

## Phase 3 Cook 3 → 3.3 — GREEN (2026-05-27, committed 425b62e)

**Status:** Phase 3 functionally COMPLETE. Real NFC capture live-fired on AmorPoee. Committed as ONE commit on `phase3-cook1-host-refactor` (Cook 3+3.1+3.2+3.3 squashed — edits were intermingled in cfc.c/module.py, never separately committed; per-cook story preserved in `D:\Dev\scratch\day11_phase3_cook3_log.md`). NOT pushed/merged — operator review pending.

**What each cook did:**
- **Cook 3:** swapped mock broadcasts for live Momentum NFC — FAP worker detects, polls, broadcasts real card UIDs over the 0x42 lane; host reader reassembles + delivers.
- **Cook 3.1:** persistent scanner — keep sweeping after `detect_cb` instead of stop-on-first. PROVEN correct on hardware (detect_cb fired 60+ times in the Cook 3.2 diagnostic).
- **Cook 3.2:** 0x4F diag broadcast (separate op_code, host-only buffer, concurrent harness drainer) — exposed that detect fired reliably but never transitioned to poll. Reusable diagnostic pattern.
- **Cook 3.3:** widened the accepted-protocol gate. Root cause: gate was exact-enum-equality `if(detected[i] != NfcProtocolIso14443_3a) continue`, but NTAGs arrive as the LEAF `NfcProtocolMfUltralight` because `nfc_scanner_filter_detected_protocols` strips parent protocols. Fix: 2-line change using firmware's own `nfc_protocol_has_parent(protocol, Iso14443_3a)` walk to accept the whole ISO14443-3A family. ADDITIVE — Iso14443_3a path unchanged.

**Gates passed (driven by Claude Desktop from PowerShell, see meltdown note):**
- 51 host tests green, zero regressions from the widened gate.
- FAP clean -Werror build, Target 7 / API 87.1, `nfc_protocol_has_parent` linked clean (exported on f7 per api_symbols.csv).
- Deploy via `uvx ufbt launch`.
- **LIVE-FIRE PASS:**
  ```
  tap#1: uid=04:6d:d7:0a:48:20:90 type=ISO14443-3A txn=0x80000002
  tap#2: uid=04:6d:d7:0a:48:20:90 type=ISO14443-3A txn=0x80000005
  PASS: real NFC UIDs delivered host-side; continuous scan confirmed.
  ```
  Real UID off Victor's NTAG/Ultralight, two sequential taps, M3 high-bit txn, continuous capture without re-subscribe, HAL released clean on unsubscribe (stock NFC app confirmed working post-test — no F4-class bug).

**cc tool-layer meltdown (operational fact):** Cook 3.3's cc (Opus 4.8) session had Read/Grep/Bash return empty mid-cook, one Bash flooded "the the the" garbage, then a 400 API error on final reply (`thinking blocks in latest assistant message cannot be modified` — protocol-level, not model). cc HALTED HONESTLY rather than fabricating green results — the 4.8 strict-honesty muscle. Claude Desktop finished the mechanical gates (pytest/build/deploy/live-fire) from PowerShell directly. Workaround if it recurs: don't restart cc into a degraded session; Desktop drives remaining mechanical work.

**Deferred (optional, belt-and-suspenders):** `tests/phase3/test_nfc_ntag_event.py` — synthesize a 0x42 broadcast with 7-byte UID + type="ISO14443-3A", assert `_check_real_event` accepts it. Live-fire already proved this in reality.


---

## Phase 3 Sub-GHz Cook 1 — GREEN (2026-05-28, live-fire passed; UNCOMMITTED→committing now)

**Status:** Second RF vertical COMPLETE. Real fixed-code Sub-GHz (Princeton) decoded off-air end-to-end and delivered host-side. Branch phase3-cook1-host-refactor, layered on 425b62e. Live-fire PASSED.

**What's true now:**
- FAP `cfc/cfc.c` gains a Sub-GHz decoded-stream RX worker (twin of the NFC worker): subscribe(0x52) arms a SubGhzWorker on 433.92/OOK650, every decoded fixed-code parcel broadcasts {protocol,bits,key,frequency,timestamp_ms,drops} on op 0x52; 0x5F diag lane mirrors every decode pre-gate. Host `flipper_mcp/modules/cfc/module.py` decodes the 0x52 event; reuses the Cook 1.5 reader + 0x80000000 broadcast routing unchanged.
- Mock suite `tests/phase3/test_subghz_decode_and_drops.py` (17) + full regression 49 green.
- **LIVE-FIRE PASS** (Kiisu#2 TX Princeton 433.92 → AmorPoee RX): `protocol=Princeton bits=24 key=0xA34E44 freq=433920000 drops=0`, M3 high-bit txns, 20 parcels delivered under one subscription, clean unsubscribe/disarm. Expected key 0x00A34E44 matched exactly.

**TWO real bugs found AT LIVE-FIRE (both invisible to the 49 mock tests — mocks don't touch the radio):**
1. **begin-NULL fatal-gate bug.** `cfc_subghz_arm` treated `!subghz_devices_begin()` as fatal. The INTERNAL CC1101 interconnect has `.begin == NULL` (cc1101_int_interconnect.c), so `subghz_devices_begin()` returns false BY DESIGN (begin is the EXTERNAL-radio power-on handshake). Fix: call begin for external-device compat, do NOT gate on its return; real bring-up is reset/load_preset/set_frequency/set_rx; `.end`=furi_hal_subghz_shutdown still pairs in disarm. Dead error-unwind/fail: path removed.
2. **SubGhzBlockGeneric ABI drift (THE big one).** ufbt SDK `generic.h` is STOCK and narrower than Momentum's: Momentum inserts `data_2`(uint64) after `data`, plus `cnt_2`/`seed`. SDK puts `data_count_bit` at offset 20; firmware keeps it at 28. The struct-cast read bits from inside the firmware's unused `data_2` → always 0 (fingerprint: protocol=Princeton, bits=0, accepted=false). `data`/key at offset 8 in both, so key was fine. Fix: `CfcSubghzDecoderHead.generic` pinned to a firmware-accurate `CfcMtmGeneric` struct (not the SDK's). **GENERAL LESSON: ufbt SDK headers are stock/upstream and do NOT reflect Momentum struct extensions — never trust an SDK struct's field offsets for a private FAP cast; pin to the mirror (d3ba597).**

**Diagnostics added & kept:** `cfc_subghz_arm` now returns a reason code (1=no device, 2=freq invalid, 3=begin) surfaced as a distinct CFC error string — turned an opaque "subghz arm failed" into a one-run diagnosis. Keep.

**Live-fire harness:** `D:\Dev\scratch\live_fire_subghz.py` (EXPECTED_KEY=0x00A34E44 wired). FAP deployed via `uvx ufbt launch` (full path `C:\Users\N01\.local\bin\uvx.exe` from non-interactive shells; cfc.fap 28KB→/ext/apps/Tools/).

**ENVIRONMENTAL BUG FOUND (ship-blocker, see 03-active #1):** orphaned `flipper_mcp.cli.main` reader processes busy-spin a full core each (4.16% on a 24-thread box = 1 core at 100%); one had burned 1967 CPU-sec. They cooked the CPU for 8h AND caused the COM9 "Access is denied" + MCP wedging all night. Killed all this session. ROOT cause likely the Cook 1.5 reader loop not blocking/backing-off + no orphan cleanup on exit (R7). A fresh git-clone user would hit this immediately.


---

## Reader CPU-spin (R7 heat) — FIXED (2026-05-28, Day 12)

**Was:** the §13.1 single-reader loop did `if main is None: continue` with no backoff. A healthy idle port makes `_receive_main_message` block ~READER_POLL_S (0.1s) → light. A dead/closed/grabbed port makes the underlying `serial.read` fast-fail → None returns instantly → the loop spins at 100% of a CORE. Orphaned readers (port died after unplug / session end) each pegged a full core for hours (one had 1967 CPU-sec). This cooked the operator's CPU for 8h AND was a hidden contributor to the COM9 "Access is denied" + MCP-wedge churn. A fresh git-clone user would hit this immediately = reputation/ship-blocker.

**Fix (`flipper_mcp/core/protobuf_rpc.py`):** `_reader_loop` now measures poll elapsed; if a None came back FASTER than READER_POLL_S (fast-fail signature), it sleeps the remainder → loop rate capped at ~10/s regardless of how fast the read failed. Same backoff added to the `except Exception` path (port-closed-under-us). `import time` added (was only a local import elsewhere). Zero healthy-path cost (a live idle port already blocks the full window).

**Verified:** tests/phase3 41/41 green AND runtime collapsed 34.4s→2.5s (the 32s WAS the spin); tests/cfc_phase2 27/27 green on live AmorPoee (no healthy-read regression). Post-fix: 0 flipper_mcp processes spinning; CPU calm.

**Residual (NOT urgent, R7 follow-up):** the fix stops the HEAT, not the LINGER — orphaned readers can still survive a dead session as idle (near-zero-CPU) processes. A clean shutdown hook (stop reader + close port) or a `python -m flipper_mcp.tools.kill_stale` helper would stop them piling up. Side-task, queued.
