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


### 013 — CFC architecture: Path A (FAP + AppDataExchange), Path B (.fal) ruled out
**Date:** 2026-05-27 (Day 9)
**Status:** ACTIVE — Phase 1 spec v5 SHIPPABLE
**Pick:** Single `.fap` (FlipperAppType.EXTERNAL) using `RpcAppEventTypeDataExchange` for all host↔device communication. CFC-layer 16-byte frame header carrying msgpack-encoded payloads. Max 884 bytes usable payload per RPC envelope.
**Alternative considered:** Path B — out-of-tree `.fal` JS modules. Definitively ruled out by NotebookLM Q4: the CompositeApiResolver only exposes mJS-engine helpers from `app_api_table_i.h`. Hardware functions are absent from both the JS app's private table and the global firmware API table. Zero out-of-tree `.fal` modules exist in 800MB of community FAPs (recon Finding G).
**Reasoning:** Path A is the documented intended pattern in Momentum/OFW/Unleashed firmware. `rpc_app.h` is identical across all three firmwares (recon Finding D). Official Python bindings already expose `rpc_app_data_exchange_send/recv` (recon Finding E). qFlipper documents the host-side FIFO queue + complete-response timeout pattern (NotebookLM Q6). Spec went through 4 adversarial review passes via Sherpa.
**Captured in:** `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` (v5)

### 014 — Wire protocol: 16-byte CFC frame header, msgpack payload, 8KB transaction cap
**Date:** 2026-05-27 (Day 9)
**Status:** ACTIVE — Phase 1 spec v5
**Pick:** Fixed 16-byte header per frame (magic + version + op_code + transaction_id + fragment_index + fragment_total + payload_length). Payload after header is msgpack-encoded. Max payload_length per transaction: 8192 bytes (8KB). Single-fragment outbound in Phase 2; multi-fragment inbound assembling required for §12.1 stress tests.
**Alternative considered:** (a) Protobuf payloads — rejected for high schema-evolution friction; (b) JSON — rejected for ~30% encoding overhead; (c) 64KB transaction cap — rejected after adversarial review found it would OOM Flipper's ~128KB heap.
**Reasoning:** msgpack is binary, schemaless, has small C and Python libraries. The 8KB cap leaves heap headroom. Per-frame data limits (884 bytes) prevent buffer overflows. ASSEMBLING-state 5-second timer prevents dropped-cable scenarios from bricking the FAP.
**Captured in:** `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` §4 (v5)

