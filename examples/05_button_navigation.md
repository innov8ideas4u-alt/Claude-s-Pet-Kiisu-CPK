# 05 — Driving menus with synthetic input

> **What this shows:** how to navigate the Momentum desktop and apps using `flipper_gui_send_input` — the tool that injects synthetic button presses at the firmware's input layer.
>
> **Why it matters:** most Flipper apps don't expose RPC callbacks. To drive their UIs (open Sub-GHz, pick a frequency, save a capture) Claude has to "press buttons" the same way you would with your thumb. This file explains the conventions you'll see in every mission that navigates UI.

---

## The keymap

Momentum desktop responds to the same six buttons the hardware has:

| Key   | What it does on the desktop                                                           |
|-------|---------------------------------------------------------------------------------------|
| UP    | Opens the **Lock-screen / Favorite app 1** depending on Momentum settings             |
| DOWN  | Opens **Favorite app 2** / passport screen depending on settings                      |
| LEFT  | **Archive** (file browser)                                                            |
| RIGHT | **Apps menu** (main launcher — Sub-GHz, NFC, IR, GPIO, BadUSB, JS Runner, etc.)       |
| OK    | **Main menu** (settings, file browser, etc., the central menu)                        |
| BACK  | Universal cleanup — wakes the lockscreen prompt, exits apps, dismisses dialogs        |

Once you're *inside* an app, the meaning of each key is app-dependent — Sub-GHz's UP/DOWN cycles frequency presets, NFC's OK reads a card, etc. The desktop bindings above are the only ones you can rely on globally.

## The triplet default

A real hardware button press isn't a single event — it's a sequence:

```
PRESS  →  SHORT  →  RELEASE
```

…all delivered to the same input handler within ~10 ms. Most Momentum app scenes *only* react to `SHORT` if it arrives bracketed by `PRESS` and `RELEASE`. A lone `SHORT` event is silently absorbed.

CPK's `flipper_gui_send_input` tool sends the full triplet **by default**. You just say:

```
flipper_gui_send_input(key="RIGHT")
```

…and Claude emits PRESS→SHORT→RELEASE under the hood. This is the validated, working behavior — empirically verified on mntm-dev.

## Advanced: single-event mode

The rare cases where you want one specific event type without the triplet:

- **`LONG`** — held-button gestures (e.g. some apps use long-OK to save). Send only the LONG event after a normal triplet, with a small gap.
- **`REPEAT`** — auto-repeat behavior (scrolling fast through a long list). Send REPEAT events at ~50 ms intervals.
- **Manual triplet construction** — debugging tooling, recording macros, fault-injection tests.

For those, set `single_event=True` and pick the explicit `event_type`:

```
flipper_gui_send_input(key="OK", event_type="LONG", single_event=True)
```

If you don't have a specific reason to override, **always use the default**. The triplet is what apps actually expect.

---

## Worked example: open Sub-GHz, then back out (4 tool calls)

The shortest reliable sequence for "go into Sub-GHz, then return to the desktop":

| # | Tool call                                                | What happens on the device                                 |
|---|----------------------------------------------------------|------------------------------------------------------------|
| 1 | `flipper_desktop_is_locked()`                            | Returns false → safe to proceed. If true, call `flipper_desktop_unlock()` first. |
| 2 | `flipper_gui_send_input(key="RIGHT")`                    | Desktop → Apps menu opens. (Triplet emitted automatically.) |
| 3 | `flipper_gui_send_input(key="OK")`                       | Apps menu → Sub-GHz launches (assuming it's the first item; if Momentum's app ordering differs, navigate with UP/DOWN first). |
| 4 | `flipper_gui_send_input(key="BACK")`                     | Sub-GHz quits, back to desktop.                            |

That's it. Four calls. No CLI. No file-system pokes. No JS Runner.

### Why we don't just call `flipper_app_start("Sub-GHz")`

You absolutely can, and for *programmatic* launches that's better — see `04_using_flipper_js_run.py`. But for **teaching demos** (showing a student the Flipper's menu structure on screen), synthetic input is more pedagogical: the student sees the menus open as if a hand were pressing buttons. RPC `app_start` jumps straight to the app, skipping the menu animation.

## BACK is the universal cleanup verb

Whatever app or screen the Flipper is on:

- JS Runner "Script done" success screen → BACK dismisses it.
- Any app's error dialog → BACK dismisses it.
- A stuck/running script → BACK exits.
- The lockscreen prompt → BACK opens the unlock UI (you'd still need to dismiss that, but you got somewhere).

That's why every CPK mission ends with one BACK press. You don't branch on what the screen *looks* like — you just send BACK and trust it.

---

## Gotchas to remember

- **`gui_send_input` does NOT wake the backlight.** RPC input bypasses the power-management path that hardware buttons trigger. To wake the screen (so a human can actually see what's happening), have your JS mission call `notification.success()` or `notification.error()` — those routes do wake the display + play audio.
- **App-loader gate:** if an app is already running (including the lockscreen), `flipper_app_start` returns `ERROR_APP_SYSTEM_LOCKED`. Use `flipper_desktop_is_locked()` to check the *lockscreen* state specifically, then call `flipper_desktop_unlock()` if needed.
- **The keymap above is for the *desktop scene only*.** Inside an app, the same key may do something completely different.

**Next:** `06_adding_a_new_tool.md` — extending the MCP server with your own tool.
