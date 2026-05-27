# Day 8 Decision Document — The CPK Companion FAP

**Date:** 2026-05-27
**Status:** VISION / NOT YET BUILT
**Builds on:** All Day 1-7 work; specifically the empirical finding that mission code is bottlenecked by stock-app button-press automation and the missing JS bindings (`require("gpio")` fails; `require("nfc")` fails)

---

## TL;DR

We're going to build **one Flipper Application Package (FAP)** that lives on the Kiisu's SD card alongside Momentum's stock apps. This FAP exposes a clean RPC vocabulary that CPK's missions speak natively — no button-press automation, no save-dialog scraping, no UI navigation.

It is **a thin shim**, not a feature replacement. It wraps Momentum's existing C APIs (which are stable) and exposes them through a vocabulary CPK's mission framework can consume directly. Missions become *first-class*: one call in, structured result out.

Working name: **CPK Companion** (CFC for short — "CPK FAP Companion").

---

## Why this exists

The Day 1-7 work proved CPK can drive a Flipper via RPC + JS missions + synthetic button input. It also proved the cost of that architecture: every mission that needs the stock NFC/Sub-GHz/IR app pays the "navigate the UI by pressing buttons" tax. Today's NFC reconnaissance (Day 8 morning) showed `require("nfc")` doesn't exist on `mntm-dev`; cc Day 6 showed `require("gpio")` doesn't either. We were about to spend the rest of today building button-press automation of Momentum's NFC app — fragile, brittle to firmware updates, and limited to whatever the app already offers.

The Companion FAP solves all three:
- **No more button presses.** The FAP exposes RPC primitives. CPK calls them. Done.
- **Stable across Momentum updates.** Momentum's *internal app UIs* change between releases. Momentum's *firmware C APIs* are far more stable. The FAP depends on the latter.
- **Capability extension.** We can expose primitives Momentum's stock apps don't (e.g. "read NFC card and return UID without saving" — currently impossible via the NFC app's UI).

This is also where CPK's red-team mission category genuinely becomes clean. `nfc_clone_owned` becomes a single `cfc.nfc.write(uid_data)` call instead of a multi-step UI-driving choreography.

---

## What it does (the public surface)

A small set of noun-and-verb RPC pairs, namespaced by the FAP. Initial proposal:

### nfc
- `nfc.capture(target_class)` → reads whatever card is presented, returns `{uid, type, ndef_blocks, dump_path}`. `target_class` ∈ `{owned, ctf, authorized, observe}`; logged for audit.
- `nfc.list_saved()` → enumerate `.nfc` files in `/ext/nfc/`
- `nfc.read_saved(path)` → load a saved card's structured data
- `nfc.write(target_class, data)` *(red-team gated)* → write data to a writable card. Requires explicit `target_class != observe` and `dual_confirm`.

### subghz
- `subghz.capture(freq, duration_ms, target_class)` → RX a frequency for a window, save the capture, return `{file_path, sample_count, peak_rssi}`
- `subghz.scan(freq_list, samples_per)` → already-validated pattern from Day 7; returns `{freq: {min, max, mean, samples}}` per band
- `subghz.replay(target_class, file_path)` *(red-team gated)* → transmit a saved capture. Hard guarded.

### ir
- `ir.capture(timeout_ms)` → wait for an IR burst, decode protocol, return `{protocol, address, command, raw}`
- `ir.list_saved()` → enumerate `.ir` files
- `ir.replay(target_class, file_path)` *(red-team gated)* → TX a saved IR signal. Hard guarded.

### gpio
- `gpio.read_all()` → snapshot of every user pin's mode + state. Replaces the failing `require("gpio")` JS path.
- `gpio.read(pins)` → multi-pin read with explicit pin list.

### system
- `system.info()` → superset of Momentum's `systeminfo_get`: firmware version, vendor, battery, JS SDK version, free heap, uptime, lock state, CPK Companion version
- `system.audit_log_tail(n)` → return last N entries of the FAP's audit log (the FAP keeps its own structured operations log, separate from Momentum's logs)

### meta
- `meta.capabilities()` → returns the list of namespaces and verbs the current FAP build supports. So CPK missions can feature-detect before calling.

---

## What it explicitly is NOT

- **NOT a UI.** No menus, no screens. The only screen the FAP ever shows is a status line saying "CFC operating" and a struct dump on operations. If the user wants a UI, they use Momentum's apps.
- **NOT a feature replacement.** We don't reimplement NFC card emulation, Sub-GHz analyzer, IR remote learning. The FAP wraps these where they exist; missions still launch the stock app via `flipper_app_start` for UI-required tasks.
- **NOT a runtime competitor to Momentum.** The FAP runs as one app among many; the user can exit it like any other app.
- **NOT a place to put red-team-specific logic.** Red-team gating (target_class, dual_confirm, audit logging) lives in the *missions* that call the FAP, not in the FAP itself. The FAP just exposes capabilities; the *mission* enforces the rules around their use.
- **NOT something we ship to npm/PyPI/anywhere.** It lives in `cfc/` inside the CPK repo, builds with `ufbt`, ships as a `.fap` file in releases.

---

## Architecture in one paragraph

