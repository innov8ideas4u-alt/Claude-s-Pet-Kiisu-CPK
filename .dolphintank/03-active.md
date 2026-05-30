# CPK ACTIVE — What's In Flight Right Now

> 03-active wins on **"what should we work on."**
> If 03-active disagrees with anything else about priority, 03-active is correct.
> If you're a future Claude reading this, **the first item is what to start with.**

---

**Last updated:** 2026-05-27 (Day 11 — PHASE 3 GREEN; Phase 4 is next)

---

## 🔥 Currently in flight (active work)

### 1. RFID Cook 1 — LF 125 kHz capture vertical (CFC opcode 0x62)

**Status:** SPEC CLEARED TO FIRE (Day 13), CODE NOT STARTED. Spec at `D:\Dev\scratch\day13_rfid_cook1_recon.md`; review trail `..._REVIEW.md`. Third RF capture vertical after NFC (0x42) + Sub-GHz (0x52). Reviewed by cc + NotebookLM (converged).

**Next action:** fire the cook (FAP build order: busy-guard FIRST → alloc → start_thread → read_start(Auto) → value-only queue → DEFERRED re-arm → verify stock RFID app reads post-test). No COM9 needed for the cook (files-only); build/deploy I drive from PowerShell.

**⛔ LIVE-FIRE BLOCKED:** operator has NO LF card/fob. Cook + build + deploy can proceed; the real-card live-fire waits for an EM4100/HID-Prox tag. Do NOT mark shipped or touch README until a real card reads.

**Locked decision:** global single-active RF worker (decision 027) — busy-guard is crash-prevention (furi_hal_bus furi_check → bluescreen).

### 2. IR Cook — RX-learn + TX vertical (recon done, spec unwritten)
**Status:** RECON DONE at `D:\Dev\scratch\ir_cook_recon.md`. IR is TX + RX = TWO opcodes (first host→device ACTION opcode, not just capture). Pairs with the `app_load_file` "replay saved .ir via stock app" idea. Spec it after RFID.

### 3. Phase 4 — "Clawd walks Kiisu" companion UI

**Status:** NOT STARTED. Deferred behind the RFID + IR verticals. Phase 3 closed GREEN (real NFC capture live-fired).

**Concept:** Crab (Claude Code mascot) + cat (Kiisu) on the Flipper screen. Ideas doc at `D:\Dev\scratch\cfc_companion_ui_ideas.md`. The PHASE4-UI-HOOK comment marker is already placed in the FAP worker (Cook 2 left the seam).

**Before starting:** read the ideas doc + decide scope of the first cook. No fire prompt drafted yet.

---

### (historical) Phase 3 Cook 2 — subscription dispatcher + FAP worker + MOCK NFC

**Status:** ✅ SHIPPED Day 11 (48/48, first "it's alive" milestone). Superseded by Cook 3.x which swapped mock for real NFC. Kept for history.

---

### (historical) Cook 1.5 — migrate existing tools to reader

**Status:** Cook 1 SHIPPED (commit aa5a1c8, branch phase3-cook1-host-refactor, 33/33, NOT pushed). Cook 1.5 is next. Spec at `docs/decisions/DAY11_PHASE3_SPEC.md` v4.

**Cook 1.5 scope — migrate existing RPC paths onto the (now-proven) reader:**
- Migrate `_send_rpc_message` (single-shot) to future pattern
- Migrate `_cfc_send_one_frame` to reader-driven CFC-txn path
- Update the 4 mock tests in `tests/cfc_phase2/` that hardcode internal call shape
- Engage the reader (auto-start at connect) ONCE all paths migrated — not before (racing readers = red suite)

