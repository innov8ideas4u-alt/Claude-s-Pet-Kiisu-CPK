# Mandatory device-side setup for cooking against AmorPoee (mntm-dev) over USB-CDC

**Discovered:** 2026-05-17 during Phase 1 capability survey (Claude Code session).
**Symptom without it:** every `app_start` returns `ERROR_APP_SYSTEM_LOCKED`; RPC drops cascade into relocks that require physical unlock.

## Required toggles (Momentum mntm-dev)

Path on device: `UP` from Desktop → `MNTM` → `Interface` → `Lockscreen`

| Setting | Default | Required value | Why |
|---|---|---|---|
| **Allow USB RPC while locked** | OFF | **ON** | Without this, `app_start` over RPC returns `ERROR_APP_SYSTEM_LOCKED` whenever the desktop is on its lock scene. The default is hostile to RPC automation. |
| **Allow BLE RPC while locked** | OFF | ON (if cooking over BLE) | Same as above, BLE side. |
| **Prevent Auto Lock with USB/RPC** | OFF (?) | **ON** | Keeps the desktop unlocked while RPC is connected. Note: protection ends the moment RPC drops. |
| **Lock on Boot** | ON | OFF (for cooks) | So you don't have to PIN-unlock after reboot/reflash. |

> **Critical understanding:** "Prevent Auto Lock with USB/RPC" only prevents *new* lock events while RPC is alive. If RPC drops (USB CDC idle, JS crash, etc.) the device resumes its normal auto-lock behavior. **"Allow USB RPC while locked" only enables RPC ops like storage_* — it does NOT enable `app_start` while the desktop lock scene is active.** `app_start` over RPC against a locked desktop returns `ERROR_APP_SYSTEM_LOCKED` regardless of that toggle, because the desktop lockscreen is itself treated as a running app by the loader.

## The actual programmatic unlock

**Send a single `flipper_gui_send_input(UP, SHORT)`** before any `app_start` when the desktop is locked. Momentum's lock scene treats `UP` as the unlock action (the "Press UP to unlock!" prompt). This works even if "Unlock prompt" is disabled (it's just the visual cue that's hidden).

```
1. flipper_app_lock_status                # returns LOCKED?
2. flipper_gui_send_input("UP", "SHORT")  # unlocks
3. flipper_app_lock_status                # confirm unlocked
4. flipper_app_start(...)                 # now works
```

This is **the** path. BACKx3 / OK / RIGHT do not work on default Momentum.

## Source

- [Momentum Lockscreen wiki](https://github.com/Next-Flip/Momentum-Firmware/wiki/Lockscreen)
- [GitHub Issue #330 — split BLE / USB RPC-while-locked toggles](https://github.com/Next-Flip/Momentum-Firmware/issues/330)

## Other findings from the same session

- App launch via `flipper_app_start` requires the full **.fap path** on mntm-dev, NOT the appid `"js_app"` nor display name `"JS Runner"`. Correct: `flipper_app_start(name="/ext/apps/assets/js_app.fap", args="/ext/apps_data/mcp_missions/<x>.js")`. This contradicts KIISU_DEEP_KNOWLEDGE.md §1.2 which says either string works — the loader's `strcmp` against `appid`/`name` apparently doesn't match for `js_app` on this firmware. Possible cause: js_app is an external FAP on mntm-dev (lives under `/ext/apps/assets/`) so `loader_start` falls through to the path-based load.
- `storage.fsInfo()` aborts the JS script on call — likely **does not exist** on mntm-dev JS API. KIISU_DEEP_KNOWLEDGE.md §2.8 lists it; reality contradicts.
- `for..in` over a native module object (`require("storage")`) crashes the JS script hard enough to drop USB-CDC RPC entirely. Cause unknown — possibly mJS's iteration over C-bound objects with non-string keys panics. Use explicit `typeof obj.method` probes instead of enumeration.
- The MCP server's `storage_write` tool may return "Write failed" even when the write succeeded — verify by re-reading the file.
