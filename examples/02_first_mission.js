// 02 — Your first useful mission
//
// What this shows:
//   A complete, runnable JS mission that reads device info on the Flipper
//   and logs the result back to the host. About as small as a CPK mission
//   gets while still being non-trivial.
//
// Why it matters:
//   Every CPK mission follows the same five-part shape:
//     1. require() the mJS modules you need
//     2. open a log file
//     3. do your work
//     4. write `finished=true` to the log
//     5. notification.success() so the human can see/hear the device ran
//   Once you can read this script and understand each part, you can write
//   your own.
//
// How to run (from Claude or cc):
//   "Push /ext/apps_data/mcp_missions/first_mission.js then run it."
//   CPK will use storage_write to push the file, then flipper_js_run to
//   launch and clean up.
//
// Host-side equivalent:
//   For a "do something useful, return a structured report" mission that
//   doesn't need a JS payload on the device, see
//   `missions/llmdr/missions/storage_health_check.py` — pure host-side,
//   async, returns a dataclass with .summary(). That's the reference impl
//   for host-side missions.
//
// What you'll see / hear:
//   Screen wakes, short success chime, log file at
//   /ext/apps_data/mcp_logs/first_mission.log with three lines.
//
// Constraints to remember (full list in docs/for_ai_contributors.md):
//   - mJS has NO try/catch. If a call throws, the script aborts and you'll
//     see no `finished=true` line — that's how you debug.
//   - mJS has NO `Date`. No `Date.now()`, no `new Date()`. For wall-clock
//     timing, have the host record start/stop timestamps around the call.
//   - mJS has NO implicit number-to-string coercion. Every number you
//     concatenate into a log line needs an explicit `.toString()`. The
//     existing missions in `missions/llmdr/missions/library.py` all do
//     this — read them for reference.
//   - Keep total script size under ~800 chars where possible. Large scripts
//     (~1500+) crash the JS engine and can drop USB-CDC.
//   - storage.fsInfo() is broken on mntm-dev — use host-side `storage_info`
//     instead. We don't call it here, but don't try.

let storage = require("storage");
let notification = require("notification");

// Log path convention: /ext/apps_data/mcp_logs/<mission_name>.log
// CPK's flipper_js_run tool auto-infers this from the script path if you
// use /mcp_missions/<stem>.js → /mcp_logs/<stem>.log.
let LOG_PATH = "/ext/apps_data/mcp_logs/first_mission.log";

let f = storage.openFile(LOG_PATH, "w", "create_always");

// Step marker: writing this first means even an abort partway through
// leaves SOMETHING in the log to debug from.
f.write("mission=first_mission\n");
f.write("step=loaded\n");

// === mission body ===
// We're keeping the body trivial: write a small counter loop that proves
// the script ran past `loaded`. That's it — no hardware access, no apps,
// just storage + notification. For richer device info (battery, firmware
// version, free SD space), prefer the host-side `systeminfo_get` and
// `storage_info` MCP tools.
//
// If you want to extend this: add more f.write() lines below before the
// `finished=true` marker. Anything you write here lands in the log.
// Numeric values need `.toString()` — see PING_JS / RF_RSSI_LOG_JS in
// `missions/llmdr/missions/library.py` for reference patterns.

let counter = 0;
for (let i = 0; i < 5; i++) {
    counter += 1;
}
f.write("counter=" + counter.toString() + "\n");

// Required final marker. The host parses logs by looking for this line —
// if it's missing, the mission "failed" (script aborted somewhere above).
f.write("finished=true\n");
f.close();

// notification.success() wakes the screen + plays the success chime.
// gui_send_input button presses do NOT wake the backlight, but this does.
// For a classroom demo where students need to SEE the Flipper do
// something, this line is non-negotiable.
notification.success();
