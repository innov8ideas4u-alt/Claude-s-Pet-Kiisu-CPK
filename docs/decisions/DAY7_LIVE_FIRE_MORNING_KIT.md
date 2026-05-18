# Day 7 Decision Document — Morning Kit Live-Fire Results

**Date:** 2026-05-17
**Hardware:** AmorPoee (Kiisu V4B + Momentum `mntm-dev`), serial `5A3DEA0027E18000`, COM9
**Builds on:** `docs/MORNING_KIT.md` (Day 6 cc-built missions), Day 4 `flipper_js_run` helper, Day 5.5 `storage_health_check`

---

## TL;DR

First live-fire session of cc's overnight morning kit. **4 of 6 missions validated end-to-end on real hardware.** Plus 3 new firmware/MCP-server findings worth tracking. Sub-GHz quick scan produced genuine RF data — including detection of ambient signal at 315 MHz (likely TPMS or car-key fob within range).

This session is the first time CPK has been used end-to-end the way *external contributors* would use it: ask Claude a thing, fire a mission, get real data back.

---

## Test results

| Mission | Status | Notes |
|---|---|---|
| Ping (warmup) | ✅ PASS | `flipper_js_run` + R5 storage_write fix survived overnight |
| Radio handshake | ✅ PASS (v2) | Original crashed on `require("gpio")`; v2 with gpio section removed ran clean |
| Sub-GHz quick scan | ✅ PASS | 5 freqs × 10 samples; ambient signal at 315 MHz at -97 dBm |
| GPIO full read | ⏭️ SKIPPED | Same `require("gpio")` bug as handshake — see F1 below |
| Device inventory (manual) | ✅ PASS | All primitives composed cleanly; found F2 below |
| Flipper info | ✅ PASS | JS-side `flipper` global intact; battery + JS SDK version surfaced |

---

## What this session validated end-to-end

1. **The full Sub-GHz RX subsystem works via JS.** `setup → setFrequency → setRx → getRssi → setIdle → end` — six distinct radio calls, returned without error, produced calibrated RSSI values consistent with chip datasheet. CPK can drive real RF hardware, not just file I/O.

2. **`flipper_js_run` survived a real mission.** Not just the trivial ping — a multi-module, multi-call mission with 5+ subsystem calls. Helper handled it cleanly.

3. **`notification.success()` audio + screen wake still works** on missions that include it. Original `ping.js` doesn't include it (silent); future mission templates should always end with notification.

4. **Cross-source identity consistency.** RPC `systeminfo_get` and JS `flipper.getName()` returned matching device identity. Two independent paths to the same truth = real validation.

5. **The validated launch + cleanup recipe is robust.** Three real missions in succession, each ending with `flipper_js_run`'s automatic BACK cleanup. Device returned to clean state every time.

---

## Real RF data captured

Sub-GHz quick scan results (10 samples each, 50ms apart):

| Frequency | Mean RSSI | Interpretation |
|---|---|---|
| 315.0 MHz | -97 dBm | **Real ambient signal nearby** — likely TPMS or car-key fob |
| 433.92 MHz | -110.5 dBm | Quiet ISM band (Europe-style remotes) |
| 868.0 MHz | -113 dBm | Very quiet (short-range Europe ISM) |
| 915.0 MHz | -111 dBm | Quiet (North American ISM) |
| 925.0 MHz | -110 dBm | Quiet (high-end ISM) |

Notes on real-hardware behavior we observed:
- **PLL granularity** — requested frequencies got rounded to the nearest synthesizable value (315000000 → 314999664 Hz). Expected CC1101 behavior.
- **RSSI quantization** — 433.92 MHz returns fractional dBm (-110.5) while other bands quantize to integers. The chip's RSSI register uses different LSB step sizes for different band groups. Another real-hardware fingerprint.
- **Sample stability** — RSSI values steady across all 10-sample windows. Clean noise-floor environment.

---

## New findings (require follow-up)

### F1 — `require("gpio")` fails on mntm-dev

**Severity:** Medium (blocks any JS mission that wants GPIO access).
**Symptoms:** `'gpio' module load fail at <line>` error dialog. Script aborts at the `require` call.
**Affects:** `missions/handshake/radio_handshake.js` (cc-built), `missions/handshake/gpio_full_read.js` (cc-built, not yet tested but will hit same bug).
**Hypotheses:**
- The GPIO JS module might be conditionally compiled out on `mntm-dev`. `mntm-release-*` may include it.
- The module may exist under a different name (`gpio_pin`? `gpio_io`?).
- The KB §2 documentation cc cited may be from OFW or a different fork.
**Workaround:** GPIO functionality may still be accessible via host-side RPC (`gpio_*` tools in the MCP, if any). To investigate.
**Action:** Patch `radio_handshake.js` to skip gpio (done — v2 shipped this session). Mark `gpio_full_read.js` as BLOCKED in the morning kit doc until the right API is identified.

