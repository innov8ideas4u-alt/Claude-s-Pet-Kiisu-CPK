# CPK STATE — What's True Right Now

> 02-state wins on **"what is true now."**
> If 02-state disagrees with anything else, 02-state is correct.
> If 02-state's timestamp is stale (>7 days old), distrust it and verify.

---

**Last updated:** 2026-05-27 (Day 8 session)
**Updated by:** Victor + Claude Desktop
**Confidence:** HIGH — values verified during this session

---

## Repository state

- **Default branch on GitHub:** `main` at commit `ed6f743` (8 commits deep, last commit "docs: signal upcoming red-team mission category")
- **Active experiment branch:** `experiment/day4-storage-fix-and-mission-helper` — fully merged to main as of this session; safe to delete eventually
- **Stargazers:** 2 (Victor's most-starred public repo)
- **Working tree:** Clean as of this snapshot; the Day 8 vision doc + DolphinTank files are uncommitted while writing

---

## Hardware state

- **Primary device:** AmorPoee — Kiisu V4B clone, serial `5A3DEA0027E18000`
- **Firmware:** Momentum `mntm-dev`
- **Transport:** USB on COM9
- **Auto-lock:** 30 minutes (manually configured to avoid fighting lockscreen during dev)
- **Connection health:** verified responsive at session start

---

## Tooling state

- **MCP server:** `flipper-mcp` runs in Claude Desktop's MCP config; holds COM9 while connected
- **Editable install:** `D:\Dev\Projects\Kiisu\.venv\Lib\site-packages\__editable__.flipper_mcp-0.1.0.pth` points to `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\` (Day 4 band-aid; works; clean fix is a dedicated CPK venv)
- **flipper-mcp version:** v0.4.0 (8 tools in `app_lifecycle` module)
- **Validated MCP tools fired this session:** `flipper_connection_health`, `flipper_desktop_is_locked`, `flipper_app_lock_status`, `flipper_app_start`, `storage_write`, `storage_read`, `storage_list`, `flipper_gui_send_input`, `storage_info`

---

## Mission framework state

**Validated working end-to-end on real hardware (Day 7 live-fire):**
- ping (warmup)
- radio_handshake (v2, gpio section removed)
- subghz_quick_scan (real RF data captured, ambient signal at 315 MHz at -97 dBm)
- flipper_info (JS-side `flipper` global)
- device_inventory (host-side composition, primitives validated individually)

**Built but not validated end-to-end:**
- gpio_full_read (blocked by F1 — `require("gpio")` fails)
- ble_passive_scan (documented as no-op; module doesn't exist)
- storage_health_check (has unit tests; live composition validated via device_inventory)

**Not yet built:**
- NFC capture mission (Day 2 idea, deferred today in favor of FAP planning)
- All red-team missions
- All Companion FAP-dependent missions

---

## Known firmware/MCP bugs (open, prioritized)

- **F1:** `require("gpio")` fails on mntm-dev (Medium severity, blocks all gpio JS missions). Cause unknown; module may be conditionally compiled out or named differently.
- **F2:** `storage_info` MCP tool returns SD card stats for `/int` requests (Medium severity). Bug in `flipper_mcp/modules/storage/module.py` — path arg not passed through to protobuf `StorageInfoRequest`.
- **F3:** `storage_list` returns empty for `/ext/apps_data` even when files exist (Low severity, files still readable by full path).
- **F4 (Day 8 finding):** `require("nfc")` fails on mntm-dev (Medium severity, motivated the FAP project). Same shape as F1.

---

## Open R-series findings (from cc Phase 1 capability survey, Day 5)

- **R5 (storage_write false-failure):** ✅ FIXED Day 4, re-validated Day 7
- **R6 (large script crash):** ✅ SUBSUMED by R5, re-validated Day 4 + Day 7
- **R7 (orphan flipper-mcp processes):** Last observed Day 4; not recurring. Watch.

---

## Tool ecosystem this Claude session has access to

- `flipper-mcp` (live RPC to AmorPoee)
- `claude-memory` (hybrid search over Victor's pgvector_load memory store)
- `anythingllm` 15-specialist fleet (each specialist deep on a pgvector_load subsystem; **hermes-plugin-specialist** and **pg-rdfstar-specialist** likely useful for FAP plugin/RPC patterns)
- Desktop Commander (Windows filesystem + shell)
- Windows-MCP (Windows automation)
- Standard web tools (web_search, web_fetch)

NOT in this session: NotebookLM access (browser-only; Victor uses it manually).

---

## Current AI session context

- **Plan:** Pro plan (Max20x days ended around Day 7)
- **Last session goal achieved:** Day 7 live-fire + merge to main (today)
- **This session goal:** FAP vision lock-in + DolphinTank initialization
