# Day 2 Decision Document — App-RPC Diagnostics + Synthetic Input + JS-via-RPC

**Date:** 2026-05-16
**Hardware:** AmorPoee (Kiisu V4B + Momentum `mntm-dev`), serial `5A3DEA0027E18000`, COM9
**Builds on:** `experiments/ble_probe/DAY1_DECISION.md` (BLE capability proof, Apr 30 2026)

---

## TL;DR

Day 1 left a load-bearing open question: **can JS missions launch over pure RPC, bypassing the CLI text-shell that Day 1 proved was sealed off on BLE?**

**Answer: yes, with a specific recipe.** This session built the diagnostic and input primitives needed to find that recipe and validated the full launch + cleanup loop end-to-end.

The session also generated a 1596-line deep knowledge base (`docs/KIISU_DEEP_KNOWLEDGE.md`) covering the entire Flipper RPC surface, JS module reference, transport quirks, and ecosystem gotchas — primary-source-cited, with a contradictions section flagging where our prior team understanding was wrong.

---

## What we shipped

### 1. `AppRpcResult` diagnostic refactor

Old `app_start` / `app_load_file` returned `bool`, discarding the firmware's `CommandStatus` enum. Now they return `AppRpcResult(ok, status_code, status_name)`. Still truthy/falsy (so existing `if await app_start(...)` idiom keeps working), but `.status_name` surfaces `ERROR_APP_CANT_START`, `ERROR_INVALID_PARAMETERS`, `ERROR_APP_SYSTEM_LOCKED`, etc.

Impact: every failure now reports *why*. The probe we ran in this session would have been opaque without it.

### 2. Three missing app-RPCs wired up

Already in the protobuf descriptor, never exposed in Python:
- `app_exit` — clean "close currently-running app"
- `app_get_error` — read firmware's verbose error text after a failure
- `app_lock_status` — query desktop lock state

### 3. `gui_send_input_event` RPC

The most operationally important addition. Synthesizes a hardware button press at the GUI input layer (below the RPC-callback layer the app_button_press RPCs require). Works on any app, including apps that don't register an RPC callback. This is **the only way** to programmatically exit apps like JS Runner.

Key gotcha (discovered live): real hardware emits `PRESS → SHORT → RELEASE`. JS Runner ignores a lone `SHORT`. The full three-event sequence is required.

### 4. `app_lifecycle` MCP module (6 tools)

Surfaces all of the above to Claude:
- `flipper_app_start` (now with status_name on failure)
- `flipper_app_load_file` (same)
- `flipper_app_exit`
- `flipper_app_get_error`
- `flipper_app_lock_status`
- `flipper_gui_send_input`

### 5. Knowledge base

`docs/KIISU_DEEP_KNOWLEDGE.md` — 1596 lines, three-tier organization, sources cited, gotcha index, contradictions section. Pre-flight reading for any Kiisu/Flipper mission work going forward.

---

## The validated launch + cleanup recipe

```
1. flipper_app_lock_status                     # check baseline (must be unlocked)
2. flipper_app_start("/ext/apps/assets/js_app.fap", "/abs/path/script.js")
3. <wait for log marker or known duration>     # script runs to completion
4. flipper_gui_send_input(BACK, PRESS)         # exit sequence step 1
5. flipper_gui_send_input(BACK, SHORT)         # exit sequence step 2
6. flipper_gui_send_input(BACK, RELEASE)       # exit sequence step 3
# loader is now free; can fire next mission
```

**Live-validated:** two consecutive ping.js runs end-to-end, no manual button presses, no port juggling.

---

## Contradictions with `KIISU_DEEP_KNOWLEDGE.md` §1.2 (mntm-dev addendum needed)

cc's knowledge base, from reading firmware source, predicted that `app_start("js_app", path)` and `app_start("JS Runner", path)` would both work. On `mntm-dev` they don't — both return `ERROR_INVALID_PARAMETERS`. Only the full FAP path works:

