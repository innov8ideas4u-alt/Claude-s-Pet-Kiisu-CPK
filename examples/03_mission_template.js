// 03 — Mission template (copy this, then edit)
//
// What this shows:
//   The canonical scaffolding every CPK mission should follow. No working
//   logic — just `// FILL THIS IN` markers where your code goes.
//
// Why it matters:
//   Mission scripts run in mJS, an embedded JS dialect with sharp edges.
//   Following this template avoids the most common ways to lose 20 minutes:
//   silent aborts, missing logs, the screen never waking, etc.
//
// How to use:
//   1. Copy this file to /ext/apps_data/mcp_missions/<your_name>.js on the
//      Flipper (CPK's storage_write tool does this from host).
//   2. Replace MISSION_NAME and the FILL THIS IN block.
//   3. Launch with `flipper_js_run script_path="/ext/apps_data/mcp_missions/<your_name>.js"`.
//
// Dos and don'ts (cribbed from docs/for_ai_contributors.md):
//
//   DO:
//     - Open the log file FIRST and write `step=loaded` immediately. If
//       anything below this point throws, the host can still see "the
//       script reached load."
//     - End with `f.write("finished=true\n")` then `f.close()` then
//       `notification.success()` (or `.error()` on failure).
//     - Keep total script size under ~800 chars where you can. The JS
//       engine crashes around ~1500+ chars and can take USB-CDC with it.
//     - Use `notification.success()` / `.error()` to wake the screen and
//       play audio. These are the only paths that wake the backlight.
//
//   DON'T:
//     - Use try/catch — mJS doesn't have it. Aborts on throw, period.
//       Your debugging signal is "did the log get the `finished=true`
//       line or not?"
//     - Use `Date.now()` / `new Date()` — mJS has no Date object. For
//       wall-clock timing, have the HOST record start/stop around the
//       call; do not try to compute elapsed_ms inside the script.
//     - Forget `.toString()` on numeric values when concatenating into
//       log lines. mJS does NOT implicitly coerce; `"x=" + 42 + "\n"`
//       throws. Use `"x=" + (42).toString() + "\n"` instead.
//     - Call `storage.fsInfo()` — confirmed broken on mntm-dev. Crashes
//       the script. Use the host-side `storage_info` MCP tool instead.
//     - Skip `notification.success()` — without it the screen never
//       wakes and the human watching has no clue if the mission ran.
//     - Make the cleanup recipe more complicated than "host sends BACK."
//       BACK dismisses success screens, error screens, AND stuck scripts.
//       One press, no branching.

let storage = require("storage");
let notification = require("notification");

// ─── customise these two lines ────────────────────────────────────────
let MISSION_NAME = "FILL_THIS_IN";  // e.g. "subghz_quick_scan"
let LOG_PATH = "/ext/apps_data/mcp_logs/" + MISSION_NAME + ".log";
// ───────────────────────────────────────────────────────────────────────

let f = storage.openFile(LOG_PATH, "w", "create_always");
f.write("mission=" + MISSION_NAME + "\n");
f.write("step=loaded\n");

// ─── mission body ─────────────────────────────────────────────────────
// FILL THIS IN
//
// Examples of what you might do here:
//   - require("subghz") and call subghz.setFrequency(...) / subghz.receive(...)
//   - require("gpio") and read pin states
//   - require("notification") and play a custom pattern
//
// Each piece of work should write a marker line so the host log is
// useful even on partial completion. Remember `.toString()` for numbers:
//
//   f.write("step=frequency_set\n");
//   f.write("rssi_dbm=" + rssi.toString() + "\n");
//
// ───────────────────────────────────────────────────────────────────────

f.write("finished=true\n");
f.close();
notification.success();
