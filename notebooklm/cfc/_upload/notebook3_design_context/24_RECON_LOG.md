# Bundle: 24_RECON_LOG.md
# 1 files concatenated for NotebookLM ingestion



=== FILE: _meta\RECON_LOG.md ===

# CFC Recon Log

Append-only running log of recon hits. Wide → medium → tight.

---

## WIDE-1 — "Can a FAP register its own RPC service?"

**Date:** 2026-05-26
**Hunt:** web search for "Flipper Zero custom FAP register protobuf RPC service" + variants

**Finding:** Every public Flipper RPC project is **client-side only**:
- `flipperdevices/flipperzero-protobuf` — schema only
- `flipperdevices/flipperzero_protobuf_py` — Python client bindings
- `flipperdevices/go-flipper` — Go client bindings
- `elijah629/flipper-rpc` — Rust client bindings
- `flipperdevices/qFlipper` — qFlipper desktop client

**Zero hits** on extending the firmware's RPC server with new verbs from a FAP.

**Interpretation:** Either it's not supported at all, or it's supported but never publicly used. Both possibilities collapse Phase 1 toward the same answer: **read the firmware source for the RPC service infrastructure and verify directly.**

**Implication for CFC design:** strong signal that the FAP will NOT register canonical RPC verbs. Likely architectural pivot to one of:
- **Side-channel via storage:** CFC writes structured JSON to `/ext/apps_data/cfc/`, host polls.
- **Side-channel via JS bridge:** CFC plugin exposes new `require("cfc")` modules; host calls via `flipper_js_run`.
- **Embed-in-RPC-payload:** CFC piggybacks on `app_start_request.args` and writes result to a known path.

The third option is most consistent with existing CPK patterns (`flipper_js_run` already does this for JS missions).

**Files to fetch in next pass:**
- Momentum `applications/services/rpc/` — the RPC service implementation
- Momentum `applications/services/rpc/rpc.h` — the public registration API (if any exists)
- Flipper SDK `furi_hal_subghz.h`, `furi_hal_nfc.h`, `furi_hal_infrared.h` — what C APIs FAPs can call
- Public sample FAPs that touch NFC/Sub-GHz/IR — pattern templates

---

## WIDE-2 — Direct source inspection of `applications/services/rpc/`

**Date:** 2026-05-26
**Method:** sparse clone of Next-Flip/Momentum-Firmware @ main

### Finding A: `rpc_add_handler` is INTERNAL

- Lives in `rpc_i.h`, not `rpc.h`. The `_i` suffix is firmware convention for "internal."
- Used by the built-in subsystems (rpc_storage, rpc_system, rpc_gui, rpc_gpio, rpc_app, rpc_desktop, rpc_property, rpc_debug) at session-open time.
- A FAP CANNOT call this without rebuilding the firmware. Confirmed: there is no public registration path for new top-level RPC verbs.

### Finding B (CRITICAL): `rpc_app.h` exists and is the canonical extension path

**The Flipper firmware has an official, public, documented API for FAPs to exchange arbitrary data with a host over RPC.**

Header: `applications/services/rpc/rpc_app.h`
Schema reference: `application.proto` (per the file header comment)
Event type: `RpcAppEventTypeDataExchange`

Doc quote (literal):
> "The client has sent a byte array of arbitrary size. This command's purpose is bi-directional exchange of arbitrary raw data. Useful for implementing higher-level protocols while using the RPC as a transport layer."

Public API surface for FAPs:
- `rpc_system_app_set_callback(app, cb, ctx)` — register a callback that fires when host sends data
- `rpc_system_app_send_started(app)` — handshake "I'm ready"
- `rpc_system_app_send_exited(app)` — clean shutdown
- `rpc_system_app_confirm(app, ok)` — ACK each command
- `rpc_system_app_set_error_code/text` — surface errors
- `rpc_system_app_exchange_data(app, bytes, size)` — send bytes back to host

**This is the CFC architecture.** CFC does NOT need to register new top-level RPC verbs. CFC runs as the "current app," and CPK uses `AppDataExchange` to send command frames (JSON or protobuf) and receive structured responses.

### Implication for CFC design

Architecture is now de-risked:
1. CFC is a normal `.fap`, no firmware fork needed
2. Host sends `Application.AppDataExchangeRequest` with serialized command
3. FAP's callback fires, parses command, runs C-API call (e.g. `furi_hal_nfc_*`)
4. FAP calls `rpc_system_app_exchange_data()` to return result
5. Host receives matching `Application.AppDataExchangeRequest` (the protocol is symmetric — both directions use the same message)

This is consistent with how qFlipper currently does file-content streaming for some apps; we're just using the documented surface for our own protocol.

