# CPK ACTIVE — What's In Flight Right Now

> 03-active wins on **"what should we work on."**
> If 03-active disagrees with anything else about priority, 03-active is correct.
> If you're a future Claude reading this, **the first item is what to start with.**

---

**Last updated:** 2026-05-27 (Day 8 session)

---

## 🎯 Currently in flight (active work)

### 1. CPK Companion FAP — Phase 1 research planning

**Status:** Vision locked (`docs/decisions/DAY8_FAP_VISION.md`). Phase 1 spec not yet written.

**What Phase 1 produces:**
- A NotebookLM corpus plan (which files go into which notebook, with concrete file URLs)
- A specialist query batch — questions to broadcast to `hermes-plugin-specialist`, `pg-rdfstar-specialist`, and any other anythingllm specialists with relevant patterns
- A list of 8-12 load-bearing questions to fire at the NotebookLM corpus once loaded
- Saved as `docs/decisions/DAY8_FAP_PHASE1_SPEC.md`

**Why it matters:** the most expensive mistake we could make is locking the FAP's design before research tells us what Momentum/Flipper firmware already exposes. NotebookLM + specialists answer those questions in ~30 minutes; cc trying to figure it out from source takes ~4 hours.

**Next concrete action:** Write `DAY8_FAP_PHASE1_SPEC.md` collaboratively with Victor.

---

## 🟡 Queued (next, after Phase 1 spec ships)

### 2. FAP Phase 1 — execute the research

Load the NotebookLM corpus. Run the specialist broadcast. Synthesize findings into `notebooklm/cfc/00_PROJECT_CONTEXT.md`. Output: a clear picture of what the FAP can/can't do given Momentum's firmware ABI.

**Estimated wall clock:** ~2-3 hours, mostly waiting on NotebookLM and specialist responses.

### 3. FAP Phase 2 — skeleton FAP boots + responds to one RPC

A `.fap` that registers its RPC service, responds to `meta.capabilities()` with an empty list, exits cleanly. One cc cook + one live-fire session.

**Estimated wall clock:** ~3-4 hours.

### 4. FAP Phase 3 — NFC vertical slice

Add `nfc.capture` and `nfc.list_saved`. End-to-end: ask Claude in chat to capture a card, get UID back. Resolves the original Day 2 "auto-save card scan" idea without button presses.

**Estimated wall clock:** ~2-3 hours.

### 5. FAP Phase 4 — capability expansion

Sub-GHz, IR, GPIO, system info, meta. Each is a short cook informed by the NotebookLM corpus.

**Estimated wall clock:** ~4-6 hours across multiple sessions.

---

## 🟢 Side-tasks ready to grab (lower priority, independent)

### Fix F2: `storage_info` returns SD card stats for `/int`

Quick win, ~30 min. Bug in `flipper_mcp/modules/storage/module.py` — `path` arg not passed through to protobuf `StorageInfoRequest`. Read the module, find the omission, fix it, add a test.

### Investigate F1 + F4: `require("gpio")` and `require("nfc")` both fail on mntm-dev

Short cc cook with isolated module probes. ~90 min. Result: either we find the right gpio/nfc API or we definitively document them as unavailable on mntm-dev. **The FAP project subsumes part of this** — if `gpio.read_all` and `nfc.capture` land in the FAP, we don't need the JS bindings to work — but it's still worth knowing.

### NFC button-press capture mission (the deferred Day 8 work)

If the FAP project hits a major delay, this is the fallback. Builds the original Day 2 idea with button-press automation. Documented as fallback in `MISSIONS_COOKBOOK.md`. **DO NOT START** unless explicitly de-prioritizing the FAP.

### First red-team mission: `nfc_clone_owned`

Was prepped but never built. Depends on either the NFC button-press mission OR the FAP's `nfc.write`. Defer until one of them is live.

---

## ❄️ Frozen (won't pick up unless something changes)

### Android-as-BLE-bridge architecture

Deep recon dossier at `D:\Dev\scratch\llmdr_android_recon\`. Real option but multi-month project. Parked by Victor's explicit call: "rabbit hole too deep for me right now."

### CPK venv migration (cleanup the .pth band-aid)

The editable install at `D:\Dev\Projects\Kiisu\.venv\...` works; fresh CPK venv is a hygiene-only fix. Pick up when something actually breaks because of the band-aid.

---

## Working principles for items in flight

- **Vision before research, research before design, design before build.** Phase ordering matters.
- **Each phase produces a decision doc.** Vision → research → skeleton → vertical → expansion. Five docs by the time the FAP ships.
- **Live-fire validation is mandatory.** No "smoke tests are enough" hand-waving. Real device, real card/signal, real log lines.
- **Commit per phase, not per feature.** Each phase commit captures one coherent unit of work, with the decision doc as anchor.

---

## What this list does NOT include

State changes go in 02-state, not here. Decisions go in 04-decisions, not here. Things already shipped go in 05-dont-rebuild, not here. **03-active is forward-looking only.**
