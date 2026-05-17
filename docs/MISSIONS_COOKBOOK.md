# Missions Cookbook

> **What this is:** recipes for missions we plan to build, not implementations. Each entry is a sketch of the shape — what tools it uses, what the log should look like, what the human asks Claude in plain English. Pseudocode-grade, designed so a contributor can pick one and turn it into a real mission in a few hours.
>
> **What this isn't:** finished missions. None of these are wired up yet. When one gets implemented, move it to `missions/` and link back here.
>
> **Status legend:** ☐ = not started · ▣ = sketched, partial impl · ✓ = implemented, link in entry

---

## ☐ NFC card capture

**Human ask:** *"I'm about to tap a card. Capture whatever it is and save the dump."*

**Shape of the mission:**

1. `flipper_app_start("NFC", "")` — opens NFC app on the "Read" scene.
2. Mission script polls `/ext/nfc/` for a new file appearing (the NFC app auto-saves on successful read; we just need to know *when*).
3. While waiting, the human taps the card. NFC app captures it, writes a `.nfc` file.
4. After a successful read, NFC app shows a "Save?" prompt — `flipper_gui_send_input("OK")` to accept the default name.
5. Mission writes the new filename to its log so the host knows what was just saved.
6. `flipper_gui_send_input("BACK")` × 2 to exit NFC and return to desktop.

**Tools touched:** `flipper_app_start`, `storage_list` (or `storage_list_detailed`), `flipper_gui_send_input`, `storage_read` (for the log).

**Why this is a good first-real-mission to build:** exercises every CPK primitive without any RF risk. The hardware-side action is reading, never transmitting.

**Gotchas:** NFC app lazily creates `/ext/nfc/assets/` on first launch — use `list_detailed` and filter on `type == "FILE"` so you don't mistake the assets directory for a captured card.

---

## ☐ Sub-GHz frequency hop scan

**Human ask:** *"Scan 315, 433.92, and 868 MHz for activity. Tell me which band has the strongest signal."*

**Shape of the mission:**

1. JS mission script that requires the `subghz` module.
2. Walks a configurable frequency list. For each: `subghz.setFrequency(f)`, listen for `dwell_ms` (start with 500 ms), capture peak RSSI.
3. Logs one line per band: `freq_mhz=433.92 peak_rssi_dbm=-72`.
4. Final `step=done`, `winner_mhz=<best>`, `finished=true`.
5. Host launches with `flipper_js_run` (no GUI needed — pure JS).

**Tools touched:** `flipper_js_run` (which orchestrates app_start + BACK cleanup), `storage_read` for the log.

**Why this is interesting:** first mission that does something *useful* and *hardware-specific*. Good demo for an EDGE classroom — "the Flipper just told us which band a remote keyfob is on."

**Gotchas:** mJS scripts > ~800 chars start risking JS-engine crashes. If the band list grows, split into multiple mission files invoked back to back, or move the band loop to the host.

---

## ☐ IR remote learning (read-only, no TX)

**Human ask:** *"Point your TV remote at the Flipper and press the Power button. Save what you see."*

**Shape of the mission:**

1. `flipper_app_start("Infrared", "")` — opens the IR app on the "Learn New Remote" scene.
2. Human presses their remote button. IR app captures, prompts for a name.
3. Synthetic `OK` press accepts default name (e.g. "TV Power").
4. IR app writes the `.ir` file to `/ext/infrared/`. Mission script polls for it.
5. Mission logs the new filename and the protocol the IR app detected (read from the file header).
6. `BACK` × 2 to exit.

**Tools touched:** `flipper_app_start`, `flipper_gui_send_input`, `storage_list_detailed`, `storage_read`.

**Why this is read-only:** IR TX is permissioned (could be confused with adversarial). RX is just a sensor; never an action on the world. This is the IR equivalent of the NFC capture mission above.

**Gotchas:** the IR app's "Save?" prompt UI has changed across Momentum versions. Check `docs/decisions/` for any post-mntm-014 changes before relying on a specific button sequence.

---

## ☐ GPIO digital read sweep

**Human ask:** *"Quick — what's connected to my GPIO header right now? Read every pin."*