**Next files to fetch:**
- `application.proto` from flipperdevices/flipperzero-protobuf (the exact wire schema for AppDataExchange)
- `rpc_app.c` from Momentum (the implementation, to understand timing/buffering constraints)
- Existing FAP examples that USE `rpc_app.h` (find via grep on `rpc_system_app_exchange_data` callers)
- Public Python or C example of a host driving an app via AppDataExchange

---

## WIDE-3 — JS modules (`.fal`) as alternative architecture

**Date:** 2026-05-26
**Source:** `documentation/js/js_using_js_modules.md` + `applications/system/js_app/`

### Finding C: Custom JS modules are first-class and documented

> "JS modules are written in C/C++, making them fast and efficient. They come with Flipper Zero firmware and are stored on the microSD card in compiled form as FAL (Flipper Application File) files."

This is a **second viable CFC architecture**: instead of a single FAP using AppDataExchange, ship one `.fal` per capability domain (cfc_nfc.fal, cfc_subghz.fal, ...) and import them from JS missions via `require()`.

In-tree examples: 14 module sources at `applications/system/js_app/modules/`:
- js_badusb.c, js_blebeacon.c, js_flipper.c, js_gpio.c, js_i2c.c, js_math.c, js_notification.c, js_serial.c, js_spi.c, js_storage.c, js_subghz/, js_infrared/, js_tests.c, js_usbdisk/, js_vgm/

The plugin system uses `flipper_application/plugins/plugin_manager.h` + `composite_resolver.h`. Macros for module construction:
- `JS_ASSIGN_MULTI` / `JS_FIELD` — register methods on an object
- `JS_GET_INST` / `JS_GET_CONTEXT` — fetch the C-side struct from a JS handle
- `JS_VALUE_*` declaration macros for typed args (enum, int32, string, object)

### Architecture comparison

| Path | Mechanism | Pros | Cons |
|---|---|---|---|
| A. CFC as FAP w/ AppDataExchange | one .fap, bytes both ways via RPC | single binary; host drives via existing protobuf RPC | FAP must keep running; UI tax; first user of DataExchange branch |
| B. CFC as JS modules (.fal) | one .fal per capability domain, loaded by `require()` from JS missions | no new RPC surface needed; CPK already speaks JS; 14 in-tree examples; documented | more individual binaries; reimplements some failing built-in modules (gpio, nfc) but THAT'S THE POINT — fix them |

### Strategic note

**Path B may be the better fit for CPK** because:
1. CPK's mission framework already runs JS missions via `flipper_js_run`. A `require("cfc_nfc")` call slots into the existing pattern with zero new infrastructure.
2. F1 (`require("gpio")` fails) and F4 (`require("nfc")` fails) — the original motivation for building CFC — are LITERALLY the gap that .fal-style modules fill. We can ship `cfc_gpio.fal` and `cfc_nfc.fal` as drop-in replacements for the missing built-ins.
3. Smaller blast radius per binary. Easier to ship incrementally (NFC first, Sub-GHz next, etc.) without coupling them all into one process.

This pivots the Phase 1 spec significantly. Path B should be the **default**; Path A is fallback if module-system limits are discovered.

**Open questions for Phase 1 to resolve:**
1. Can a .fal module call `furi_hal_nfc_*` / `furi_hal_subghz_*` APIs, or are these gated to in-tree FAPs?
2. What's the .fal build pipeline under ufbt? Is it the same as .fap or different?
3. What stack/heap is available to a .fal vs a .fap?
4. Does `require("cfc_nfc")` work for external .fal files, or only firmware-bundled ones?

These map directly to 4 of the 8-12 load-bearing NotebookLM questions.

**Next:** Look for any in-the-wild example of an out-of-tree .fal module — and check the API symbol table to confirm furi_hal_* and furi_hal_nfc_* are FAP-visible.

---

## ROUND 2

### WIDE-4 — Cross-firmware API stability

**Date:** 2026-05-26 (round 2)
**Method:** sparse-clone OFW, Unleashed, Xtreme; diff against Momentum

