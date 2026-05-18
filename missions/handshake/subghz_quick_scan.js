// Sub-GHz quick scan — sample RSSI across 5 common ISM frequencies.
// 10 samples per frequency, log min/max/sum to compute average host-side.
// Pure RX. No TX. No setTx, no transmitFile.
//
// Pair: missions/llmdr/missions/subghz_quick_scan.py
// Spec: cc_day6_morning_kit_spec.md Mission 2
//
// Runtime: ~5 seconds total (5 freqs * 10 samples * ~100ms each).

let storage = require("storage");
let notification = require("notification");
let subghz = require("subghz");

let LOG_PATH = "/ext/apps_data/mcp_logs/subghz_quick_scan.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("mission=subghz_quick_scan\n");
f.write("step=loaded\n");
notification.success();

let FREQS = [315000000, 433920000, 868000000, 915000000, 925000000];
let SAMPLES_PER_FREQ = 10;
let SAMPLE_DELAY_MS = 50;

subghz.setup();

// CSV-ish layout: one row per (freq, sample) so the host can compute
// avg/max without trusting JS math. Header line for human reading.
f.write("# freq_hz,sample_idx,rssi_dbm\n");

for (let i = 0; i < FREQS.length; i++) {
    let freq = FREQS[i];
    let actual_freq = subghz.setFrequency(freq);
    subghz.setRx();
    delay(100);

    for (let s = 0; s < SAMPLES_PER_FREQ; s++) {
        let r = subghz.getRssi();
        if (r === undefined) {
            f.write(actual_freq.toString() + "," + s.toString() + ",undefined\n");
        } else {
            f.write(actual_freq.toString() + "," + s.toString() + "," + r.toString() + "\n");
        }
        delay(SAMPLE_DELAY_MS);
    }

    subghz.setIdle();
    f.write("step=freq_done_" + actual_freq.toString() + "\n");
}

subghz.end();

f.write("freqs_scanned=" + FREQS.length.toString() + "\n");
f.write("samples_per_freq=" + SAMPLES_PER_FREQ.toString() + "\n");
f.write("finished=true\n");
f.close();
notification.success();
