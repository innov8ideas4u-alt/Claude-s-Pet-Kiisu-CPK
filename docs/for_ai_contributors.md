# For AI Contributors

> **If you're an AI agent (Claude, GPT, cc, Codex, etc.) reading this to help your human extend CPK — read me first.**

This document is the project's *meta-context* — it tells you what CPK is, how it's built, how to avoid the mistakes the project already learned from, and where to find authoritative information.

## What you are about to work on

CPK ("Claude's Pet Kiisu") is a system where an AI agent autonomously operates a Flipper Zero (or Kiisu V4B clone) running Momentum firmware. The agent uses a Model Context Protocol (MCP) server to call structured tools that translate to protobuf RPC commands the device understands.

Your role as an AI contributor will typically be one of:

1. **Adding new MCP tools** that expose firmware capabilities (e.g., `flipper_bluetooth_scan`)
2. **Writing JS mission scripts** that run on the device and report results back
3. **Improving documentation** based on something you learned during a session
4. **Debugging live hardware behavior** when the user reports something weird
5. **Generating recon reports** like the ones in `recon/` and `docs/KIISU_DEEP_KNOWLEDGE.md`

## Critical context — read before suggesting anything

### The hardware is real and unforgiving

Mistakes hit physical hardware. Some specific patterns to be careful about:

- **`badusb` JS module sends keystrokes to the host PC.** Never run a `badusb`-using script without explicit user permission. The host PC is whichever machine the Flipper is plugged into.
- **`subghz.transmit` and `ir.tx` emit RF.** Receive-side functions are fine. TX requires explicit user permission.
- **`usbdisk` module changes USB mode** and will drop the MCP transport mid-session. Don't run it speculatively.
- **Writing to TCA8418 register 0x05 via raw I²C silently wedges the keyboard** until reboot. Don't do blanket I²C scans on Cardputer-Adv (different project, but the principle applies).
- **The orphan-process problem.** If you spawn an MCP server from a hardware-touching task, ensure it terminates on session end. See `recon/PHASE1_SUMMARY.md` finding R7.

### Knowledge sources, ranked by authority

When facts disagree, trust them in this order:

1. **Live hardware behavior** — what the device actually does, observed in this session
2. **Firmware source code** — `github.com/Next-Flip/Momentum-Firmware`, `github.com/Next-Flip/flipperzero-protobuf`
3. **`docs/KIISU_DEEP_KNOWLEDGE.md`** — cc-generated, source-cited, 1596 lines. Authoritative for *what should work*. May contain mntm-dev-version drift — see the Contradictions section.
4. **`docs/decisions/DAY*.md`** — what *this team* learned and decided. Captures contradictions with the KB.
5. **Official Wiki / official docs** — usually right, sometimes outdated
6. **Community forums / GitHub issues** — useful for context, verify against source
7. **Your training data** — *least* authoritative for anything Flipper-specific. The ecosystem moves fast and your priors will be stale.

### Things we already learned the hard way

These are sourced in `docs/decisions/` but worth surfacing here:

- **`app_start` requires the full `.fap` path on Momentum mntm-dev.** `app_start("js_app", ...)` and `app_start("JS Runner", ...)` both return `ERROR_INVALID_PARAMETERS`. The working form is `app_start("/ext/apps/assets/js_app.fap", "/path/to/script.js")`. KB §1.2 disagrees; reality wins.
- **`gui_send_input` must emit the full PRESS→SHORT→RELEASE triplet.** A lone `SHORT` is silently absorbed by most app scenes. The `flipper_gui_send_input` MCP tool defaults to emitting the full triplet — only override with `single_event=True` for advanced cases.
- **BACK is the universal cleanup verb.** Whether JS Runner shows a "Script done" success screen, an error dialog, or a stuck-running script — a single BACK press dismisses all three. No state-machine branching needed in mission helpers.
- **`gui_send_input` does NOT wake the backlight.** RPC button presses bypass the power-management code that hardware buttons trigger. To wake the screen (for visible classroom demos), have your JS mission call `notification.success()` or `notification.error()` — these go through a different feedback path that does wake the display + plays audio.
- **`storage.fsInfo()` is a confirmed broken binding on mntm-dev.** It crashes the calling script. Use the host-side `storage_info` MCP tool instead.
- **`ERROR_APP_SYSTEM_LOCKED` is misleading.** It means "another app is running, which might be the lockscreen scene," not "system is locked." Use `flipper_desktop_is_locked` for the *real* lock state.
- **`storage_write` returns "Write failed" on many successful long writes.** Known MCP-server-side bug in response parsing. Always verify writes by reading back.
- **Large JS scripts (~1500+ chars) crash the JS engine and can drop USB-CDC.** Keep mission scripts under ~800 chars where possible. If you need more, split across multiple files.