**Shape of the mission:**

1. Pure JS mission, no app launches.
2. `let gpio = require("gpio");`
3. For each of pins 2, 3, 4, 5, 6, 7, 10, 12, 13, 14, 15, 16, 17:
   - `gpio.init(pin, "input", "pullup");`
   - read state, log `pin_<n>=<HIGH|LOW>`.
4. Final `finished=true`.

**Tools touched:** `flipper_js_run`, `storage_read`.

**Why this is useful:** the "what's wired up" debug mission. Common student question is "is my LED on pin 4 actually getting power?" — this answers it in one ask.

**Gotchas:** pullup vs. pulldown matters for what you call "connected." For probing what's connected to a board, pullup means "LOW = something is pulling this pin to ground." Document the assumption in the log header line.

---

## ☐ BLE device scan

**Human ask:** *"What Bluetooth devices are around me right now?"*

**Shape of the mission:**

1. The mission is mostly host-side, because Momentum's mJS doesn't have a stable `ble` module across versions.
2. Host calls `flipper_app_start("Bluetooth Remote", "")` only as a side-effect to ensure BLE radio is initialized.
3. Mission polls a BLE-scan output area (TBD — depends on what Momentum exposes; see `docs/decisions/DAY1_BLE_PROBE.md` for prior research).
4. Output: list of devices with `ble_device=<name|MAC> rssi_dbm=<n>` lines.
5. `BACK` × 2.

**Tools touched:** TBD — needs BLE-stack probe work first. See the probe results in `experiments/ble_probe/PROBE_RESULTS.md`.

**Why this is a stretch goal:** Day 1's BLE probe found the surface is fragmented across firmware versions. Likely needs a CPK-side BLE transport layer rather than a JS mission. Listed here so future-Victor doesn't re-derive the question.

**Gotchas:** *all* of them. BLE on Momentum is the one subsystem CPK has the most outstanding questions about. Don't promise this works without testing on the exact firmware build the user is on.

---

## ✓ Storage health check — **IMPLEMENTED**

**Human ask:** *"How much room is left on my SD card? Anything weird going on with storage?"*

**Implementation:** `missions/llmdr/missions/storage_health_check.py` — pure host-side, async, returns a `StorageHealthReport` dataclass with `.summary()` for human output. Unit tests at `tests/missions/test_storage_health_check.py`.

**Tools touched:** `client.rpc.storage_info(path)`, `client.storage.list_detailed(path)`. No app launches, no JS, no GUI input. No MCP tool wrapper yet — that's a follow-up.

**Why this was the right first-real-mission to ship:** zero hardware risk, no firmware-edge-case behavior, no UI navigation, trivial to mock for tests. Now serves as the reference impl for what a host-side CPK mission looks like.

---

## Conventions used in these recipes

- **Pseudocode tone** — every step uses real CPK tool names so a reader can grep them, but doesn't paste the literal Python/JS body.
- **Tools touched** — explicit list, so a reviewer can sanity-check that the mission is wired against real, existing tools (not invented ones).
- **Gotchas** — mandatory section. The whole point of writing a recipe before the implementation is to capture what's likely to bite.
- **Status marker** — flip from ☐ to ▣ as soon as a PR opens; to ✓ when it lands. Link the mission file in the entry.

When you implement one of these:

1. Move the implementation under `missions/` (mission scripts) and/or `flipper_mcp/modules/` (new tools, if any).
2. Update the entry here to ✓ with a link to the mission file.
3. Add any new "things we learned the hard way" to `docs/for_ai_contributors.md`.
4. If the recipe was wrong in some way once you actually built it, update the recipe so the next reader doesn't trip on the same assumption.

---

## What to add next

When you're ready to add a new recipe to this cookbook, the bar is:

- It's something a human would actually ask Claude to do.
- It uses CPK primitives that already exist (or proposes the new primitive needed).
- The "gotchas" section can name at least one specific firmware/mJS/RPC quirk that will bite the implementer. (If you can't think of one, you haven't researched it enough yet.)

Recipes are cheap. Implementations are expensive. Write recipes liberally.
