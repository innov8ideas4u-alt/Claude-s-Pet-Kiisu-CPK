"""LLMDR — LLM Defined Radio: mission library.

LLMDR exposes parameterizable reconnaissance "missions" as MCP tools.
Each mission's preferred backend depends on what the connected firmware
supports:

  RPC   — pure protobuf RPC against firmware primitives (storage, app_start,
          app_load_file, etc.). Works on stock OFW. No on-device scripting.
  JS    — pushes a JavaScript template to the SD card, launches it, reads
          the log. Requires the Momentum-class JS runtime (subghz, nfc, etc).

Each mission picks the best available backend, with a `prefer_backend`
parameter so the LLM (or user) can override.

Architecturally: this module sits on top of `flipper_mcp` (the library).
flipper_mcp handles protocol primitives. LLMDR handles strategy.
"""

import asyncio
import logging
from typing import Any, List, Optional, Sequence, Tuple

from mcp.types import Tool, TextContent

from flipper_mcp.modules.base_module import FlipperModule

log = logging.getLogger("llmdr.missions")


# Shared on-device paths. Match flipper_mcp's js_runner so logs and missions
# land in the expected places when the JS backend is used.
MISSION_DIR = "/ext/apps_data/mcp_missions"
LOG_DIR = "/ext/apps_data/mcp_logs"


# ---------- FREQUENCY GUARDRAIL ------------------------------------------
# CC1101 chip can only physically transmit/receive in three ISM bands. Anything
# outside these bands will be silently rejected by the CC1101's PLL with no
# helpful error from the firmware. We catch it here at the host so the LLM
# (or human) gets an explicit warning instead of mysterious silence.
#
# Policy: SOFT WARNING. We log + flag, but pass the request through. This keeps
# the door open for legitimate pen-test use cases (people who got paid to do
# this work and need to scan unusual freqs) while still creating an audit
# record of every weird-freq attempt.
#
# When TX missions land in the future, they should use a STRICTER guardrail
# (hard reject + region-aware) since transmission is the part that gets you
# fined by the regulator, not reception.

CC1101_BANDS_HZ = (
    (300_000_000, 348_000_000),  # US ISM (key fobs, garage doors)
    (387_000_000, 464_000_000),  # EU+US ISM (433.92 MHz center)
    (779_000_000, 928_000_000),  # EU+US ISM (868, 915 MHz)
)


def _check_freq_in_cc1101_band(freq_hz: float) -> Optional[str]:
    """Return None if freq is in a CC1101 band, else a warning string.

    Caller decides whether to surface this to the user, log it, or both.
    Returning a string instead of raising lets us keep the soft-warning policy.
    """
    f = float(freq_hz)
    for lo, hi in CC1101_BANDS_HZ:
        if lo <= f <= hi:
            return None
    bands_human = ", ".join(
        f"{lo / 1e6:.0f}-{hi / 1e6:.0f} MHz" for lo, hi in CC1101_BANDS_HZ
    )
    return (
        f"WARNING: {f / 1e6:.3f} MHz is outside CC1101's supported bands "
        f"({bands_human}). The chip cannot physically tune there \u2014 the "
        f"mission will likely fail silently. If you meant to use this freq "
        f"as a control / null-test, fine; otherwise check the value."
    )


def _prepend_warnings(text: str, warnings: List[str]) -> str:
    """If we have any soft-warnings, surface them at the top of the response."""
    if not warnings:
        return text
    return "\n".join(warnings) + "\n\n" + text


# ---------- JS TEMPLATES (Momentum-class firmware only) -------------------
# Defensive: try/catch around module loads so a missing API doesn't silently
# kill the mission. Every JS mission writes a header + footer to its log.

