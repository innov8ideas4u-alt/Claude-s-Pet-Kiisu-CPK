"""GPIO full read — single snapshot of every Flipper user GPIO pin.

Configures each pin (2, 3, 4, 5, 6, 7, 10, 12, 13, 14, 15, 16, 17) as
a plain-digital input with no pull, reads the state, returns a dict.

Useful for "what's connected to my header right now" — if a pin is
externally pulled HIGH or LOW it'll show up; floating pins will read
noise (expected, not a failure).

HOW TO FIRE (Victor + Claude Desktop):
    Ask Claude: "Run the GPIO full read mission"

WHAT YOU SHOULD HEAR/SEE:
    - First beep + screen wake
    - ~1 second of silent activity
    - Second beep at end
    - Claude shows pin states. Anything you wired up to a known level
      (LED with pulldown, button to ground, etc.) should show its
      actual value; unwired pins are noise.

EXPECTED LOG SHAPE:
    mission=gpio_full_read
    step=loaded
    gpio_p2=0
    gpio_p3=1
    ...
    gpio_p17=0
    pins_read=13
    pins_attempted=13
    finished=true

CAVEATS:
    - Floating inputs are noise — don't read meaning into them.
    - We don't write to any pin, so devices wired to outputs are safe.
    - The Flipper header pin numbers are header positions, not STM32
      pin names. The mJS `gpio.get(n)` accepts header positions.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._runner import run_js_mission

_JS_PATH = (
    Path(__file__).resolve().parents[3]
    / "missions"
    / "handshake"
    / "gpio_full_read.js"
)
JS_SOURCE = _JS_PATH.read_text(encoding="utf-8")

MISSION_NAME = "gpio_full_read"
DEFAULT_WAIT_SECONDS = 3.0

PINS = (2, 3, 4, 5, 6, 7, 10, 12, 13, 14, 15, 16, 17)


@dataclass
class GpioFullReadReport:
    pin_states: dict[int, int] = field(default_factory=dict)
    pins_read: int = 0
    pins_attempted: int = 0
    failed_pins: list[int] = field(default_factory=list)
    finished: bool = False
    raw_log: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        if not self.pin_states and not self.failed_pins:
            return f"no pin data (warnings: {'; '.join(self.warnings) or 'none'})"
        rows = " ".join(
            f"p{p}={s}" for p, s in sorted(self.pin_states.items())
        )
        head = f"{self.pins_read}/{self.pins_attempted} pins read"
        if not self.finished:
            head += " (NOT FINISHED — script aborted)"
        out = f"{head}: {rows}"
        if self.failed_pins:
            out += f" | gpio.get fail: {sorted(self.failed_pins)}"
        if self.warnings:
            out += "\nwarnings: " + "; ".join(self.warnings)
        return out


async def run(
    client: Any,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
) -> GpioFullReadReport:
    """Run the GPIO full read. Returns a `GpioFullReadReport`."""
    raw, parsed, elapsed_ms, warnings = await run_js_mission(
        client=client,
        mission_name=MISSION_NAME,
        js_source=JS_SOURCE,
        wait_seconds=wait_seconds,
    )

    rep = GpioFullReadReport(
        raw_log=raw,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
        finished=parsed.get("finished") == "true",
    )
    for pin in PINS:
        v = parsed.get(f"gpio_p{pin}")
        if v in ("0", "1"):
            rep.pin_states[pin] = int(v)
        elif v == "getfail":
            rep.failed_pins.append(pin)
    try:
        rep.pins_read = int(parsed.get("pins_read", "0"))
        rep.pins_attempted = int(parsed.get("pins_attempted", str(len(PINS))))
    except ValueError:
        pass
    return rep


if __name__ == "__main__":
    from flipper_mcp.core.flipper_client import FlipperClient
    from flipper_mcp.core.transport.usb import USBTransport

    async def _main() -> int:
        transport = USBTransport(config={})
        client = FlipperClient(transport)
        if not await client.connect():
            print(f"connect failed: {client.last_connection_error}")
            return 1
        try:
            print((await run(client)).summary())
        finally:
            await client.disconnect()
        return 0

    raise SystemExit(asyncio.run(_main()))
