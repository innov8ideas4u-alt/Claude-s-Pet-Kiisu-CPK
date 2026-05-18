"""BLE passive scan — BEST EFFORT mission, documented non-support.

Investigated Momentum's `blebeacon` JS module and concluded BLE RX is
not bound in mJS on mntm-dev. Rather than skip the mission, we fire it
anyway so the morning-kit log records the non-support fact and
preserves the reasoning for future contributors.

HOW TO FIRE (Victor + Claude Desktop):
    Ask Claude: "Run the BLE passive scan mission"

WHAT YOU SHOULD HEAR/SEE:
    - First beep + screen wake
    - ~1 second of silent activity
    - Second beep at end
    - Claude reports `ble_supported=false` with rationale

WHY THIS ISN'T IMPLEMENTED FOR REAL:
    Per docs/KIISU_DEEP_KNOWLEDGE.md §2.1 + §2.7, the only BLE-related
    JS module on mntm-dev is `blebeacon`, which is TX-only (advertising).
    The Flipper firmware DOES have BLE RX internally (its own BLE
    pairing flow uses it), but it's not exposed to mJS. To get a scan
    we'd need either:
      1. A firmware-side patch adding `js_bluetooth.c` with scan bindings.
      2. An external BLE dongle + UART bridge.
      3. A phone app for the scan and pair Flipper for upload.

    Option 1 is the cleanest long-term fix. Listed in
    docs/MISSIONS_COOKBOOK.md as a stretch goal.

EXPECTED LOG SHAPE:
    mission=ble_passive_scan
    step=loaded
    ble_supported=false
    reason=no_rx_module_bound_in_mjs
    available_jsmodules=blebeacon_only
    blebeacon_is_tx=true
    what_we_wanted=passive_scan_with_name_and_rssi_per_device
    workaround=use_external_ble_dongle_or_phone_app
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
    / "ble_passive_scan.js"
)
JS_SOURCE = _JS_PATH.read_text(encoding="utf-8")

MISSION_NAME = "ble_passive_scan"
DEFAULT_WAIT_SECONDS = 2.0


@dataclass
class BlePassiveScanReport:
    ble_supported: bool = False
    reason: str = ""
    workaround: str = ""
    finished: bool = False
    raw_log: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        if self.ble_supported:
            return f"BLE scan returned data — see raw_log for details (warnings: {self.warnings})"
        parts = [f"BLE not supported in mJS ({self.reason or 'unknown'})"]
        if self.workaround:
            parts.append(f"workaround: {self.workaround}")
        if not self.finished:
            parts.append("NOT FINISHED")
        if self.warnings:
            parts.append("warnings: " + "; ".join(self.warnings))
        return " | ".join(parts)


async def run(
    client: Any,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
) -> BlePassiveScanReport:
    """Run the BLE passive scan (documents non-support). Returns a report."""
    raw, parsed, elapsed_ms, warnings = await run_js_mission(
        client=client,
        mission_name=MISSION_NAME,
        js_source=JS_SOURCE,
        wait_seconds=wait_seconds,
    )
    return BlePassiveScanReport(
        ble_supported=parsed.get("ble_supported") == "true",
        reason=parsed.get("reason", ""),
        workaround=parsed.get("workaround", ""),
        finished=parsed.get("finished") == "true",
        raw_log=raw,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


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
