# Phase 1 Summary — capability survey cook against AmorPoee (mntm-dev)

## Wall clock

- **Start:** 2026-05-17 00:33 UTC
- **End:** 2026-05-17 ~02:35 UTC
- **Total:** ~2 h 02 min
- **Effective probe time:** maybe 20 minutes — the rest was unblocking lock-screen and RPC-drop infrastructure issues that the spec recipe assumed away

## Counts

| Module | PASS | FAIL | SKIP_UNSAFE | INCONCLUSIVE | NOT ATTEMPTED |
|---|---|---|---|---|---|
| storage | 5 | 0 | 0 | 1 | ~20 |
| notification | 1 | 0 | 0 | 0 | 2 |
| gpio | 0 | 0 | 0 | 0 | all |
| subghz | 0 | 0 | 0 | 0 | all |
| infrared | 0 | 0 | 2 | 0 | 0 |
| blebeacon | 0 | 0 | 0 | 0 | all |
| event_loop | 0 | 0 | 0 | 0 | all |
| gui | 0 | 0 | 0 | 0 | all |
| nfc | 0 | 0 | 0 | 0 | all |
| **TOTAL** | **6** | **0** | **2** | **1** | **~70+** |

Spec budget called for "~50-70 probes." We landed at 6 PASSes + 1 INCONCLUSIVE + 2 SKIP_UNSAFE = 9 graded probes. **The matrix is not the deliverable. The infrastructure findings are.**

## Top 10 surprises

1. **`flipper_app_start("js_app")` and `flipper_app_start("JS Runner")` both return `ERROR_INVALID_PARAMETERS` on mntm-dev.** Only the full `.fap` path works (`/ext/apps/assets/js_app.fap`). KIISU_DEEP_KNOWLEDGE.md §1.2 explicitly says either appid or display name should work — for OFW this is probably right, but for Momentum where the JS Runner is external, it's wrong. The spec recipe got this right; the KB doesn't.

2. **`ERROR_APP_SYSTEM_LOCKED` is the lockscreen masquerading as a running app, not a "system lock."** Per the loader source, the error fires when `loader->app.thread != NULL`. When the desktop is locked, the lockscreen *is* the running app. `flipper_app_exit` returns NOT_RUNNING simultaneously (it only sees user-launched apps, not system scenes), making the state look impossible from the RPC client side. The error name is misleading.

3. **The Momentum unlock combo is a single UP press, not BACK x3 or any combination.** The spec recipe (`OK PRESS+SHORT+RELEASE, BACK PRESS+SHORT+RELEASE, RIGHT PRESS+SHORT+RELEASE`) does nothing on a default Momentum mntm-dev lockscreen. None of those keys progress the lock state. UP does. Even when "Unlock prompt" is disabled (which just hides the visual cue), UP is still the unlock key.

4. **"Allow USB RPC while locked" does NOT permit `app_start` while locked.** Default is OFF and enabling it unblocks the other storage/info RPCs, but app_start remains gated because of finding #2 (lockscreen-as-app). The wiki does not call this out. You always need the UP keypress to dismiss the lockscreen before any app_start can succeed.

5. **"Prevent Auto Lock with USB/RPC" only holds while RPC is alive.** Drop the RPC connection for any reason (USB CDC timeout, JS script crash, host-side reconnect) and the device's normal auto-lock resumes. Within a few seconds the lockscreen scene reactivates, and the cycle (drop → relock → blocked app_start → manual UP) costs ~10 seconds each time. This is the dominant time sink.

6. **mJS reports native function types as `"foreign_ptr"`, not `"function"`.** Any typeof check that looks for `=== "function"` will return false for every module method. Tests need to allow `"foreign_ptr"` or `"function"`.

