# CPK ACTIVE — What's In Flight Right Now

> 03-active wins on **"what should we work on."**
> If 03-active disagrees with anything else about priority, 03-active is correct.
> If you're a future Claude reading this, **the first item is what to start with.**

---

**Last updated:** 2026-05-27 (Day 10 session close — Phase 2.5 SHIPPED at 27/27)

---

## 🎯 Currently in flight (active work)

### 1. CPK Companion FAP — Phase 3 (NFC vertical slice + host-listener architecture)

**Status:** Phase 2.5 shipped at 27/27 on 2026-05-27 (commit `6bf1d32`). Phase 3 is the next major phase — substantially bigger lift than 2.5.

**Why it's next:** Phase 2.5's route-by-tag drain pattern and `cfc_recv_response_assembled` helper are the foundation Phase 3 builds on. F4 (`require("nfc")` failing on mntm-dev) gets resolved by Phase 3's `cfc.nfc_capture()` opcode instead of fixing the JS binding.

**Three concrete deliverables (high-level — needs spec doc before cook):**

**A. `flipper_cfc_listen` MCP tool for unsolicited frames.**
- Host-side listener that runs as a background asyncio task, consuming `app_data_exchange_request` frames whose `command_id == 0` (broadcast) or whose op_code matches a registered subscription.
- Routes to per-opcode handler callbacks. Tests dispatch async events without polling.
- Architecture per DAY10 design doc §6: route-by-tag is already in place; listener hooks into the same dispatch but for the broadcast/subscribe path instead of the request/response path.
- **Estimated wall clock:** ~3-4 hours including adversarial review.

**B. FAP-side `FuriThread` worker pattern.**
- Heavy-weight ops (NFC capture, SubGHz scan) can't block the RPC callback. Phase 3 introduces a worker thread on the FAP side that does the actual hardware work; the RPC callback just queues a job and returns immediately.
- Job results flow back via `rpc_system_app_exchange_data` broadcasts (command_id=0) — which the host listener (deliverable A) picks up.
- **Estimated wall clock:** ~2-3 hours including spec.

**C. First NFC opcode: `NFC_SUBSCRIBE_CAPTURE`.**
- Validates A+B end-to-end. Subscribes to NFC reads, receives unsolicited frames as cards approach.
- Replaces F4 (`require("nfc")` broken on mntm-dev).
- **Estimated wall clock:** ~2-3 hours.

**Next concrete action:** Open new chat, do a Phase 3 spec design doc (DAY11_PHASE3_SPEC.md). Run it through the same 8-round review pipeline that worked for Phase 2.5. Then cook.

**Pre-Phase-3 prep available now (out of band):**
- NotebookLM Round 4 question (queued from Phase 2.5): enumerate ALL frame types the firmware emits — sync AND async — in response to host RPC requests. Findings inform the listener's allowlist.

---

## 🟡 Queued (next, after Phase 3 ships)

### 2. Phase 4 — SubGHz / IR / GPIO opcodes

Each is a short cook informed by the NotebookLM corpus and the patterns Phase 3 established.

**Estimated wall clock:** ~4-6 hours across multiple sessions.

### 3. Momentum PR submission

Draft is ready at `D:\Dev\scratch\day10_momentum_pr_draft.md`. Patches both `rpc_system_app_exchange_data` and `rpc_system_app_send_state_response` with memset-after-malloc to zero `command_id`. Phase 2.5's workaround can be sunset once this lands upstream and AmorPoee runs a Momentum build that includes the merge.

**Estimated wall clock:** ~1-2 hours (line-number verification, build local Momentum, before/after wire-trace, submit). Not blocking anything.

---

## 🟢 Side-tasks ready to grab (lower priority, independent)

### Fix F2: `storage_info` returns SD card stats for `/int`

Quick win, ~30 min. Bug in `flipper_mcp/modules/storage/module.py` — `path` arg not passed through.

### Investigate F1: `require("gpio")` failure

**Subsumed by CFC Phase 4** (gpio opcode). Park indefinitely.

### Mitigate R7: orphan flipper-mcp / pyserial processes

Re-observed in Phase 2 AND Phase 2.5 cooks. Worth a small helper: `python -m flipper_mcp.tools.kill_stale` that finds and kills orphan instances. Day 10 operational learning: physical USB unplug/replug is the fastest workaround when this hits. ~1 hour for a proper script.

### First red-team mission: `nfc_clone_owned`

Depends on CFC Phase 3's NFC opcodes. Defer until Phase 3 ships.

---

## ❄️ Frozen (won't pick up unless something changes)

### Android-as-BLE-bridge architecture

Deep recon dossier at `D:\Dev\scratch\llmdr_android_recon\`. Multi-month project. Parked.

### CPK venv migration (cleanup the .pth band-aid)

The editable install works. Hygiene-only fix. Pick up when something breaks.

---

## Working principles for items in flight

- **Vision → research → design → build.** Phase 1 (research+design), Phase 2 (build), Phase 2.5 (refine) all shipped via this discipline. Phase 3 follows the same template.
- **Each phase produces a decision/cook doc.** Phase 1 produced spec v5.1, Phase 2 produced DAY9_PHASE2_COOK_LOG.md, Phase 2.5 produced DAY10_PHASE2_5_DESIGN.md (1464 lines, 8.4 review iterations). Phase 3 will produce DAY11_PHASE3_SPEC.md.
- **Live-fire validation is mandatory.** No "smoke tests are enough." Real device, real RPC frames, real log lines.
- **Commit per phase, not per feature.** Each phase commit captures one coherent unit of work.
- **Multi-reviewer adversarial review pays off massively.** Phase 2.5's 8 rounds (Sherpa ×2, Gemini ×2, NotebookLM ×3, Arena ×2) caught issues no single reviewer would have. The Arena.ai random-model approach was a particularly cheap win.

---

## Day 10 highlights (full session)

**Phase 2.5 cook — 60 minutes wall-clock, 4 attempts, 6 halts:**

- **Halt 1 (v8.1):** §4.0 mock scaffold defect — MagicMock-hasattr-everything trap. Resolved by passing rpc directly as client.
- **Halt 2 (v8.1):** COM9 locked by flipper-mcp. Resolved by toggling flipper-mcp off in cc.
- **Halt 3 (v8.2):** `empty` sync RPC ack frame not in Q6 allowlist. Resolved by adding empty to allowlist + parametrize.
- **Halt 4 (v8.3):** PING handler 884-byte ceiling, pre-existing FAP bug unmasked. Resolved by implementing spec §6.4 multi-fragment outbound.
- **Halt 5 (v8.3 deploy):** COM9 lock after deploy script (pyserial reader orphan). Resolved by physical USB unplug/replug.
- **Halt 6 (v8.3):** test_stale_transaction expected single-fragment response. Resolved by adding `cfc_recv_response_assembled` helper + updating test.

**Result:** 27/27 full Phase 2 suite, 10/10 deterministic stale_transaction. Phase 2.5 commit `6bf1d32` pushed to origin/main.

**Major discoveries (folded into design doc):**
- `rpc_system_app_send_state_response` shares the uninit-malloc bug with `rpc_system_app_exchange_data`
- The RPC dispatcher emits a per-request `empty` Main as sync ack for EVERY host request (previously invisible)
- The PING handler's 884-byte stack buffer ceiling was unexposed pre-Phase-2.5

---

## What this list does NOT include

State changes go in 02-state, not here. Decisions go in 04-decisions, not here. Things already shipped go in 05-dont-rebuild, not here. **03-active is forward-looking only.**