**Finding D:** `rpc_app.h` is **identical** between OFW, Momentum, and Unleashed. Only Xtreme differs, and only by missing `RpcAppEventTypeButtonPressRelease` (which CFC doesn't need).

`rpc_app.c` and `js_modules.c` show single-digit lines of diff between Momentum and OFW.

**Implication:** CFC built against Momentum will work on OFW and Unleashed unchanged. Single binary, three-firmware portability. Xtreme is the only edge case and we can ignore it.

---

## ROUND 2 — additional findings

### Finding E: Official Python bindings already expose AppDataExchange

`flipperzero_protobuf_py` ships `rpc_app_data_exchange_send(data)` and `rpc_app_data_exchange_recv() -> bytes` in `flipperzero_protobuf/flipper_app.py`. ~12 lines of host-side code total.

**Implication:** CPK's host transport for talking to CFC will literally mirror this code. We don't need to invent the host side; we copy the two functions.

There's also a `do_data_exchange` interactive CLI command in `flipperCmd.py` proving the end-to-end pattern (host → device → host).

### Finding F: Zero in-the-wild AppDataExchange consumers in 800MB of community FAPs

Searched 513MB of Momentum-Apps + 269MB of Xtreme-Apps. **Zero** uses of `rpc_system_app_exchange_data` or `RpcAppEventTypeDataExchange`.

**Implication:** CFC will be the first publicly-known FAP using the DataExchange branch. The API exists, is documented, has firmware test coverage in the form of the built-in app handlers, but has never been exercised in the open. Both opportunity (real moat) and risk (we'll find any rough edges).

### Finding G: Zero out-of-tree custom JS modules in the community catalogs

Same searches: no `.fal` modules outside the firmware tree. Only jamisonderek's SAO (which still requires overlay-into-firmware) and the in-tree set.

**Implication:** Same as F — CFC's `.fal` modules will be among the first public ones if not the first.

### Finding H: `DataExchangeRequest.data` has no declared max_length

From `application.options`: `PB_App.DataExchangeRequest.data type:FT_POINTER`. No explicit `max_length` cap, but bounded by `RPC_BUFFER_SIZE` (1024 bytes from `rpc.h`).

**Implication:** CFC's protocol must chunk anything >~1KB. NFC card dumps, sub-GHz captures will need chunked framing. This goes inline in the Phase 1 spec.

### Finding I: Expansion Module Protocol is a fallback architecture

`developer.flipper.net/.../expansion_protocol.html` documents a UART-based protocol for external hardware modules that can forward RPC frames. Not relevant for CFC v1 (USB is fine), but useful to know exists if we ever want CFC to run on a companion microcontroller.

---

## Round 2 corpus summary

- **818 files, 6.4 MB** at `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\notebooklm\cfc\` (NOT YET TRANSFERRED — sandbox-only as of session compaction)
- 23 source repos pulled, mix of official Flipper, Momentum, community FAPs, host-side bindings, dev docs
- All in MIT/LGPL/GPL/CC0/unspecified — reading is fine; if we paste anything verbatim into the MIT-licensed CFC code, we have to be careful (`_meta/MANIFEST.md` tracks per-source license)

## Critical artifacts for next session

1. **`_meta/RECON_LOG.md`** — this file. The cumulative findings doc with implications and follow-up questions.
2. **`_meta/NOTEBOOKLM_GROUPING_PLAN.md`** — the three-notebook split plan with which subdirs go where, plus the load-bearing questions to ask each notebook once loaded.
3. **`_meta/MANIFEST.md`** — flat per-subdir inventory with provenance and license tracking.
4. **`_meta/concat_for_notebooklm.py`** — the bundler that combines per-subdir source into NotebookLM-uploadable text blobs.

## RECOVERY NOTE (added during session compaction)

The 895-file corpus under `wide/`, `medium/`, `tight/` was assembled in the Linux sandbox at `/mnt/d/Dev/Projects/Claude-s-Pet-Kiisu-CPK/notebooklm/cfc/` under the (mistaken) assumption this was a WSL passthrough to Windows D:\. It wasn't. The sandbox is its own filesystem.

The corpus was NOT transferred to Windows D:\ before this chat ran out of context. Only this `_meta/` directory survived.

**Next session recovery:** run `_meta/concat_for_notebooklm.py` from Windows. It re-runs the source-fetch logic (sparse git clones) and rebuilds `wide/medium/tight/` directly on D:\. Estimated time: 10-15 min depending on network. The clone targets and per-subdir file lists are documented in `_meta/MANIFEST.md`.

## What Phase 1 spec needs to commit to (suggested decisions)

Based on findings A through I, the Phase 1 spec can lock in:

1. **Architecture: PATH B (.fal JS modules) is the default, PATH A (.fap + AppDataExchange) is the fallback for longer-running missions.** Path B has more community precedent (14 in-tree examples, 1 in-the-wild), fits CPK's existing JS-mission framework, and directly fills the F1/F4 gaps. Path A is still in scope for use cases that can't fit a JS mission.

2. **Cross-firmware target: Momentum + OFW + Unleashed.** Xtreme is the only edge case and we deliberately defer. (Finding D)

3. **Wire-level chunking: required for any payload >900 bytes.** Frame format goes inline in the spec. (Finding H)

4. **Host-side transport: extend `flipper_mcp` with `flipper_cfc_call()` mirroring `rpc_app_data_exchange_send/recv`.** No new MCP server work; just a new method. (Finding E)

5. **No firmware rebuild required for v1.** Both .fal modules and AppDataExchange-using FAPs are out-of-tree. (Findings B, C)

6. **Risk to flag: we're the first.** Both architectures (DataExchange + out-of-tree .fal modules) have zero in-the-wild public reference. Phase 2 should include live-fire validation of the firmware path BEFORE locking in the host side. (Findings F, G)