### The validated launch + cleanup recipe

```
1. flipper_desktop_is_locked            # if locked, call flipper_desktop_unlock
2. flipper_app_start("/ext/apps/assets/js_app.fap", "/abs/path/to/script.js")
3. <wait — log marker or fixed duration>
4. flipper_gui_send_input(BACK)         # one call dismisses success/error/stuck
5. ready for next mission
```

That's it. Don't make it more complicated. The full triplet for BACK is emitted automatically by the tool's default behavior.

### Mission script template

```javascript
let storage = require("storage");
let notification = require("notification");
let LOG_PATH = "/ext/apps_data/mcp_logs/<your_mission>.log";
let f = storage.openFile(LOG_PATH, "w", "create_always");

f.write("step=loaded\n");

// === mission body ===
// Remember: mJS has no try/catch. If a call throws, the script aborts and the
// log is incomplete. Missing "finished=true" IS your signal that something
// threw.

f.write("finished=true\n");
f.close();
notification.success();   // wakes the screen + plays audio so the user can SEE Claude doing things
```

Always end with `notification.success()` on success or `notification.error()` on failure. This is how the human knows the mission ran.

## How to onboard your human's local AI session

If you're being asked to extend CPK in a fresh session, here's the minimum context to absorb:

1. Read `README.md` (you may have already)
2. Read this file
3. Skim `docs/decisions/DAY1_BLE_PROBE.md`, `DAY2_APP_RPC_AND_INPUT.md`, `DAY3_DESKTOP_RPC_AND_POLISH.md` — these are the project's narrative history
4. For your specific task:
   - Adding an MCP tool → read `docs/module_development.md` + look at `flipper_mcp/modules/app_lifecycle/module.py` as a reference implementation
   - Writing a JS mission → look at `missions/` for existing examples
   - Investigating hardware behavior → read `docs/KIISU_DEEP_KNOWLEDGE.md` first
5. Look at the most recent commits on the active branch — that's where the team's current focus is

## Working style we expect from AI contributors

- **No fabrication.** If you don't have the tools to test something, say so — don't invent a result. cc has been refused execution before for trying to fake-run a probe without the right MCP loaded; this was the correct behavior.
- **Source-cite anything controversial.** When making claims about firmware behavior, link to the file:line in the relevant repo, or quote the wiki page.
- **Discipline over heroics.** If a task is going to overrun its spec's stop conditions, stop and write a partial report. cc's Phase 1 capability survey ended at 2h instead of 90min and produced *more value* than a clean finish would have — because it stopped at a stop condition.
- **Push back when the human is wrong.** If you observe behavior that contradicts what the human is asking you to assume, surface that. Don't quietly do the thing they asked anyway.
- **Document what you learn in the appropriate place.** New gotcha? Add it to `docs/KIISU_DEEP_KNOWLEDGE.md` under the right section. New architectural decision? Drop a `docs/decisions/DAY_N_*.md`. Don't bury insights in commit messages.

## Things to never do

- Never commit anything that touches `D:\Dev\Projects\pgvector_load\.atlas\` or any MemoryCore content. CPK is LLMDR-only.
- Never make the JS Runner exit recipe more complicated than "send BACK." It works for everything.
- Never fake-run a hardware probe. If the tools aren't loaded, report and stop.
- Never widen the license without team discussion. CPK is MIT and the upstream (busse/flipperzero-mcp) is MIT; preserve that.
- Never delete `recon/` artifacts. They're the project's empirical truth-record.

## When in doubt

- Open an issue describing what you're trying to do
- Read `docs/decisions/` for prior reasoning on similar things
- Check `recon/` for empirical findings about the hardware
- Look at the most recent Day-N decision doc to see what the team is focused on

If you read this whole file, you have enough context to be productive. Welcome to the project.
