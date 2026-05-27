# CPK STATE — What's True Right Now

> 02-state wins on **"what is true now."**
> If 02-state disagrees with anything else, 02-state is correct.
> If 02-state's timestamp is stale (>7 days old), distrust it and verify.

---

**Last updated:** 2026-05-27 (Day 9 session)
**Updated by:** Victor + Claude Desktop
**Confidence:** HIGH — values verified during this session

---

## Repository state

- **Default branch on GitHub:** `main` at commit `ed6f743` (no commits this session — spec work only)
- **Active experiment branch:** none — `experiment/day4-storage-fix-and-mission-helper` merged earlier, safe to delete eventually
- **Stargazers:** 2
- **Working tree (Day 9 close):** uncommitted: `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` (v5, 29.6 KB), `docs/_abandoned/` (Abacus's Day 9 drafts moved here), `notebooklm/cfc/_upload/` (NotebookLM bundles uploaded successfully), updated `.dolphintank/02-state.md` and `03-active.md`

---

## Hardware state

- **Primary device:** AmorPoee — Kiisu V4B clone, serial `5A3DEA0027E18000`
- **Firmware:** Momentum `mntm-dev`
- **Transport:** USB on COM9
- **Auto-lock:** 30 minutes (manually configured)
- **Connection health:** not exercised this session (pure spec work, no hardware ops)

---

## Tooling state

- **MCP server:** `flipper-mcp` v0.4.0 — unchanged this session
- **Editable install:** `D:\Dev\Projects\Kiisu\.venv\Lib\site-packages\__editable__.flipper_mcp-0.1.0.pth` points to `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\` (Day 4 band-aid; works)
- **flipper-mcp version:** v0.4.0 (8 tools in `app_lifecycle` module)
- **Sherpa adversarial review pipeline:** validated working — 4 passes against Phase 1 spec, ~$0 cost per pass (registry quirk), ~5-8 min per pass, 3 reviewers (Grok 4.3, DeepSeek V4 Pro, MiMo V2.5 Pro)

---

## Mission framework state

**Unchanged from Day 8** — no missions executed this session.

Validated working end-to-end on real hardware (Day 7 live-fire):
- ping, radio_handshake (v2), subghz_quick_scan, flipper_info, device_inventory

Built but not validated end-to-end: gpio_full_read (F1), ble_passive_scan (no-op), storage_health_check (unit tests only)

Not yet built: NFC capture, red-team missions, all CFC-dependent missions

---

## Known firmware/MCP bugs (open, prioritized)

Unchanged from Day 8:

- **F1:** `require("gpio")` fails on mntm-dev (Medium severity)
- **F2:** `storage_info` MCP tool returns SD card stats for `/int` requests
- **F3:** `storage_list` returns empty for `/ext/apps_data` even when files exist
- **F4:** `require("nfc")` fails on mntm-dev — motivated CFC project

---

## CFC (CPK Companion FAP) project state — NEW Day 9

**Phase 1: COMPLETE.** Architecture spec shippable.

- **Spec location:** `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\docs\decisions\DAY8_FAP_PHASE1_SPEC.md` (v5, 29.6 KB)
- **Architecture decision:** Path A (single .fap with AppDataExchange). Path B (.fal modules) ruled out — symbol resolution can't reach `furi_hal_*`.
- **NotebookLM corpus uploaded:** 3 notebooks (firmware-side, host-side, design-context) totaling 70 sources at `notebooklm/cfc/_upload/`. Successfully ingested by Victor as the human-API.
- **Research questions answered (Q1-Q7):** all 9 hard facts in §3 of spec are empirically anchored to firmware source or NotebookLM Q&A
- **Adversarial review:** 4 passes × 3 reviewers = 12 critique runs. Convergence reached at v5 — remaining items require live-device empirical validation, which is Phase 2's job.
- **Abacus's Day 9 implementation drafts:** abandoned (moved to `docs/_abandoned/`) — they invented a non-functional `cpk.cfc.v1.CfcService` standalone RPC service that the firmware can't route. Path A (AppDataExchange) is the correct architecture, captured in spec v5.

**Phase 2: NOT STARTED.** Ready to cook.

- **Phase 2 scope:** skeleton FAP boots + responds to PING/META/RESET/ERROR. 15 acceptance tests defined in §12.1 of spec.
- **Phase 2 preconditions (§13.1 of spec):** ufbt installed, Pillow/msgpack/flipperzero-protobuf importable, AmorPoee reachable, repo clean, cmp library vendored, icon generated, reference FAP inspected.
- **Phase 2 stop conditions (§13.2):** 8 explicit halts including 2-hour cap, 10-rebuild cap, transport disconnect, callback safety failure.
- **Phase 2 rollback (§13.3):** 5-step recovery via `storage_delete` + git checkout. FAP on SD card, no firmware damage.

---

## Open R-series findings (from cc Phase 1 capability survey, Day 5)

- **R5 (storage_write false-failure):** ✅ FIXED Day 4, re-validated Day 7
- **R6 (large script crash):** ✅ SUBSUMED by R5
- **R7 (orphan flipper-mcp processes):** Last observed Day 4; watch

---

## Tool ecosystem this Claude session has access to

- `flipper-mcp` (live RPC to AmorPoee) — not exercised this session
- `claude-memory` (hybrid search over Victor's pgvector_load memory store) — not exercised
- `anythingllm` 15-specialist fleet — not exercised
- Desktop Commander / Windows-MCP (Windows filesystem + shell) — extensively used
- Sherpa tooling at `E:\Sherpa\tools\` — heavy use for adversarial review pipeline
- Standard web tools (web_search, web_fetch) — used for Hermes+NotebookLM recon

---

## Current AI session context

- **Plan:** Pro plan
- **Last session goal achieved:** Phase 1 spec shipped at v5 after 4 adversarial review iterations
- **Next session goal:** Phase 2 cook — build the CFC FAP skeleton, validate PING + META + ERROR over real hardware
