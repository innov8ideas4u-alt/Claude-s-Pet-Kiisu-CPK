# 08 — Onboarding your AI to CPK

> **What this is:** a copy-pasteable prompt to give your AI (Claude Desktop, Claude Code, ChatGPT in a tools-capable harness, etc.) so it learns CPK fast and starts being useful in the first 5 minutes.
>
> **Why it matters:** CPK has a lot of project-specific gotchas (mJS quirks, the validated launch+cleanup recipe, the lockscreen vs. app-loader distinction, the BACK-is-universal rule). Your AI doesn't know any of that on first contact. This doc skips the slow ramp.

---

## The onboarding prompt

Paste this into Claude (or your AI of choice) at the start of a new session:

> *I want to use CPK ("Claude's Pet Kiisu") to drive my Flipper Zero. The MCP server is already running and you should have tools like `flipper_app_start`, `flipper_js_run`, `mission_ping`, `storage_read`, etc. available.*
>
> *Before suggesting anything, please read these in order:*
>
> *1. `docs/for_ai_contributors.md` — the meta-context doc. Read it cover-to-cover. It's short (~150 lines) and saves us both from mistakes the project already learned from.*
> *2. `docs/KIISU_DEEP_KNOWLEDGE.md` — skim the table of contents. Don't read the whole thing. The Gotcha Index in §15 and Contradictions in §16 are the priority sections.*
> *3. `examples/` — pick whichever example file matches what we're about to do (button navigation, writing a mission, adding a tool).*
>
> *Once you've done that, suggest what we should build first based on what's already wired up. Lead with one recommendation, not three options.*

That prompt assumes the AI has filesystem-read access to the repo (Claude Code does by default; Claude Desktop needs the filesystem MCP server enabled). If it doesn't, paste the contents of `for_ai_contributors.md` directly into the chat.

## Why this prompt works

It does four things in one paragraph:

1. **Names the project** — "CPK" and the cute "Claude's Pet Kiisu" framing help the AI prime on the right context.
2. **Tells it which tools to expect** — so it doesn't waste a turn asking *"what can I do?"*
3. **Gives it a *reading order*, not just "go read everything"** — important; AI assistants often spend the first 10 minutes randomly browsing a repo otherwise.
4. **Asks for one recommendation, not a menu** — keeps the first response actionable rather than "here are five things we could do…"

## Example prompts that work well with CPK

Once your AI is onboarded, these are the kinds of asks that play to CPK's strengths:

> *"Run the ping mission and tell me the Flipper is awake."*

The smallest sanity check. If this fails, every more-ambitious thing will fail too. (See `01_hello_flipper.md`.)

> *"Push the mission at `examples/02_first_mission.js` to the Flipper and run it. Show me the log."*

Exercises storage_write + flipper_js_run + storage_read in one ask.

> *"Open Sub-GHz, wait 5 seconds, then back out. Don't actually capture anything — I just want to see the menus."*

A pure UI-navigation demo (good for classroom). Uses `flipper_gui_send_input` only. See `05_button_navigation.md`.

> *"What apps are installed? List the .fap files under `/ext/apps/`."*

Exercises `storage_list` and recursive listing. Great first "exploration" prompt that doesn't risk anything.

> *"I want to write a mission that scans for Sub-GHz signals across these three frequencies: 315, 433.92, 868. Walk me through the structure first, then write the script."*

Pushes the AI to plan before writing. CPK's structured-log conventions (`captured_signal=`, `rssi_dbm=`) shine here.

> *"Read `docs/for_ai_contributors.md` again — specifically the 'Things we already learned the hard way' section. Then tell me what you'd avoid before we touch the BadUSB module."*

The "before you do something risky, recall the rules" prompt. Encourages the AI to surface project-specific safety constraints.

> *"There's a JS mission I want to add at `missions/llmdr/missions/library.py`. Read the existing missions in that file as references, then propose the function signature for the new one before writing any body."*

Pattern-match on what's already there before adding to it. Saves you from getting a snowflake mission that looks nothing like the rest.

## Anti-patterns to discourage

If your AI starts heading these directions, gently redirect:

- **Asking you to "just run this command in a terminal."** CPK was built so the AI drives the Flipper. If a tool exists for the job (and one usually does), have it call the tool instead of dictating commands to you.
- **Inventing protobuf RPC method names.** If `client.rpc.foo()` doesn't exist, the AI should check `flipper_mcp/core/protobuf_rpc.py` rather than guess. The deep KB (`docs/KIISU_DEEP_KNOWLEDGE.md`) has the firmware-side names.
- **Skipping the BACK cleanup.** Every JS Runner mission must end with `flipper_gui_send_input("BACK")` (or use `flipper_js_run` which does it automatically). Without it, the Flipper is stuck on a success screen.
- **Fabricating hardware results.** If the AI doesn't have an MCP tool that can actually probe what it's claiming, it should say so. See `docs/for_ai_contributors.md`, "No fabrication."

## When you start a fresh session next week

The CPK repo doesn't have persistent AI memory. Every new session starts cold. The fastest way to re-onboard your AI is the same prompt above. Save it as a snippet, paste it on every new chat.

If you find your AI is *still* drifting (forgetting the BACK rule, recommending the broken `storage.fsInfo()`, etc.), the fix is probably to add the gotcha to `docs/for_ai_contributors.md` under "Things we already learned the hard way." That document is the project's institutional memory — load it once, and every onboarded AI inherits it.

**Next:** `docs/MISSIONS_COOKBOOK.md` — recipes for missions we plan to build (not yet implemented).
