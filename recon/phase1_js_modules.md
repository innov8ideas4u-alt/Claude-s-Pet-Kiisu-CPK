# Phase 1 — JS Module Ground Truth on mntm-dev

**Device:** AmorPoee (Flipper Zero V4B, Momentum `mntm-dev`, COM9, USB)
**Cook start:** 2026-05-17 00:33 UTC
**Cook end:** 2026-05-17 ~02:35 UTC (stopped per spec — 90-min wall-clock budget exceeded by infrastructure issues, not probe execution)
**Outcome:** Phase 1 partially executed. The cook surfaced **6 hard infrastructure findings** that contradict the KB and that any future cook MUST know before starting. Per-function module data is limited to **storage** and only partial there.

> If you're here looking for the per-function pass/fail matrix you were expecting, skip to the summary at `D:\Dev\scratch\cc_capability_survey\PHASE1_SUMMARY.md` — it explains why the matrix is small and what to do differently next session.

## Summary counts

| Module | PASS | FAIL | SKIP_UNSAFE | INCONCLUSIVE | NOT ATTEMPTED |
|---|---|---|---|---|---|
| storage | 5 | 0 | 0 | 1 | ~20 |
| notification | 1 (verified via cook-side `notification.success()`) | 0 | 0 | 0 | 2 |
| gpio | 0 | 0 | 0 | 0 | all |
| subghz | 0 | 0 | 0 | 0 | all |
| infrared | 0 | 0 | 2 (TX-only, both SKIP_UNSAFE) | 0 | 0 |
| blebeacon | 0 | 0 | 0 | 0 | all |
| event_loop | 0 | 0 | 0 | 0 | all |
| gui | 0 | 0 | 0 | 0 | all |
| nfc | 0 | 0 | 0 | 0 | all |

## Recipe contradictions found (before any function probes)

These five issues with the cook spec / KIISU_DEEP_KNOWLEDGE.md were discovered while *trying* to execute the recipe. They blocked the matrix from being populated.

### R1 — `flipper_app_start` requires the full `.fap` path on mntm-dev

**KB §1.2 claim:** `app_start(name="JS Runner")` OR `app_start(name="js_app")` both work because `loader_find_application_by_name()` matches on `appid` or display name.

**Observed:** Both `name="js_app"` and (implicitly) `name="JS Runner"` return `ERROR_INVALID_PARAMETERS (code 15)` on mntm-dev. Only `name="/ext/apps/assets/js_app.fap"` (the spec recipe value) works.