### 015 — Sherpa adversarial review made part of pre-cook hygiene
**Date:** 2026-05-27 (Day 9)
**Status:** ACTIVE
**Pick:** Any multi-session implementation spec runs through Sherpa's `adversarial_review.ps1` (Grok 4.3 + DeepSeek V4 Pro + MiMo V2.5 Pro) before cook starts. Iterate spec until convergence (verdicts shift from "structural issues" to "empirically-dependent details").
**Alternative considered:** (a) Single-pass review with one model — rejected, misses domain blind spots; (b) Skip review entirely — rejected, costs much more in failed cook time than $0.04 review.
**Reasoning:** Phase 1 spec went through 4 iterations × 3 reviewers = 12 critique runs. v1 had a serious async/sync architectural mismatch that would have wasted a full Phase 2 session if missed. v2 had an ASSEMBLING-state timeout gap that would have bricked the device on first dropped cable. v3 had ambiguous error-code definitions. Each pass caught real issues that survived multiple human reviews. The pattern is: spec drafts CONVERGE rather than oscillate — after 4 passes, reviewers run out of structural issues and start hitting empirical questions that only live testing can answer.
**Captured in:** This decision, plus the 4 review runs at `E:\Sherpa\working\reviews\DAY8_FAP_PHASE1_SPEC\`

### 016 — Path B (.fal modules) abandoned for hardware-touching code
**Date:** 2026-05-27 (Day 9)
**Status:** ACTIVE
**Pick:** No `.fal` modules in CFC v1+. If a future feature ever needs a JS-engine-only helper (e.g., pure-math utility), `.fal` remains viable for that narrow use case — but not for any code that touches RF, NFC, IR, GPIO, or storage.
**Alternative considered:** Mixed-architecture (Path A for hardware, Path B for utility helpers). Rejected to keep CFC as a single deployable artifact.
**Reasoning:** NotebookLM Q4 closed the door on hardware-touching `.fal`. The community's zero-in-the-wild `.fal` pattern confirms the architecture deliberately blocks this. Keeping the project Path-A-only simplifies build, deploy, debugging, and documentation.
**Captured in:** `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` §2.1 (v5)


### 017 — CFC Phase 2 ships at 17/18; architecture EMPIRICALLY VALIDATED
**Date:** 2026-05-27 (Day 9, late evening)
**Status:** ACTIVE — Phase 2 deployed at `/ext/apps/Tools/cfc.fap` on AmorPoee
**Pick:** Ship Phase 2 with 17/18 tests passing. The one failing test (`test_stale_transaction`) is documented in cook log as a known protocol-interaction edge case requiring Phase 2.5 investigation, NOT a structural architecture failure.
**Alternative considered:** (a) Continue iterating Phase 2 cook until 18/18. Rejected because the failure is on the host-side stale-frame matching, not the FAP-side state machine, and per spec §13.2 the 1-fix-per-test budget was exhausted. Halting cleanly is the right behavior. (b) Mark Phase 2 as incomplete and defer ship. Rejected because 17/18 represents a fully working architecture — PING, all META opcodes, RESET (both flavors), all 9 negative paths, and 1 of 2 stress tests prove the design end-to-end.
**Reasoning:** The single failing test exercises a complex multi-transaction interleaving that exposes an apparent uninitialized-memory bug in firmware-side `rpc_system_app_exchange_data()`. Critically: Q-IMPL-5 (the biggest unknown going into Phase 2) was EMPIRICALLY VALIDATED — `rpc_system_app_exchange_data()` IS safe to call from within the RPC callback context. All other architectural claims in the spec hold up under real hardware testing. Phase 2.5 will close the stale-transaction gap as a focused investigation rather than blocking Phase 2 shipping.
**Captured in:** `docs/decisions/DAY9_PHASE2_COOK_LOG.md` (full cook record), commit `35a9332`

### 018 — Use CPK's internal protobuf_gen for CFC host module (NOT external flipperzero-protobuf)
**Date:** 2026-05-27 (Day 9, late afternoon)
**Status:** ACTIVE
**Pick:** CFC's host module (`flipper_mcp/modules/cfc/module.py`) uses `flipper_mcp.core.protobuf_gen.flipper_pb2` and `application_pb2` directly. Wire calls go through `flipper_mcp.core.protobuf_rpc.FlipperRPC._send_rpc_message()`, protected by the existing `@_with_wire_lock` decorator pattern.
**Alternative considered:** External `flipperzero-protobuf` PyPI package. Rejected at Phase 2 precondition stage when discovered the PyPI version (0.1.20221108) hard-pins `numpy==1.22.3` which doesn't build on modern Python. The PyPI package is stale from November 2022.
**Reasoning:** CPK already has its own generated protobuf classes from `.proto` files at `flipper_mcp/core/protobuf_gen/`. The `Main.app_data_exchange_request` field is already exposed and used in BOTH directions (host→FAP and FAP→host — the field name is historical/misleading). The existing transport layer at `flipper_mcp.core.protobuf_rpc` already handles command_id matching, stale-frame discarding, varint framing, and wire-mutex locking. Adding an external library would have introduced a fragile pinned dependency for capabilities CPK already has internally. This is the cleaner architecture.
**Captured in:** Spec v5.1 §7.1 (commit `c1f74a8`), Phase 2 cook log preamble

### 019 — Firmware rewrites app_start args to "RPC %08lX" — CRITICAL undocumented detail
**Date:** 2026-05-27 (Day 9, Phase 2 cook)
**Status:** ACTIVE — must be remembered for any future FAP that uses RPC
**Pick:** When the host calls `flipper_app_start("cfc", "RPC")` against an RPC-aware FAP, the firmware INTERNALLY rewrites the args string from `"RPC"` to `"RPC %08lX"` where the hex value is the pointer to the `RpcAppSystem` instance the firmware allocated for this FAP. The FAP's entry point (`int32_t cfc_app_main(void* p)`) receives `p` as a `const char*` pointing to this rewritten string. The FAP MUST parse the hex value to obtain its `RpcAppSystem*` handle.
**Alternative considered:** None — this is a firmware behavior, not a design choice. We discovered it by inspecting `notebooklm/cfc/_upload/notebook1_firmware_side/01_rpc_service_all.txt:783-787` during Phase 2 cook's reference-FAP inspection step (Q-IMPL-7).
**Reasoning:** This is the *only* way an RPC FAP can obtain its `RpcAppSystem*` handle. The handle is required to call `rpc_system_app_set_callback()`, `rpc_system_app_confirm()`, and `rpc_system_app_exchange_data()`. Without this rewrite, the FAP has no way to know its own RPC session. This detail is invisible from the public docs and lives only in the firmware source — but it IS in the NotebookLM corpus we built, so future Claudes can find it. The pattern of "host launches FAP with simple args → firmware mutates args → FAP parses mutated args" is non-obvious and worth elevating to a decision.
**Captured in:** `docs/decisions/DAY9_PHASE2_COOK_LOG.md` §4, `cfc/cfc.c` parsing code (lines TBD — see commit `35a9332`)

### 020 — Phase 2 spec discrepancy: rpc_system_app_exchange_data() returns void, not bool
**Date:** 2026-05-27 (Day 9, Phase 2 cook)
**Status:** ACTIVE — spec patch deferred to Phase 2.5
**Pick:** Spec v5.1 §6.4 sample code implies `rpc_system_app_exchange_data()` returns `bool` (with an `if (!sent)` error path). The actual header at `rpc_app.h:220` declares it `void`. Phase 2 implementation correctly uses `void`; the spec has a minor inaccuracy.
**Alternative considered:** Hot-patch the spec immediately. Rejected because Phase 2 single-fragment outbound paths don't exercise the would-be error path; no functional impact. Cleaner to bundle this fix into Phase 2.5 along with the §7.1 §6.4 chunking work.
**Reasoning:** The error-handling story for fragmented outbound sends in Phase 2.5 needs to account for the fact that `rpc_system_app_exchange_data()` provides NO success/failure signal to the caller. Backpressure and transport-failure detection happen at a different layer (e.g., the next host-side request timing out). Phase 2.5 should redesign §6.4's pseudocode to be realistic.
**Captured in:** `docs/decisions/DAY9_PHASE2_COOK_LOG.md` §4 (last paragraph), Phase 2.5 carry-forward in 03-active item 1.C


### 021 — Phase 3 Cook 1 scope split: infrastructure-only first, migration in Cook 1.5
**Date:** 2026-05-27 (Day 11)
**Status:** ACTIVE — Cook 1 in flight per this decision
**Pick:** Cook 1 adds reader-task scaffolding + new MCP tools (`flipper_cfc_subscribe`, `_listen`, `_unsubscribe`) that USE the reader, but leaves all existing tools on their current `_receive_main_message` path. Migration of existing tools + update of 4 mock tests in `tests/cfc_phase2/` deferred to Cook 1.5.
**Alternative considered:** (a) Full migration in Cook 1 as originally specced — rejected because cc halt surfaced that 4 mock tests in `tests/cfc_phase2/` hardcode internal call shape; combining wire-model refactor + mock-test migration + CFC routing changes in one cook would force debugging two unfamiliar things at once if anything failed. (b) Hybrid (migrate non-CFC, leave CFC alone) — rejected as architectural debt; creates two parallel mental models for the wire layer.
**Reasoning:** Phase 2.5's discipline ("small validated step, then build on it") earned 27/27 in 4 cook attempts. Cook 1 as infrastructure-only proves the reader correct in isolation against synthesized frames before any production code depends on it. Cook 1.5 then does the migration with a proven reader, reducing the unknown count per cook. The cc halt is the system working correctly — pre-flight discipline caught a spec blind spot before any code was written.
**Captured in:** `docs/decisions/DAY11_PHASE3_SPEC.md` §15.2, `D:\Dev\scratch\day11_phase3_cook1_log.md` (cc-maintained)

### 022 — CFC frames routed by inner transaction_id, not outer command_id
**Date:** 2026-05-27 (Day 11)
**Status:** ACTIVE — encoded in Phase 3 reader task design
**Pick:** The host-side reader task maintains TWO parallel pending maps:
- `_pending: dict[int, Future]` keyed by outer `Main.command_id` for non-CFC tools
- `_cfc_pending: dict[int, Future]` keyed by inner `cfc_header.transaction_id` for CFC tools

For any incoming frame with `tag == 'app_data_exchange_request'`, the reader parses the 16-byte CFC header and routes by `transaction_id`. The outer `Main.command_id` field is IGNORED for CFC traffic.
**Alternative considered:** Single pending map keyed by outer command_id (the original §4.3 design). Rejected because Phase 2.5 already documented the Momentum uninit-malloc bug in `rpc_system_app_exchange_data`: the firmware mallocs the command_id field without zeroing, so inbound CFC frames carry garbage there. The `MOMENTUM_RPC_EXCHANGE_DATA_FIXED=False` constant gates this exact issue.
**Reasoning:** The CFC `transaction_id` is host-allocated and lives in the CFC header (a field WE wrote into the payload). The FAP correctly preserves it. The outer protobuf command_id is not under our control on the FAP side; it's clobbered by firmware mismanagement. Routing by transaction_id is both correct AND independent of the upstream Momentum fix. When the Momentum PR (D:\Dev\scratch\day10_momentum_pr_draft.md) lands, we can OPTIONALLY simplify back to a single pending map, but the dual-map design will keep working unchanged.
**Captured in:** `docs/decisions/DAY11_PHASE3_SPEC.md` §15.1, Phase 2.5 DAY10 design doc (uninit-malloc discovery)
