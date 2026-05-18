// BLE passive scan — BEST EFFORT, documented non-support.
//
// Per docs/KIISU_DEEP_KNOWLEDGE.md §2.1, the Momentum mntm-dev JS SDK
// exposes only `blebeacon` (TX/advertising, OUT OF SCOPE for the
// morning kit). There is no `bluetooth` or `ble` RX/scan module bound
// to mJS as of the KB's 2026-05-15 snapshot.
//
// Outcome: log the non-support fact + the reasoning, so morning-Victor
// reads a deliberate result rather than a confusing failure.
//
// Pair: missions/llmdr/missions/ble_passive_scan.py
// Spec: cc_day6_morning_kit_spec.md Mission 4

let storage = require("storage");
let notification = require("notification");

let LOG_PATH = "/ext/apps_data/mcp_logs/ble_passive_scan.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("mission=ble_passive_scan\n");
f.write("step=loaded\n");
notification.success();

f.write("ble_supported=false\n");
f.write("reason=no_rx_module_bound_in_mjs\n");
f.write("available_jsmodules=blebeacon_only\n");
f.write("blebeacon_is_tx=true\n");
f.write("what_we_wanted=passive_scan_with_name_and_rssi_per_device\n");
f.write("workaround=use_external_ble_dongle_or_phone_app\n");

f.write("finished=true\n");
f.close();
notification.success();
