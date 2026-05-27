# CPK ACTIVE — What's In Flight Right Now

> 03-active wins on **"what should we work on."**
> If 03-active disagrees with anything else about priority, 03-active is correct.
> If you're a future Claude reading this, **the first item is what to start with.**

---

**Last updated:** 2026-05-27 (Day 9 session close — Phase 2 shipped at 17/18)

---

## 🎯 Currently in flight (active work)

### 1. CPK Companion FAP — Phase 2.5 (fix the one halt + validate chunking)

**Status:** Phase 2 shipped at 17/18 tests passing. One known halt: `test_stale_transaction`. Two small items + one tiny spec patch carry forward.

**Three concrete deliverables:**

**A. Resolve `test_stale_transaction` halt.**
- Symptom: After FAP correctly sends BUSY for a foreign-txn fragment during ASSEMBLING, the *original* transaction's resume fragment receives ERROR (0xFF) instead of PING success.
- Hypothesis (per cook log §10): FAP's `rpc_system_app_exchange_data()` mallocs a Main with uninitialized `command_id` → host's stale-frame matching (in `_send_rpc_message`) discards the wrong frame.
- Plan A: Instrument FAP-side `cfc_send_*` paths to log the outbound Main `command_id` before sending. Confirm or refute the uninit hypothesis.
- Plan B (if A confirms): either (1) submit Momentum patch to zero the Main in `rpc_system_app_exchange_data`, or (2) relax host-side command_id matching specifically for `app_data_exchange` responses (treat them as broadcasts per spec H8).
- **Estimated wall clock:** ~2 hours (1 hour investigation, 1 hour fix + verify test passes).

**B. End-to-end chunking validation (Phase 2.5 per spec §9).**
- Send a >884-byte PING echo, verify fragmentation roundtrip works in both directions.
- Catches msgpack encode-decode mismatches between cmp (C) and msgpack-python before Phase 3.
- Test: `tests/cfc_phase2/test_chunked_ping_roundtrip.py` — send 2KB nested msgpack via PING, assert byte-identical echo.
- **Estimated wall clock:** ~1 hour.

**C. Spec §6.4 patch — `bool` → `void`.**
- Spec §6.4 implies `rpc_system_app_exchange_data()` returns `bool`. Actual `rpc_app.h:220` declares it `void`. Update §6.4 to reflect reality. No fallback "if !sent" path because the firmware doesn't tell you.
- **Estimated wall clock:** ~5 minutes.

**Next concrete action:** Open new chat, fire `cc cook` for Phase 2.5 with the three items above. Same cook discipline as Phase 2.

---

## 🟡 Queued (next, after Phase 2.5 ships)

### 2. Phase 3 — Host-listener architecture + NFC vertical slice

Implement `flipper_cfc_listen` MCP tool for unsolicited frames, add `FuriThread` worker pattern on FAP side, then build first NFC opcode (NFC_SUBSCRIBE_CAPTURE). Resolves F4 (`require("nfc")` failing on mntm-dev) by replacing it with `cfc.nfc_capture()`.

**Estimated wall clock:** ~6-8 hours across multiple sessions.

### 3. Phase 4 — SubGHz / IR / GPIO

Each is a short cook informed by the NotebookLM corpus and the patterns Phase 3 established.

**Estimated wall clock:** ~4-6 hours across multiple sessions.

### 4. Push Day 9 commits to GitHub

Three commits sitting locally on `main`: `1d5dcca`, `c1f74a8`, `35a9332`. Push when Victor's ready. Not blocking anything.

---

## 🟢 Side-tasks ready to grab (lower priority, independent)

### Fix F2: `storage_info` returns SD card stats for `/int`

Quick win, ~30 min. Bug in `flipper_mcp/modules/storage/module.py` — `path` arg not passed through. Park until Phase 2.5 ships.

### Investigate F1 + F4: `require("gpio")` and `require("nfc")` failures

**Subsumed by CFC Phase 3+.** If gpio.read_all and nfc.capture land in the CFC FAP, we don't need the JS bindings to work. Park indefinitely.

### Mitigate R7: orphan `flipper_mcp.cli.main` processes

Six stale processes held COM9 during Phase 2 cook. Worth a small helper script: `python -m flipper_mcp.tools.kill_stale` that finds and kills orphan instances. Or auto-detect at startup and warn. ~1 hour. Park.

### First red-team mission: `nfc_clone_owned`

Depends on CFC Phase 3's nfc.write. Defer until Phase 3 ships.

---

## ❄️ Frozen (won't pick up unless something changes)

### Android-as-BLE-bridge architecture

Deep recon dossier at `D:\Dev\scratch\llmdr_android_recon\`. Multi-month project. Parked.

### CPK venv migration (cleanup the .pth band-aid)

The editable install works. Hygiene-only fix. Pick up when something breaks.

---

## Working principles for items in flight

- **Vision → research → design → build.** Phase 1 (research+design) and Phase 2 (build) shipped via this discipline. Phase 2.5 + Phase 3 follow the same template.
- **Each phase produces a decision/cook doc.** Phase 1 produced spec v5.1, Phase 2 produced DAY9_PHASE2_COOK_LOG.md. Phase 2.5 will produce DAY9_PHASE2_5_COOK_LOG.md (or similar).
- **Live-fire validation is mandatory.** No "smoke tests are enough." Real device, real RPC frames, real log lines.
- **Commit per phase, not per feature.** Each phase commit captures one coherent unit of work.
- **Adversarial review before any multi-session implementation cook.** For Phase 3 (the bigger lift), run a Sherpa review pass on the host-listener spec before coding.

---

## Day 9 highlights (full session)

**Phase 1 work (morning/midday):**
- NotebookLM corpus bundled and uploaded (3 notebooks, 70 sources)
- Abacus's overshoot drafts audited and abandoned to docs/_abandoned/
- Spec v1 → v5.1 via 4 Sherpa adversarial review passes (12 critique runs)
- Architecture locked: Path A only

**Phase 2 work (afternoon/evening):**
- Precondition discovery: external `flipperzero-protobuf` PyPI broken → spec v5.1 surgical fix to use CPK's internal protobuf_gen
- Cook executed: ~25 min wall-clock, 1 rebuild, 17/18 tests passing
- Q-IMPL-5/6/7 all resolved with concrete answers
- Critical undocumented finding: firmware rewrites `app_start` args to `"RPC %08lX"` carrying hex pointer to `RpcAppSystem`

**Three commits on main, ready to push when Victor wants.**

---

## What this list does NOT include

State changes go in 02-state, not here. Decisions go in 04-decisions, not here. Things already shipped go in 05-dont-rebuild, not here. **03-active is forward-looking only.**
