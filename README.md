# Claude's Pet Kiisu — CPK

> **An AI literally owns a Flipper Zero.** Claude drives. The dolphin works.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()
[![Firmware: Momentum](https://img.shields.io/badge/firmware-Momentum-blueviolet.svg)](https://momentum-fw.dev/)

---

## What is this?

CPK turns a Flipper Zero (or Kiisu V4B clone) into Claude's **autonomous RF reconnaissance pet**. Claude doesn't just *advise* you on what to do with your Flipper — Claude *operates* it. Push a mission, walk away, come back to results.

The Flipper community's running joke is that the dolphin on screen is your "pet." CPK takes that literally: the dolphin's new owner is an AI.

### What that looks like in practice

Ask Claude something like:

> *"Find me a Sub-GHz weather sensor signal in this room, log it for 30 seconds, and tell me what frequency it's on."*

Under the hood, Claude:

1. Checks the device is unlocked (via RPC)
2. Writes a JavaScript mission script to the SD card
3. Launches the JS Runner with that script via direct RPC (no terminal, no CLI)
4. Waits while the Flipper scans
5. Sends a synthetic **BACK** press to exit cleanly
6. Reads the mission log
7. Answers you in plain English

No buttons pressed by you. No commands typed. Claude drives the device end to end.

---

## Why does this exist?

Three reasons:

1. **Teaching tool.** CPK is being built for [EDGE](https://example.org) — a non-profit teaching technical skills to at-risk youth. The "Claude drives the Flipper" framing makes hardware-security concepts *visible and tangible* for students who haven't worked with embedded devices before.

2. **CompTIA / cert prep.** The Flipper is becoming standard kit in security training. Letting students command it conversationally is the difference between "I memorized the menus" and "I understand what I'm asking the radio to do."

3. **AI-driven RF research.** Most LLMs can talk *about* Flippers. CPK is the first project (we know of) where an LLM *operates* one autonomously over a structured RPC interface, with mission verification and audit trails.

---

## Quickstart (~15 minutes)

You need: a Flipper Zero (or Kiisu V4B) running [Momentum firmware](https://momentum-fw.dev/), a USB cable, Python 3.11+, and either Claude Desktop or Claude Code.

```bash
git clone git@github.com:innov8ideas4u-alt/Claude-s-Pet-Kiisu-CPK.git
cd Claude-s-Pet-Kiisu-CPK
python -m venv .venv
.venv\Scripts\activate          # or source .venv/bin/activate on Linux/Mac
pip install -e .
```

Configure your AI agent to use the MCP server — see **[SETUP.md](./SETUP.md)** for step-by-step instructions including the device settings you need to enable on Momentum.

Then in Claude: *"What's connected? Run the ping mission."* — and watch.

---

## How it works (architecture)

```
┌────────────┐    MCP tools     ┌───────────────┐   protobuf RPC   ┌──────────┐
│  Claude /  │ ───────────────► │  flipper_mcp  │ ───────────────► │ Flipper  │
│  Claude    │                  │  (this repo)  │   over USB/BLE   │ Zero /   │
│  Code      │ ◄─────────────── │               │ ◄─────────────── │ Kiisu    │
└────────────┘   tool results   └───────────────┘   structured      └──────────┘
                                                    responses
```

Three independent layers:

| Layer | What it does |
|---|---|
| **`flipper_mcp/`** | The Python MCP server. Wraps the Flipper's protobuf RPC into tools Claude can call (`flipper_app_start`, `flipper_gui_send_input`, `storage_write`, etc.). |
| **`missions/`** | Higher-level mission framework. Reusable JS mission scripts + Python orchestration for multi-step flows. |
| **`proto/`** | The wire-protocol definitions. Reference for anyone adding new RPCs. |

For deeper architecture see **[`docs/architecture.md`](./docs/architecture.md)**.

---

## What works today

- ✅ **Direct app launch via RPC** — no CLI text-shell required. JS missions, NFC app, Sub-GHz app, all launchable without typing.
- ✅ **Synthetic button presses** — `flipper_gui_send_input(BACK)` etc. emit the full PRESS→SHORT→RELEASE triplet a real hardware press produces. All six keys validated on Momentum mntm-dev.
- ✅ **Lock-screen detection + dismissal** via direct RPC (`flipper_desktop_unlock`).
- ✅ **Mission cleanup** with a single BACK press — works for success screens, error dialogs, and stuck-running scripts alike.
- ✅ **Visible/audible mission feedback** via `notification.success()` and `notification.error()` from inside JS scripts — wakes the backlight, plays a sound, screen lights up so the student/instructor can *see* Claude doing things.
- ✅ **Full diagnostic responses** — `app_start` returns the firmware's actual error name (`ERROR_INVALID_PARAMETERS`, `ERROR_APP_SYSTEM_LOCKED`, etc.) instead of just true/false.

## What's in flight

- 🚧 BLE transport — protocol-validated (see [`experiments/ble_probe/`](./experiments/ble_probe/)), needs final wire-up
- 🚧 NFC capture mission with auto-save via synthetic input — the "Claude takes a card scan for you" flow
- 🚧 **Active-protocol mission category** (red-team / authorized-testing missions) — Sub-GHz replay, NFC clone, IR replay, RFID brute, BadUSB. All gated to owned-hardware / CTF-lab / explicit-authorization-only use. Catalog sketched at [`innov8ideas4u-alt/LLMDR_redteam`](https://github.com/innov8ideas4u-alt/LLMDR_redteam); first missions will land in `missions/redteam/` as they're implemented.
- 🚧 Fix for `storage_info` MCP tool — currently returns SD card stats for `/int` requests (F2 from Day 7 live-fire findings)
- 🚧 Investigation of `require("gpio")` failure on `mntm-dev` (F1)

See **[ROADMAP.md](./ROADMAP.md)** for what's planned.

---

## Documentation map

- **[SETUP.md](./SETUP.md)** — your first 15 minutes
- **[docs/claude_setup.md](./docs/claude_setup.md)** — Claude Desktop / Claude Code configuration in detail
- **[docs/KIISU_DEEP_KNOWLEDGE.md](./docs/KIISU_DEEP_KNOWLEDGE.md)** — **1596 lines** of source-cited reference covering every Flipper RPC, every Momentum JS module, every gotcha. Read this if you're going to extend CPK.
- **[docs/SETUP_REQUIREMENTS_mntm-dev.md](./docs/SETUP_REQUIREMENTS_mntm-dev.md)** — required device settings for RPC-driven work
- **[docs/architecture.md](./docs/architecture.md)** — how the layers fit
- **[docs/decisions/](./docs/decisions/)** — Day-N decision docs capturing every major architectural choice and why
- **[docs/for_ai_contributors.md](./docs/for_ai_contributors.md)** — **if you're an AI contributor reading this, start here**
- **[recon/](./recon/)** — autonomous research artifacts (cc-generated knowledge surveys)

---

## Contributing

CPK is built **with** AI, not just **for** humans. Whether you're a person or an LLM helping someone build on CPK, **[CONTRIBUTING.md](./CONTRIBUTING.md)** has the rules.

The fast version: read **[`docs/for_ai_contributors.md`](./docs/for_ai_contributors.md)** if you're an AI. Read **[`SETUP.md`](./SETUP.md)** if you're a human. Both work.

---

## Credits

CPK builds on the work of others — see **[CREDITS.md](./CREDITS.md)** for the full list. In short:

- [**busse/flipperzero-mcp**](https://github.com/busse/flipperzero-mcp) — the original MCP server CPK forks and extends
- [**Next-Flip/Momentum-Firmware**](https://github.com/Next-Flip/Momentum-Firmware) — the firmware powering every device this works on
- [**Flipper Devices**](https://flipperzero.one/) — the hardware that started this whole community
- [**Anthropic**](https://anthropic.com) — for Claude, the AI that actually drives the dolphin

---

## License

MIT. Use it, fork it, teach with it, build commercial products on it. See **[LICENSE](./LICENSE)**.

---

*Made with ☕ and a Flipper Zero that's tired of being told what to do.*
