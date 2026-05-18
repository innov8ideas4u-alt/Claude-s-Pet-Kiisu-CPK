# Morning Kit — what to fire first

You woke up. The Flipper is plugged in. Claude Desktop (or Claude Code) is running with the `flipper-mcp` server loaded. Try these missions in order. Each one is **RX-only / observe-only** — no RF emission, no BadUSB, no USB-mode changes. Safe to fire blind.

> If anything fails in the first three missions, stop and read "What to do if something fails" at the bottom. Don't push deeper into the kit if the connection isn't healthy.

---

## 1. Connection check

**Ask Claude:** *"What's the health of my Flipper connection?"*

**Expected:** Claude calls `flipper_connection_health` and reports `connected: true`, `transport_connected: true`, `rpc_responsive: true`, with the COM port shown.

**If it fails:** USB cable issue (try a different cable — charge-only cables are a classic trap), or the MCP server didn't load. Unplug, replug, restart Claude.

---

## 2. Device inventory

**Ask Claude:** *"Run the device inventory mission"*

**Helper:** `missions/llmdr/missions/device_inventory.py` — `run(client)` returns a `DeviceInventoryReport`. Pure host-side, no JS, no beeps, no LED activity.

**Expected:** Claude reports device name, hardware model, firmware (Momentum mntm-dev), connection details, both lock states (desktop + app-loader), and an embedded storage health report (total/free per volume + top-level dirs).

**If it fails:** RPC unresponsive — usually means the MCP server lost the connection. Reconnect via Claude or run mission 1 first.

---

## 3. Radio handshake — **THE MAIN EVENT**

**Ask Claude:** *"Run the radio handshake mission"*

**Helper:** `missions/llmdr/missions/radio_handshake.py` — pushes `missions/handshake/radio_handshake.js` and runs it.

**Expected (in order):**
- First beep + screen wakes (`notification.success` at script start)
- ~1 second of silent activity (Sub-GHz RX probe at 433.92 MHz)
- ~1 second more (GPIO sweep over pins 2/4/5/6/7 + storage list)
- Blue LED brief blink (`notification.blink("blue", "short")`)
- Second beep at end
- Claude reports: `subghz_ok=true, rssi_433_92=<negative int>, gpio_p2..7=0/1, ext_apps_count=<int>, notification_blink_ok=true, uncertain_modules=infrared,bluetooth`

**Why this is the main event:** it's a single mission that proves five radio-related subsystems (Sub-GHz radio, GPIO module, storage filesystem, notification subsystem, JS Runner itself) are all responsive in one go. If this passes, everything else in the kit will probably pass.

**If `finished=true` is missing:** the JS script aborted somewhere. Read the `step=*` lines in the log — the last one tells you which phase died.

---

## 4. Sub-GHz quick scan

**Ask Claude:** *"Run the Sub-GHz quick scan mission"*

**Helper:** `missions/llmdr/missions/subghz_quick_scan.py`.

**Expected:** ~5 seconds of silent activity (RX-only, no LED). Then Claude reports per-band average/min/max RSSI for 315, 433.92, 868, 915, 925 MHz. Quiet bands sit around -110 to -120 dBm; anything notably higher means something's transmitting nearby — a key fob, garage opener, weather sensor, etc.

**If it fails:** if `subghz_ok=false` in mission 3 already, this will fail the same way. CC1101 issue, not your fault.

---

## 5. GPIO full read

**Ask Claude:** *"Run the GPIO full read mission"*

**Helper:** `missions/llmdr/missions/gpio_full_read.py`.

**Expected:** Two beeps bracketing ~1 second of activity. Claude reports the state of every Flipper user GPIO pin (2, 3, 4, 5, 6, 7, 10, 12, 13, 14, 15, 16, 17) as 0 or 1. Floating pins read noise (expected). Anything you wired up externally should show its real level.

**If pins all read 0 or all read 1:** likely a floating header — totally fine, no failure.

---

## 6. BLE passive scan (documented non-support)

**Ask Claude:** *"Run the BLE passive scan mission"*

**Helper:** `missions/llmdr/missions/ble_passive_scan.py`.

**Expected:** ~1 second of activity then `ble_supported=false` with the reason: the only BLE-related JS module on mntm-dev is `blebeacon` (TX/advertising), and the morning kit is RX-only. RX-side BLE bindings would require a firmware-side patch.

**This is a SUCCESS even though it returns "not supported":** the mission's job is to record the non-support fact so we don't re-derive it next time. Treat it as a passing test.

---

## 7. Flipper info (bonus)

**Ask Claude:** *"Run the Flipper info mission"*

**Helper:** `missions/llmdr/missions/flipper_info.py`.

**Expected:** ~1 second of activity. Claude reports device name, model, battery %, firmware vendor, and JS SDK version — read via the JS-side `flipper` global. Useful as a cross-check against mission 2 (which reads the same info via protobuf RPC). If they disagree, that's a bug worth investigating.

---

## What to do if something fails

- **Connection fails (mission 1):** unplug/replug the Flipper. If Claude can't see the MCP tools at all, restart Claude entirely. Check `~/.claude/claude_desktop_config.json` lists `flipper-mcp`.
- **`ERROR_APP_SYSTEM_LOCKED`:** another app is running on the device. Press BACK on the hardware until you're back on the desktop, then retry.
- **`Desktop is LOCKED`:** the lockscreen is showing. Ask Claude *"unlock the desktop and then re-run mission X"* — or wake the device with any hardware button first.
- **Missing `finished=true` in any JS mission:** the script aborted. Read the `step=*` lines in the log — the last one printed is where it died. Common culprits:
  - mJS module not bound (we logged `getfail` for gpio.get; check for similar)
  - script size over ~1500 chars (mJS engine crash — should not apply to morning-kit missions, all are sized safely)
  - typo in the mission script that abused mJS's no-coercion rule (every numeric concat must call `.toString()`)
- **Anything weirder:** read `docs/for_ai_contributors.md` → "Things we already learned the hard way." Most CPK gotchas are already documented there.

---

## Recommended order if you only have 10 minutes

1 → 2 → 3. That covers connection, full device inventory (incl. storage health), and the radio handshake (which exercises five subsystems at once). If those three pass, your Flipper is healthy and ready for whatever you want to do today.

Everything past mission 3 is value-add for specific debugging or exploration tasks.

---

## What this kit does NOT cover

By policy, the morning kit excludes:

- **TX-side anything:** Sub-GHz transmit, IR transmit, BadUSB HID emulation, BLE beacon advertising. Those require an explicit "I meant to do this" confirmation, not a morning-run.
- **USB-mode-changing apps:** USB Disk (`usbdisk`) and BadUSB profile-switching. Both drop the host's CDC transport mid-call.
- **NFC card read:** requires you to physically tap a card on the Flipper. Not "fire and walk away" friendly. Sketched as a recipe in `docs/MISSIONS_COOKBOOK.md` for when you're at the device.

When you want any of those, run them deliberately — not as part of a morning sanity sweep.
