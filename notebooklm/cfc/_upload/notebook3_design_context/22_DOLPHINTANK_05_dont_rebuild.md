# CPK DON'T-REBUILD — Things Already Shipped & Validated

> 05-dont-rebuild wins on **"have we built X already?"**
> If a future Claude is about to "design" something listed here, STOP and use what exists.
> If you find yourself thinking "I should write a helper for this" — search this file first.

---

## Mission framework primitives (DO NOT RE-DERIVE)

### `flipper_js_run` (Day 4, commit `57fefff`)

**Location:** `flipper_mcp/modules/app_lifecycle/module.py` (AppLifecycleModule v0.4.0)
**What it does:** Wraps the validated 5-step recipe (lock-check → unlock → `app_start("/ext/apps/assets/js_app.fap", script_path)` → wait → BACK → optional log-read) into one MCP call.
**Don't:** Re-derive the recipe inline in mission code. **Do:** Call `flipper_js_run(script_path)`.

### `flipper_gui_send_input` (Day 3)

**Location:** `flipper_mcp/modules/app_lifecycle/module.py`
**What it does:** Emits the full PRESS→SHORT→RELEASE triplet by default. `single_event=True` for advanced cases.
**Don't:** Send three separate `gui_send_input_event` calls. **Do:** One call, default behavior.

### `flipper_desktop_unlock` and `flipper_desktop_is_locked` (Day 3)

**Location:** `flipper_mcp/modules/app_lifecycle/module.py`
**What it does:** Direct RPC for desktop lock state (NOT the misleading `app_lock_status` which is actually the app-loader mutex).
**Don't:** Use `flipper_app_lock_status` to detect "is the desktop locked" — that flags LOCKED whenever any app is running. **Do:** Use `flipper_desktop_is_locked` for actual lock state.

### `storage_write` chunked-ACK pattern (Day 4, commit `34c0db7`)

**Location:** `flipper_mcp/modules/storage/module.py`
**What it does:** Sends all chunks back-to-back with `has_next=True`; reads one ACK at the end. Empirically validated up to 3721+ chars.
**Don't:** Implement chunked-write with per-chunk ACK reads. **Do:** Use `storage_write` as-is; it works.

---

## JS mission patterns (DO NOT RE-DERIVE)

### The standard mission script template

Lives at `examples/03_mission_template.js`. Every JS mission starts from this scaffold:

```javascript
let storage = require("storage");
let notification = require("notification");
let LOG_PATH = "/ext/apps_data/mcp_logs/<your_mission>.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("step=loaded\n");

// === mission body ===

f.write("finished=true\n");
f.close();
notification.success();
```

**Don't:** Reinvent the log pattern. **Do:** Copy the template, fill in the body.

### `notification.success()` wakes the backlight

Empirically validated: `gui_send_input` does NOT wake the backlight (RPC bypasses power-mgmt code path). `notification.success()` does. For visible/audible classroom demos, every mission must end with this.

**Don't:** Wonder why the screen isn't waking when missions complete. **Do:** Include `notification.success()` at end of every visible mission.

---

## mJS gotchas (DO NOT RE-DERIVE)

The full cheat sheet lives at `examples/09_mjs_cheat_sheet.md`. Top quick-references:

- **No `Date`, no `try/catch`, no JSON.stringify, no Promise/async/await**
- **`.toString()` is mandatory** on every numeric→string concat
- **Missing `finished=true` in the log is the signal** that the script threw mid-run
- **`require("gpio")` fails on mntm-dev** (F1, open)
- **`require("nfc")` fails on mntm-dev** (F4, open)
- **`storage.fsInfo()` aborts the calling script** on mntm-dev (use host-side `storage_info` instead)

**Don't:** Hit each of these the hard way. **Do:** Read `09_mjs_cheat_sheet.md` before writing a JS mission.

---

## Empirical hardware facts (DO NOT RE-DERIVE)

### Momentum desktop key-map (validated Day 3)

| Key | Press from desktop opens |
|---|---|
| UP | Momentum menu |
| DOWN | File Browser |
| LEFT | Clock |
| RIGHT | Passport (the angry dolphin) |
| OK | Main menu / app list |
| BACK | No-op on desktop; exits in apps |

### Sub-GHz RX recipe (validated Day 7)

```javascript
let subghz = require("subghz");
subghz.setup();
subghz.setFrequency(freq_hz);   // returns actual synthesized freq (PLL granularity)
subghz.setRx();
delay(ms);
let rssi = subghz.getRssi();    // float, fractional on 433.92 only
subghz.setIdle();
subghz.end();
```

`subghz.stop()` does NOT exist (cc tried Day 6, KB was wrong). Use `setIdle()` then `end()`.

### What modules work in JS on mntm-dev

✅ `storage`, `notification`, `subghz`, `flipper` (the global), `event_loop`
❌ `gpio` (F1), `nfc` (F4), `bluetooth` (no RX path; only `blebeacon` exists, TX-only)
🟡 `infrared` (TX-only verified; RX-side not yet probed — handle as SKIP_UNSAFE for now)

---

## Documentation that exists (DO NOT REWRITE)

If you're about to write a doc about CPK, check whether it exists first:

- **For external users:** `README.md`, `SETUP.md`, `CONTRIBUTING.md`, `ROADMAP.md`, `CREDITS.md`
- **For AI contributors:** `docs/for_ai_contributors.md` (the must-read first), `docs/AI_KNOWLEDGE_BASE.md` (the 600-line deep dive)
- **For firmware-level questions:** `docs/KIISU_DEEP_KNOWLEDGE.md` (the 1596-line authoritative reference)
- **For mission-writing:** `docs/MISSIONS_COOKBOOK.md`, `docs/MORNING_KIT.md`, `examples/01_*` through `examples/09_*`
- **For setup edge cases:** `docs/SETUP_REQUIREMENTS_mntm-dev.md`, `docs/claude_setup.md`
- **For architectural reasoning:** `docs/architecture.md` + every `docs/decisions/DAY*.md`

If your new doc would substantially duplicate any of these, update the existing one instead.

---

## Test infrastructure that exists

- `tests/missions/test_storage_health_check.py` — 11 unit tests for the storage health mission, mocked FlipperClient pattern
- The full test suite lives under `tests/` and runs with `pytest` from CPK's venv
- **Note:** Tests outside CPK's venv fail due to `missions/llmdr/missions/__init__.py` eager-import (flagged Day 5.5, still open). Run tests inside CPK's venv.

---

## Documentation that is INTENTIONALLY duplicated

Some content appears in multiple places on purpose:

- The mission script template is in `03_mission_template.js` AND `for_ai_contributors.md` AND `09_mjs_cheat_sheet.md`. Three places because different audiences encounter it.
- The launch+cleanup recipe is in `DAY3_DESKTOP_RPC_AND_POLISH.md` AND `for_ai_contributors.md` AND `AI_KNOWLEDGE_BASE.md`. Same reason.

**Don't:** Try to "DRY" these — the duplication is deliberate.

---

## What this file is for

If you're a Claude (any flavor) reading this in a future session: this file is your "stop and check before starting" reference. Most "let me design X" thoughts have a "X already exists at Y" answer somewhere in here. When in doubt, search the file by topic before writing new code.