**THREE spec-corrections cc found during Cook 1 that Cook 1.5 MUST handle (spec §16):**
1. **has_next chains need a STREAM, not a single-shot Future** (§16.1). `get_device_info`, `storage_read`, `storage_list` pull multiple frames per logical call. Use a per-cmd_id asyncio.Queue for these; Future only for true single-response methods.
2. **storage_write reuses one cmd_id across many chunks** (§16.2). The `_pending[cmd_id]` cleanup must defer to the FINAL ack, not fire between chunks.
3. **cli_command leaves RPC mode** (§16.3). Stop the reader before the CLI switch, restart after — or bypass the reader for cli_command entirely.

**Next concrete action:** Decide push-now-or-after-1.5 (operator). Then fire Cook 1.5 with the three §16 corrections in the cc prompt.

---

## 🟡 Queued

### 2. Phase 3 Cook 1.5 — migrate existing tools to reader pattern
- Migrate `_send_rpc_message` and `_cfc_send_one_frame` to future-driven model
- Update 4 mock tests in `tests/cfc_phase2/` (test_broadcast_path_mock, test_non_cfc_frame_raises_desync, test_async_event_consumed_during_drain, test_cfc_timeout_returns_none)
- All 27 Phase 2.5 tests + 9 phase3 tests stay green
- Estimated 2-3 hours

### 3. Phase 3 Cook 2 — FAP worker skeleton + mock NFC broadcasts
- Add `CfcWorker` struct + FuriThread + queues to `cfc/cfc.c`
- Implement CFC_OPCODE_NFC_SUBSCRIBE / UNSUBSCRIBE (mock, no real NFC)
- Worker emits a mock broadcast every 2 seconds when armed
- Estimated 3-4 hours

### 4. Phase 3 Cook 3 — real NFC + live-fire
- Replace mock with Momentum NFC C API
- Live-fire on AmorPoee
- DAY11_PHASE3_COOK_LOG.md
- Estimated 2-4 hours

### 5. Momentum PR submission
Draft ready at `D:\Dev\scratch\day10_momentum_pr_draft.md`. Not blocking. ~1-2 hours.

---

## 🟢 Side-tasks ready to grab (lower priority)

### Fix F2: storage_info returns SD card stats for /int
Quick win, ~30 min.

### Mitigate R7: orphan flipper-mcp / pyserial processes
~1 hour for `python -m flipper_mcp.tools.kill_stale` helper.

### First red-team mission: nfc_clone_owned
Depends on Cook 3.

---

## ❄️ Frozen

### Android-as-BLE-bridge architecture
Deep recon at `D:\Dev\scratch\llmdr_android_recon\`. Parked.

### CPK venv migration (.pth band-aid cleanup)
Hygiene-only.

---

## Working principles for items in flight

- **Vision → research → design → build.** Phase 3 followed this. The cc halt is a feature, not a bug — caught spec blind spots.
- **Each phase produces a decision/cook doc.** DAY11_PHASE3_SPEC.md is the current authoritative doc; v3 includes Sherpa fixes + cc halt resolution.
- **Live-fire validation is mandatory.** Cook 3 closes Phase 3, not Cook 1.
- **Commit per cook, not per phase.** Phase 3 will have 3-4 commits.
- **Adversarial review + cc pre-flight catches blind spots no single reviewer would.** Day 11 proved this: Sherpa caught reassembly gap (§13.1), cc caught mock-test migration tension (§15.2).

---

## Day 11 highlights (in progress)

- **Morning recon:** NotebookLM Rounds 4+5, Arena.ai dual-review, Sherpa pre-spec critique. Surfaced architecture failure modes BEFORE drafting the spec — saved hours.
- **Defaults sheet:** `D:\Dev\scratch\day11_phase3_defaults_sheet.md` resolved Q1-Q7 with cited reasoning per question.
- **Spec drafted:** `docs/decisions/DAY11_PHASE3_SPEC.md` v3. 557 lines. 3 Sherpa reviewers + 1 cc halt = 3 patch sections folded in.
- **Cook 1 launched:** infrastructure-only after the scope split.

---

## What this list does NOT include

State changes go in 02-state. Decisions go in 04-decisions. Things already shipped go in 05-dont-rebuild. **03-active is forward-looking only.**


