# Roadmap

CPK is alpha. This roadmap is the project's best current guess at what's next — not a commitment, and not exhaustive. It changes as we learn.

## Now (current sprint)

- **Mission helper wrapping the validated launch + cleanup recipe** — collapses the four-step pattern (`is_locked?` → `app_start(FAP_PATH, script)` → wait → `BACK`) into one MCP call, so adding new missions stops requiring boilerplate
- **NFC capture mission** — Claude opens the NFC app, user taps a card, Claude presses OK to save, presses BACK to exit. The original "auto-press the save dialog" idea.
- **`storage_write` false-failure bug fix** — known MCP-server-side response-parser bug that reports "Write failed" on successful long writes. Workaround documented; needs the real fix.
- **`flipper_mcp` rename hygiene** — package structure cleanup so `pip install -e .` is the canonical install path for CPK contributors, not for the legacy `flipperzero-mcp` namespace.

## Near (next few sessions)

- **BLE transport finalization** — protocol probed and validated in `experiments/ble_probe/`; needs final integration into the transport layer so missions can run untethered.
- **Sub-GHz frequency analyzer mission** — proven pattern (we already have `freq_analyzer_5f_*.js` scripts on test devices); needs to land as a first-class mission in `missions/`.
- **RTL-SDR integration** — Victor has a Nooelec NESDR working with `rtl_433`. CPK could use the RTL-SDR as a secondary receiver to validate signals the Flipper claims to have captured.
- **The seven §16 corrections for `cardputeradv-LLM-control`** — sister project; applying cc's recon findings as a clean commit.

## Mid (planned)

- **LLMDR meta-server (Path 2 from Day 2 decision doc)** — CPK becomes one FastMCP Provider; Cardputer-Adv becomes another. Claude sees one unified tool surface with namespaced cross-device missions (`llmdr.kiisu.subghz_scan`, `llmdr.cardputer.wifi_scan`, `llmdr.unified.rf_recon_both_devices`).
- **Mission audit log** — every mission writes a structured record to a pgvector-backed log. Search past missions by natural language. "Show me every Sub-GHz capture I ran last month."
- **Web dashboard** — simple read-only UI for monitoring active and recent missions. EDGE classroom use: instructor can see what students' Flippers are doing at a glance.
- **Mission catalog auto-doc** — script that walks the registered missions and emits `MISSIONS.md` for the README to link.

## Far (vision)

- **Multi-device orchestration** — CPK drives a fleet. One Claude session, 30 Flippers in a classroom, parallel missions, aggregate results.
- **Mission marketplace** — community-contributed mission scripts, vetted and signed.
- **Voice interface** — for the demo / classroom / accessibility use case. "Hey Claude, scan for the garage door opener" → CPK fires the mission → audio response with results.
- **Formal verification of mission outputs** — borrowing from the EBM / layered-reasoning-stack pattern: every mission emits a machine-checkable predicate (`finished=true`, `captured_signal=true`, `frequency_in_band=true`) that a downstream verifier can check before Claude makes claims to the user.

## What we're NOT doing

- **Adversarial / offensive features.** No jamming. No unauthorized access tooling. The Flipper community is divided on this; CPK's stance is education and defense only. If your use case requires offensive capability, fork — under MIT you're allowed, and we won't stop you — but it won't land in upstream CPK.
- **Replicating stock Flipper apps.** CPK isn't a UI replacement. The Flipper's UI is fine when a human is using it. CPK's value is *autonomous operation*, not "Flipper but on a screen."
- **Supporting every firmware fork.** Tested on Momentum. May work on others. We'll accept PRs that improve cross-firmware compatibility, but Momentum is the primary target.

## How priorities shift

Roadmap changes as we learn. The biggest drivers:

- **Empirical findings from `recon/`** — when a cc cook surfaces structural issues (like the lockscreen-as-app reality), priorities reshuffle
- **EDGE classroom feedback** — what students struggle with becomes urgent
- **Contributor interest** — if someone's actively building toward a feature, we'll prioritize the supporting work
- **Upstream changes** — Momentum drops new firmware regularly; we follow

## Want to influence the roadmap?

Open an issue describing what you'd build or want to see. We're a small project; loud voices count.
