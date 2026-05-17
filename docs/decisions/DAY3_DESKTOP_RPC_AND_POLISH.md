# Day 3 Decision Document — Desktop RPC, Full-Press Polish, Universal Cleanup

**Date:** 2026-05-17
**Hardware:** AmorPoee (Kiisu V4B + Momentum `mntm-dev`), serial `5A3DEA0027E18000`, COM9
**Builds on:** `experiments/ble_probe/DAY1_DECISION.md` (BLE capability proof), `docs/DAY2_DECISION.md` (app-RPC + synthetic input + JS-via-RPC validation)

---

## TL;DR

Day 2 left three operational rough edges that cc's capability survey cook (~2hr) surfaced as material gotchas: (1) lockscreen handling used a made-up unlock dance that didn't work, (2) every button press required three RPC calls, (3) JS Runner's exit recipe was unclear when scripts crashed vs succeeded.

This session resolves all three. Plus a confirmed firmware bug in `storage.fsInfo()` that should be documented and worked around.

---

## What we shipped

### 1. `flipper_desktop_is_locked` + `flipper_desktop_unlock`

Two new MCP tools wrapping protobuf tags 66 and 67 (PB_Desktop.IsLockedRequest, PB_Desktop.UnlockRequest). Previously not exposed in the Python layer despite being in the protobuf descriptor.

Plain English on why these matter: `flipper_app_lock_status` (added Day 2) is actually the **app-loader mutex**, not the desktop lock state. It returns LOCKED whenever any app is running, including the lockscreen-as-app. cc's R3 finding documented this confusing overlap. `flipper_desktop_is_locked` is the genuine "is the lockscreen showing" check. `flipper_desktop_unlock` dismisses it via direct RPC (no synthetic keypress needed).

### 2. `flipper_gui_send_input` polished — full-press by default

The biggest UX win of the session. Previously, every button press required three separate RPC calls (PRESS / SHORT / RELEASE). A lone SHORT was silently absorbed by most app scenes — cc's R2 + live observation confirmed.

The tool now emits the full PRESS→SHORT→RELEASE triplet automatically when called without `single_event=True`. Existing callers that explicitly pass an event_type and set `single_event=True` get the old single-event behavior (for LONG holds, REPEAT events, manual triplet construction).

Also added `gui_send_input_full_press` to the underlying RPC layer for direct Python use.

Validated live with all six keys on Momentum's default desktop:
- **UP** → Momentum menu
- **DOWN** → File Browser
- **LEFT** → Clock app
- **RIGHT** → Passport (angry dolphin)
- **OK** → Main menu (apps list)
- **BACK** → no-op on desktop / exit in apps

### 3. Universal cleanup verb: BACK

cc's R8 (and Victor's live observation) showed that JS Runner shows different screens for success vs error. The recipe for cleanup wasn't obvious for the error case.

**Live-validated:** a single BACK press dismisses **all three** JS Runner end-states:
- "Script done" success screen
- "Error: ..." error dialog (e.g. require()'ing a non-existent module)
- Stuck-running scripts

No state-machine branching needed in the mission helper. **The cleanup recipe is literally just "send BACK after every script run."**

### 4. Confirmed `storage.fsInfo()` is broken on `mntm-dev`

cc's INCONCLUSIVE finding (P1_storage_005) is now CONFIRMED. An isolated minimal probe shows the script aborts on the `storage.fsInfo()` call itself — log captures `step=loaded` and nothing else, despite the function being bound (typeof returns `foreign_ptr`).

Workaround for missions: use the **host-side** `storage_info` MCP tool instead of the JS-side `fsInfo()`. Both return the same total/free-space data; only the JS binding is broken.

This is firmware-side and not something we can fix from our codebase. Worth filing upstream to Next-Flip/Momentum-Firmware once we have a minimal repro.

---

## The validated launch + cleanup recipe (current)

```
1. flipper_desktop_is_locked            # if true, call flipper_desktop_unlock
2. flipper_app_start(FAP_PATH, script)  # launch
3. <wait for log marker or duration>    # script runs
4. flipper_gui_send_input(BACK)         # ONE call dismisses success/error/stuck
5. ready for next mission
```

That's it. Compare to Day 2's 10-step recipe with three-call BACK sequence and OK/BACK/RIGHT recovery dance. **Same outcome, 4 steps shorter.**

---

## What's still open from cc's findings

- **R5 — `storage_write` reports "Write failed" on most long writes.** MCP-server-side bug in the response parser. Not fixed this session. Workaround: always verify writes by reading back. ~30-60 min job for next session.
- **R6 — Large JS scripts (~1500+ chars) crash mJS and drop USB-CDC.** Probably downstream of R5 (truncated script → parse error → handler crash). Fix R5, R6 likely evaporates.
- **R7 — cc spawns orphan flipper-mcp processes that don't terminate on session end.** Killed 10 of them tonight to free COM9. Worth investigating the next time cc runs a hardware-touching cook.

---

## Files in this commit

| File | What |
|---|---|
| `src/flipper_mcp/core/protobuf_rpc.py` | Added `desktop_pb2` import, `desktop_is_locked`/`desktop_unlock` RPCs, `gui_send_input_full_press` helper |
| `src/flipper_mcp/core/rpc.py` | Facade wrappers for all three new methods |
| `src/flipper_mcp/modules/app_lifecycle/module.py` | Bumped to v0.4.0, added `flipper_desktop_is_locked` + `flipper_desktop_unlock` tools, polished `flipper_gui_send_input` to emit full triplet by default |
| `docs/DAY3_DECISION.md` | This file |
| `docs/SETUP_REQUIREMENTS_mntm-dev.md` | (created by cc during the cook) Required device settings for RPC-driven work |

The cc capability survey deliverables (`D:\Dev\scratch\cc_capability_survey\phase1_js_modules.md`, `PHASE1_SUMMARY.md`) are not in the repo — they're research artifacts. Their findings drove this session.

---

## What this leaves us ready for

The full UI-automation primitive set is now in place:
- ✅ Launch any app by FAP path
- ✅ Press any button (single call, full triplet)
- ✅ Detect AND dismiss lockscreen
- ✅ Check current app state
- ✅ Notify with audio + screen wake via `notification.success()`
- ✅ Universal cleanup with one BACK call

Next session's natural moves:
1. Fix `storage_write` false-failure bug (R5) — unblocks cc cooks
2. Build `flipper_js_run_rpc` mission helper that wraps the validated recipe
3. NFC capture mission using the new primitive set — the original idea Victor spotted on Day 2
4. Or: pivot to Cardputer-Adv firmware work, applying the seven §16 corrections from that side's KB

---

## Acknowledgements

cc spent 2 hours on Phase 1 of a capability survey and produced six structural infra findings instead of the per-function matrix we asked for — which was the right call. Those findings drove every change in this commit. The "didn't finish the matrix" outcome was net-positive.
