"""Radio handshake mission — RX-only.

Probes Sub-GHz, GPIO, Storage, Notification modules in sequence
without emitting any RF. Verifies each responds and logs results.

This is the CPK equivalent of `ping` for the radio subsystems — call it
first thing in the morning to confirm every radio path is alive.

HOW TO FIRE (Victor + Claude Desktop):
    Ask Claude: "Run the radio handshake mission"
    Claude will:
      1. push missions/handshake/radio_handshake.js to /ext/apps_data/mcp_missions/
      2. call the JS Runner with the validated launch + cleanup recipe
      3. read the log
      4. parse it into a RadioHandshakeReport dataclass
      5. report back

WHAT YOU SHOULD HEAR/SEE:
    - First beep + screen wake (notification.success at start)
    - Blue LED brief blink mid-mission (notification.blink "blue" "short")
    - Second beep at end
    - Claude reports parsed results: subghz_ok, rssi_433_92, gpio states,
      ext_apps_count, notification_blink_ok

EXPECTED LOG SHAPE:
    mission=radio_handshake
    step=loaded
    subghz_ok=true
    rssi_433_92=<some int, typically -90 to -120 dBm>
    step=subghz_done
    gpio_p2=<0 or 1>
    gpio_p4=<0 or 1>
    gpio_p5=<0 or 1>
    gpio_p6=<0 or 1>
    gpio_p7=<0 or 1>
    step=gpio_done
    ext_apps_count=<int>
    step=storage_done
    notification_blink_ok=true
    step=notification_done
    uncertain_modules=infrared,bluetooth
    finished=true

WHY infrared AND bluetooth ARE INTENTIONALLY SKIPPED:
    - `infrared` module exposes sendSignal / sendRawSignal only (TX-side).
      No RX-side bindings in mntm-dev. Including it would require TX,
      which is OUT OF SCOPE for the morning kit (RX-only by policy).
    - `bluetooth` is not a JS-callable module on mntm-dev. `blebeacon`
      exists but is TX-only (advertising). RX/scan API is not bound.
      See `ble_passive_scan` mission for the documented best-effort.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._runner import run_js_mission

# .js source is on disk next to the repo so the file is the source of
# truth (lint-able, diff-able). The helper reads it at import time.
_JS_PATH = (
    Path(__file__).resolve().parents[3] / "missions" / "handshake" / "radio_handshake.js"
)
JS_SOURCE = _JS_PATH.read_text(encoding="utf-8")

MISSION_NAME = "radio_handshake"
DEFAULT_WAIT_SECONDS = 6.0  # enough for delay(200) + GPIO loop + readDirectory


@dataclass
class RadioHandshakeReport:
    """Parsed result of one radio-handshake run."""

    subghz_ok: bool = False
    rssi_433_92: int | None = None
    gpio_states: dict[int, int] = field(default_factory=dict)
    ext_apps_count: int = 0
    notification_blink_ok: bool = False
    uncertain_modules: list[str] = field(default_factory=list)
    finished: bool = False
    last_step: str = ""
    raw_log: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        parts: list[str] = []
        parts.append(f"subghz: {'OK' if self.subghz_ok else 'FAIL'}")
        if self.rssi_433_92 is not None:
            parts.append(f"433.92 MHz RSSI {self.rssi_433_92} dBm")
        if self.gpio_states:
            gpio_str = " ".join(
                f"p{p}={s}" for p, s in sorted(self.gpio_states.items())
            )
            parts.append(f"gpio {gpio_str}")
        parts.append(f"/ext/apps entries: {self.ext_apps_count}")
        parts.append(f"notification blink: {'OK' if self.notification_blink_ok else 'FAIL'}")
        if self.uncertain_modules:
            parts.append(f"intentionally skipped: {', '.join(self.uncertain_modules)}")
        if not self.finished:
            parts.append(f"NOT FINISHED — last step: {self.last_step or 'unknown'}")
        if self.warnings:
            parts.append("warnings: " + "; ".join(self.warnings))
        return " | ".join(parts)


def _parse(parsed: dict[str, Any], raw: str, warnings: list[str], elapsed_ms: int) -> RadioHandshakeReport:
    rep = RadioHandshakeReport(raw_log=raw, warnings=warnings, elapsed_ms=elapsed_ms)
    rep.subghz_ok = parsed.get("subghz_ok") == "true"
    rssi_raw = parsed.get("rssi_433_92")
    if rssi_raw and rssi_raw != "undefined":
        try:
            rep.rssi_433_92 = int(float(rssi_raw))
        except ValueError:
            warnings.append(f"could not parse rssi_433_92={rssi_raw!r}")
    for pin in (2, 4, 5, 6, 7):
        key = f"gpio_p{pin}"
        val = parsed.get(key)
        if val in ("0", "1"):
            rep.gpio_states[pin] = int(val)
        elif val == "getfail":
            warnings.append(f"gpio.get({pin}) returned falsy on device")
    try:
        rep.ext_apps_count = int(parsed.get("ext_apps_count", "0"))
    except ValueError:
        pass
    rep.notification_blink_ok = parsed.get("notification_blink_ok") == "true"
    uncertain = parsed.get("uncertain_modules", "")
    if uncertain:
        rep.uncertain_modules = [s.strip() for s in uncertain.split(",") if s.strip()]
    rep.finished = parsed.get("finished") == "true"
    # last_step = highest step= seen (the parser collapses repeats into a list).
    steps = parsed.get("step", "")
    if isinstance(steps, list):
        rep.last_step = steps[-1]
    elif isinstance(steps, str):
        rep.last_step = steps
    return rep


async def run(
    client: Any,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
) -> RadioHandshakeReport:
    """Run the radio handshake mission. Returns a `RadioHandshakeReport`.

    Never raises — failures surface as warnings + `finished=False` on the report.
    """
    raw, parsed, elapsed_ms, warnings = await run_js_mission(
        client=client,
        mission_name=MISSION_NAME,
        js_source=JS_SOURCE,
        wait_seconds=wait_seconds,
    )
    return _parse(parsed, raw, warnings, elapsed_ms)


if __name__ == "__main__":
    # Manual smoke test: requires a real connected Flipper. Do not run
    # this from the autonomous cook environment.
    from flipper_mcp.core.flipper_client import FlipperClient
    from flipper_mcp.core.transport.usb import USBTransport

    async def _main() -> int:
        transport = USBTransport(config={})
        client = FlipperClient(transport)
        if not await client.connect():
            print(f"connect failed: {client.last_connection_error}")
            return 1
        try:
            report = await run(client)
            print(report.summary())
            print(f"\nelapsed_ms: {report.elapsed_ms}")
            print(f"\n--- raw log ---\n{report.raw_log}")
        finally:
            await client.disconnect()
        return 0

    raise SystemExit(asyncio.run(_main()))
