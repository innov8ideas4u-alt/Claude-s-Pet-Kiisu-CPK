// Radio handshake — RX-only sequential probe of every radio subsystem
// the Flipper exposes to JS. Verifies each responds, logs results,
// gracefully closes. NO RF emission of any kind.
//
// Pair: missions/llmdr/missions/radio_handshake.py
// Spec: cc_day6_morning_kit_spec.md Mission 1
//
// mJS gotchas observed:
//   - No try/catch — if any call throws, script aborts and the log is
//     missing `finished=true` (the host's signal that we broke).
//   - No Date — no timing inside JS. Phase markers only.
//   - Explicit .toString() on every numeric concat.

let storage = require("storage");
let notification = require("notification");
let subghz = require("subghz");
let gpio = require("gpio");

let LOG_PATH = "/ext/apps_data/mcp_logs/radio_handshake.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("mission=radio_handshake\n");
f.write("step=loaded\n");

// Announce start — wakes screen + plays chime so morning-Victor knows
// the mission is alive.
notification.success();

// ── Sub-GHz handshake ────────────────────────────────────────────────
// RX-only: setup -> setFrequency(433.92 MHz) -> setRx -> sample RSSI ->
// setIdle. NO setTx, NO transmitFile. This just confirms the radio
// responds to commands and can read ambient noise.
subghz.setup();
subghz.setFrequency(433920000);
subghz.setRx();
delay(200);
let rssi = subghz.getRssi();
subghz.setIdle();
subghz.end();
if (rssi === undefined) {
    f.write("subghz_ok=false\n");
    f.write("rssi_433_92=undefined\n");
} else {
    f.write("subghz_ok=true\n");
    f.write("rssi_433_92=" + rssi.toString() + "\n");
}
f.write("step=subghz_done\n");

// ── GPIO handshake ──────────────────────────────────────────────────
// Iterate pins 2, 4, 5, 6, 7 as plain digital inputs (no pull). Log
// whatever state we see. Don't drive anything.
let pins = [2, 4, 5, 6, 7];
for (let i = 0; i < pins.length; i++) {
    let p = pins[i];
    let g = gpio.get(p);
    if (!g) {
        f.write("gpio_p" + p.toString() + "=getfail\n");
    } else {
        g.init({ direction: "in", inMode: "plain_digital" });
        let state = g.read();
        f.write("gpio_p" + p.toString() + "=" + (state ? "1" : "0") + "\n");
    }
}
f.write("step=gpio_done\n");

// ── Storage handshake ────────────────────────────────────────────────
// Count entries under /ext/apps. Pure read.
let entries = storage.readDirectory("/ext/apps");
let count = entries ? entries.length : 0;
f.write("ext_apps_count=" + count.toString() + "\n");
f.write("step=storage_done\n");

// ── Notification handshake ──────────────────────────────────────────
// Blue blink, short. Visible confirmation the notification subsystem
// is responsive. notification.blink() doesn't return a value to check,
// but if it throws the script aborts (and the log shows no finished).
notification.blink("blue", "short");
f.write("notification_blink_ok=true\n");
f.write("step=notification_done\n");

// ── Skipped modules (documented intentionally) ──────────────────────
f.write("uncertain_modules=infrared,bluetooth\n");

f.write("finished=true\n");
f.close();

// End-of-mission chime. Wakes screen + audio confirmation.
notification.success();
