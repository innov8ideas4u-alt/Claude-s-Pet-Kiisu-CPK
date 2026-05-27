# CPK BRIEF — Mission & Constraints

> 01-brief wins on **mission / constraints / who-it's-for**.
> If 01-brief disagrees with anything else, 01-brief is correct.

---

## What CPK is

**CPK (Claude's Pet Kiisu)** is an AI-driven RF reconnaissance and hardware control framework. Claude autonomously operates a Kiisu V4B (Flipper Zero clone, "AmorPoee") running Momentum `mntm-dev` firmware. The user asks Claude in plain English; Claude drives the device end-to-end via MCP tools that wrap the Flipper's protobuf RPC surface.

The framing is the dolphin joke made literal: the user has always been called the dolphin's "pet owner" in Flipper culture. In CPK, **the owner is an AI**.

Public repo: `github.com/innov8ideas4u-alt/Claude-s-Pet-Kiisu-CPK`
License: MIT
Status: alpha, 2 stargazers as of 2026-05-27

---

## Who CPK is for

In ranked priority:

1. **Victor's personal flagship repo.** This is his most-praised public project. He cares about it.
2. **EDGE non-profit students.** Teaching hardware-security concepts to at-risk youth. The "Claude drives the Flipper" framing makes embedded concepts visible and tangible.
3. **CompTIA / cert-track learners.** The Flipper is becoming standard kit in security training. Letting students command it conversationally beats menu-memorization.
4. **AI-driven RF research community.** CPK is (we know of) the first project where an LLM autonomously operates a Flipper over structured RPC with mission verification.

CPK is NOT for: jamming, unauthorized access, blanket DoS, attacks on third-party infrastructure. See `ROADMAP.md` "What we're NOT doing" — CPK is for education, defensive research, and **authorized** offensive testing only.

---

## Hard constraints

- **Hardware:** AmorPoee = Kiisu V4B clone on COM9, Momentum `mntm-dev` firmware. Tested ONLY on this device + this firmware. Cross-firmware behavior is theoretical.
- **License:** MIT. Matches the busse/flipperzero-mcp upstream we forked from. Never widen without team discussion.
- **No unauthorized-target missions.** Active-protocol missions (replay, clone, brute) gate to `target_class ∈ {owned, ctf, authorized}` and require explicit dual-confirm. Never ship a mission that could be pointed at unconsenting infrastructure.
- **No commits without review unless Victor explicitly says "let her rip."** cc cooks are write-files-only by default; Victor commits.
- **Atlas separation:** CPK has its own structured-state directory (`.dolphintank/`). DO NOT load or write to `D:\Dev\Projects\pgvector_load\.atlas\` from CPK work. Atlas is MemoryCore's; DolphinTank is CPK's. Two separate projects, two separate authoritative truths.

---

## The moat

Plain English: CPK's moat is **not the code**. The code is a few thousand lines of Python wrapping a well-documented protobuf RPC surface. Anyone could write that.

CPK's moat is **the empirical knowledge base of what actually works on real hardware + the AI-friendly project structure**:

- `docs/KIISU_DEEP_KNOWLEDGE.md` (1596 lines, source-cited firmware reference)
- `docs/AI_KNOWLEDGE_BASE.md` (600 lines, AI-onboarding doc with negative examples)
- 5 Day-N decision docs capturing every architectural choice and why
- 10 worked examples that get a contributor productive in <30 minutes
- `recon/` artifacts from autonomous research cooks
- Validated mission framework with `flipper_js_run` recipe

Anyone copying the code without the documentation will fail in ways CPK has already debugged. **That's the moat.**

The upcoming CPK Companion FAP (DAY8_FAP_VISION.md) will deepen the moat by adding device-side capabilities that don't exist in stock Momentum — first-class NFC/Sub-GHz/IR primitives without UI choreography.

---

## Non-goals

These keep us focused. Things CPK explicitly will NOT become:

- **A UI replacement for the Flipper.** The Flipper's UI is fine when a human uses it. CPK's value is autonomous operation, not "Flipper but on a screen."
- **An npm package or PyPI release in v1.** Github + git clone is the install path. Distribution mechanics can come after the v1 feature set is locked.
- **Every-firmware-fork-compatible.** Momentum is the primary target. PRs welcome for other firmwares; we won't bend the architecture to chase them.
- **A wrapper for Claude Code only.** Claude Desktop, Claude Code, and any MCP-speaking AI agent are equally first-class. The MCP server doesn't care who's calling.
- **MemoryCore-adjacent or competing with it.** Different project, different goals, separate authoritative truth.

---

## Success criteria

A year from now, CPK has succeeded if:

1. The repo has more contributors than just Victor and Claude
2. EDGE classroom uses CPK in at least one cohort and the students don't get blocked on environmental setup issues
3. The Companion FAP is shipped and a "demo someone on YouTube" video exists
4. At least one external mission has landed (someone other than Victor wrote a mission file that got merged)
5. The "for AI contributors" pattern has been adopted by at least one other project as a reference

These are the goals. Don't lose track of them when chasing tactical wins.
