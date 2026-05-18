// Flipper info — read the `flipper` global's device identity surface.
// Pure observation. No hardware access. ~15 lines of actual code.
//
// Pair: missions/llmdr/missions/flipper_info.py
// Spec: cc_day6_morning_kit_spec.md Mission 6 (bonus)
//
// Why this complements device_inventory.py:
//   device_inventory reads identity via protobuf RPC (get_device_info).
//   This mission reads the same fields via the JS-side `flipper` global.
//   Two independent views of the same data — useful for confirming
//   consistency, and a sanity check that the JS Runner is healthy.

let storage = require("storage");
let notification = require("notification");
let flipper = require("flipper");

let LOG_PATH = "/ext/apps_data/mcp_logs/flipper_info.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("mission=flipper_info\n");
f.write("step=loaded\n");
notification.success();

f.write("device_name=" + flipper.getName() + "\n");
f.write("device_model=" + flipper.getModel() + "\n");
f.write("battery_pct=" + flipper.getBatteryCharge().toString() + "\n");
f.write("firmware_vendor=" + flipper.firmwareVendor + "\n");

// jsSdkVersion is an array [major, minor].
let v = flipper.jsSdkVersion;
if (v && v.length >= 2) {
    f.write("js_sdk_major=" + v[0].toString() + "\n");
    f.write("js_sdk_minor=" + v[1].toString() + "\n");
} else {
    f.write("js_sdk_version=unavailable\n");
}

f.write("finished=true\n");
f.close();
notification.success();
