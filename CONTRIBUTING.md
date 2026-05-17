# Contributing to CPK

Whether you're a human or an AI, contributions are welcome. The bar is the same for both: **make the project better, don't make it worse, and respect the hardware.**

## If you're an AI agent

Read **[`docs/for_ai_contributors.md`](./docs/for_ai_contributors.md)** first. It tells you everything CPK has already learned the hard way, where the authoritative sources of truth are, and how to avoid the failure modes the project has documented. Skipping that file will cost you (and your human) hours of debugging.

## If you're a human

Read **[`SETUP.md`](./SETUP.md)** first to get a working environment. Then come back here.

## How to contribute

### Easy contributions

- **Typo fixes, doc clarifications, broken-link reports.** Open a PR or an issue.
- **New mission scripts** in `missions/` that demonstrate something specific (a Sub-GHz scan, an NFC read, an IR replay). Single-file, well-commented JS files are perfect.
- **Reporting empirical findings** that contradict the documentation. The `docs/` is wrong sometimes. Tell us.

### Medium contributions

- **New MCP tools** that wrap firmware capabilities not yet exposed. See [`docs/module_development.md`](./docs/module_development.md) and use `flipper_mcp/modules/app_lifecycle/module.py` as a reference.
- **Cross-firmware testing** — does CPK work on Unleashed? RogueMaster? Stock OFW? Report findings, propose patches where it doesn't.
- **Documentation expansions** — particularly worked examples in `examples/`, or new sections of `docs/KIISU_DEEP_KNOWLEDGE.md` based on your own deep dives.

### Big contributions

- **BLE transport finalization** — the protocol's been probed (`experiments/ble_probe/`); needs final wire-up
- **Cross-device missions** — Cardputer-Adv work is happening in a separate repo; once that's stable, CPK can orchestrate both devices simultaneously
- **Web UI / dashboard** — currently CPK is "drive from chat." A simple web dashboard for monitoring missions would be huge for the EDGE classroom use case.

If you're considering a big contribution, **open an issue first** so we can discuss scope. We won't reject substantial work that came out of nowhere, but we'd rather not see you put 20 hours into something that conflicts with planned changes.

## How to submit a PR

1. Fork the repo
2. Branch from `main` with a descriptive name: `feature/bluetooth-scan` or `fix/storage-write-parser`
3. Make your changes, with commits that have informative messages (terse is fine — `fix(storage): correct ACK parsing for chunked writes` beats `update`)
4. If you added/changed user-facing behavior, update the relevant `docs/` file
5. If you discovered an empirical truth about the hardware, update `docs/KIISU_DEEP_KNOWLEDGE.md` and cite a primary source
6. Open the PR; describe what changed, why, and how you tested it

We try to review PRs within a week. If we miss yours, ping the issue.

## Hardware contributions

You don't have to own hardware to contribute. But if you DO have a Kiisu V4B or Flipper Zero and you're willing to test cross-firmware or test on hardware variants, that's gold — open an issue with what you've got and we'll figure out a test matrix.

## Style

- **Python:** standard PEP 8, type hints encouraged, no `black` enforcement yet
- **JavaScript / JS missions:** mJS dialect (Momentum's JS engine). No `try/catch`, no `Promise`, no `Date`. Use `print()` for diagnostics, write structured logs.
- **Markdown docs:** plain markdown, GitHub-flavored. Code blocks should specify the language.
- **Commit messages:** present tense ("add foo" not "added foo"), informative subject line, optional longer body explaining *why*.

## Sensitive operations

CPK can drive a Flipper. The Flipper can do things that affect the physical world. **PRs that demonstrate or enable malicious capability (jamming, unauthorized access, real-world deception)** will be closed and discussed publicly. CPK's intended use cases are education, defensive research, and legitimate hardware-security work.

If you're unsure whether your contribution falls in a gray area, **ask first**.

## Code of Conduct

Be respectful. Disagree on substance, not on identity. We don't have a formal CoC yet because we're small; if/when we grow, we'll adopt something standard (probably Contributor Covenant). For now, the standard is: would you say this to someone's face? If not, don't put it in the issue tracker.

## License

By contributing, you agree your changes are released under the same MIT license as the rest of CPK. See [LICENSE](./LICENSE).

## Questions?

Open an issue. We watch the repo.