RF_RSSI_LOG_JS = r"""
// LLMDR RF RSSI LOG (JS backend, Momentum)
// mJS gotchas: no Date, no try/catch, NO IMPLICIT TYPE COERCION.
// All number-to-string concatenation needs explicit .toString().
let FREQ = {freq_hz};
let DURATION_MS = {duration_ms};
let POLL_MS = 250;
let LOG_PATH = "{log_path}";

checkSdkFeatures(["subghz"]);
let storage = require("storage");
let subghz = require("subghz");

let f = storage.openFile(LOG_PATH, "w", "create_always");
f.write("mission=rf_rssi_log\n");
f.write("freq_hz=" + FREQ.toString() + "\n");
f.write("duration_ms=" + DURATION_MS.toString() + "\n");
f.write("poll_ms=" + POLL_MS.toString() + "\n");

subghz.setup();
subghz.setIdle();
subghz.setFrequency(FREQ);
subghz.setRx();

let samples = 0;
let ticks = DURATION_MS / POLL_MS;
for (let i = 0; i < ticks; i++) {{
    let rssi = subghz.getRssi();
    f.write("i=" + i.toString() + " rssi=" + rssi.toString() + "\n");
    samples += 1;
    delay(POLL_MS);
}}

subghz.setIdle();
f.write("samples=" + samples.toString() + "\n");
f.write("finished=true\n");
f.close();
print("rf_rssi_log done samples=" + samples.toString());
""".strip()


PING_JS = r"""
// LLMDR PING (JS backend smoke test)
// NOTE: Momentum's mJS lacks Date, try/catch, and many web-JS globals.
// Stick to: print(), require("storage"), require("notification"),
// require("subghz"), delay(ms), basic operators.
let LOG_PATH = "{log_path}";
let storage = require("storage");
let f = storage.openFile(LOG_PATH, "w", "create_always");
f.write("mission=ping\n");
f.write("runtime=mJS\n");
f.write("ok=true\n");
f.write("finished=true\n");
f.close();
print("ping done");
""".strip()


FREQ_ANALYZER_JS = r"""
// LLMDR FREQUENCY ANALYZER (JS backend, Momentum)
//
// Sweep a list of frequencies, sample RSSI on each, write to log.
// LLM-friendly format: one CSV-like line per (sweep, freq) sample.
//
// mJS gotchas: no Date, no try/catch, NO implicit number-to-string coercion.
// Every numeric value in a string concat needs an explicit .toString().
let FREQS = {freqs_array};
let SWEEPS = {sweeps};
let DWELL_MS = {dwell_ms};
let LOG_PATH = "{log_path}";

checkSdkFeatures(["subghz"]);
let storage = require("storage");
let subghz = require("subghz");

let f = storage.openFile(LOG_PATH, "w", "create_always");
f.write("mission=freq_analyzer\n");
f.write("freqs=" + FREQS.length.toString() + "\n");
f.write("sweeps=" + SWEEPS.toString() + "\n");
f.write("dwell_ms=" + DWELL_MS.toString() + "\n");
f.write("# sweep_no,freq_hz,rssi_dbm\n");

subghz.setup();

for (let s = 0; s < SWEEPS; s++) {{
    for (let i = 0; i < FREQS.length; i++) {{
        let freq = FREQS[i];
        subghz.setIdle();
        subghz.setFrequency(freq);
        subghz.setRx();
        delay(DWELL_MS);
        let rssi = subghz.getRssi();
        f.write(s.toString() + "," + freq.toString() + "," + rssi.toString() + "\n");
    }}
}}

subghz.setIdle();
f.write("finished=true\n");
f.close();
print("freq_analyzer done sweeps=" + SWEEPS.toString());
""".strip()


# ---------- MODULE --------------------------------------------------------