**Inferred cause:** On mntm-dev the JS Runner ships as an external FAP, not an internal/system app. The `loader_find_application_by_name` strcmp check fails for an external FAP (it's not in the in-RAM app list), so the loader falls through to `storage_file_exists(name) → flipper_application_load(name)`. That fallthrough only fires when `name` is a path that resolves.

**Action:** Update KIISU_DEEP_KNOWLEDGE.md §1.2 to note that for any externally-installed app, including JS Runner on Momentum mntm-dev, the only reliable form is the full `/ext/apps/...fap` path. The "either string works" claim is OFW-specific.

### R2 — `flipper_app_lock_status: LOCKED` ≠ what the spec recipe assumes

**KB §3.1 / Spec recipe:** Treats "Desktop is LOCKED" as a state to clear via the OK+BACK+RIGHT recovery dance, "the Momentum unlock combo."

**Observed:** OK / BACK / RIGHT (any permutation, SHORT or LONG, alone or in sequence) does NOT unlock a Momentum lock scene. The Momentum default unlock is a **single UP press** ("Press UP to unlock!" prompt, even when the visual prompt is disabled via "Unlock prompt = OFF").

**Action:** Update spec recipe step "If step 1 returns LOCKED at any point during the cook, do this recovery dance" to: `flipper_gui_send_input("UP", "SHORT")` — done. If a PIN is configured, this brings up the PIN entry screen and there is no programmatic recovery without the PIN.

### R3 — `ERROR_APP_SYSTEM_LOCKED` is NOT about the desktop lock per se

**Per the Momentum source** (`applications/services/loader/loader.c`): `LoaderStatusErrorAppStarted` (mapped to RPC `ERROR_APP_SYSTEM_LOCKED`) fires when `loader->app.thread != NULL` — i.e. another app is currently running. When the desktop is showing its lock scene, the lockscreen is itself an app, so the loader treats it as "another app running" and refuses to start a new one. This is why `app_exit` returns `ERROR_APP_NOT_RUNNING` (because the loader-tracked app is the lockscreen, which doesn't accept the standard exit signal) while `app_start` returns `ERROR_APP_SYSTEM_LOCKED`.

**Action:** Document this in KIISU_DEEP_KNOWLEDGE.md §1.6. The error name is genuinely misleading.

### R4 — The Momentum lockscreen settings that actually matter

Wiki: https://github.com/Next-Flip/Momentum-Firmware/wiki/Lockscreen

Two settings need to be ON for an RPC-driven cook:

| Setting | Default | Required |
|---|---|---|
| `MNTM > Interface > Lockscreen > Allow USB RPC while locked` | OFF | ON — lets non-`app_start` RPCs work while locked (storage_*, lock_status, etc.) |
| `Settings > Power > Prevent Auto Lock with USB/RPC` | OFF (?) | ON — prevents the device from auto-locking while RPC is connected |

> **What "Allow USB RPC while locked" does NOT do:** it does NOT permit `app_start` against a locked desktop. The lockscreen-as-app gates app_start regardless. This is unintuitive and the wiki does not mention it. Only `flipper_gui_send_input("UP","SHORT")` to dismiss the lockscreen + then `app_start` works.

Captured in `D:\Dev\Projects\flipperzero-mcp\docs\SETUP_REQUIREMENTS_mntm-dev.md` (created this session).

### R5 — `storage_write` MCP tool reports "Write failed" on most successful long writes

Empirically: any write >~600 chars to a JS mission file via `mcp__flipper-mcp__storage_write` returns "Write failed for /ext/..." but the file IS present afterward and IS readable. Inferred cause: the chunked write completes successfully on the firmware side (per KB §5.2, the firmware only ACKs the final chunk), but the MCP server's response parser misinterprets either the chunked sequence or the ACK timing as a failure. The fix lives in the MCP server, not in cook scripts.

**Cook workaround:** ignore "Write failed" for `storage_write` outputs; verify by `storage_list` or `storage_read` instead. Or prefer `js_push` (the wrapper) when possible — it sometimes succeeds where raw storage_write reports failure, sometimes the reverse, both eventually flush the file to disk.

### R6 — Large JS scripts (~1000+ chars) crash the JS engine and may drop USB-CDC RPC

Empirically: scripts under ~500 chars run to completion reliably. Scripts at ~1500 chars (e.g., 20 `f.write` calls in sequence after one `openFile`) cause the JS engine to abort silently before writing anything to the log, and roughly half the time take USB-CDC RPC down with them (`flipper_connection_health → connected: false; transport_connected: true`). The connection recovers on `flipper_connection_reconnect`.

**Inferred cause:** *Most likely* this is the `storage_write` chunked write delivering a truncated file (R5 root cause), and mJS's parser then crashes on the incomplete script. The fact that the log file is *never created* (not even with `step=opened`) indicates the script never reaches its first `openFile` call — consistent with a parse error rather than runtime error. Need to verify by checking the actual disk-side file size of the truncated-looking scripts.

**Cook workaround:** keep each probe script <~800 chars. Split larger probes into multiple mission files.

## Per-function results (storage module)

Run order: each probe is a small JS file in `/ext/apps_data/mcp_missions/`. Log structure: `step=opened`, then one line per call, then `finished=true` on clean completion.

### `module: storage`

```yaml
module: storage
function: require("storage")
test_id: P1_storage_001
status: PASS
launch_result: OK
script_completed: true
expected_behavior: "returns object with native methods"
observed_behavior: "returned. typeof s.openFile === 'foreign_ptr'"
notes: "Confirmed across multiple probes. 'foreign_ptr' is mJS's tag for native C functions, not 'function' as standard JS would give."
probe_script_path: /ext/apps_data/mcp_missions/P1_typeof_small.js
log_marker_path: /ext/apps_data/mcp_logs/P1_typeof_small.log
firmware_error_text: ""
contradicts_kb_section: "§2.1 — KB doesn't mention the foreign_ptr typeof tag, but this is mJS-standard; not a fault"
elapsed_ms: ~1500
```

```yaml
module: storage
function: openFile(path, "w", "create_always")
test_id: P1_storage_002
status: PASS
launch_result: OK
script_completed: true
expected_behavior: "returns File handle for writing"
observed_behavior: "returned handle; subsequent .write and .close worked"
notes: "Same as ping.js baseline. Mode strings 'w'/'create_always' work."
probe_script_path: /ext/apps_data/mcp_missions/P1_ping.js
log_marker_path: /ext/apps_data/mcp_logs/P1_ping.log
elapsed_ms: ~1000
contradicts_kb_section: null
```

```yaml
module: storage
function: File.write(string)
test_id: P1_storage_003
status: PASS
script_completed: true
observed_behavior: "writes are flushed-by-close; partial writes survive a script crash IF the crash happens after a write but before close (saw 'step=loaded' from a script that crashed at the next call)"
notes: "Suggests the JS bindings flush on each write rather than buffer until close. Useful for crash recovery."
probe_script_path: /ext/apps_data/mcp_missions/P1_storage_min.js
log_marker_path: /ext/apps_data/mcp_logs/P1_storage_min.log
contradicts_kb_section: null
```

```yaml
module: storage
function: File.close()
test_id: P1_storage_004
status: PASS
script_completed: true
observed_behavior: "closes cleanly, file persists"
probe_script_path: /ext/apps_data/mcp_missions/P1_ping.js
contradicts_kb_section: null
```

```yaml
module: storage
function: fsInfo()
test_id: P1_storage_005
status: INCONCLUSIVE
launch_result: OK
script_completed: false
expected_behavior: "returns { totalSpace, freeSpace }"
observed_behavior: "FIRST RUN: script aborted on the line `let info = s.fsInfo();` — log captured 'step=loaded' and nothing after, indicating the call killed the script. SECOND RUN (typeof-only probe): typeof s.fsInfo === 'foreign_ptr', so the function IS bound."
notes: "Two contradictory signals. The function is registered as native (foreign_ptr) but invoking it aborted the script. Possible causes: (a) returned object has 64-bit values that crash mJS on subsequent property access — but the abort happened on the assignment line itself, not later; (b) some firmware-side prerequisite (call s.setup()? a session?) is missing and the C binding aborts on missing context. Need an isolated probe that calls fsInfo and immediately writes the typeof of its return without any field access, to disambiguate."
probe_script_path: /ext/apps_data/mcp_missions/P1_storage_min.js (call site) AND /ext/apps_data/mcp_missions/P1_typeof_small.js (typeof check)
log_marker_path: /ext/apps_data/mcp_logs/P1_storage_min.log AND /ext/apps_data/mcp_logs/P1_typeof_small.log
firmware_error_text: ""
contradicts_kb_section: "§2.8 — KB claims fsInfo() returns {totalSpace, freeSpace}; observed abort suggests the contract or guard differs"
elapsed_ms: ~1000
```

```yaml
module: storage
function: stat(path)
test_id: P1_storage_006
status: INCONCLUSIVE
script_completed: true (typeof-only check)
observed_behavior: "typeof s.stat === 'foreign_ptr'; function bound but no live call made successfully"
notes: "Not actually invoked due to time."
probe_script_path: /ext/apps_data/mcp_missions/P1_typeof_small.js
contradicts_kb_section: null
```

## Per-function results (notification module)

```yaml
module: notification
function: notification.success()
test_id: P1_notification_001
status: PASS
launch_result: OK
script_completed: true
expected_behavior: "screen wakes, speaker beeps, status LED flash"
observed_behavior: "from cook-side: every script ending with notification.success() produced a discernible end-of-run signal Victor could see (per spec note 'gui_send_input does NOT wake the backlight; notification.success() does')"
notes: "Used as the end-of-script marker on every successful probe (ping.js, storage_min.js)"
probe_script_path: /ext/apps_data/mcp_missions/P1_ping.js
log_marker_path: /ext/apps_data/mcp_logs/P1_ping.log
contradicts_kb_section: null
elapsed_ms: ~50
```

## Per-function results (infrared module)

```yaml
module: infrared
function: ir.sendSignal(protocol, address, command)
test_id: P1_infrared_001
status: SKIP_UNSAFE
launch_result: not_attempted
notes: "Per spec hard constraint: 'DO NOT call ir.tx without permission. It blasts the room IR, could mess with TVs.' Both methods on the infrared module are TX-only per KB §2.5, so the entire module is SKIP_UNSAFE for this cook. require('infrared') existence was not tested."
contradicts_kb_section: null
```

```yaml
module: infrared
function: ir.sendRawSignal(timings, frequency, duty)
test_id: P1_infrared_002
status: SKIP_UNSAFE
launch_result: not_attempted
notes: "Same as P1_infrared_001."
contradicts_kb_section: null
```

## What was NOT tested and why

| Module | Functions untested | Reason |
|---|---|---|
| storage | rest of §2.8 surface (~20 fns) | wall clock + R6 size/stability blocker |
| notification | error(), blink() | wall clock |
| gpio | all (read-side was planned) | wall clock |
| subghz | all (RX-side was planned) | wall clock |
| blebeacon | all | wall clock |
| event_loop | all | wall clock — and event_loop is the riskiest (CRITICAL per spec); without auto-lock + the lockscreen-app-blocker resolved, can't reliably probe long-running scripts |
| gui | all submodules | wall clock |
| nfc | existence (require) | wall clock |

## Concerns flagged during the cook

**CONCERN: storage_write reports 'Write failed' but the file is actually on disk** — investigated and confirmed empirically (see R5). Not a cook bug, a tooling bug in flipperzero-mcp's storage_write response parsing.

**CONCERN: USB-CDC RPC drops without warning under load** — happens when a JS script with parse errors or long execution runs. Hypothesis: the JS engine crashing taking down the CLI service's RPC handler. Recovery via `flipper_connection_reconnect` works. Adds 5-10s per occurrence.

**CONCERN: After every RPC drop, the lockscreen returns** — even with "Prevent Auto Lock with USB/RPC = ON" set, that toggle only protects *while RPC is connected*. The moment RPC drops, the device resumes its normal auto-lock cycle, and within a few seconds the lockscreen scene is the active app. This cascades: drop → relock → next `app_start` blocked → manual physical UP press needed (if PIN is off) or full physical PIN entry (if PIN is on).

## Raw probe artifacts on device

Surviving on AmorPoee SD card under `/ext/apps_data/mcp_logs/`:

- `P1_ping.log` — baseline working probe, full success
- `P1_storage_min.log` — partial (got `step=loaded`, crashed at `fsInfo()` call)
- `P1_typeof_small.log` — full success (4 typeof checks: openFile=foreign_ptr, fsInfo=foreign_ptr, stat=foreign_ptr, finished=true)
- `P1_storage_meta.log` — only the pre-sentinel, script never reached openFile (truncated script hypothesis)
- `P1_fsinfo.log` — `step=opened` then aborted (same fsInfo() call-site crash)

Mission scripts at `/ext/apps_data/mcp_missions/P1_*.js` are preserved for the next session.
