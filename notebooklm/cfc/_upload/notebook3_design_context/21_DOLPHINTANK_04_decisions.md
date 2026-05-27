# CPK DECISIONS — Append-Only Log of Why

> 04-decisions wins on **"why did we do X."**
> If 04-decisions disagrees with anything else about reasoning, 04-decisions is correct.
> APPEND ONLY. Don't revise old decisions; supersede them with a new entry and link the old one as superseded.

---

## Format

Each decision is numbered, dated, framed as "we picked A over B because..." and links to whatever decision doc or commit captures the full reasoning.

---

## Decisions

### 001 — Architecture: Claude drives Flipper via RPC, not CLI
**Date:** 2026-04-30 (Day 1)
**Status:** ACTIVE
**Pick:** Pure protobuf RPC + JS mission scripts. CLI text-shell deliberately not used.
**Alternative considered:** CLI text-shell via the firmware's interactive prompt.
**Reasoning:** Day 1 BLE probe proved CLI is sealed off over BLE. To preserve mobile-deployment optionality, RPC-only.
**Captured in:** `docs/decisions/DAY1_BLE_PROBE.md`

### 002 — App-launch uses full FAP path on mntm-dev
**Date:** 2026-05-13 (Day 2)
**Status:** ACTIVE
**Pick:** `app_start("/ext/apps/assets/js_app.fap", script_path)` for external FAPs; built-in apps accept short names like `"NFC"`.
**Alternative considered:** Short-name `"js_app"` or `"JS Runner"`.
**Reasoning:** Both short names return `ERROR_INVALID_PARAMETERS` on mntm-dev for external FAPs. KB §1.2 was wrong; reality wins.
**Captured in:** `docs/decisions/DAY2_APP_RPC_AND_INPUT.md`

### 003 — Synthetic button input requires full PRESS→SHORT→RELEASE triplet
**Date:** 2026-05-14 (Day 3)
**Status:** ACTIVE
**Pick:** `gui_send_input` default behavior emits the full triplet automatically. `single_event=True` flag for advanced cases (LONG holds, REPEAT events).
**Alternative considered:** Send only SHORT (which is what real-button-press apps listen for, per docs).
**Reasoning:** Empirically, a lone SHORT is silently absorbed by most app scenes. The full triplet is what firmware actually expects.
**Captured in:** `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md`

### 004 — Universal cleanup verb: BACK
**Date:** 2026-05-14 (Day 3)
**Status:** ACTIVE
**Pick:** A single BACK press dismisses success screens, error dialogs, AND exits JS Runner. Mission helpers don't need state-machine branching.
**Alternative considered:** Detect dialog type and choose key per state.
**Reasoning:** Live-validated that BACK works for all three end-states. Simpler is better.
**Captured in:** `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md`

### 005 — Storage chunked-write: send all chunks, read one ACK
**Date:** 2026-05-15 (Day 4)
**Status:** ACTIVE
**Pick:** Fire chunks back-to-back with `has_next=True`, read exactly one ACK at the end.
**Alternative considered:** Read an ACK after each chunk.
**Reasoning:** R5 root cause — firmware only ACKs the final chunk (per `rpc_storage.c send_response = !request->has_next`). Reading per-chunk caused timeouts and file truncation.
**Captured in:** Commit `34c0db7`, `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md`

### 006 — `flipper_js_run` wraps the validated recipe
**Date:** 2026-05-15 (Day 4)
**Status:** ACTIVE
**Pick:** One MCP tool collapses lock-check → unlock → app_start → wait → BACK → log-read into a single call.
**Alternative considered:** Keep the 5-step pattern as separate calls per mission.
**Reasoning:** Composability — every mission script repeats this pattern. One call cuts boilerplate everywhere.
**Captured in:** Commit `57fefff`

