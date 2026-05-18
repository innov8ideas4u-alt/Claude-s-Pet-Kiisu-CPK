"""Device inventory mission — pure host-side, no JS.

Composes existing primitives into one "everything about this Flipper
right now" report. Calls only host-side / RPC primitives that already
exist in the codebase; no new firmware reach, no risk surface.

Composition:
  - `client.get_connection_health()` — transport + RPC ping
  - `client.get_device_info()` — name, hardware, firmware
  - `client.rpc.app_lock_status()` — app-loader mutex state
  - `client.rpc.desktop_is_locked()` — real lockscreen state
  - `storage_health_check.run()` — total/free space + top dirs
    (reuse the function from Day 5.5 — don't re-derive)

HOW TO FIRE (Victor + Claude Desktop):
    Ask Claude: "Run the device inventory mission"

WHAT YOU SHOULD HEAR/SEE:
    - Nothing on the device — this is purely host-side. No beeps, no
      screen wake, no LED activity.
    - Claude reports a structured summary: device name, firmware,
      connection state, lock state, storage health.

EXPECTED OUTPUT:
    DeviceInventoryReport(
      device_name='Kiisu_AmorPoee',
      hardware='kiisu v4b',
      firmware='Momentum mntm-dev',
      transport='usb:COM9',
      connected=True,
      desktop_locked=False,
      app_running=False,
      storage=StorageHealthReport(...),
    )
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from .storage_health_check import StorageHealthReport, run as storage_health_run


@dataclass
class DeviceInventoryReport:
    """One-shot snapshot of the Flipper's identity + state."""

    device_name: str = ""
    hardware: str = ""
    firmware: str = ""
    firmware_vendor: str = ""
    serial_number: str = ""
    transport: str = ""
    connected: bool = False
    transport_connected: bool = False
    rpc_responsive: bool = False
    desktop_locked: Optional[bool] = None
    app_running: Optional[bool] = None
    storage: Optional[StorageHealthReport] = None
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        parts: list[str] = []
        # Identity
        ident_bits = []
        if self.device_name:
            ident_bits.append(self.device_name)
        if self.hardware:
            ident_bits.append(f"hw={self.hardware}")
        if self.firmware:
            ident_bits.append(f"fw={self.firmware}")
        if ident_bits:
            parts.append("Device: " + ", ".join(ident_bits))
        # Connection
        conn_str = "connected" if self.connected else "DISCONNECTED"
        if self.transport:
            conn_str += f" via {self.transport}"
        parts.append(conn_str)
        # State
        if self.desktop_locked is True:
            parts.append("desktop LOCKED")
        elif self.desktop_locked is False:
            parts.append("desktop unlocked")
        if self.app_running is True:
            parts.append("app loader BUSY (another app running)")
        # Storage (delegates to its own summary)
        if self.storage is not None:
            parts.append("storage: " + self.storage.summary())
        if self.warnings:
            parts.append("warnings: " + "; ".join(self.warnings))
        return "\n  ".join(parts)


def _format_transport(health: dict[str, Any]) -> str:
    t = health.get("transport") or {}
    ttype = t.get("type") or ""
    if ttype.startswith("usb") or "USB" in ttype:
        return f"usb:{t.get('port', '?')}"
    if ttype.startswith("wifi") or "WiFi" in ttype:
        return f"wifi:{t.get('host', '?')}:{t.get('port', '?')}"
    return ttype or "unknown"


async def run(client: Any) -> DeviceInventoryReport:
    """Run device inventory. Never raises — failures surface as warnings."""
    import time

    started = time.monotonic()
    warnings: list[str] = []
    rep = DeviceInventoryReport()

    # 1) Connection health — single authoritative source.
    try:
        health = await client.get_connection_health(probe_rpc=True)
    except Exception as e:
        warnings.append(f"get_connection_health raised {type(e).__name__}: {e}")
        health = {}
    rep.connected = bool(health.get("connected"))
    rep.transport_connected = bool(health.get("transport_connected"))
    rep.rpc_responsive = bool(health.get("rpc_responsive"))
    rep.transport = _format_transport(health)
    if health.get("last_error"):
        warnings.append(f"connection last_error: {health['last_error']}")

    # 2) Device identity (only meaningful if RPC is alive).
    if rep.rpc_responsive:
        try:
            info = await client.get_device_info()
            rep.device_name = str(info.get("name") or "")
            rep.hardware = str(
                info.get("hardware_model")
                or info.get("hardware")
                or ""
            )
            rep.firmware = str(
                info.get("firmware_version")
                or info.get("firmware")
                or ""
            )
            rep.firmware_vendor = str(info.get("firmware_vendor") or "")
            rep.serial_number = str(info.get("serial_number") or "")
        except Exception as e:
            warnings.append(f"get_device_info raised {type(e).__name__}: {e}")
    else:
        warnings.append("RPC unresponsive — skipping device_info and lock probes")

    # 3) Lock state — both layers, because they mean different things
    # (see docs/for_ai_contributors.md "Things we already learned" #5/#6).
    if rep.rpc_responsive and getattr(client, "rpc", None):
        try:
            rep.desktop_locked = await client.rpc.desktop_is_locked()
        except Exception as e:
            warnings.append(f"desktop_is_locked raised {type(e).__name__}: {e}")
        try:
            rep.app_running = await client.rpc.app_lock_status()
        except Exception as e:
            warnings.append(f"app_lock_status raised {type(e).__name__}: {e}")

    # 4) Storage health — delegate to storage_health_check.run().
    if rep.rpc_responsive:
        try:
            rep.storage = await storage_health_run(client)
        except Exception as e:
            warnings.append(f"storage_health_check.run raised {type(e).__name__}: {e}")

    rep.warnings = warnings
    rep.elapsed_ms = int((time.monotonic() - started) * 1000)
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
