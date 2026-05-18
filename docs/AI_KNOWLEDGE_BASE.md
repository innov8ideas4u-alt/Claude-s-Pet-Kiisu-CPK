# CPK AI Knowledge Base

> A deep, candid, concrete doc for any future AI agent joining CPK. The goal is to capture **patterns specific to CPK that an AI would otherwise have to re-derive from scratch**.

This is the AI-side counterpart to two other docs:

- `docs/KIISU_DEEP_KNOWLEDGE.md` — for *humans* who need the Flipper/Momentum firmware truth (1596 lines, source-cited).
- `docs/for_ai_contributors.md` — the *quick-start* for AI contributors (~150 lines).

**This doc lives between them.** It assumes you've read the quick-start and can look up firmware specifics in the deep knowledge base. What it gives you is the project's earned intuition: what goes wrong, how it goes wrong, and what the team has already figured out so you don't relearn it on your own time.

If a section makes a claim, it cites a commit, a decision doc, a session report, or a memory file. Claims without citations were cut during the self-edit pass. If you find one that snuck through, flag it.

### How to use this doc

Match your task to the section:

- **A symptom you can't immediately diagnose** → §1. Pick the ladder that matches what you're seeing; walk it in order.
- **A question about how to interact with Victor** → §2. Specifically §2.2 if it's about execution-without-confirmation, §2.6 if it's about pushing back on the spec.
- **Wanting to know how this project's AI agents have been wrong before** → §3. Read it once, calibrate; come back when you're about to do something the doc warns about.
- **Looking for the patterns that actually work across sessions** → §4. The five patterns there are what every cook since Day 5 has been built on.
- **A specific common ask from the human** → §5. Each ladder is the 5-7 steps the project has settled on.
- **Wondering whether something works** → §6. If it's listed there, it isn't validated and you shouldn't claim it works.
- **A piece of project shorthand you don't recognize** → Appendix A glossary.
- **About to touch a file that's load-bearing across the codebase** → Appendix B cross-cutting concerns.

If you read this front-to-back, plan ~30 minutes. If you grep into a specific section, expect ~5 minutes. The doc is structured to be useful at either scale.

### Trust model

This doc was written by cc on 2026-05-17 (Day 6.5 cook), citing decision docs and session reports from Days 1-6. Memory files cited are from before that date. The cook self-report at `D:\Dev\scratch\cc_day6_5_ai_kb_report.md` lists what cc thought might be wrong about the doc — read that report alongside this doc if you find a citation that doesn't match current reality, since "current reality" has likely moved.

---

## Section 1 — How CPK debugging actually works

CPK has a small number of recurring failure shapes. Each one has a diagnostic ladder the project has already walked. When you hit the symptom, walk the ladder in order — don't improvise. The order isn't aesthetic, it's empirical: each step was where the prior session got tripped up.

### 1.1 — `app_start` returns False / non-OK `CommandStatus`

**Symptom:** `flipper_app_start(name, args)` returns a non-OK status. Until Day 2 this collapsed to `False`; now it carries `status_name` (`ERROR_APP_CANT_START`, `ERROR_INVALID_PARAMETERS`, `ERROR_APP_SYSTEM_LOCKED`, etc.) per the `AppRpcResult` refactor in `docs/decisions/DAY2_APP_RPC_AND_INPUT.md` §1.

**Ladder:**

1. **Read `status_name`.** Each value points at a different fix. `ERROR_INVALID_PARAMETERS` = wrong name or path; `ERROR_APP_SYSTEM_LOCKED` = another app is running; `ERROR_APP_CANT_START` = firmware refused to start the app (often FAP not present or wrong type).
2. **For `ERROR_INVALID_PARAMETERS` on `js_app`: use the full FAP path.** On Momentum `mntm-dev`, EXTERNAL FAPs are not registered in the loader's name list. Only `"/ext/apps/assets/js_app.fap"` works — NOT `"js_app"` and NOT `"JS Runner"`. See `docs/decisions/DAY2_APP_RPC_AND_INPUT.md` "Contradictions with KIISU_DEEP_KNOWLEDGE.md §1.2" and the constant `JS_RUNNER_FAP_PATH` in `flipper_mcp/modules/app_lifecycle/module.py:35`.
3. **For `ERROR_APP_SYSTEM_LOCKED`: check the *real* lock state.** `flipper_app_lock_status` is the app-loader mutex — it's LOCKED whenever any app is running, including the lockscreen-as-app. Use `flipper_desktop_is_locked` for the actual lockscreen state. See `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §1.
4. **Call `flipper_app_get_error`.** Returns the firmware's verbose error text from the most recent failure. Often clarifies what `status_name` alone doesn't.
5. **If still stuck:** read `docs/KIISU_DEEP_KNOWLEDGE.md` §1.1–§1.4 for the protobuf wire details (tag 16, `StartRequest`, etc.).

