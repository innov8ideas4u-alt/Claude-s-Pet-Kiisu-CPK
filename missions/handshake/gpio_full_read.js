// GPIO full read — single snapshot of every Flipper user GPIO pin's
// state as a plain digital input. No outputs, no pulses. Configure
// each pin as input (no pull), read the state, log it. Then we're done.
//
// Pair: missions/llmdr/missions/gpio_full_read.py
// Spec: cc_day6_morning_kit_spec.md Mission 3
//
// Pins covered: 2, 3, 4, 5, 6, 7, 10, 12, 13, 14, 15, 16, 17.
// (1, 8, 9, 11, 18 are GND/3V3/5V/etc on the Flipper header, not GPIO.)
//
// Default with no pull means a floating pin reads as noise — that's
// expected. The point is to confirm the GPIO module responds at all
// and to expose which pins have something driving them HIGH or LOW.

let storage = require("storage");
let notification = require("notification");
let gpio = require("gpio");

let LOG_PATH = "/ext/apps_data/mcp_logs/gpio_full_read.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("mission=gpio_full_read\n");
f.write("step=loaded\n");
notification.success();

let pins = [2, 3, 4, 5, 6, 7, 10, 12, 13, 14, 15, 16, 17];
let read_count = 0;

for (let i = 0; i < pins.length; i++) {
    let p = pins[i];
    let g = gpio.get(p);
    if (!g) {
        f.write("gpio_p" + p.toString() + "=getfail\n");
    } else {
        g.init({ direction: "in", inMode: "plain_digital" });
        let state = g.read();
        f.write("gpio_p" + p.toString() + "=" + (state ? "1" : "0") + "\n");
        read_count = read_count + 1;
    }
}

f.write("pins_read=" + read_count.toString() + "\n");
f.write("pins_attempted=" + pins.length.toString() + "\n");
f.write("finished=true\n");
f.close();
notification.success();
