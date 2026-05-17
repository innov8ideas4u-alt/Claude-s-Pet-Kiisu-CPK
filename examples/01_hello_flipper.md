# 01 — Hello, Flipper

> **What this shows:** the simplest possible interaction with CPK. No code. No Python. Just chat.
>
> **Why it matters:** if this works, your whole CPK install is healthy — MCP server up, USB-CDC alive, JS Runner reachable, GUI input wired. If it *doesn't* work, you know something is broken before you write anything more ambitious.
>
> **Read time:** 60 seconds. Run time: ~10 seconds.

---

## Before you start

You need:

- A Flipper Zero (or Kiisu V4B) running [Momentum firmware](https://momentum-fw.dev/) and connected over USB.
- CPK installed and the MCP server configured in either **Claude Desktop** or **Claude Code** (see `SETUP.md` if you haven't done this yet).
- The Flipper on the desktop screen (not in an app, not on the lockscreen). If unsure, press **BACK** on the device a few times.

That's it. No SD card setup, no extra scripts to push.

## The three steps

### 1. Open Claude

Either:
- **Claude Desktop** — open the app. The Flipper MCP tools load automatically if `~/.claude/claude_desktop_config.json` has the `flipper-mcp` server registered.
- **Claude Code** — open a terminal in any directory and run `claude`. The MCP server loads from the same config.

### 2. Say this

> *"Run the ping mission on my Flipper."*

That's the whole prompt. You don't need to tell Claude how. The `mission_ping` tool is one of CPK's built-in missions — Claude will find it, call it, and report back.

### 3. Watch the Flipper

You should see and hear:

- **Screen wakes up** (if it was asleep) — the backlight turns on.
- **A short beep / vibration** — Momentum's `notification.success()` audio.
- **A "JS Runner — Script done" or similar success screen for a moment**, then the device returns to the desktop on its own (CPK sends a BACK press to clean up).
- **Claude tells you** something like *"Ping mission completed in 3.2 seconds. The Flipper responded."*

If you saw and heard those things — congratulations. CPK can talk to your Flipper.

---

## Troubleshooting (5 lines)

- **No screen wake, no audio, Claude says "transport not connected"** → USB cable issue. Try a different cable (charge-only cables are a classic trap). Unplug and replug. Restart Claude.
- **"ERROR_APP_SYSTEM_LOCKED"** → another app is running on the Flipper. Press BACK on the device until you're on the desktop, then retry.
- **"Desktop is LOCKED"** → the lockscreen is up. Wake the device (any hardware button) or ask Claude to *"unlock the desktop and then run the ping mission."*
- **Claude can't find a `mission_ping` tool** → the `flipper-mcp` MCP server didn't load. Check your Claude config and look for a Python error in the MCP server logs.
- **Anything weirder than that** → read `docs/for_ai_contributors.md` "Things we already learned the hard way." Most CPK gotchas are documented there.

---

## What just happened, under the hood

For the curious — Claude executed roughly this sequence:

1. Checked the Flipper's desktop wasn't locked (`flipper_desktop_is_locked`).
2. Called `mission_ping`, which pushed a tiny JS script to the SD card and launched it via `flipper_app_start("/ext/apps/assets/js_app.fap", "<path>")`.
3. Waited for the script to write its log marker.
4. Sent a synthetic `BACK` press (full PRESS→SHORT→RELEASE triplet) to dismiss the JS Runner success screen.
5. Read the log back from the SD card and summarized it for you.

You'll learn each of those moves piece-by-piece in the rest of this directory. This was just to prove the connection works.

**Next:** `02_first_mission.js` — the smallest mission script you can actually read and modify.
