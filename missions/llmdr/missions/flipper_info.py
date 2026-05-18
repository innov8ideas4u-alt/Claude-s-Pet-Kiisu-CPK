"""Flipper info — read the `flipper` JS global's identity fields.

The bonus mission for the Day 6 morning kit. Picked because:
  - Pure RX / observation (matches the morning kit's RX-only policy).
  - <60 lines of JS.
  - Useful for a morning demo (confirms identity from a SECOND
    independent source — JS-side, complementing device_inventory's
    RPC-side read).

If `device_inventory.firmware` and `flipper_info.firmware_vendor`
disagree, you've got a bug worth investigating.

HOW TO FIRE (Victor + Claude Desktop):
    Ask Claude: "Run the Flipper info mission"

WHAT YOU SHOULD HEAR/SEE:
    - First beep + screen wake
    - <1 second of silent activity
    - Second beep at end
    - Claude reports name, model, battery %, firmware vendor, JS SDK ver

EXPECTED LOG SHAPE:
    mission=flipper_info
    step=loaded
    device_name=Kiisu_AmorPoee
    device_model=kiisu v4b
    battery_pct=87
    firmware_vendor=Momentum
    js_sdk_major=1
    js_sdk_minor=0
    finished=true
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
    / "flipper_info.js"
)
JS_SOURCE = _JS_PATH.read_text(encoding="utf-8")

MISSION_NAME = "flipper_info"
DEFAULT_WAIT_SECONDS = 2.0


@dataclass
class FlipperInfoReport:
    device_name: str = ""
    device_model: str = ""
    battery_pct: int | None = None
    firmware_vendor: str = ""
    js_sdk_major: int | None = None
    js_sdk_minor: int | None = None
    finished: bool = False
    raw_log: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        bits = []
        if self.device_name:
            bits.append(self.device_name)
        if self.device_model:
            bits.append(f"model={self.device_model}")
        if self.firmware_vendor:
            bits.append(f"vendor={self.firmware_vendor}")
        if self.battery_pct is not None:
            bits.append(f"battery={self.battery_pct}%")
        if self.js_sdk_major is not None:
            ver = f"{self.js_sdk_major}.{self.js_sdk_minor or 0}"
            bits.append(f"jsSdk={ver}")
        out = " | ".join(bits) if bits else "(no fields parsed)"
        if not self.finished:
            out += " | NOT FINISHED"
        if self.warnings:
            out += " | warnings: " + "; ".join(self.warnings)
        return out


async def run(
    client: Any,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
) -> FlipperInfoReport:
    """Run flipper_info. Returns a `FlipperInfoReport`."""
    raw, parsed, elapsed_ms, warnings = await run_js_mission(
        client=client,
        mission_name=MISSION_NAME,
        js_source=JS_SOURCE,
        wait_seconds=wait_seconds,
    )

    rep = FlipperInfoReport(
        raw_log=raw,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
        finished=parsed.get("finished") == "true",
        device_name=parsed.get("device_name", ""),
        device_model=parsed.get("device_model", ""),
        firmware_vendor=parsed.get("firmware_vendor", ""),
    )
    try:
        if "battery_pct" in parsed:
            rep.battery_pct = int(float(parsed["battery_pct"]))
    except ValueError:
        warnings.append(f"could not parse battery_pct={parsed.get('battery_pct')!r}")
    try:
        if "js_sdk_major" in parsed:
            rep.js_sdk_major = int(parsed["js_sdk_major"])
        if "js_sdk_minor" in parsed:
            rep.js_sdk_minor = int(parsed["js_sdk_minor"])
    except ValueError:
        warnings.append("could not parse js_sdk_(major|minor)")
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