### F2 — `storage_info` MCP tool returns SD card stats for `/int` requests

**Severity:** Medium (any caller asking "how much internal flash do I have free" gets a wrong answer).
**Symptoms:** `storage_info` called with `path="/int"` returns identical numbers to the `/ext` (SD card) call — both showed 33.5 GB total / 33.5 GB free. The Flipper's internal flash is ~1 MB; that number can't be `/int`.
**Likely cause:** The MCP server's `storage_info` tool isn't passing the `path` argument through to the protobuf `StorageInfoRequest`, defaulting to whatever the firmware returns first (probably `/ext` since SD card is enumerated first).
**Impact on missions:** `storage_health_check.run()` would compute nonsense for `/int` — would report ~0.2% used on a "33GB internal flash" that doesn't exist.
**Action:** Bug in `flipper_mcp/modules/storage/module.py` — investigate and fix in a future cook. Until fixed, `storage_health_check` should only report `/ext` values.

### F3 — `storage_list` returns empty for `/ext/apps_data` even when files exist

**Severity:** Low (confusing but not blocking — files can still be read by full path).
**Symptoms:** `storage_list("/ext/apps_data")` returns `(empty)` even though `/ext/apps_data/mcp_missions/ping.js` exists and can be read. `storage_list("/ext")` works correctly and shows `apps_data` as a child.
**Hypotheses:**
- A permissions/filter quirk in the firmware for that specific subdirectory.
- The MCP server's `storage_list` tool may be misinterpreting an "empty directory" response that's actually "directory has subdirectories but no files at this level."
**Action:** Investigate in a future cook. Note in `docs/for_ai_contributors.md` as a known limitation.

---

## What's still open from prior days

- **R5 (storage_write false-failure):** ✅ Fixed Day 4, validated again today
- **R6 (large script crash):** ✅ Subsumed by R5, validated Day 4
- **R7 (orphan flipper-mcp processes):** Not recurred this session
- **CPK venv migration:** Still using the band-aid `.pth` redirect from Day 4. Working fine. Low priority.
- **4 additional `src/` drift files** (cc Day 5.5 flag): `minimal_module/README.md`, `wifi_dev_board.md`, `claude_setup.md`, `protobuf_rpc.md`. Not addressed today.
- **`missions/llmdr/missions/__init__.py` eager-import:** Still blocks tests outside CPK's venv. Lazy-load would fix.

---

## What's coming

**For the next session (Pro plan):**
- Investigate the `gpio` JS module situation — is it conditionally compiled out? What's the right API?
- Fix the `storage_info` `/int` bug (find it in `modules/storage/module.py`, patch, test)
- Build and live-validate the `flipper_js_run` `no_cleanup` flag — when a JS mission crashes, the auto-BACK dismisses the error dialog before the user can read it. Debug-mode flag would help.
- NFC capture mission — the original "Claude takes a card scan for you" idea from Day 2. Now that we've validated everything else, this is the next demo-able feature.

**For the morning kit doc itself:**
- Add a "what happens when a mission crashes" subsection. Today's session showed the auto-cleanup dismisses errors before the user can read them. Need explicit guidance for debug workflows.
- Mark `gpio_full_read` as BLOCKED until F1 is resolved.

---

## Files shipped this session

| File | What |
|---|---|
| Day 6 morning kit work (cc, 13 files, 1523 lines) | Mission helpers + handshake missions + `MORNING_KIT.md` |
| Day 6.5 `AI_KNOWLEDGE_BASE.md` (cc, 600 lines) | Deep AI-onboarding doc with negative examples |
| `docs/decisions/DAY7_LIVE_FIRE_MORNING_KIT.md` | This file |

All previously uncommitted. Landing as a single Day 7 commit with morning-kit-as-tested plus today's decision doc.

The patched v2 `radio_handshake.js` that actually worked stays on the device's SD card but isn't checked into the repo yet — the version in `missions/handshake/` still has the broken gpio section. That gets fixed in a follow-up commit once F1 is properly diagnosed (so we either patch or rewrite with the correct API rather than removing functionality).

---

## Acknowledgements

cc's overnight build was usable as-shipped except for the gpio issue, which cc itself had flagged in its overnight report as "documented but unverified." The flagging was honest; the bug just landed in production-test. That's the discipline pattern working as intended.