### 007 — License is MIT (not GPL-3.0)
**Date:** 2026-05-16
**Status:** ACTIVE
**Pick:** MIT.
**Alternative considered:** GPL-3.0 (for copyleft protection).
**Reasoning:** Upstream busse/flipperzero-mcp is MIT. Flipper ecosystem skews permissive. EDGE classroom benefits from MIT (students can fork freely). Project moat is documentation + community, not code.
**Captured in:** This chat history.

### 008 — Project umbrella shape: fresh copy + generous CREDITS (not subtree-merge or submodules)
**Date:** 2026-05-16
**Status:** ACTIVE
**Pick:** Copy files into fresh CPK repo; CREDITS.md attributes upstream explicitly.
**Alternative considered:** Subtree-merge to preserve git history; submodules.
**Reasoning:** Contributor onboarding wins over historical lineage; `CREDITS.md` is more discoverable than commit ancestry.
**Captured in:** Initial commit `2d2bc8d`

### 009 — Live-fire results published in commit history (Day 7)
**Date:** 2026-05-17 (Day 7)
**Status:** ACTIVE
**Pick:** Real RF-data capture (315 MHz ambient signal at -97 dBm) committed publicly.
**Alternative considered:** Sanitize specifics, leave only "the system works."
**Reasoning:** Empirical evidence is the moat. Burying it hides what makes CPK different.
**Captured in:** `docs/decisions/DAY7_LIVE_FIRE_MORNING_KIT.md`

### 010 — Active-protocol (red-team) framing: "authorized offensive testing" not "defense only"
**Date:** 2026-05-17
**Status:** ACTIVE
**Pick:** CPK supports active-protocol missions with explicit `target_class` and `dual_confirm` gating.
**Alternative considered:** "Defense only" stance forever.
**Reasoning:** CompTIA / pentest audience is real. "Defense only" was less honest than "authorized offensive testing only." ROADMAP updated to reflect.
**Captured in:** Commit `ed6f743`

### 011 — Build a CPK Companion FAP (CFC)
**Date:** 2026-05-27 (Day 8 — today)
**Status:** ACTIVE — vision locked, Phase 1 research pending
**Pick:** One custom Flipper Application Package exposing a clean RPC vocabulary that CPK missions speak natively. Thin shim layer wrapping Momentum C APIs.
**Alternative considered:** (a) Button-press automation of stock NFC/Sub-GHz/IR apps; (b) PR-ing JS module additions upstream to Momentum.
**Reasoning:** Button-press automation is brittle to Momentum UI changes and limited to existing app features. Upstream-PR path takes weeks and depends on Momentum maintainer attention. Custom FAP is tractable for Victor's velocity (~small-handful-of-sessions per the pgvector_load precedent) and produces a lasting moat.
**Captured in:** `docs/decisions/DAY8_FAP_VISION.md`

### 012 — Structured-state management: DolphinTank (not Atlas)
**Date:** 2026-05-27 (Day 8 — today)
**Status:** ACTIVE
**Pick:** CPK gets its own `.dolphintank/` directory with the same 5-file structure as MemoryCore's `.atlas/` but explicitly namespaced separately.
**Alternative considered:** (a) No structured state, decision docs only; (b) Extend Atlas to recognize CPK as a sub-namespace.
**Reasoning:** Victor explicitly chose to add this now rather than retrofit later ("I'll look back in a few weeks at 100 stars and say WTF was I thinking not using atlas from the start"). Namespace separation prevents cross-contamination with MemoryCore's authoritative Atlas. Cheap to add now, expensive to retrofit.
**Captured in:** This commit (the DolphinTank files themselves are the artifact).

---

## How to add a new decision

1. Append a new numbered entry at the bottom (don't insert in the middle)
2. If the new decision supersedes an old one, change the old entry's `Status:` from `ACTIVE` to `SUPERSEDED BY #NNN` and add a one-line note explaining what changed
3. Date format: YYYY-MM-DD
4. Always cite a captured-in source (decision doc or commit hash)
5. Never delete old decisions; they're history