```
✅ app_start("/ext/apps/assets/js_app.fap", "/abs/path/script.js")
❌ app_start("js_app", "/abs/path/script.js")        — INVALID_PARAMETERS
❌ app_start("JS Runner", "/abs/path/script.js")     — INVALID_PARAMETERS
❌ app_load_file("/abs/path/script.js")              — ERROR_APP_NOT_RUNNING (per §1.4: JS Runner has no RPC callback)
```

Hypothesis: on `mntm-dev`, EXTERNAL FAPs are not registered in the loader's name-list at boot — only built-in apps (Sub-GHz, NFC, etc.) match by name. EXTERNAL FAPs are resolvable only by full filesystem path. This needs a §1.2 addendum in the knowledge base.

---

## Bonus discovery: `notification.success()` wakes the backlight

The synthetic `gui_send_input` does NOT wake the backlight — RPC button presses bypass the power-management code path that hardware button presses trigger. This is a real limitation for "watch Claude drive the device" demos.

**Workaround that works:** call `notification.success()` (or `notification.error()`) from inside the JS mission script. These trigger preset feedback events that DO wake the display, with audio + LED + backlight. Live-validated.

Mission script template (going forward, every visible mission should start with):
```javascript
let notification = require("notification");
notification.success();   // wake screen, announce activity
// ... mission body ...
```

For the EDGE classroom use case this is huge — students get an audible + visual confirmation that Claude fired a mission, without instructor intervention.

`notification.error()` produces a different two-tone "fail" beep — useful for missions that detect bad outcomes and want to flag them.

`notification.blink(color, type)` does NOT trigger the backlight wake — only LED. Use `success()`/`error()` for visible feedback.

---

## What was NOT shipped this session

- `app_state_response` subscription. The firmware emits this server-initiated when an app's state changes. A clean implementation needs receive-loop work and is the architecturally correct way to know "the script has actually finished" rather than polling a log marker. Future phase.
- `app_button_press` / `app_button_release` RPCs. Confirmed from firmware source (`rpc_app.c` line 206) that these require `rpc_app->callback` which JS Runner doesn't register — so they'd fail on JS Runner anyway. Other apps (Sub-GHz, NFC, IR, BadUSB) do register callbacks; future work if we need fine-grained button injection into RPC-aware apps.
- BLE-side validation of the new recipe. USB-only this session. Next phase pairs the recipe with the BLE transport from `experiments/ble_probe/`.
- A `flipper_js_run_rpc` mission helper that wraps the full recipe into one call. Deferred to keep this commit focused on primitives.

---

## Where this leaves us

**Path 2 (LLMDR meta-server with cross-device tools, per cc's roadmap) is unblocked.** The transport-agnostic launch primitive exists. Once paired with BLE, the same recipe will work mobile. Mission helpers can be built on top.

**The Day 1 architecture decision (split-mode Option 1 vs app_start Option 2) resolves in favor of Option 2.** The `app_start` route works (with the FAP-path caveat). No need to ship split-mode.

---

## Files in this commit

| File | What |
|---|---|
| `src/flipper_mcp/core/protobuf_rpc.py` | `AppRpcResult` dataclass; `gui_pb2` import; refactored + added 4 new RPCs |
| `src/flipper_mcp/core/rpc.py` | facade wrappers for new methods + re-export of `AppRpcResult` |
| `src/flipper_mcp/modules/app_lifecycle/__init__.py` | new module package |
| `src/flipper_mcp/modules/app_lifecycle/module.py` | 6 MCP tools |
| `docs/KIISU_DEEP_KNOWLEDGE.md` | 1596-line knowledge base (cc-generated, verified) |
| `docs/DAY2_DECISION.md` | this file |

Test missions (`/ext/apps_data/mcp_missions/ping_blink.js`, `ping_success.js`, `ping_error.js`) were also created on the device's SD card during this session but are not in the repo.

---

## Acknowledgements

- cc handled the recon: the 1596-line knowledge base would have eaten a full Claude.ai session token budget. Worth every token cc spent.
- GPT-5.5-Pro's Day 1 review still pays dividends — its emphasis on "answer architecture questions before building transports" is what made today's recipe-discovery cheap instead of expensive.
