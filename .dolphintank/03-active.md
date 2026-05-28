# CPK ACTIVE — What's In Flight Right Now

> 03-active wins on **"what should we work on."**
> If 03-active disagrees with anything else about priority, 03-active is correct.
> If you're a future Claude reading this, **the first item is what to start with.**

---

**Last updated:** 2026-05-27 (Day 11 — Cook 1 IN FLIGHT)

---

## 🔥 Currently in flight (active work)

### 1. CPK Companion FAP — Phase 3 Cook 2 (subscription dispatcher + FAP worker + MOCK NFC)

**Status:** Cook 1 + Cook 1.5 SHIPPED. Reader is LIVE (33/33, all 19 tools migrated, host genuinely listens). Cook 2 is next. Fire prompt ready at `D:\Dev\scratch\day11_phase3_cook2_fire_prompt.md`.

**Cook 2 = FIRST "it's alive" moment.** After this cook Victor can run `flipper_cfc_subscribe` + `flipper_cfc_listen` and watch FAKE NFC events (DE:AD:BE:EF) stream every ~2s. Every moving part real (reader, worker thread, broadcast lane, dispatch) — only the card data is faked.

**Cook 2 scope:** un-stub subscription dispatcher (host MCP tools) + FAP FuriThread worker + mock broadcasts. Leave Phase-4 UI hook seam (comment marker only). Use the EXISTING reader — do NOT spin a second.

**Then Cook 3:** swap mock for real Momentum NFC, live card tap, closes Phase 3.

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