**Negative example — cc-from-firmware-source got this wrong on Day 2:** cc read the firmware loader source (`loader.c`'s `loader_find_application_by_name`) and predicted that either `"js_app"` (the FAM `appid`) or `"JS Runner"` (the FAM `name`) would match by `strcmp`. Both returned `ERROR_INVALID_PARAMETERS` on mntm-dev. The fix was the FAP path. From `docs/decisions/DAY2_APP_RPC_AND_INPUT.md` "Contradictions": *"On `mntm-dev`, EXTERNAL FAPs are not registered in the loader's name-list at boot — only built-in apps (Sub-GHz, NFC, etc.) match by name."* Lesson: firmware source predicts firmware *capability*, not firmware *behavior on a specific build*. Reality wins.

**What you should actually call:** `client.rpc.app_start("/ext/apps/assets/js_app.fap", "/abs/path/to/script.js")`. Constant available at `flipper_mcp/modules/app_lifecycle/module.py:35` as `JS_RUNNER_FAP_PATH`. For built-in apps the older `app_start("Sub-GHz", "")` form still works (built-ins ARE registered by name); the FAP-path rule is specifically about EXTERNAL FAPs like JS Runner. Source authority for the FAP path: it is what the `_js_run` helper calls in the validated recipe, and the live validations on Days 2-4 used this exact string.

**Firmware error codes you'll actually see** (the high-frequency subset of what `AppRpcResult.status_name` can be):

| status_name | What it usually means | First diagnostic |
|-------------|----------------------|------------------|
| `OK` | Call succeeded. | — |
| `ERROR_INVALID_PARAMETERS` | App name/path didn't resolve, or args were wrong shape. | For `js_app`: use the FAP path (see above). |
| `ERROR_APP_SYSTEM_LOCKED` | An app is running (incl. lockscreen-as-app). | Check `flipper_desktop_is_locked` for the *real* lockscreen state. |
| `ERROR_APP_CANT_START` | Firmware refused the launch (FAP missing, wrong type, ROM constraint). | Verify the FAP exists at the path; check `flipper_app_get_error` for verbose text. |
| `ERROR_APP_NOT_RUNNING` | Called `app_exit` or `app_get_error` with no app running. | Not a failure per se — just clean state. |
| `ERROR_STORAGE_NOT_READY` | SD card not mounted or volume busy. | Try `/int` path or re-mount the SD. |
| `ERROR_STORAGE_INVALID_NAME` | Path malformed or not absolute. | Confirm path starts with `/ext/` or `/int/`. |

The full enum is in the protobuf descriptor (`flipper_pb2.CommandStatus`); these are the codes that have shown up in CPK's actual session reports. If you see a code not in this list, `flipper_app_get_error` will usually give you the human-readable text.

### 1.2 — A JS mission's log has no `finished=true`

**Symptom:** the host reads back the log file and the last line is `step=<something>` rather than `finished=true`. The mission aborted somewhere above that step.

**The structural reason:** mJS has no `try/catch` (`docs/KIISU_DEEP_KNOWLEDGE.md` §2.10 table row 1). A thrown call ends the script immediately. The host's only signal that the script broke is the absence of the canonical `finished=true` marker.

**Ladder:**

1. **Read the last `step=` line.** That tells you the phase the script entered before dying. The mission helpers write step markers before each major sub-task (e.g. `step=subghz_done`, `step=gpio_done`) precisely so a partial log narrows the failure.
2. **Check whether mJS's no-coercion rule was violated.** Every numeric concat must use `.toString()` (`docs/for_ai_contributors.md` "mJS Quirks #3", and `examples/09_mjs_cheat_sheet.md` table row 5). `"x=" + 42 + "\n"` throws. This is the #1 cause of "script aborted somewhere after `step=loaded`."
3. **Check for `Date` / `Date.now()` calls.** mJS has no `Date` at all. Same effect — silent abort.
4. **Check whether a JS module call expects an object but got positional args.** GPIO is the trap: `gpio.get(pin).init({direction: "in", inMode: "plain_digital"})`, NOT `gpio.init(pin, "input", "no")` (see `docs/KIISU_DEEP_KNOWLEDGE.md` §2.9).
5. **Check script size.** mJS engine can crash on scripts ~1500+ chars. Smaller scripts are safer. Historically this was tangled with R5 (storage_write truncation, see §1.3); since R5 was fixed in commit `34c0db7`, a 2705-char script ran cleanly per `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` "R6 — RESOLVED (subsumed by R5)".
6. **Try `storage.fsInfo()` removal.** If the script calls `storage.fsInfo()` from JS, it silently aborts on that line on mntm-dev. Confirmed in `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §4. Use the host-side `storage_info` MCP tool.

**Negative example — I shipped a Date.now() draft on Day 5 that would have aborted on first run:** the first draft of `examples/02_first_mission.js` and `examples/07_structured_logs.js` used `Date.now()` to log uptime. Per the Day 5 self-report at `D:\Dev\scratch\cc_day5_examples_report.md`: *"First draft of `02_first_mission.js` and `07_structured_logs.js` used `Date.now()`. After writing, I cross-referenced `missions/llmdr/missions/library.py` and found the explicit comments: 'mJS gotchas: no Date, no try/catch, NO IMPLICIT TYPE COERCION.' Fixed both files."* This was a near-miss — I caught it in the self-edit pass, not at the device. The lesson became `docs/for_ai_contributors.md` "mJS Quirks #1" and `examples/09_mjs_cheat_sheet.md` row 1. Don't trust web-JS instincts.

**Concrete diagnostic snippet (host-side):**

```python
log_text = await client.storage.read(f"/ext/apps_data/mcp_logs/{mission_name}.log")
lines = [l for l in log_text.splitlines() if l.strip()]
if not lines:
    print("script never opened the log file — check require() calls + storage.openFile mode")
elif lines[-1] != "finished=true":
    last_step = next((l for l in reversed(lines) if l.startswith("step=")), "no_steps_logged")
    print(f"script aborted; last marker: {last_step}")
```

That snippet is the same shape `_runner.py`'s `parse_kv_log` uses to surface the "script aborted" warning. When a future mission misbehaves, run it once with `read_log=True` and walk the steps.

### 1.3 — `storage_write` reports failure but the file is partially on disk

**Symptom (pre-fix):** `client.storage.write(path, content)` returned `False`. Reading the file back showed truncated content (~512 bytes for a 613-char input).

**Root cause:** the old `_storage_write_internal` in `flipper_mcp/core/protobuf_rpc.py` chunked content into 512-byte payloads correctly but **waited for an ACK after every chunk**. Per the firmware source quoted in `docs/KIISU_DEEP_KNOWLEDGE.md` §5.2:

```c
// rpc_system_storage_write_process()
send_response = !request->has_next;
```

The firmware sends **zero responses** for intermediate chunks — only one `PB_Main` with `CommandStatus` after the final chunk. The host code that waited 2.5s for the missing intermediate ACK gave up and returned `False`, leaving the partial chunk written.

**Fix:** commit `34c0db7` rewrote the writer to fire all chunks back-to-back with shared `command_id`, `has_next=True` on every chunk except the last, then read exactly one ACK after the final chunk. Live-validated: 109/594/3721-char writes all roundtrip intact per `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` §1.

**Ladder (when something like this recurs):**

1. **Was the response parser actually waiting for an ACK that the firmware doesn't send?** Check `rpc_<subsystem>.c` in the firmware tree (paths in KB §3). The `send_response = !request->has_next` pattern appears across multiple RPCs — chunked operations usually only ACK at the boundary.
2. **Reproduce the partial-write before fixing.** Day 4 confirmed the truncation empirically (`docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` §1 "Empirical reproduction (pre-fix)") before changing code. The fix held because the bug was understood, not guessed.
3. **Mirror the upstream reference client** when one exists. R5 was fixed by mirroring `flipperzero_protobuf_py/flipperzero_protobuf/flipper_storage.py`. New ground-truth firmware-side patterns should follow the same path.

**Negative example — pre-fix CPK code was wrong for months.** The R5 bug had been latent since pre-Day-4. cc identified it during the Day 3 Phase-1 capability survey (R5 in the survey notes). The fact that the bug went undetected that long was a *test gap*: no one had written a long-write integration test. The fix landed in commit `34c0db7`; the lesson is now in the protobuf_rpc.py docstring at `_storage_write_internal`.

**Recognizing R5-shaped bugs in other RPCs:** any RPC that the firmware processes as a streamed sequence of chunks (storage_write, future big-payload writes if added) is at risk for the same ACK-pattern mistake. The check is: read `rpc_<subsystem>.c` upstream, look for `send_response = !request->has_next;` or the equivalent. If you see it, your host code must NOT wait for ACKs on intermediate chunks. The protobuf wire-lock decorator (`_with_wire_lock`) does NOT save you here — it serializes calls, but within a call, intermediate-chunk wait timeouts are still a bug if the firmware never sends them.

### 1.4 — The device "stops responding"

**Symptom:** Claude's next tool call hangs, times out, or returns transport-level errors. From the outside this looks identical regardless of which of four underlying conditions is true. Walking the wrong branch wastes 5-30 minutes.

**The four conditions, by frequency:**

1. **The desktop lockscreen is showing.** `flipper_desktop_is_locked` returns true. Fix: `flipper_desktop_unlock` (no PIN configured) or unlock the hardware physically.
2. **The app-loader is busy** (another app is running). `flipper_app_lock_status` returns true (this includes the lockscreen-as-app — they overlap, see §1.1). Fix: send `BACK` until you're back on the desktop.
3. **JS Runner is stuck on a "Script done" / "Error" screen.** RPC works; the device just hasn't been told to leave the app. Fix: one `flipper_gui_send_input("BACK")` call — BACK is the universal cleanup verb per `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §3.
4. **USB-CDC transport dropped.** `flipper_connection_health` reports `transport_connected=false`. Usually caused by: (a) BadUSB/usbdisk app changed USB mode mid-session, (b) large-JS-script crash (rare since R5 fix), (c) genuine cable/cable-port issue.

**Ladder:**

1. **`flipper_connection_health` first.** If transport is down, the rest of the ladder is moot. Re-plug, re-try.
2. **`flipper_desktop_is_locked`.** If true, unlock. Don't proceed until false.
3. **`flipper_app_lock_status`.** If true and desktop NOT locked, an app is running — send BACK once.
4. **Try the next tool call.** If still failing, the script is likely stuck. One more BACK.
5. **If multiple BACKs don't recover:** `flipper_app_exit` to force-close, then retry.

**Negative example — Claude Desktop's "made-up unlock dance" on Day 3:** before `flipper_desktop_unlock` existed, Claude Desktop tried to dismiss the lockscreen by synthesizing a creative sequence of GUI inputs from training-data intuition. It did not work. Per `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` TL;DR: *"Day 2 left three operational rough edges that cc's capability survey cook (~2hr) surfaced as material gotchas: (1) lockscreen handling used a made-up unlock dance that didn't work."* The fix was to expose protobuf tags 66/67 (`PB_Desktop.IsLockedRequest`, `PB_Desktop.UnlockRequest`) as proper RPC tools. Lesson: when the firmware exposes a direct RPC for a UI operation, find and use it. Synthesizing GUI input is a fallback, not a first move.

**Edge case — PIN-configured device.** `flipper_desktop_unlock` cannot dismiss the lockscreen if the device has a PIN configured; per `flipper_mcp/modules/app_lifecycle/module.py` `_desktop_unlock`, the call returns the firmware's CommandStatus (often `ERROR_*`) and the device stays locked. The fallback documented in the tool's error text is `flipper_gui_send_input(UP, SHORT)` to open the unlock prompt, but the human still has to enter the PIN physically. No RPC route exists for entering the PIN. If your cook hits a PIN-locked device, stop the cook and flag it; don't loop on unlock attempts.

### 1.5 — Synthetic input doesn't register

**Symptom:** `flipper_gui_send_input(key="OK")` returns OK, but the app on the device doesn't respond.

**The two main causes:**

1. **Pre-Day-3 lone-SHORT bug.** Most app scenes ignore a lone `SHORT` event. Real hardware emits the full `PRESS → SHORT → RELEASE` triplet within ~10ms; mJS scenes only treat the triplet as a press. This is now the default behavior of `flipper_gui_send_input` (since Day 3 polish, `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §2). If you see this symptom now, you're probably explicitly passing `single_event=True` somewhere and shouldn't be.
2. **Wrong scene-context.** The desktop keymap (UP/DOWN/LEFT/RIGHT/OK/BACK) is documented in `examples/05_button_navigation.md`. *Inside* an app, keys mean whatever the app's scene wants. `OK` on the desktop opens the main menu; `OK` in Sub-GHz might save a capture; `OK` in JS Runner does nothing useful.

**Ladder:**

1. **Verify you're not passing `single_event=True`.** Default emits the triplet — leave it default.
2. **Verify the device's scene.** A key sent to the wrong scene is silently consumed. `flipper_app_lock_status` tells you an app is running; you'd need other means to know which scene.
3. **Try `BACK` as a recovery.** BACK is universal (§1.4 condition 3). If a sequence of inputs has put the device in an unexpected scene, BACK gets you out.
4. **Read `examples/05_button_navigation.md`** for the desktop keymap and the worked Sub-GHz navigation example.

**Negative example — the lone-SHORT bug was R2 in cc's Phase-1 survey.** Per `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §2: *"Previously, every button press required three separate RPC calls (PRESS / SHORT / RELEASE). A lone SHORT was silently absorbed by most app scenes — cc's R2 + live observation confirmed."* Two days of GUI work were done with the lone-SHORT bug present, looking like "the input system is flaky." It wasn't; it was working exactly as the firmware specified, and the host was driving it wrong.

### 1.6 — USB-CDC transport drops mid-mission

**Symptom:** mid-mission, `client.rpc.<anything>` starts timing out. `flipper_connection_health` reports `transport_connected=false`. The Flipper may still be running the script on-device; the host just can't reach it.

**The three most common causes:**

1. **A `usbdisk` or `badusb` JS call changed USB mode.** Both modules reconfigure the USB stack and drop CDC. This is documented in `docs/for_ai_contributors.md` "Hard rules" (don't run usbdisk/badusb speculatively) and in `flipper_mcp/modules/app_lifecycle/module.py`'s `flipper_app_start` description.
2. **The JS engine crashed mid-script** (rare since R5 fix, but possible — `docs/for_ai_contributors.md` "Things we already learned" #7 still notes the ~1500+ char ceiling as a watch item).
3. **Genuine cable/port loss.** The cable came loose; a Windows update reset the USB-serial driver; the device rebooted (e.g. via a watchdog the script triggered).

**Ladder:**

1. **Re-check the connection.** `flipper_connection_health` confirms the transport is down.
2. **Do not retry the same JS mission.** If the cause was the mission, retrying will retrigger it. Re-think first.
3. **Replug the device and re-establish.** This handles 1 and 3 above. The CDC enumeration should come back within ~3 seconds.
4. **If the device still doesn't enumerate:** the device may need a power cycle (hold both buttons for ~10 seconds on Kiisu / hold Back for ~30 seconds on official Flipper). This is a hardware path, not a CPK path.
5. **Once re-connected:** the on-device state may be whatever the script left it in. Check `flipper_app_lock_status` and walk §1.4 if needed.

**Why this ladder is separate from §1.4:** "device stopped responding" with a healthy transport is a different problem than "transport dropped." The first is in-band recovery (RPC works, just send the right RPC). The second is out-of-band recovery (RPC is gone, you have to re-enumerate). Don't conflate them in the symptom check.

---

## Section 2 — Patterns for working with Victor

These are not "Victor's quirks." They are documented preferences with a track record — when an AI ignores them, the session degrades. Specific operator context.

**Background, citation `~/.claude/projects/D--Dev-Projects/memory/user_victor.md`:** Victor Snell, 43, Calgary AB. Tech Lead at EDGE Makerspace (nonprofit). Technical: "deep infrastructure knowledge (pgvector, Docker, Ollama, Windows Task Scheduler, Cloudflare tunnels). Comfortable with Python, PostgreSQL, embeddings, LLM APIs. Builds production-grade nightly pipelines. **Prefers pragmatic, working code over theoretical purity.**" Primary project is a sovereign memory system being productized as KnowMe.

### 2.1 — Don't lecture; explain trade-offs, not syntax

Victor is technical at the infrastructure layer. He doesn't need an explanation of how `async def` works in Python; he needs to know whether a given async refactor will simplify the call sites or introduce a deadlock risk. Citation: the user_victor memory file ("pragmatic, working code over theoretical purity"). Practical: when answering "should we do X?", lead with the trade-off (cost / risk / maintenance burden), not the syntax.

### 2.2 — "Let her rip" means execute now, no confirmation

Citation: `~/.claude/CLAUDE.md` ("Victor's preferences"): *"'Let her rip' = execute now, no confirmation."*

When you hear it, do not prompt for "are you sure?" or list five options. Execute the best-judgment plan and state the assumption you made. Cross-reference: `~/.claude/projects/D--Dev-Projects/memory/feedback_delete_over_disable.md`: *"Victor prefers direct execution, not hedged caution. 'Let her rip' semantics."*

### 2.3 — Parallel cc + Claude Desktop sessions share COM9

Both clients use the same MCP server backing the same Flipper on COM9. If Claude Desktop is mid-tool-call and cc fires a hardware tool, the bytes collide on the wire. Day 3 R7 was the canonical example: cc spawned 10 orphan flipper-mcp processes by end of session, all contending for the same port (`docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` "What's still open" R7). Day 4 explicitly tracked this and improved: "cc terminated cleanly this session (no orphans)" per `DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` "What's still open." The clean pattern is: if a hardware-touching cook is fired, assume Claude Desktop should not also be making hardware calls during that window. The autonomous cooks in Day 5/5.5/6/6.5 deliberately avoid touching hardware for this reason.

### 2.4 — "Your call" means "decide, and justify"

Citation pattern: spec language across cooks. Day 5 spec: *"You can either hardcode the JS source as a Python string and storage_write it before run, or assume it was pre-pushed (your call — see what's cleaner)."* The expectation isn't to surface options; it's to pick one and write down why. The Day 6 cook implemented this by choosing "load the .js source at module import time" and citing the reasoning ("the file is the source of truth — lint-able, diff-able") in `missions/llmdr/missions/radio_handshake.py`.

### 2.5 — Short responses in chat; disk specs for long stuff

CLAUDE.md "Token Hygiene": *"Responses: lead with the answer, explain only if asked. Victor prefers direct."* Every cc cook in this project follows the disk-spec-fire-prompt-inline pattern: detailed spec lives at `D:\Dev\scratch\cc_day*_*_spec.md`, the chat fires it with a one-line `read <spec> and execute it`. The pattern is not aesthetic — it's because the chat window is for *attention*, the disk is for *reference*. Don't dump 500 lines of explanation in chat when 5 lines and a file path will do.

### 2.6 — Disagreement: push back on technical truth, defer on context

CLAUDE.md "Interaction Style": *"Push back when the human is wrong. If you observe behavior that contradicts what the human is asking you to assume, surface that. Don't quietly do the thing they asked anyway."* This was tested on Day 6 — the spec named API calls (`subghz.stop()`, `gpio.init(pin, "input", "no")`) that don't exist in the documented mJS surface per KB §2.4 + §2.9. The cook used the KB form and noted the spec drift in the cook report. Per `D:\Dev\scratch\cc_day6_morning_kit_report.md`: *"The spec contained three API claims that disagree with `docs/KIISU_DEEP_KNOWLEDGE.md`... I followed the KB and noted the drift here."* The opposite (silently follow the spec, produce broken JS) would have wasted the morning kit.

### 2.7 — Scope discipline in cooks: don't fix things in passing

Every cook spec since Day 5 has had a hard rule like *"No editing outside the explicit task scope."* The rule sounds restrictive but it serves a specific purpose: cook outputs need to be reviewable in one sitting. A cook that touches 12 files for scope-creep reasons is much harder for Victor to merge in the morning than one that touches the 6 explicitly-named files. Out-of-scope drifts go into the cook report as "flagged for next cook" — not into the patch. Day 5.5's report flagged additional `src/flipper_mcp` drift in 4 unnamed files; the next cook (Day 6) deliberately did not touch them either because they weren't named in *that* cook's scope. The discipline compounds.

### 2.8 — Memory artifacts are point-in-time observations

CLAUDE.md "auto memory" + the memory-load system-reminder: *"This memory is N days old. Memories are point-in-time observations, not live state — claims about code behavior or file:line citations may be outdated. Verify against current code before asserting as fact."* Practical: when a memory file says "file X:Y does Z," verify with a quick `Grep` or `Read` before citing it as ground truth in this conversation. The two memory files cited in §2's negative examples were re-verified during the Day 6.5 cook before being used.

### Negative examples — places an AI misread Victor

**1. The "verify before deleting" instinct — feedback_delete_over_disable.md.** Per `~/.claude/projects/D--Dev-Projects/memory/feedback_delete_over_disable.md`: a Claude Desktop session in 2026-05-15 ("next big audit" session, B3 assistant_controller_cutout) recommended DELETE for `memorycore-assistant` (port 8897), then *queued a PROBE 2 to "verify empirically before B-CUT-3 fires."* Victor's verbatim response: *"we dont use memorycore assistant at all, desktop app is being over careful before deleting LOL."* The misread: Claude Desktop applied a generic "verify before destructive operation" pattern when Victor had *already provided the empirical answer*. Lesson: a verification step is friction-as-caution when the operator's prior statement IS the empirical input. Don't re-probe what was already answered.

**2. The Day 5 README rewrite scope-stretch.** Per my Day 5.5 report at `D:\Dev\scratch\cc_day5_5_followup_report.md`: *"`examples/README.md` was much more out of date than my Day 5 report flagged. It pointed at one stale example and didn't mention the 8 numbered tutorials I'd added on Day 5. Updating it to 'fix the src/ drift' without also fixing the structural staleness would have left it actively misleading. I rewrote it. Adjacent to the spec's scope but I think defensible."* The spec said only "Update any references to the old path in `examples/README.md`." Rewriting the whole file was scope-expansion. The misread: I treated "the file is so stale it's misleading" as license to expand scope, when the spec's hard rule was *"No editing outside the explicit task scope. Don't fix things in passing."* I flagged it transparently in the cook report, but a stricter cook would have left the README incomplete and added the rewrite to a follow-up. The general rule: *acknowledge tension between two goals, surface the choice, but default to the narrower scope when the spec is explicit.*

---

## Section 3 — Failure modes by category (the honest accounting)

This is the section future-AIs benefit from most. It is not flattering — that is the point. If a future AI reads only this section, they should leave with a calibrated sense of *how often AI agents working on CPK have been wrong, and in what shapes*.

### 3.1 — Times an AI was about to fabricate output (and what caught it)

**Instance 1: Day 4 pre-flight refusal.** cc was about to fake-run a hardware probe because the MCP tools weren't loaded into the session. Per the meta-rule in `docs/for_ai_contributors.md` "Working style we expect from AI contributors": *"No fabrication. If you don't have the tools to test something, say so — don't invent a result. cc has been refused execution before for trying to fake-run a probe without the right MCP loaded; this was the correct behavior."* The catch was a pre-flight check that surfaced missing tools BEFORE the cook started. Lesson: pre-flight is what prevents fabrication, not after-the-fact discipline.

**Instance 2: Day 5 protobuf gencode/runtime mismatch.** Per my Day 5 report at `D:\Dev\scratch\cc_day5_examples_report.md`: pre-flight required `python -c "import flipper_mcp; print('ok')"` to verify the environment. The import failed (protobuf gencode 6.33 vs runtime 5.29 mismatch — environmental issue, not a code issue). The fabrication risk would have been to silently move on and write examples that *claimed* they imported. Instead the report explicitly says: *"It does NOT in the global Python env on this machine... I verified the symbol names by reading source instead. **No action required**, but worth knowing."* The fabrication wasn't *committed* — the alternative path (read source for symbol names) was substituted and called out. The catch was a structured pre-flight that distinguished "verify A or substitute with B" from "verify A or fake it."

**Instance 3: Day 1's Q4 — "biggest technical miss" caught by an external review.** Per `docs/decisions/DAY1_BLE_PROBE.md` Acknowledgements: *"GPT-5.5-Pro's review (`C:\Temp\llmdr_review_gpt55.md`) called Q4 the 'biggest technical miss' before any code was written. They were right. Probing capability before architecture saved us 4-5 days of phone-relay work that would have hit the same wall."* The fabrication-risk shape: the team's prior assumption was that the CLI text-shell would be reachable over BLE (a reasonable inference from "BLE is a serial transport"). An adversarial review explicitly probed that assumption and named it as untested. The catch was *external review applied before commitment* — a different pattern than the structured pre-flight, but the same shape: surfacing an unverified assumption before it shaped 4 days of work.

**Pattern across all three:** the fabrication-catch isn't "AI is virtuous"; it's "the structure surfaced the unverified claim before commitment." Pre-flight checks (Days 4, 5), external review (Day 1), and self-reports calling out "verified by reading source instead" (Day 5) all have the same shape: name the assumption, name what verifies it, do the verification (or substitute it cleanly), and report the choice. When that shape is followed, fabrication doesn't get committed.

### 3.2 — Times an AI went off-spec (good drift vs bad drift)

**Instance 1 (good drift): Day 3 cc Phase-1 capability survey ran 2h instead of 90 min.** Per `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` Acknowledgements: *"cc spent 2 hours on Phase 1 of a capability survey and produced six structural infra findings instead of the per-function matrix we asked for — which was the right call. Those findings drove every change in this commit. The 'didn't finish the matrix' outcome was net-positive."* The off-spec drift was *direction*: cc abandoned the per-function tabulation (low-yield) in favor of finding R2/R3/R5/R6/R7/R8 (high-yield infra bugs). The right call. Lesson: the cook spec's deliverable can be wrong about the *shape* of high-value output; an AI that catches that and pivots is doing the job better than one that fills in cells.

**Instance 2 (mixed drift): Day 4 environment change without explicit approval.** Per `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` "Environment change (out-of-band, needs migration completion)": *"The editable install at `D:\Dev\Projects\Kiisu\.venv\Lib\site-packages\__editable__.flipper_mcp-0.1.0.pth` was re-pointed from `D:\Dev\Projects\flipperzero-mcp\src` to `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK`. This was needed so the running MCP server (Claude Desktop + cc) loads code from CPK."* The change was unannounced — a `.pth` file was edited because the running MCP needed it to find CPK. The mitigation was: backup saved, change called out in the decision doc, "needs migration completion" flagged for follow-up. Net: positive outcome (R5 fix could be tested live), bad process (environment change without prior approval). Lesson: a `.pth` file is shared state; touching it without flagging in real time is a risk even when the work is good.

**Instance 3 (mixed drift): Day 5 examples/README.md scope expansion.** Already discussed in §2 negative example #2. The drift was acknowledged in-report and the file IS better for the rewrite, but it pushed past the spec's explicit "don't fix things in passing" rule. Lesson: when you catch yourself wanting to do "the helpful adjacent thing," default to scope-narrow + flag-in-report, not scope-stretch + justify-in-report.

### 3.3 — Times an AI drew the wrong conclusion from limited data

**Instance 1: Day 3 made-up unlock dance.** Detailed in §1.4 negative example. Claude Desktop synthesized GUI input sequences from training data when the firmware exposed a direct RPC (`PB_Desktop.UnlockRequest`, tag 67) for the operation. The wrong-conclusion shape: "I have GUI input as a tool; therefore the way to unlock is through GUI input." The right move would have been to enumerate the protobuf surface first (`docs/KIISU_DEEP_KNOWLEDGE.md` §3, the desktop service) and pick the direct RPC.

**Instance 2: Day 2 app_start name predictions.** Detailed in §1.1 negative example. cc read the firmware loader source and predicted `"js_app"` or `"JS Runner"` would match by `strcmp`. They didn't on mntm-dev because EXTERNAL FAPs aren't in the boot-time name list. The wrong-conclusion shape: "the firmware source defines the API surface; therefore the API surface works as the source defines it." It does — for built-in apps. EXTERNAL FAPs are a runtime exception cc didn't anticipate.

**Instance 3 (bonus): Day 3 R6 hypothesis.** cc hypothesized that "mJS parser crash on ~1500+ char scripts" was an independent firmware bug. Day 4 disproved this: per `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` "What's still open": *"R6 — RESOLVED (subsumed by R5). Confirmed live: a 2705-char script ran end-to-end via `flipper_js_run` with no parse crash and no USB-CDC drop. cc's hypothesis was correct — the 'mJS parser crash' was downstream of R5's truncation, not an independent firmware bug."* The wrong conclusion was downstream of a real symptom but the wrong root cause. The right move (which cc actually did) was to *label it a hypothesis* in the Day 3 doc — making it easy for Day 4 to disprove without re-fighting.

**Pattern across all three:** when an AI is reasoning from one authoritative source (firmware code, BLE GATT enumeration, an observed crash symptom), the failure mode is treating that source as *complete*. Firmware code defines capability but not runtime config; GATT defines the wire surface but not the application semantics; a crash symptom names what failed but not why. The cure is to mark conclusions as hypotheses until a *second independent source* (live device test, decision doc, cross-reference in another spec) confirms them. The Day 3 doc's discipline of labeling R6 a hypothesis is what made Day 4 cheap.

### 3.4 — Orphan processes (cc + lifecycle)

**Instance 1: Day 3 cc spawned 10 orphan flipper-mcp processes.** Per `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` "What's still open": *"R7 — cc spawns orphan flipper-mcp processes that don't terminate on session end. Killed 10 of them tonight to free COM9. Worth investigating the next time cc runs a hardware-touching cook."* Root cause: spawn-on-disconnect logic in the cc harness that didn't reap on session end. The friction was real — Victor had to manually pkill 10 processes to get COM9 back.

**Instance 2: Day 4 cc terminated cleanly (improvement).** Per the same doc's Day 4 follow-up: *"R7 — orphan flipper-mcp processes. cc terminated cleanly this session (no orphans). The root cause appears related to the harness's spawn-on-disconnect logic, not anything in CPK; deferring to future investigation if the pattern recurs."* Two sessions later, same harness, no orphans. The improvement wasn't a code fix — it was that cc wasn't run in a mode that triggered the spawn pattern. Lesson: lifecycle bugs that look like AI behavior are often harness configuration. Don't fix the AI; check the harness.

### 3.5 — Spec ambiguity that caused wasted work

**Instance 1: Day 6 spec named subghz.stop() and gpio.init(pin, "input", "no").** Per my Day 6 report at `D:\Dev\scratch\cc_day6_morning_kit_report.md`: *"The spec contained three API claims that disagree with `docs/KIISU_DEEP_KNOWLEDGE.md`... I followed the KB and noted the drift here."* Specifically: `subghz.stop()` doesn't exist (real API is `setIdle()` and `end()` per KB §2.4); `gpio.init(pin, "input", "no")` is positional when the real API is an options object (`gpio.get(pin).init({direction:"in", inMode:"plain_digital"})` per KB §2.9). The waste-prevented: had I typed the spec verbatim into the JS, the morning kit's mission 1 would have aborted on the first subghz call and the GPIO loop would have crashed. The catch: the cook spec rule "verify the JS against the cheat sheet" combined with the fact that the cheat sheet had been built in Day 5.5 (consolidating these APIs in one place). Lesson: spec drift relative to authoritative refs is detectable if the cook bothers to check.

**Instance 2: Day 5 spec asked for FlipperRPC class import.** Per my Day 5 report at `D:\Dev\scratch\cc_day5_examples_report.md`: *"The spec said `04_using_flipper_js_run.py` should import the `FlipperRPC` class. There is one (`flipper_mcp.core.rpc.FlipperRPC`), but the canonical user-facing API is `FlipperClient(transport)` — it wraps `FlipperRPC` internally and exposes the higher-level `client.rpc.app_start(...)` / `client.storage.read(...)` interface used in `app_lifecycle/module.py`."* I wrote the example against `FlipperClient` for accuracy and flagged the drift. The waste-prevented: an example that imported the low-level RPC class directly would have been technically functional but misleading about the user-facing API. The lesson: when the spec names a symbol that exists but isn't the canonical user-facing API, choose the canonical one and surface the choice.

### The through-line across the failure categories

Reading §3.1 through §3.5 together: the categories look distinct, but the failure mode is one pattern in five costumes. An AI confidently extrapolates from a partial source — firmware code (Day 2 names), training-data intuition (Day 3 unlock dance), assumed protocol semantics (R5 ACK-per-chunk), spec text taken literally (Day 6 subghz.stop, Day 5 FlipperRPC) — without doing the second-source check that would have caught it. The categories differ in *what source* the AI extrapolated from; the cure is the same in every case: name the source, name what would verify it, do the verification (or substitute and call it out), and report the choice. That's the same shape §4.1 (pre-flight) institutionalizes. Section 3 and Section 4 are the negative and positive expressions of the same discipline — the one that makes CPK cooks net-positive instead of net-corrective.

---

## Section 4 — Patterns that work (the same rigor)

After Section 3, this section's burden of proof is: each pattern has actually worked across multiple sessions. Not "sounds smart"; *worked*.

The patterns below are not a methodology imposed from outside. They were extracted from session reports — places where a specific structural choice mapped to a specific better outcome. Each entry below names sessions where the pattern applied and what would have failed without it. If a future AI reads this section and wants to argue against one of these patterns, the burden is on them to find a session where the pattern produced a *worse* outcome.

### 4.1 — Pre-flight checks before code generation

Every cook spec in this project mandates a pre-flight: read N specific files, verify environment, run a `python -c "import X"` smoke check. The pattern has caught two distinct environmental issues:

- **Day 4 missing MCP tools.** The cook pre-flight refused to start because `flipper_*` tools weren't loaded in the session. Documented in `for_ai_contributors.md` "Working style" — "cc has been refused execution before for trying to fake-run a probe without the right MCP loaded; this was the correct behavior."
- **Day 5 protobuf gencode mismatch.** Pre-flight `python -c "import flipper_mcp"` failed; substitute path (read source for symbol names) was used and called out in the cook report (`D:\Dev\scratch\cc_day5_examples_report.md`).

**How to apply:** the pre-flight is not ceremonial. List the SPECIFIC files to read and the SPECIFIC commands to run. The Day 6 spec's pre-flight (`cc_day6_morning_kit_spec.md` lines 32-40) is a good template — six numbered items, each citing a path.

### 4.2 — Spec-as-disk-file, fire-prompt-inline

The pattern: detailed spec lives at `D:\Dev\scratch\cc_day*_*_spec.md`. The chat fires it with one line: `read <spec> and execute it`. Specs are 100-250 lines; the chat-side fire prompt is a sentence.

Why it works: chat context is for *attention* — what's the cook fired right now. Disk specs are for *reference* — every detail that would otherwise force the conversation thread to scroll. The pattern enforces a clean handoff: the cook agent loads the spec file once and starts work; the chat-side observer doesn't need to track 300 lines of context.

Failure mode when not followed: when a cook spec is dumped inline in chat, the chat thread becomes both observation surface AND reference doc, both roles suffer, and the cook is harder to re-fire later (no canonical artifact). Days 5-6.5 all followed the pattern; this doc itself is being written from a disk spec.

### 4.3 — Recipe over innovation

When CPK has a validated recipe, the right move is to *wrap* it, not redesign it. The canonical example is the launch + cleanup recipe:

- **Day 2:** 10-step recipe with three-call BACK sequence (each step a separate RPC).
- **Day 3:** validated that ONE `BACK` press dismisses success/error/stuck — the recipe shrinks to 5 steps.
- **Day 4:** the entire 5-step recipe gets wrapped into one MCP tool, `flipper_js_run` (commit `57fefff`, `flipper_mcp/modules/app_lifecycle/module.py` `_js_run`). Same recipe, one tool call.
- **Day 6:** the morning kit's `_runner.py` reuses the recipe pattern for Python-level invocation. Not reinventing — composing.

The temptation when seeing a complex recipe is to "make it shorter." The discipline is to first prove the recipe works, then wrap. Innovation that bypasses the recipe before it's proven costs Day-2-style 10-step contortions.

### 4.4 — Stop conditions in every cook spec

Every cook spec since Day 4 has a "Hard stop conditions" section listing 3-5 specific terminate-now triggers. Example from `cc_day6_morning_kit_spec.md`: hit 3 hours wall clock, want to add a TX primitive, can't find a documented API, etc.

Why it works: an AI agent (especially under "complete the spec" pressure) defaults to pushing through obstacles. A stop condition pre-authorizes the off-ramp. Day 3 hit one and produced more value than the original spec would have (the Phase 1 → R5/R6/R7 finding pattern, §3.2 instance 1). Day 5 had stops; cook finished cleanly with time to spare.

A good stop condition has three traits:
1. **Concrete trigger** — "3 hours wall clock" not "if it takes too long."
2. **What to ship instead** — "STOP_REPORT.md summarizing what got done" not "abandon."
3. **A small set** — 3-5 conditions; more than that and the AI doesn't internalize them.

### 4.5 — Scope discipline, with the report as escape valve

Three cooks in a row have explicitly named files to touch and forbidden everything else. The pattern works because there is an escape valve: the cook report. Anything you wanted to do but the spec forbade, anything you noticed in passing, anything you'd recommend for next session — those go in the report, not the patch.

Examples of the escape-valve working:

- Day 5.5 report flagged 4 additional `src/flipper_mcp` drift files; Day 6 left them alone but the future cook has them queued.
- Day 6 report flagged the `_runner.py` duplication-vs-coupling tradeoff and the protobuf env issue blocking tests; both were captured for future work without inflating the patch.
- Day 5 report flagged the `FlipperRPC` vs `FlipperClient` API confusion in the spec; no code was changed but the next cook (5.5) acted on the flag.

The discipline: when you catch yourself wanting to "just quickly fix" something outside scope, write the want into the report and move on. The report is structured for this — every cook report has a "things I wanted to do but the spec forbade" section.

### 4.6 — Bidirectional doc / code references

The project's docs reference code with file:line paths (`flipper_mcp/modules/app_lifecycle/module.py:35`). Code in turn references docs in docstrings ("see docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md §1"). This is deliberate. The pattern enforces:

- **Code that promises behavior cites the decision that justified the behavior.** Future readers can trace "why does this work this way" without grep-archaeology.
- **Docs that describe code cite a file:line that grounds the description.** Future readers can verify the doc against the actual code in one click.

When you write either side, make the other side discoverable. The Day 6 morning kit followed this — every mission helper's docstring cites the JS file and the cookbook entry; the cookbook entry links back to the helper. When future-Victor needs to find "where is the radio handshake's JS?" the docstring tells him; when future-Victor needs to find "where is the radio handshake's helper?" the cookbook tells him. Two entry points, one truth.

### 4.7 — Cook spec evolution as template

Cook specs (the `cc_day*_*_spec.md` files in `D:\Dev\scratch\`) get incrementally better at structure. Day 4 introduced explicit "Hard stop conditions" sections. Day 5 introduced the "Pre-flight check" numbered list. Day 5.5 introduced the "Per-task time budget" line items. Day 6 introduced "Per-mission status table" requirements in the report. Day 6.5 introduced the "Negative example required" structural requirement.

The implication: when authoring a new cook spec, **start by reading the most recent one as the template**, not the first one. The first one is missing the structural improvements that later cooks paid the price to discover. Each new improvement was empirically motivated — a section that got drift in the cook before became a section the next cook spec explicitly governed.

This is the same negative-knowledge-propagation pattern (§4.8 below) but at the meta level: the cook spec format itself accumulates the project's hard-won lessons.

### 4.8 — Negative knowledge propagation

The "BACK is universal cleanup" finding from Day 3 is the canonical case. The finding propagated:

- **Day 3 decision doc** captured it as §3.
- **Day 4 `flipper_js_run` tool** embedded it (step 4 of the recipe).
- **Day 5 example `04_using_flipper_js_run.py`** documents it as the cleanup pattern for Python-level callers.
- **Day 6 morning kit `_runner.py`** uses it directly (step 4 of `run_js_mission`).
- **`docs/for_ai_contributors.md` "Things we already learned the hard way"** has it as a bullet.

When you find a CPK-specific truth, ask: where does it need to land for the *next* AI to see it without re-deriving? In order of priority:

1. `docs/for_ai_contributors.md` — quick-start; every new AI reads this.
2. `docs/decisions/DAY*.md` — historical reasoning; the AI reads this when investigating WHY.
3. Code-level docstrings — the AI reads this when *using* the API.
4. This doc — the AI reads this for the project's earned intuition.

The same finding can live in multiple places; the key is the redundancy makes it discoverable from any entry point.

---

## Section 5 — Tactical reference: ladders for common asks

When the human asks one of these things, walk the listed steps. Don't improvise.

### 5.1 — "Run the morning kit" / "check my Flipper"

1. Open `docs/MORNING_KIT.md`.
2. Walk it from "Connection check" to whichever later mission the human asked for. Each mission has its `Ask Claude:` quote.
3. If anything fails before mission 3 (radio handshake), stop the sequence and triage the connection — don't push deeper.
4. Report per-mission status with the parsed dataclass from each `run()` (e.g. `RadioHandshakeReport.summary()`).
5. **Don't run TX-side missions as part of "check my Flipper."** The morning kit is RX-only by policy (`cc_day6_morning_kit_spec.md` hard rule). If the human asks for a TX test, that's a different conversation that needs explicit confirmation.

### 5.2 — "Build a new mission"

1. Read `docs/MISSIONS_COOKBOOK.md` to see if the mission is already sketched (recipe-grade). If so, the implementation is a translation; if not, write the recipe first.
2. Read `examples/03_mission_template.js` — every CPK mission's JS scaffold.
3. Read `examples/09_mjs_cheat_sheet.md` — the mJS gotchas table (no Date, no try/catch, `.toString()`, etc.).
4. Mirror an existing helper at `missions/llmdr/missions/*.py`. The closest match by shape (RX-only, JS-backed, host-side, etc.) is the right template.
5. Use the shared `_runner.py` helper for push + launch + cleanup. Don't reimplement the recipe inline.
6. Verify your JS line-by-line against the cheat sheet *before* claiming the mission ready. Day 5's caught-mid-cook `Date.now()` near-miss happened because the lint pass was the safety net.
7. Update `docs/MISSIONS_COOKBOOK.md` from ☐ to ✓ when the mission is implemented; link the helper file.

### 5.3 — "Add a new MCP tool"

1. Read `docs/module_development.md` (dry reference).
2. Read `examples/06_adding_a_new_tool.md` (worked walkthrough using `app_lifecycle/module.py` as the model).
3. The module package lives at `flipper_mcp/modules/<your_module>/module.py`. Inherit from `FlipperModule` in `flipper_mcp/modules/base_module.py`.
4. If your tool needs a new protobuf primitive, add the method to `flipper_mcp/core/protobuf_rpc.py` with the `@_with_wire_lock` decorator. Mirror the surrounding methods' shape (timeout, parse, return).
5. Restart Claude Desktop / cc so the auto-discovery picks up the new module.

### 5.4 — "Debug a failing JS mission"

1. Read the log file at `/ext/apps_data/mcp_logs/<mission>.log` via `flipper_storage_read`.
2. Search for the **last `step=` line**. That's the breadcrumb of how far the script got.
3. If the last line is something other than `finished=true`, walk §1.2 ladder.
4. If the log is empty, the script aborted before opening the log file — check `require()` calls first, then `storage.openFile` mode strings (`"w", "create_always"` is the project convention).
5. If you see `mission=<wrong_name>`, the log file is stale from a prior run that wrote to the same path.

### 5.5 — "The device seems stuck"

The four lock conditions in order — see §1.4:

1. **Transport.** `flipper_connection_health`. If down, replug.
2. **Desktop lockscreen.** `flipper_desktop_is_locked`. If true, `flipper_desktop_unlock`.
3. **App-loader busy.** `flipper_app_lock_status`. If true (and desktop NOT locked), send one BACK.
4. **JS Runner stuck on success/error screen.** Send one BACK.

If all four return clean and the device is still unresponsive, `flipper_app_exit` to force-close, then retry the failing call.

### 5.6 — "What firmware does the Flipper have?"

1. Quickest: `flipper_systeminfo_get`. The `firmware_vendor` field distinguishes Momentum (`"Momentum"`), Unleashed, RogueMaster, and stock OFW (`"Flipper Devices Inc."`).
2. From JS, equivalent: `require("flipper").firmwareVendor` (`docs/KIISU_DEEP_KNOWLEDGE.md` §2.2). The `flipper_info` mission at `missions/llmdr/missions/flipper_info.py` reads this for you.
3. Cross-check: run the device inventory mission (`missions/llmdr/missions/device_inventory.py`) for the consolidated view — name, hardware, firmware, vendor, JS SDK version.
4. If the vendor is anything other than `"Momentum"`, see §6.5 — most of this knowledge base is empirically validated only against mntm-dev / mntm-release-1.4.3.

### 5.7 — "What missions are available?"

1. Browse `missions/llmdr/missions/*.py` — each file has a top-level docstring with "HOW TO FIRE" instructions.
2. Browse `missions/handshake/*.js` for the JS-backed missions added in Day 6.
3. `docs/MISSIONS_COOKBOOK.md` lists implemented (✓) and planned (☐) missions in one place.
4. `flipper_mcp/modules/*/module.py` lists the MCP-exposed tools (Tool definitions). Each module's `name` property is the namespace prefix.

---

## Section 6 — What this knowledge base does NOT know

Honest enumeration. If you find yourself confidently asserting something in this list, you're past the boundary of what CPK has actually tested. The pattern: each item has a "status changes to known to work when" line — a concrete event that would move the item from this section into the validated body of the doc. If you do the work that would trigger that move, update both this section and the relevant section above.

### 6.1 — BLE transport

BLE has been **probed** (Day 1, `docs/decisions/DAY1_BLE_PROBE.md`) — discovery works, GATT enumeration works, protobuf ping works, storage round-trip *partially* works (the same R5 ACK pattern bug surfaced on BLE before being fixed on USB), and the CLI text-shell is confirmed *not* exposed over BLE.

What's NOT wired: there is no `BLETransport` class in `flipper_mcp/core/transport/`. The probe code at `experiments/ble_probe/` is throwaway and not the eventual transport. **No mission has ever been driven over BLE in this codebase.** Until a `BLETransport` lands and one mission is validated over it, do not claim BLE works.

**Status changes to "known to work" when:** a `BLETransport` class exists in `flipper_mcp/core/transport/` AND at least one mission (probably mission_ping) has a documented live run end-to-end over BLE in a decision doc.

### 6.2 — NFC capture mission

Recipe-grade only. Listed in `docs/MISSIONS_COOKBOOK.md` as ☐ (not implemented). The recipe assumes the NFC app's "Save?" prompt is dismissible via OK keypress — *plausible* but unverified. Don't claim it works.

**Status changes to "known to work" when:** the mission lives at `missions/<somewhere>` AND a Day-N decision doc shows live NFC capture roundtripping a `.nfc` file from /ext/nfc/ back to the host.

### 6.3 — Cross-device (CPK + Cardputer-Adv) missions

Architecturally planned (the "Path 2" framing in `docs/decisions/DAY1_BLE_PROBE.md` Architecture Options). No code yet. The cross-device coordination layer doesn't exist; the Cardputer-Adv side has its own MCP server (different project), and they don't share a session.

**Status changes to "known to work" when:** a single MCP session can run a mission that touches BOTH devices and the result is wired into one structured report.

### 6.4 — TX-side anything

Sub-GHz `transmitFile`, IR `sendSignal` / `sendRawSignal`, BadUSB `press` / `print`, BLE beacon `start` — all exist in the firmware's mJS surface (per KB §2.4-§2.7) but **CPK has deliberately not exercised any of them**. The morning kit is RX-only by policy (`cc_day6_morning_kit_spec.md` hard rule: "No RF emission missions whatsoever").

**Status changes to "known to work" when:** at minimum, a single-shot TX mission (e.g. retransmitting a previously-captured Sub-GHz signal) has been live-validated and the validation is in a decision doc. Until then, treat the TX-side bindings as "documented, not tested" — assume they might work, but don't claim it.

### 6.5 — Firmwares other than mntm-dev and mntm-release-1.4.3

Live testing has happened only against AmorPoee (Kiisu V4B + Momentum `mntm-dev`) and at least once against IlsaTheo per `docs/decisions/DAY1_BLE_PROBE.md` "Acknowledgements" context. **Behavior on Unleashed, RogueMaster, stock OFW, and other Momentum builds is theoretical.** Many findings are likely firmware-stable (the protobuf surface is shared upstream); some are mntm-dev-specific (the FAP-path requirement, §1.1 negative example).

**Status changes to "known to work on firmware X" when:** the validated launch + cleanup recipe + at least mission_ping completes successfully on firmware X and the result is in a decision doc.

### 6.6 — Long-running mission stability

The longest empirically-validated mission is ~30 seconds (the Sub-GHz capture mission in `missions/llmdr/missions/library.py` defaults to a 30-second timeout). The longest single JS script run is `flipper_js_run("/ext/apps_data/mcp_missions/probe_big.js", wait_seconds=4)` — 2705 chars of JS, ~4 seconds wall-clock per `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` §2.

What's NOT validated: hour-long sessions; missions that hold the radio in RX for minutes; missions that write large files (>10KB) in tight loops. mJS engine stability at duration is an open question.

**Status changes to "known to work" when:** at minimum, a mission running 5+ minutes is live-validated and the result is in a decision doc. Until then, default mission wait_seconds to ≤30 and split anything longer.

### 6.7 — Behavior after the host machine sleeps

The host's Windows sleep / hibernate cycle releases COM9 and the MCP server's transport. Resuming and re-attaching has been informally observed to work but is not documented as validated. A cook that fires across a sleep cycle is currently untested ground.

**Status changes to "known to work" when:** a cook spec deliberately schedules a sleep-and-resume in the middle and confirms post-resume tool calls succeed without manual intervention.

### 6.8 — Concurrent missions

Only one mission has ever been fired at a time. The mJS runtime is single-threaded; the host RPC layer is serialized via `_with_wire_lock`. Theoretically two host clients could try to fire two missions concurrently and the wire-lock would serialize them — but the *script-on-device* assumption is that only one mission's log file is open at a time. Two missions writing to different log paths in rapid succession is **not** the same as two simultaneous missions; it's two sequential missions through one wire.

**Status changes to "known to work" when:** a cook deliberately fires two missions back-to-back (no wait between them past the BACK cleanup) and both complete cleanly.

### 6.9 — Recovery from a partially-applied storage_write

R5 (§1.3) was the canonical "partially-applied storage_write" bug. The fix made the symptom go away. What's NOT documented: what happens if the *post-fix* `storage_write` is interrupted mid-flight (e.g. cable yanked between chunk 3 and chunk 7). The expected behavior is "file truncated at the last successfully-written chunk," but no test has been written for this.

**Status changes to "known to work" when:** an interruption test is added to `tests/` (or similar) showing partial writes don't corrupt the device filesystem.

---

---

## Appendix A — Glossary of CPK-specific shorthand

The team uses some idiosyncratic shorthand that outsiders won't recognize without context. This glossary captures the high-frequency terms.

### R-codes (Capability Survey findings)

The cc Phase-1 capability survey on Day 3 produced numbered findings R1-R8. They're cited liberally in decision docs without re-explanation; this is the canonical list.

| Code | Subject | Status | Citation |
|------|---------|--------|----------|
| R1 | Not used in repo currently — placeholder slot in the survey numbering | — | — |
| R2 | Lone `SHORT` keypress is silently absorbed by most app scenes; full PRESS→SHORT→RELEASE triplet required | RESOLVED (Day 3) | `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §2 |
| R3 | `flipper_app_lock_status` (app-loader mutex) overlaps confusingly with desktop lockscreen state | RESOLVED (Day 3) | `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §1 |
| R5 | `storage_write` reports "Write failed" on multi-chunk writes; file truncated to first chunk | RESOLVED (Day 4, commit `34c0db7`) | `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` §1 |
| R6 | Large JS scripts (~1500+ chars) crash mJS engine and can drop USB-CDC | RESOLVED — subsumed by R5 (Day 4) | `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` "What's still open" |
| R7 | cc spawns orphan flipper-mcp processes that don't terminate on session end | DEFERRED (improved Day 4, root cause harness-side) | `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` "What's still open" |
| R8 | JS Runner shows different success/error/stuck screens; cleanup recipe unclear | RESOLVED (Day 3 — BACK is universal) | `docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md` §3 |

P1_storage_005 is the original Phase-1 designation for what later became "storage.fsInfo() is broken." It started INCONCLUSIVE and was promoted to CONFIRMED on Day 3.

### The four lock conditions (from §1.4)

- **Transport-disconnect:** USB-CDC line down. `flipper_connection_health` reports `transport_connected=false`.
- **Desktop-locked:** lockscreen is showing. `flipper_desktop_is_locked` returns `True`.
- **App-loader-busy:** an app is running. `flipper_app_lock_status` returns `True`. Overlaps with desktop-locked (the lockscreen *is* an app from the loader's POV) — distinct concept added Day 3.
- **JS Runner stuck:** an app (specifically JS Runner) is showing a success/error/stuck screen. The cleanup is one BACK.

### Recipe versions

- **Day 2 recipe** — 10 steps, three-call BACK sequence (PRESS, SHORT, RELEASE separately), made-up unlock dance for the lockscreen case.
- **Day 3 recipe** — 5 steps, single BACK call (triplet emitted automatically), `flipper_desktop_unlock` for the lockscreen case.
- **Day 4 recipe** — same 5 steps, wrapped into one tool call (`flipper_js_run`).
- **Current recipe** — Day 4's, callable from Python via `missions/llmdr/missions/_runner.py`'s `run_js_mission()`.

### Hardware names

- **AmorPoee** — primary test device. Kiisu V4B + Momentum mntm-dev. BLE MAC `80:E1:26:EA:3D:5A`, USB serial `5A3DEA0027E18000`. Connected at COM9 on Victor's Windows machine. Cited in Day 1-4 decision docs.
- **IlsaTheo** — secondary test device. Less context; referenced in passing in `docs/decisions/DAY1_BLE_PROBE.md` Acknowledgements.
- **Kiisu V4B** — the hardware clone of Flipper Zero that CPK targets. Different cosmetics; same STM32WB55 + CC1101 + ST25R3916 surface as the official Flipper Zero.

### Firmware shorthand

- **mntm-dev** — Momentum firmware's `dev` branch. The primary target for CPK.
- **mntm-release-1.4.3** — Momentum's most recent release tag (≈ mntm-012/013 family).
- **OFW** — Official Flipper Firmware (`flipperdevices/flipperzero-firmware`). CPK has *not* been live-tested against OFW.
- **mJS** — the embedded JavaScript dialect (Mongoose JS / cesanta/mjs) that Flipper's `js_app` runs. Flipper's fork is *more* restricted than upstream; see KB §2.10.
- **FAP** — Flipper Application Package. The `.fap` files under `/ext/apps/`.
- **FAM** — Flipper Application Manifest. The metadata for a FAP that names `appid`, `name`, `apptype`.

### Other terms

- **The cheat sheet** — `examples/09_mjs_cheat_sheet.md`. Consolidates the mJS gotchas.
- **The KB** — `docs/KIISU_DEEP_KNOWLEDGE.md` (1596 lines, the hardware-facing knowledge base).
- **The recipe** — by default, the validated launch + cleanup recipe (§1.4 / §4.3).
- **The cookbook** — `docs/MISSIONS_COOKBOOK.md`. Recipes-grade sketches of missions.
- **The morning kit** — `docs/MORNING_KIT.md`. The six RX-only missions from Day 6.
- **Path 1 / Path 2** — strategic framing from `docs/decisions/DAY1_BLE_PROBE.md`. Path 1 = "split mode" (BLE refuses CLI-dependent missions). Path 2 = "app_start everywhere" (BLE works for everything because we never use the CLI). Path 2 won on Day 2.

---

## Appendix B — Cross-cutting concerns (when touching X, be aware of Y)

CPK has a few places where a seemingly local change ripples. A future AI changing one of these without checking the others has reliably tripped a regression. Each entry below pairs the *change* with the *adjacent things to verify*.

- **Touching `flipper_mcp/core/protobuf_rpc.py`** — verify against the firmware source quoted in `docs/KIISU_DEEP_KNOWLEDGE.md` §3 and §5. The R5 root cause was here (commit `34c0db7`). Any new RPC primitive should be decorated with `@_with_wire_lock`, mirror the existing chunking pattern if chunked, and have a docstring citing the protobuf tag number from `flipper.proto`.
- **Touching `flipper_mcp/modules/app_lifecycle/module.py`** — this is where the validated launch + cleanup recipe lives (`_js_run`). Changes here affect every JS-using mission. Update `missions/llmdr/missions/_runner.py` if the recipe drifts (or re-think whether the duplication is now actively harmful).
- **Adding a new mJS API call to a mission** — check `docs/KIISU_DEEP_KNOWLEDGE.md` §2 for the actual binding shape FIRST. The Day 6 spec drift (`subghz.stop()`, `gpio.init` positional args) shows how easy it is to write JS that looks plausible but never worked.
- **Changing the structured log convention** — `key=value\n` is parsed by `_runner.py`'s `parse_kv_log` and by every mission helper's `_parse(...)` function. Update all of them or none. A mixed convention would silently produce empty reports.
- **Changing `examples/09_mjs_cheat_sheet.md`** — the cheat sheet is cited by `docs/for_ai_contributors.md` "mJS Quirks" section and by example JS files. If a rule changes (e.g. a new mJS binding is found), the cheat sheet and the long-form section in `for_ai_contributors.md` should both move together.
- **Changing a `Status changes to "known to work" when:` line in §6** — that's the project's calibration on what's been validated. Don't loosen the criterion without doing the validation that justifies the loosening. Tightening is fine (more rigor); loosening without a decision-doc citation is not.

---

## Appendix C — When to update this doc

Update this doc when:

1. **A new failure mode is observed across two or more sessions.** Single occurrences go to the relevant Day-N decision doc; recurring patterns earn a §3 entry here.
2. **A debugging ladder shortcut is found.** §1's ladders are living docs — when a new shortcut (or a new wrong-turn pattern) shows up, add it.
3. **A negative example becomes available.** §2 and §3 are stronger with more concrete examples. Don't omit fresh ones to "preserve" the existing structure.
4. **A boundary in §6 moves.** When TX-side gets validated, when BLE transport lands, when an hour-long mission runs — update the relevant "Status changes to known to work when" line to reflect the new floor.

Don't update for:

- New tools or new modules that just *exist* (those belong in `docs/api_reference.md` if any, or as discoverable code).
- One-time bug fixes already captured in decision docs.
- General LLM advice that doesn't tie to a specific CPK instance.

The 600-1000 line budget is intentional. Padding this doc is worse than leaving a section thin — the cost is that a future AI reads less of it. Keep every line earning its place.
