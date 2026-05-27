# CPK ACTIVE — What's In Flight Right Now

> 03-active wins on **"what should we work on."**
> If 03-active disagrees with anything else about priority, 03-active is correct.
> If you're a future Claude reading this, **the first item is what to start with.**

---

**Last updated:** 2026-05-27 (Day 9 session close)

---

## 🎯 Currently in flight (active work)

### 1. CPK Companion FAP — Phase 2 implementation (skeleton + PING/META/RESET/ERROR)

**Status:** Phase 1 spec at v5, SHIPPABLE. Ready for autonomous cook.

**Spec location:** `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\docs\decisions\DAY8_FAP_PHASE1_SPEC.md`

**What Phase 2 produces:**
- `cfc/` FAP source tree at CPK repo root (parallel to `flipper_mcp/`)
- `cfc/cfc.c` implementing the unified callback flow per §6.3
- `cfc/application.fam` with the minimum manifest per §8
- `cfc/lib/cmp/cmp.{c,h}` vendored from camgunz/cmp (tag resolved at fetch time per §13.1)
- `flipper_mcp/modules/cfc/module.py` exposing `flipper_cfc_call(op_code, payload)`
- `tests/cfc_phase2/conftest.py` + 15 test files per §12.1
- `docs/decisions/DAY9_PHASE2_COOK_LOG.md` capturing build decisions and Q-IMPL-5/6/7 resolutions

**Why it matters:** This is the empirical validation that CFC's architecture (Path A, AppDataExchange) actually works on real hardware. Once Phase 2 ships, Phase 3 (NFC vertical slice) becomes a tractable extension instead of a research project.

**Next concrete action:** Open new chat, fire `cc cook` referencing the v5 spec. The spec is autonomous-cook-ready — all preconditions, stop conditions, and rollback steps are in place.

**Estimated wall clock:** 3-4 hours for cook + verification. Spec's §13.2 caps at 2 hours per cook attempt + 10 rebuilds.

---

## 🟡 Queued (next, after Phase 2 ships)

### 2. Phase 2.5 — Chunked outbound validation

After Phase 2 PING/META work, validate end-to-end chunking: send a >884-byte PING echo, verify the FAP correctly fragments outbound and the host correctly reassembles. Catches any encoding mismatches before Phase 3 hits them.

**Estimated wall clock:** ~1 hour (mostly test writing; chunking code already exists in §6.4 of spec).

### 3. Phase 3 — Host-listener architecture + NFC vertical slice

Implement `flipper_cfc_listen` MCP tool for unsolicited frames, add `FuriThread` worker pattern on FAP side, then build first NFC opcode (NFC_SUBSCRIBE_CAPTURE). Resolves F4 (`require("nfc")` failing on mntm-dev) by replacing it with `cfc.nfc_capture()`.

**Estimated wall clock:** ~6-8 hours across multiple sessions.

### 4. Phase 4 — SubGHz / IR / GPIO

Each is a short cook informed by the NotebookLM corpus and the patterns Phase 3 established.

**Estimated wall clock:** ~4-6 hours across multiple sessions.

---

## 🟢 Side-tasks ready to grab (lower priority, independent)

### Fix F2: `storage_info` returns SD card stats for `/int`

Quick win, ~30 min. Bug in `flipper_mcp/modules/storage/module.py` — `path` arg not passed through.

### Investigate F1 + F4: `require("gpio")` and `require("nfc")` failures

**Subsumed by CFC Phase 3+.** If gpio.read_all and nfc.capture land in the CFC FAP, we don't need the JS bindings to work. Park indefinitely.

### NFC button-press capture mission (the deferred Day 8 work)

**Subsumed by CFC Phase 3.** Park.

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

- **Vision before research, research before design, design before build.** Phase ordering matters. We've now completed: vision (Day 8 DAY8_FAP_VISION.md) → research (Day 9 NotebookLM Q1-Q7 + recon) → design (Day 9 spec v5). Build is next.
- **Each phase produces a decision doc.** Phase 2 produces `DAY9_PHASE2_COOK_LOG.md`.
- **Live-fire validation is mandatory.** No "smoke tests are enough." Real device, real RPC frames, real log lines.
- **Commit per phase, not per feature.** Each phase commit captures one coherent unit of work.
- **Adversarial review before any multi-session implementation cook.** v5 of the Phase 1 spec went through 4 review passes. Sherpa caught the architectural async/sync mismatch in v1 that would have wasted a Phase 2 session if missed.

---

## Day 9 highlights

- **NotebookLM corpus bundled and uploaded.** 3 notebooks, 70 sources, ~3.8 MB total. Bundler at `notebooklm/cfc/_meta/concat_for_notebooklm.py` handles future re-bundles.
- **Abacus's Day 9 drafts audited and abandoned.** They invented a non-functional standalone RPC service. Moved to `docs/_abandoned/` with explanation.
- **Architecture decisively locked.** Path A (FAP + AppDataExchange) confirmed; Path B (.fal) ruled out. Decision basis: NotebookLM Q4 (out-of-tree .fal can't reach furi_hal_*).
- **Spec iterated v1 → v5 via Sherpa adversarial review.** 12 critique runs total. Each pass surfaced smaller, more empirical issues. v5 declared shippable when remaining concerns required live-hardware validation.
- **Hermes+NotebookLM recon completed.** Documented: `notebooklm-py` (Playwright-based unofficial API, ~5,600 stars) + Hermes skill installs that wire it into agent workflows. Park as future option; current "Victor as API" works.

---

## What this list does NOT include

State changes go in 02-state, not here. Decisions go in 04-decisions, not here. Things already shipped go in 05-dont-rebuild, not here. **03-active is forward-looking only.**
