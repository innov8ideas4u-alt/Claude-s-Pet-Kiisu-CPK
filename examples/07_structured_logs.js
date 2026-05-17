// 07 — Mission log conventions
//
// What this shows:
//   The structured log format CPK missions write. Line-oriented key=value,
//   no JSON, with three required fields and a small set of conventional
//   optional ones.
//
// Why it matters:
//   The log file is the ONLY thing the host sees after a mission. If the
//   log is missing fields, malformed, or just absent, the host has nothing
//   to summarise back to the user. The format below is the de-facto
//   contract between mission scripts and CPK's host-side parsers.
//
// Why this format and not JSON:
//   - mJS does NOT have JSON.stringify. You'd have to hand-roll string
//     concat with quote-escaping for every field, and you'd get it
//     wrong eventually. Line-oriented `key=value\n` is dead simple to
//     emit and dead simple to parse (split on \n then on first =).
//   - Streaming-friendly: even a partial log (mission aborted mid-run)
//     is still parseable up to the last newline. JSON would leave you
//     with a truncated object you can't deserialize.
//   - Diff-friendly: a CHANGELOG entry showing two runs of the same
//     mission reads as a normal text diff. JSON would re-indent on every
//     change.
//
// How to run:
//   "Push /ext/apps_data/mcp_missions/structured_logs_demo.js and run it
//    with flipper_js_run; show me the log content."
//
// What you'll see in /ext/apps_data/mcp_logs/structured_logs_demo.log:
//
//   mission=structured_logs_demo
//   step=loaded
//   step=midway
//   samples=10
//   captured_signal=fake-433.92MHz
//   finished=true
//
// mJS gotchas you MUST know before writing any of these scripts (also in
// docs/for_ai_contributors.md, restated here for visibility):
//   - NO `Date` / `Date.now()`. For wall-clock timing, have the host
//     record start/stop timestamps around the call. Elapsed-time fields
//     like `elapsed_ms=` go in the HOST-SIDE summary, not the JS log.
//   - NO implicit number-to-string coercion. Every numeric value you
//     concatenate into a string needs an explicit `.toString()`.
//   - NO try/catch. A thrown exception aborts the script.
//   - `delay(ms)` is a global, not a require. `print()` likewise.

let storage = require("storage");
let notification = require("notification");

let MISSION_NAME = "structured_logs_demo";
let LOG_PATH = "/ext/apps_data/mcp_logs/" + MISSION_NAME + ".log";

let f = storage.openFile(LOG_PATH, "w", "create_always");

// ─── REQUIRED FIELDS ──────────────────────────────────────────────────
//
// `mission=` first line. Used by the host to confirm "this log is for the
// script I just launched, not a stale leftover."
f.write("mission=" + MISSION_NAME + "\n");

// `step=` lines are the breadcrumb trail. Write one whenever the mission
// crosses a meaningful phase boundary - "loaded", "frequency_set",
// "scan_started", "scan_done", etc. If the script aborts (mJS has no
// try/catch), the last step= line tells you HOW FAR it got.
f.write("step=loaded\n");

// ── mission body (synthetic for this demo) ─────────────────────────────
//
// In a real mission you'd do hardware work here. This demo writes a
// fake counter to show how numeric values are concatenated into log
// lines (note the explicit `.toString()` — mJS will NOT coerce for you).
// Keep total script size under ~800 chars where possible
// (see docs/for_ai_contributors.md).

f.write("step=midway\n");

let samples = 0;
for (let i = 0; i < 10; i++) {
    samples += 1;
}

// ── OPTIONAL CONVENTIONAL FIELDS ───────────────────────────────────────
//
// These aren't required, but the host-side log parser (see
// missions/llmdr/missions/library.py for the reference parser)
// recognises them and surfaces them in the summary it shows the user.
//
//   captured_signal=<freq + brief desc>   Sub-GHz / IR / NFC missions
//   rssi_dbm=<integer>                    RF strength missions
//   samples=<integer>                     RSSI sweeps, scan loops
//   pin_<n>=<state>                       GPIO sweeps
//   ble_device=<name|MAC>                 BLE scan results (one line per dev)
//   error=<short message>                 Soft-fail without aborting
//
// Match the syntax exactly - lowercase keys, snake_case, no spaces
// around the `=`. Custom keys are fine, but try to follow the same shape.

f.write("samples=" + samples.toString() + "\n");
f.write("captured_signal=fake-433.92MHz\n");

// `finished=true` is the canary. The host-side parser uses the presence
// of this line as the signal that the mission ran to completion. Its
// ABSENCE means the script aborted somewhere above - which is your only
// debugging signal in mJS (no try/catch, remember).
//
// If the mission failed in a structured way (sensor returned nothing,
// signal out of range, etc), you can also write a soft-fail:
//
//     f.write("error=signal_below_threshold\n");
//     f.write("finished=true\n");
//
// "Finished with an error" is different from "aborted mid-script."
// The host can act on the error field; it cannot act on a missing log.

f.write("finished=true\n");
f.close();

// notification.success() wakes the screen AND plays audio. Without it
// the human watching has no idea the mission ran (and gui_send_input
// alone wouldn't wake the screen). On structured soft-fail, use
// notification.error() instead - same effect, different chime.
notification.success();
