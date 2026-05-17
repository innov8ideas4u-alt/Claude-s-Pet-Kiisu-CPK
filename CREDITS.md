# Credits

CPK doesn't exist without an enormous amount of prior work. This document acknowledges that work explicitly.

## Direct upstream

### busse / flipperzero-mcp

[**github.com/busse/flipperzero-mcp**](https://github.com/busse/flipperzero-mcp)

CPK's `flipper_mcp/` Python package began as a fork of Joel Busse's `flipperzero-mcp` project, which established the foundational architecture: USB serial transport, protobuf RPC framing over MCP, modular Python tool structure, and the entire shape of "Claude drives Flipper via tool calls." Without busse's groundwork CPK would have started from scratch and likely never shipped.

We've added substantially on top — six MCP tool families (`app_lifecycle`, `desktop`, full-press synthetic input, diagnostics), Momentum-specific fixes, BLE protocol probing, and the entire mission framework — but the bones are busse's. **MIT-licensed**, properly attributed in source headers where applicable.

If you're building on CPK, consider checking out the upstream too. It's a cleaner starting point if you want minimal-scope.

### Next-Flip / Momentum-Firmware

[**github.com/Next-Flip/Momentum-Firmware**](https://github.com/Next-Flip/Momentum-Firmware) ([momentum-fw.dev](https://momentum-fw.dev))

Every device CPK has been tested on runs Momentum. The firmware is what exposes the protobuf RPC surface CPK depends on, ships the JS Runner that lets us push runtime missions, and provides the `notification.success()` audio-visual feedback path that makes classroom demos viable.

The Momentum team's source code is also our **canonical reference** when our knowledge base disagrees with reality. When in doubt, we read their `applications/services/` and trust what's there.

### Flipper Devices

[**flipperzero.one**](https://flipperzero.one/) ([github.com/flipperdevices](https://github.com/flipperdevices))

The hardware that started everything. The original Flipper Zero, the open architecture decisions, the protobuf RPC spec ([Next-Flip/flipperzero-protobuf](https://github.com/Next-Flip/flipperzero-protobuf)) — all of it is what makes CPK possible.

### Kiisu V4B (clone hardware)

CPK's primary test devices are Kiisu V4B clones running Momentum. The Kiisu community is smaller and more underground, but the hardware is excellent and the price-point makes CPK viable for classroom deployments where 30 official Flippers would be cost-prohibitive.

## Foundational tooling

- [**Anthropic**](https://anthropic.com) — Claude (Opus 4.6 and 4.7) is the AI that drives every CPK mission. Without Claude (and the MCP specification Anthropic published), this entire project is just a Python serial library.
- [**Model Context Protocol**](https://modelcontextprotocol.io) — the protocol that lets Claude reach the Flipper. Open spec, vendor-neutral, makes this kind of integration possible.
- [**Python protobuf**](https://protobuf.dev/) — the wire format under everything.
- [**pyserial**](https://pyserial.readthedocs.io/) — USB transport.

## Research references

- [**Momentum Wiki**](https://github.com/Next-Flip/Momentum-Firmware/wiki) — especially the Lockscreen and JS Module pages.
- [**Bruce firmware**](https://github.com/pr3y/Bruce) — Cardputer-Adv reference (AGPL, read-only).
- [**roostercoopllc/flipper-mcp**](https://github.com/roostercoopllc/flipper-mcp) — independent project pursuing similar goals on ESP32-S2 (WiFi dev board); architectural reference.
- [**redbasecap-buiss/mcpd**](https://github.com/redbasecap-buiss/mcpd) — ESP32-S3 JSON-RPC 2.0 reference implementation for the Cardputer firmware work.

## Knowledge base

The 1596-line [`docs/KIISU_DEEP_KNOWLEDGE.md`](./docs/KIISU_DEEP_KNOWLEDGE.md) was produced by **Claude Code (cc)** in a multi-hour recon mission. Every claim in that document is cited to a primary source — Momentum firmware source, the protobuf spec, official Wiki pages, GitHub issues, or community forum threads. The contradictions section flags places where our prior team understanding was wrong.

The capability survey artifacts in [`recon/`](./recon/) are similarly cc-generated and validated against live hardware.

## Contributors

If you contribute to CPK, add your name here. Real names, handles, or both — your call.

- **Victor Mota** (project lead, [@innov8ideas4u-alt](https://github.com/innov8ideas4u-alt)) — architecture, hardware, EDGE classroom integration
- **Claude** (Anthropic, Opus 4.6 / 4.7) — co-developed every line of `flipper_mcp/`, validated every RPC primitive on live hardware
- **cc / Claude Code** — produced the deep knowledge base and capability survey deliverables
- **You** — open a PR

---

If we missed an attribution that's owed to you, please open an issue and we'll fix it immediately.