7. **`storage.fsInfo()` is bound (typeof = foreign_ptr) but calling it aborted the script** with no error written to the log past the previous f.write. Two probes, two confirmed aborts. The fix or workaround is unknown — KB §2.8 says it returns `{totalSpace, freeSpace}`. The most plausible cause is that the returned object's 64-bit number fields crash on access in mJS's 32-bit arithmetic, *but* the abort happened on the assignment line itself in one probe (before any field access). Need an isolated probe with only `typeof s.fsInfo()` to confirm.

8. **`storage_write` MCP tool reports "Write failed" on most long writes (~600+ chars) but the file IS written.** Easy to chase as a transport bug for 30 min before noticing. Always verify with `storage_list` or `storage_read`.

9. **Scripts >~1500 chars (about 20 sequential f.write lines) may never reach their first openFile call.** The log file isn't even created on disk. Hypothesis: the script file itself was truncated by `storage_write` (R5 root cause), and the JS engine's parser crash takes down the CLI's RPC handler. Cook scripts should stay <800 chars. Bigger probes need to be split.

10. **The JS engine crashing on a script parse error sometimes takes USB-CDC RPC fully down** (`transport_connected: true` but `connected: false; rpc_responsive: false`). `flipper_connection_reconnect` recovers. Cost: ~5-10s per occurrence plus the cascade in #5.

## Top 5 things to investigate next

1. **Isolate `storage.fsInfo()` behavior.** A 200-char probe that runs ONLY `let info = s.fsInfo(); f.write("type=" + typeof info + "\n"); f.write("isNull=" + (info === null) + "\n"); f.write("isUndef=" + (info === undefined) + "\n");` — does it crash on the assignment, or does it return something the JS bindings can't stringify? KB §2.8 is the only API source for storage so a contract drift here would invalidate the rest of §2.8 too.