class MissionLibraryModule(FlipperModule):
    """Expose LLMDR's missions as one-call MCP tools."""

    @property
    def name(self) -> str:
        return "llmdr_missions"

    @property
    def version(self) -> str:
        return "0.2.0"

    @property
    def description(self) -> str:
        return "LLMDR mission library: ping (RPC+JS), NFC capture (RPC), Sub-GHz capture (RPC), RF RSSI log (JS)"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="mission_ping",
                description=(
                    "Smoke test: confirms the MCP↔Flipper chain is alive. "
                    "Default backend: RPC (works on every firmware). Optionally tries JS too "
                    "to confirm the JS runtime is available — useful for telling stock OFW from Momentum."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prefer_backend": {
                            "type": "string",
                            "enum": ["rpc", "js", "both"],
                            "default": "rpc",
                            "description": "rpc=just RPC ping; js=push and run a tiny JS; both=run both and compare.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="mission_nfc_capture",
                description=(
                    "RPC backend, works on stock OFW. Snapshot the contents of /ext/nfc/, "
                    "launch the NFC Read app on the device (user taps card on the Flipper), "
                    "wait N seconds, then return any .nfc files that appeared during the window. "
                    "The user must physically tap the card on the Flipper while the NFC app is open."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout_s": {
                            "type": "number",
                            "default": 30,
                            "description": "How long to wait for new .nfc files to appear (1..120).",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="mission_subghz_capture",
                description=(
                    "RPC backend, works on stock OFW. Snapshot /ext/subghz/, launch the Sub-GHz "
                    "Read app on the device (default 433.92 MHz unless the user changes it on-device), "
                    "wait N seconds, then return any .sub files that appeared. The user can leave "
                    "the device on Sub-GHz Read and walk around or wait for a transmission. "
                    "This captures whole signals, not RSSI samples — for that, use mission_rf_rssi_log "
                    "(requires Momentum)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout_s": {
                            "type": "number",
                            "default": 30,
                            "description": "How long to keep the receiver on (1..300).",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="mission_rf_rssi_log",
                description=(
                    "JS backend, requires Momentum-class firmware (the JS subghz module). "
                    "Sits on one frequency, samples RSSI every 250ms, returns the log. "
                    "Will fail on stock OFW with a helpful error pointing at mission_subghz_capture instead. "
                    "Canadian legal frequencies worth trying: 315e6, 433.92e6, 868e6, 915e6."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "freq_hz": {
                            "type": "number",
                            "description": "Frequency in Hz (e.g. 433920000 for 433.92 MHz).",
                        },
                        "duration_s": {
                            "type": "number",
                            "default": 30,
                            "description": "Survey duration in seconds (1..300).",
                        },
                    },
                    "required": ["freq_hz"],
                },
            ),
            Tool(
                name="mission_freq_analyzer",
                description=(
                    "JS backend, requires Momentum-class firmware. Sweep a list of frequencies, "
                    "sample RSSI on each, return a CSV log. The LLM gets eyes on the air: "
                    "this is what the on-device Frequency Analyzer shows visually, but as data. "
                    "Use it to find which frequencies have real signals around you. "
                    "Default freq list covers the main ISM bands: 315, 390, 433.92, 868, 915 MHz. "
                    "Pass a custom freqs_hz array to focus on a narrow band."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "freqs_hz": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": (
                                "List of frequencies in Hz. Default: "
                                "[315000000, 390000000, 433920000, 868000000, 915000000]. "
                                "Each must be in a CC1101-supported band: "
                                "300-348 MHz, 387-464 MHz, or 779-928 MHz."
                            ),
                        },
                        "sweeps": {
                            "type": "number",
                            "default": 10,
                            "description": "Number of times to repeat the full sweep (1..200).",
                        },
                        "dwell_ms": {
                            "type": "number",
                            "default": 100,
                            "description": (
                                "Milliseconds to sit on each freq before sampling RSSI (50..1000). "
                                "Higher = more accurate but slower; total runtime = freqs * sweeps * dwell."
                            ),
                        },
                    },
                    "required": [],
                },
            ),
        ]

    # -- dispatch -------------------------------------------------------

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        args = arguments or {}
        try:
            if tool_name == "mission_ping":
                return await self._mission_ping(args.get("prefer_backend", "rpc"))
            if tool_name == "mission_nfc_capture":
                return await self._mission_nfc_capture(float(args.get("timeout_s", 30)))
            if tool_name == "mission_subghz_capture":
                return await self._mission_subghz_capture(float(args.get("timeout_s", 30)))
            if tool_name == "mission_rf_rssi_log":
                return await self._mission_rf_rssi_log(
                    float(args["freq_hz"]),
                    float(args.get("duration_s", 30)),
                )
            if tool_name == "mission_freq_analyzer":
                return await self._mission_freq_analyzer(
                    args.get("freqs_hz"),
                    int(args.get("sweeps", 10)),
                    int(args.get("dwell_ms", 100)),
                )
        except KeyError as e:
            return [TextContent(type="text", text=f"Missing required arg: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"llmdr_missions error: {type(e).__name__}: {e}")]

        return [TextContent(type="text", text=f"Unknown mission '{tool_name}'")]

    # -- mission: ping --------------------------------------------------

    async def _mission_ping(self, prefer: str) -> Sequence[TextContent]:
        prefer = (prefer or "rpc").lower()
        if prefer not in ("rpc", "js", "both"):
            prefer = "rpc"

        lines: List[str] = []

        if prefer in ("rpc", "both"):
            ok, detail = await self._rpc_ping()
            lines.append(f"[RPC]  {'OK' if ok else 'FAIL'}: {detail}")

        if prefer in ("js", "both"):
            ok, detail = await self._js_ping()
            lines.append(f"[JS]   {'OK' if ok else 'FAIL'}: {detail}")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _rpc_ping(self) -> Tuple[bool, str]:
        # protobuf_ping is the most reliable "RPC alive?" probe in the library.
        try:
            health = await self.flipper.get_connection_health(probe_rpc=True)
        except Exception as e:
            return False, f"health probe raised: {type(e).__name__}: {e}"
        if not health.get("transport_connected"):
            return False, "transport not connected"
        if not health.get("rpc_responsive"):
            return False, "RPC not responsive (transport up, but ping echo failed)"
        echo = health.get("rpc_echo")
        return True, f"echo={echo!r}, transport={health.get('transport', {}).get('type')}"

    async def _js_ping(self) -> Tuple[bool, str]:
        # Push a tiny JS, try every launch strategy, see if the log appears.
        name = "ping"
        log_path = f"{LOG_DIR}/{name}.log"
        mission_path = f"{MISSION_DIR}/{name}.js"
        await self._ensure_dirs()
        # Clear any stale log
        try:
            await self.flipper.storage.delete(log_path)
        except Exception:
            pass
        code = PING_JS.format(log_path=log_path)
        ok = await self.flipper.storage.write(mission_path, code)
        if not ok:
            return False, f"failed to write {mission_path}"
        if self.flipper.rpc is None:
            return False, "RPC not connected"

        launched, how = await self._try_launch_js(mission_path)
        if not launched:
            return False, "no launch strategy succeeded (likely no JS runtime — try Momentum firmware)"

        await asyncio.sleep(1.5)
        content = await self.flipper.storage.read(log_path)
        if not content:
            return False, f"launched via {how} but log not written (JS engine may have rejected the script)"
        head = content.splitlines()[0] if content else ""
        return True, f"launched via {how}, log head: {head!r}"

    # -- mission: nfc capture (RPC) -------------------------------------

    async def _mission_nfc_capture(self, timeout_s: float) -> Sequence[TextContent]:
        timeout_s = max(1.0, min(timeout_s, 120.0))
        nfc_dir = "/ext/nfc"

        # 1. Snapshot existing entries so we only return new ones.
        # Filter to .nfc files only — never directories like 'assets'.
        before = await self._list_files_only(nfc_dir, suffix=".nfc")

        # 2. Launch NFC Read app. Stock OFW: 'NFC' app name.
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="RPC not connected")]
        launched_via = None
        for app_name in ("NFC", "nfc", "Nfc"):
            try:
                if await self.flipper.rpc.app_start(app_name, ""):
                    launched_via = app_name
                    break
            except Exception:
                continue
        if not launched_via:
            return [TextContent(
                type="text",
                text=(
                    "Could not launch the NFC app on the device.\n"
                    "Manually open NFC → Read on the Flipper, tap your card, save it, "
                    "then I can read the file directly via storage_read."
                ),
            )]

        prompt = (
            f"NFC app launched (via app_start({launched_via!r})).\n"
            f"Tap the card on your Flipper now. I'll watch /ext/nfc/ for {int(timeout_s)} seconds.\n"
        )

        # 3. Poll for new files.
        new_files: List[str] = []
        polled_for = 0.0
        poll_interval = 1.5
        while polled_for < timeout_s:
            await asyncio.sleep(poll_interval)
            polled_for += poll_interval
            now = await self._list_files_only(nfc_dir, suffix=".nfc")
            added = sorted(now - before)
            if added:
                new_files = added
                break

        # One last look — saves often land 1-2s after our final poll tick.
        if not new_files:
            await asyncio.sleep(1.5)
            now = await self._list_files_only(nfc_dir, suffix=".nfc")
            new_files = sorted(now - before)

        if not new_files:
            return [TextContent(type="text", text=(
                prompt + f"\nNo new files in {nfc_dir} after {int(timeout_s)}s.\n"
                "Either the card wasn't tapped, the user didn't save it, "
                "or the firmware writes to a different path."
            ))]

        # 4. Read each new file's contents and return them.
        chunks: List[str] = [prompt, f"Captured {len(new_files)} new file(s):"]
        for fname in new_files:
            full = f"{nfc_dir}/{fname}"
            try:
                content = await self.flipper.storage.read(full)
            except Exception as e:
                content = f"<read failed: {e}>"
            chunks.append(f"\n--- {full} ---\n{content}")

        return [TextContent(type="text", text="\n".join(chunks))]

    # -- mission: sub-ghz capture (RPC) ---------------------------------

    async def _mission_subghz_capture(self, timeout_s: float) -> Sequence[TextContent]:
        timeout_s = max(1.0, min(timeout_s, 300.0))
        sub_dir = "/ext/subghz"

        # Filter to .sub files only — Sub-GHz app creates an 'assets' dir on first launch.
        before = await self._list_files_only(sub_dir, suffix=".sub")

        if self.flipper.rpc is None:
            return [TextContent(type="text", text="RPC not connected")]
        launched_via = None
        for app_name in ("Sub-GHz", "SubGhz", "subghz"):
            try:
                if await self.flipper.rpc.app_start(app_name, ""):
                    launched_via = app_name
                    break
            except Exception:
                continue
        if not launched_via:
            return [TextContent(
                type="text",
                text=(
                    "Could not launch the Sub-GHz app on the device.\n"
                    "Manually open Sub-GHz → Read on the Flipper, capture and save signals, "
                    "then I'll read /ext/subghz/ for new files."
                ),
            )]

        prompt = (
            f"Sub-GHz app launched (via app_start({launched_via!r})).\n"
            f"On the device, navigate to Read or Read Raw, then save anything captured.\n"
            f"I'll watch /ext/subghz/ for {int(timeout_s)} seconds.\n"
        )

        new_files: List[str] = []
        polled_for = 0.0
        poll_interval = 2.0
        while polled_for < timeout_s:
            await asyncio.sleep(poll_interval)
            polled_for += poll_interval
            now = await self._list_files_only(sub_dir, suffix=".sub")
            added = sorted(now - before)
            if added:
                new_files = added
                # Don't break — let user save more during the window

        # One last look in case a save just landed.
        if not new_files:
            await asyncio.sleep(1.5)
            now = await self._list_files_only(sub_dir, suffix=".sub")
            new_files = sorted(now - before)

        if not new_files:
            return [TextContent(type="text", text=(
                prompt + f"\nNo new files in {sub_dir} after {int(timeout_s)}s.\n"
                "Save what you captured on the device (Save button on the signal screen) "
                "and run this again, or use Sub-GHz freely and I'll pick up files later."
            ))]

        chunks: List[str] = [prompt, f"Captured {len(new_files)} new file(s):"]
        for fname in new_files:
            full = f"{sub_dir}/{fname}"
            try:
                content = await self.flipper.storage.read(full)
            except Exception as e:
                content = f"<read failed: {e}>"
            # .sub files can be long; trim very aggressive
            if len(content) > 4000:
                content = content[:4000] + "\n... [truncated]"
            chunks.append(f"\n--- {full} ---\n{content}")
        return [TextContent(type="text", text="\n".join(chunks))]

    # -- mission: RF RSSI log (JS) --------------------------------------

    async def _mission_rf_rssi_log(self, freq_hz: float, duration_s: float) -> Sequence[TextContent]:
        duration_s = max(1.0, min(duration_s, 300.0))
        # Soft frequency guardrail — warn if outside CC1101 bands but don't block.
        warnings: List[str] = []
        warn = _check_freq_in_cc1101_band(freq_hz)
        if warn:
            log.warning("rf_rssi_log out-of-band freq: %s Hz", int(freq_hz))
            warnings.append(warn)
        name = f"rf_rssi_log_{int(freq_hz / 1000)}khz_{int(duration_s)}s"
        log_path = f"{LOG_DIR}/{name}.log"
        mission_path = f"{MISSION_DIR}/{name}.js"
        await self._ensure_dirs()
        code = RF_RSSI_LOG_JS.format(
            freq_hz=int(freq_hz),
            duration_ms=int(duration_s * 1000),
            log_path=log_path,
        )
        ok = await self.flipper.storage.write(mission_path, code)
        if not ok:
            return [TextContent(type="text", text=_prepend_warnings(f"Failed to write mission to {mission_path}", warnings))]
        if self.flipper.rpc is None:
            return [TextContent(type="text", text=_prepend_warnings("RPC not connected", warnings))]

        # Launch via CLI 'js <path>' — this BLOCKS until the JS script exits.
        # Plain English: previously we used a fire-and-forget launch + fixed sleep
        # of duration_s+3, then read the log. On slow SD cards the JS was still
        # writing when we read, so we returned partial logs (sometimes empty)
        # and reported "mission failed" when it actually succeeded.
        # Using cli_command makes us wait for the script's actual exit, plus the
        # built-in 250ms post-CLI settle delay handles any final SD flush.
        # Same pattern mission_freq_analyzer already uses; matches it now.
        # Generous CLI timeout: duration + 30s buffer for script setup/teardown.
        cli_timeout = max(30.0, duration_s + 30.0)
        try:
            cli_out = await self.flipper.rpc.cli_command(f"js {mission_path}", timeout_s=cli_timeout)
        except Exception as e:
            return [TextContent(type="text", text=_prepend_warnings(f"CLI launch failed: {type(e).__name__}: {e}", warnings))]

        if cli_out and ("unknown command" in cli_out.lower() or "command not found" in cli_out.lower()):
            return [TextContent(
                type="text",
                text=_prepend_warnings((
                    "Could not launch the JS mission. The connected firmware does not appear "
                    "to have a JS runtime that accepts .js launches. This mission needs the "
                    "Momentum-class JS subghz module.\n\n"
                    "Try mission_subghz_capture instead \u2014 it works on stock OFW by driving "
                    "the on-device Sub-GHz app and watching /ext/subghz/ for new files.\n\n"
                    f"CLI output:\n{cli_out}"
                ), warnings),
            )]

        # Read the log back. cli_command's 250ms post-settle should mean the
        # SD has flushed by now. If the file is still empty, the JS engine
        # actually rejected the script - that's a real failure to report.
        content = await self.flipper.storage.read(log_path)
        if not content:
            return [TextContent(type="text", text=_prepend_warnings((
                f"Mission launched but log at {log_path} is empty.\n"
                f"The JS engine may have rejected the script, or the runtime is a stub.\n\n"
                f"CLI output was:\n{cli_out[:2000]}"
            ), warnings))]

        # Verify the script actually finished. The JS template writes
        # 'finished=true' as its last log line. If we don't see it, the script
        # was killed mid-run (timeout, crash, user pressed back) and Claude
        # should know the data is partial rather than treat it as authoritative.
        finished_marker = "finished=true"
        is_complete = finished_marker in content
        completion_note = (
            "" if is_complete
            else f"\n\nWARNING: log does not contain '{finished_marker}'. "
                 f"The mission may have been cut short (timeout or crash). "
                 f"Treat samples as partial data, not a full sweep.\n"
        )

        return [TextContent(type="text", text=_prepend_warnings(
            f"Mission complete (launched via cli('js {mission_path}'))"
            f"{completion_note}\n\nLog:\n\n{content}",
            warnings,
        ))]

    # -- mission: frequency analyzer (JS) -------------------------------

    async def _mission_freq_analyzer(
        self,
        freqs_hz: Optional[List[float]],
        sweeps: int,
        dwell_ms: int,
    ) -> Sequence[TextContent]:
        # Default: classic ISM-band sweep (300-928 MHz friendly).
        if not freqs_hz:
            freqs_hz = [
                315_000_000,
                390_000_000,
                433_920_000,
                868_000_000,
                915_000_000,
            ]
        # Bound parameters defensively.
        sweeps = max(1, min(int(sweeps), 200))
        dwell_ms = max(50, min(int(dwell_ms), 1000))
        # Soft frequency guardrail — warn for any out-of-band freq in the list,
        # but pass them all through. Each weird freq gets its own log entry so
        # we keep an audit trail.
        warnings: List[str] = []
        for f in freqs_hz:
            warn = _check_freq_in_cc1101_band(f)
            if warn:
                log.warning("freq_analyzer out-of-band freq: %s Hz", int(f))
                warnings.append(warn)
        # Build a JS array literal — mJS understands the same syntax.
        freqs_js = "[" + ", ".join(str(int(f)) for f in freqs_hz) + "]"

        name = f"freq_analyzer_{len(freqs_hz)}f_{sweeps}s_{dwell_ms}ms"
        log_path = f"{LOG_DIR}/{name}.log"
        mission_path = f"{MISSION_DIR}/{name}.js"
        await self._ensure_dirs()
        code = FREQ_ANALYZER_JS.format(
            freqs_array=freqs_js,
            sweeps=sweeps,
            dwell_ms=dwell_ms,
            log_path=log_path,
        )
        ok = await self.flipper.storage.write(mission_path, code)
        if not ok:
            return [TextContent(type="text", text=_prepend_warnings(f"Failed to write mission to {mission_path}", warnings))]
        if self.flipper.rpc is None:
            return [TextContent(type="text", text=_prepend_warnings("RPC not connected", warnings))]

        # Estimate runtime: sweeps * freqs * dwell_ms + overhead.
        # Add 5s buffer for setup/teardown + log flush.
        estimated_runtime_s = (sweeps * len(freqs_hz) * dwell_ms / 1000.0) + 5.0
        # cli_command will block for the script's runtime, so set a generous timeout.
        cli_timeout = max(30.0, estimated_runtime_s + 30.0)

        # Launch via CLI 'js <path>'. This blocks until the script finishes.
        try:
            cli_out = await self.flipper.rpc.cli_command(f"js {mission_path}", timeout_s=cli_timeout)
        except Exception as e:
            return [TextContent(type="text", text=_prepend_warnings(f"CLI launch failed: {type(e).__name__}: {e}", warnings))]

        if cli_out and ("unknown command" in cli_out.lower() or "command not found" in cli_out.lower()):
            return [TextContent(
                type="text",
                text=_prepend_warnings((
                    "This firmware doesn't have the 'js' CLI command. "
                    "Need Momentum-class firmware for mission_freq_analyzer.\n\n"
                    f"CLI output:\n{cli_out}"
                ), warnings),
            )]

        # Read the log back.
        content = await self.flipper.storage.read(log_path)
        if not content:
            return [TextContent(type="text", text=_prepend_warnings((
                f"freq_analyzer launched but log at {log_path} is empty.\n\n"
                f"CLI output was:\n{cli_out[:2000]}"
            ), warnings))]

        # Quick analysis: per-frequency mean RSSI to highlight active bands.
        # Log format: header lines + '# sweep_no,freq_hz,rssi_dbm' + data rows + 'finished=true'
        per_freq_samples: dict = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" in line:
                continue
            parts = line.split(",")
            if len(parts) != 3:
                continue
            try:
                _sweep_no = int(parts[0])
                freq = int(parts[1])
                rssi = float(parts[2])
            except ValueError:
                continue
            per_freq_samples.setdefault(freq, []).append(rssi)

        summary_lines: List[str] = [f"freq_analyzer mission complete. {sweeps} sweeps x {len(freqs_hz)} freqs."]
        # Verify the script actually finished. The JS template writes
        # 'finished=true' as its last log line. If absent, the sweep was cut
        # short and the mean-RSSI ranking would be calculated over partial data
        # — Claude must NOT treat that as authoritative "loudest bands" info.
        if "finished=true" not in content:
            summary_lines.append(
                "\nWARNING: log is missing 'finished=true'. The sweep was cut "
                "short (timeout/crash/back-button). Treat the per-frequency "
                "means below as partial data, NOT a complete survey."
            )
        if per_freq_samples:
            summary_lines.append("\nMean RSSI per frequency (higher = more signal energy; -90 dBm is noise floor):\n")
            # Sort by mean RSSI descending so loudest bands surface first.
            ranked = sorted(
                per_freq_samples.items(),
                key=lambda kv: -(sum(kv[1]) / len(kv[1])),
            )
            for freq, samples in ranked:
                mean = sum(samples) / len(samples)
                peak = max(samples)
                mhz = freq / 1_000_000
                summary_lines.append(f"  {mhz:8.3f} MHz : mean={mean:6.1f} dBm  peak={peak:6.1f} dBm  n={len(samples)}")
            summary_lines.append("")
            summary_lines.append("Interpretation hints:")
            summary_lines.append("  > -70 dBm  : strong signal, something is broadcasting")
            summary_lines.append("  -70..-85   : moderate / nearby noise")
            summary_lines.append("  < -85 dBm  : near noise floor, probably empty")

        # Cap raw log to avoid blowing the response. Show last lines preferentially —
        # they include the 'finished=true' marker we want to confirm.
        raw_tail = content
        if len(content) > 6000:
            raw_tail = content[-6000:]
            raw_tail = "... [head truncated, " + str(len(content)) + " total chars]\n" + raw_tail
        summary_lines.append("\nRaw log (file contents, not CLI capture):\n")
        summary_lines.append(raw_tail)

        return [TextContent(type="text", text=_prepend_warnings("\n".join(summary_lines), warnings))]

    # -- helpers --------------------------------------------------------

    async def _ensure_dirs(self) -> None:
        await self.flipper.storage.mkdir("/ext/apps_data")
        await self.flipper.storage.mkdir(MISSION_DIR)
        await self.flipper.storage.mkdir(LOG_DIR)

    async def _list_files_only(self, path: str, suffix: Optional[str] = None) -> set:
        """
        List FILES (not directories) in a directory.

        Plain English: in /ext/nfc/, the firmware creates an 'assets' subdirectory
        on first NFC app launch. The OLD bug-fix used a suffix heuristic to filter
        that out, but that fails if a directory's name happens to match the suffix
        (e.g. an imported folder structure named 'evil_dir.nfc'). The fix uses
        storage.list_detailed() which actually returns type info from the firmware
        protobuf, so we can filter on type=='FILE' explicitly.

        Args:
            path: directory to list (e.g. /ext/nfc)
            suffix: optional file extension filter (e.g. '.nfc', '.sub')

        Returns:
            set of filenames (NOT directory names) in `path`, optionally filtered
            by extension. Returns empty set on any error.
        """
        try:
            entries = await self.flipper.storage.list_detailed(path)
        except Exception as e:
            log.warning("_list_files_only(%r) failed: %s", path, e)
            return set()
        files = set()
        for entry in entries:
            # storage.list_detailed returns dicts with {name, type, size}.
            if entry.get("type") != "FILE":
                continue
            name = entry.get("name", "")
            if not name:
                continue
            if suffix and not name.endswith(suffix):
                continue
            files.add(name)
        return files

    async def _try_launch_js(self, mission_path: str) -> Tuple[bool, Optional[str]]:
        """Try every known JS launch strategy. Returns (success, label-of-winner)."""
        # PRIMARY: CLI `js <path>` — the documented and most reliable path on both
        # Momentum and stock OFW with JS support.
        try:
            cli_out = await self.flipper.rpc.cli_command(f"js {mission_path}", timeout_s=120.0)
            if cli_out and "unknown command" not in cli_out.lower() and "command not found" not in cli_out.lower():
                return True, f"cli('js {mission_path}')"
        except Exception:
            pass
        # FALLBACK 1: app_load_file (older OFW built-in handler routing)
        try:
            if await self.flipper.rpc.app_load_file(mission_path):
                return True, "app_load_file"
        except Exception:
            pass
        # FALLBACK 2: app_start with named app (Momentum-fork variants)
        for app_name in ("js_app", "JS"):
            try:
                if await self.flipper.rpc.app_start(app_name, mission_path):
                    return True, f"app_start({app_name!r})"
            except Exception:
                continue
        # FALLBACK 3: app_start with path-as-app (some OFW builds)
        try:
            if await self.flipper.rpc.app_start(mission_path, ""):
                return True, "app_start(<path>, '')"
        except Exception:
            pass
        return False, None

    # -- lifecycle ------------------------------------------------------

    def get_dependencies(self) -> List[str]:
        return []

    def requires_sd_card(self) -> bool:
        return True

    def validate_environment(self) -> tuple[bool, str]:
        return True, ""