The FAP is a Momentum-compatible `.fap` written in C using the standard `ufbt` toolchain. It registers itself with the firmware's RPC subsystem as a callback-receiving app (which JS Runner doesn't — that's *why* JS Runner needed `gui_send_input` for cleanup). The FAP exposes a single protobuf service: `CpkCompanion` with one RPC per verb in the public surface above. CPK's MCP server gets a new module `flipper_mcp/modules/cfc/module.py` that translates MCP tool calls into `CpkCompanion` RPCs. Missions that need first-class behavior import that module's tools directly; missions that need stock-app behavior continue to use the existing recipe.

---

## How it will be built

Four phases, each ending in a working deliverable:

1. **Research phase (next session).** Load Flipper SDK docs, Momentum source, ufbt examples into a fresh NotebookLM notebook. Query specialists (`hermes-plugin-specialist`, `pgvector-schema-specialist` may have relevant patterns from MemoryCore plugin work). Output: `notebooklm/cfc/00_PROJECT_CONTEXT.md` with cited answers to the load-bearing questions.
2. **Skeleton phase.** A FAP that boots, registers its RPC service, responds to a single `meta.capabilities()` call with an empty list. ~one cc cook + a live-fire. Output: a `.fap` file that runs on the Kiisu and a CPK MCP tool that can call it.
3. **NFC vertical phase.** Add `nfc.capture` and `nfc.list_saved`. End-to-end live-fire: ask Claude to capture a card, get UID back in chat. Output: the original Day 2 NFC capture demo, now without button presses.
4. **Capability expansion phase.** Add Sub-GHz, IR, GPIO, system info, meta. Each is its own short cook informed by the NotebookLM corpus. Output: complete v1.0 FAP.

Each phase produces a decision doc capturing what was learned (especially in phase 1 where the firmware surface will probably surprise us).

---

## Estimated cost

With cooks running at the velocity we've established and NotebookLM doing the research lift, this is **a small handful of sessions**, not a months-long project. Concretely:

- Phase 1: ~2-3 hours wall clock (Notebook prep + specialist queries + writeup)
- Phase 2: ~3-4 hours (one cc cook + a live-fire session)
- Phase 3: ~2-3 hours
- Phase 4: ~4-6 hours spread over multiple sessions

If the Companion FAP is shipped within 2 weeks of starting Phase 1, that's slow. Within 1 week is realistic.

---

## Risks

Real risks, not theatrical ones:

1. **Kiisu V4B vs official Flipper Zero firmware differences.** KIISU_DEEP_KNOWLEDGE §10 line 643 warns "NFC API may differ in subtle ways" on Kiisu clones. The FAP's NFC C calls may hit clone-specific edge cases. Mitigation: test on AmorPoee early and often.

2. **ufbt toolchain learning curve.** Neither Victor nor any current Claude has built a FAP from scratch on this stack. Phase 1's research is specifically meant to absorb this risk. If Phase 1 surfaces something genuinely intractable, the FAP becomes a longer project — but we'd know that before Phase 2 burns budget.

3. **Momentum's RPC extension surface.** The FAP needs to register *its own* protobuf service with the firmware's RPC subsystem. This is a known pattern (stock NFC/Sub-GHz/IR apps all do it) but the "make your own RPC service" path may have less documentation than the "register UI scenes" path. Phase 1 must verify this is feasible before Phase 2.

4. **The audit-logging path.** Red-team missions want device-side audit trails ("CFC will refuse to write to this card without a logged target_class declaration"). Storing those logs in a tamper-evident way on the SD card is a real design decision. Initial version: append-only JSONL with line-level checksums. Can harden later.

---

## What this isn't deciding (yet)

- **Specific API signatures.** Phase 1 will refine these once we know what Momentum's NFC/Sub-GHz/IR APIs actually expose.
- **Whether to also support FlipperZero-official firmware.** Default: Momentum-only initially, port if there's contributor demand.
- **Audit log format details.** Decided in Phase 4 when we have real usage data.
- **Whether to expose CLI alongside RPC.** Probably not — CLI is sealed off over BLE per Day 1, and BLE is a real future. RPC-only.

---

## Why this is the right next move for CPK

CPK's first 7 days proved the orchestration layer works. Day 8 (today) is about proving the orchestration can extend the *device itself*. If we ship CFC, CPK stops being "Claude operates a Flipper" and becomes "Claude has a hardware companion it built itself." That's a meaningfully different (and stronger) story for the next stargazer.

It also positions CPK to do things genuinely impossible without it. NFC capture without UI choreography is one thing. *Composite missions* — "scan all RF bands, then for the loudest one capture a sample, then notify me" — become trivial. Today they require ~25 tool calls each.

---

## Cross-project hygiene note

This doc explicitly does NOT adopt the Atlas/`.atlas/`/save_state pattern from `pgvector_load`. CPK's existing `docs/decisions/DAY*_*.md` pattern is sufficient for project state, and adopting Atlas in CPK would create namespace collision risk with MemoryCore's authoritative Atlas. If CPK ever needs structured-state-management heavier than decision docs, it'll get its own pattern under a non-overlapping name.

---

## Next concrete action

Pre-research planning. Specifically: which questions to ask which specialists, and what files to load into which NotebookLM notebook. That's the Phase 1 spec document, to be written in the next session.