2. **Inspect `loader_do_is_locked()` behavior when desktop is on lockscreen.** Confirm by source inspection that the Momentum lockscreen-as-app hypothesis (finding #2) is correct, and document whether there's a clean RPC path (`desktop_unlock_request`, protobuf tag 67) that the current flipper-mcp tool surface should expose. Adding `flipper_desktop_unlock` to the MCP would eliminate the manual UP press step.

3. **Probe `for..in` over native module objects.** Earlier runs that used `for (let k in storageModule)` crashed the JS engine AND dropped RPC, before I switched to explicit `typeof obj.method`. mJS docs say closures are restricted; iteration over C-bound objects with non-string keys may be similarly restricted. Confirm and document in KB §2.10.

4. **Determine the actual size cutoff where scripts get truncated.** I observed ping (~330 chars, OK) → typeof_small (~360 chars, OK) → storage_min (~430 chars, OK to `step=loaded`) → typeof_storage (~1500 chars, never created log). The cutoff is somewhere between 430 and 1500. Pinning it down lets cook authors size their probes safely.

5. **Confirm whether the `storage_write` MCP-tool failed-but-succeeded behavior** (R5) is in the MCP server response parser or in the firmware. If it's the MCP server, a 1-line fix unblocks all future cooks. Check `D:\Dev\Projects\flipperzero-mcp\src\flipper_mcp\modules\storage\module.py` (per the KB §5.4 reference).

## Top 3 recipe refinements

1. **Replace the "recovery dance" with a single UP press.** The spec recipe step says:
   ```
   gui_send_input(OK, PRESS) + (OK, SHORT) + (OK, RELEASE)
   gui_send_input(BACK, PRESS) + (BACK, SHORT) + (BACK, RELEASE)
   gui_send_input(RIGHT, PRESS) + (RIGHT, SHORT) + (RIGHT, RELEASE)
   ```
   None of those advance the Momentum lockscreen. Replace with:
   ```
   gui_send_input(UP, SHORT)
   ```
   AND make this step a precondition on every `app_start` call, not just a recovery action. Have the cook function check `flipper_app_lock_status` and, if LOCKED, send UP first. The cook spec's "step 1 must be unlocked" needs to BE the unlock step, not just a check that aborts the cook.

2. **Pre-flight the lockscreen settings.** Add a pre-cook step that uses CLI or RPC to read `/int/.momentum/settings` (or wherever Momentum stores them) and confirm `Allow USB RPC while locked = ON` and `Prevent Auto Lock with USB/RPC = ON`. If either is off, halt the cook with a "fix this device setting first" message. Spending 90+ minutes discovering this empirically is the dominant cost.

3. **Size-limit every probe script to ~800 chars and split larger probes.** And ALWAYS verify the script size on disk after `js_push` or `storage_write` (read back the first 100 chars + last 100 chars, confirm both match the expected). The default behavior of "write big script + run + nothing happened" is hard to diagnose live.

## Tools to recommend adding to flipper-mcp

1. **`flipper_desktop_unlock`** — wrap protobuf `desktop_unlock_request` (tag 67 per KB §3.1). Sends the unlock RPC directly without needing a UP-press hack. Should be the canonical way to dismiss a lockscreen.

2. **`flipper_storage_stat`** — there's a `storage_stat_request` in protobuf (tag 24/25) but no MCP wrapper. Would let cook scripts verify file size after `storage_write` to detect truncation early.

3. **`js_push_verified`** — a higher-level helper that does `storage_write` → `storage_stat` (size check) → re-read first/last 50 chars → fail-fast if any mismatch. Drops the silent-corruption category of bug entirely.

4. **A "safe launch" helper** that combines: lock-status check → UP-press-if-locked → app_start → wait → log-read → BACK-cleanup. Encapsulates the entire recipe so cook scripts don't have to repeat it.

5. **Connection-health-aware wait helpers** — `js_wait_and_read` exists; add a variant that polls `flipper_connection_health` during the wait and reconnects automatically on drop. The current pattern (sleep N seconds, then try to read) wastes the entire sleep when the device drops at second 1.

## Concrete recommendation: Phase 2 + 3

**Defer Phase 2 (stress test) and Phase 3 (live KB verification) until at least these are done:**

1. Recipe refinement #1 (UP-press for unlock) is in the spec
2. MCP recommendation #1 (`flipper_desktop_unlock`) is implemented OR a manual confirmation is added that the cook runs entirely in a single unlocked window
3. The `storage_write` truncation issue (R5/R6) is fixed in the MCP server OR `js_push` is hardened to verify writes

Without these, Phase 2/3 will spend the same 80% of their wall clock on lock-screen recovery and silent script corruption that Phase 1 did. The remaining 20% wouldn't be enough to produce a useful matrix.

**If those three are done, Phase 2 + 3 in one combined session should be feasible in ~90 minutes** — most modules have <10 functions and the matrix mostly populates from typeof + one happy-path call each.

## What was actually useful here

Even though the function matrix is mostly empty, this cook produced documentation that materially de-risks every future cook against this device:

- `D:\Dev\Projects\flipperzero-mcp\docs\SETUP_REQUIREMENTS_mntm-dev.md` — the lockscreen settings and the UP-unlock path
- `D:\Dev\scratch\cc_capability_survey\phase1_js_modules.md` — the six recipe contradictions (R1-R6)
- This file — the surprises and the prioritized investigation list

If the goal of Phase 1 was "what do we need to know to do future cooks well," that's now answered. If the goal was "is every JS function in §2 working," that's still mostly TBD.

## Final recommendation

**Do not re-fire Phase 1 as written.** Either:
- (a) Fix the infrastructure issues (UP-unlock in recipe, fix storage_write truncation in MCP, add flipper_desktop_unlock) and run an abridged "Phase 1.5" that does the full matrix in one short session, OR
- (b) Accept that the per-function matrix isn't worth the cost and treat KB §2 as authoritative going forward, falling back to live probing only for specific failures you hit during real work.

I'd recommend (a) — the infrastructure fixes are small and unblock everything else, and once they're in, the matrix populates fast.
