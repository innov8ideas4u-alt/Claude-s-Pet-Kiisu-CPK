"""Storage health check mission.

The first ship-able, end-to-end CPK mission. Pure host-side — no JS, no
hardware quirks beyond what FlipperClient already abstracts. Suitable as
a reference for what a "real mission" looks like in this codebase.

What it does:
  1. Reads `storage_info` for /int (internal flash) and /ext (SD card).
  2. Lists the top-level directories on each volume.
  3. Computes free / used / used-pct and surfaces threshold warnings.
  4. Returns a `StorageHealthReport` dataclass — easy to log, display, or
     alert on. Has a `summary()` for human-readable output.

Why this is a useful mission to ship first:
  - Zero hardware risk. RX-only at most — no RF, no GUI input, no JS.
  - Exercises both `client.rpc.storage_info()` and `client.storage.list_detailed()`.
  - Demonstrates the host-side workaround for `storage.fsInfo()` (broken
    JS binding on mntm-dev — see docs/for_ai_contributors.md).
  - Trivial to mock for tests — no event loops on the device, no timing,
    no protocol weirdness.

What it deliberately does NOT do:
  - No MCP tool wrapper. That's a follow-up.
  - No streaming / progressive output. One sync call, one report.
  - No retry logic. If the RPC fails once, return what we have and let
    the caller decide.

See also: docs/MISSIONS_COOKBOOK.md → "Storage health check".
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


INT_PATH = "/int"
EXT_PATH = "/ext"

# Thresholds (per the cookbook entry). Tune in one place; tests pin them.
EXT_FREE_PCT_WARN = 10.0   # warn if /ext (SD) free % falls below this
INT_FREE_PCT_WARN = 5.0    # warn if /int (flash) free % falls below this


@dataclass
class StorageHealthReport:
    """One snapshot of Flipper storage health.

    All byte counts are integers; percentages are floats in [0, 100].
    `ext_present` distinguishes "SD card absent" (ext_total=0) from
    "SD card has zero free bytes" (ext_total>0 and ext_free==0).
    """

    int_total: int = 0
    int_free: int = 0
    int_used_pct: float = 0.0
    ext_total: int = 0
    ext_free: int = 0
    ext_used_pct: float = 0.0
    ext_present: bool = False
    int_top_dirs: list[str] = field(default_factory=list)
    ext_top_dirs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        """One-paragraph human-readable summary, suitable for chat / logs."""
        parts: list[str] = []

        int_free_pct = 100.0 - self.int_used_pct
        parts.append(
            f"/int: {_fmt_bytes(self.int_free)} free of "
            f"{_fmt_bytes(self.int_total)} ({int_free_pct:.1f}% free)"
        )

        if self.ext_present:
            ext_free_pct = 100.0 - self.ext_used_pct
            parts.append(
                f"/ext: {_fmt_bytes(self.ext_free)} free of "
                f"{_fmt_bytes(self.ext_total)} ({ext_free_pct:.1f}% free)"
            )
        else:
            parts.append("/ext: SD card not present")

        if self.warnings:
            parts.append("Warnings: " + "; ".join(self.warnings))
        else:
            parts.append("No warnings.")

        return " | ".join(parts)


def _fmt_bytes(n: int) -> str:
    """Render a byte count as a short human-readable string."""
    if n <= 0:
        return "0 B"
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


def _used_pct(total: int, free: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, (total - free) / total * 100.0))


async def _read_volume(client: Any, path: str) -> tuple[int, int]:
    """Return (total, free) for a volume, or (0, 0) if unreadable.

    Goes through `client.rpc.storage_info(path)` which returns a dict
    `{"total_space": int, "free_space": int}` (or None on failure).
    """
    if not getattr(client, "rpc", None):
        return 0, 0
    info = await client.rpc.storage_info(path)
    if not info:
        return 0, 0
    return int(info.get("total_space", 0)), int(info.get("free_space", 0))


async def _list_top_dirs(client: Any, path: str) -> list[str]:
    """Return the top-level *directory* names under `path`.

    Filters out files via `list_detailed`. Returns [] on RPC failure or
    if the path doesn't exist (which is the expected state for /ext when
    no SD card is inserted).
    """
    storage = getattr(client, "storage", None)
    if storage is None:
        return []
    entries = await storage.list_detailed(path)
    return sorted(e["name"] for e in entries if e.get("type") == "DIR")


async def run(client: Any) -> StorageHealthReport:
    """Run a storage health check via the provided FlipperClient.

    `client` is a `flipper_mcp.core.flipper_client.FlipperClient` instance
    that has already been `.connect()`-ed. Tests pass a mock with the
    same shape.

    Returns a `StorageHealthReport`. Never raises — failures are reflected
    in the report (zeroed counters, empty dir lists, warnings).
    """
    started = time.monotonic()
    warnings: list[str] = []

    int_total, int_free = await _read_volume(client, INT_PATH)
    ext_total, ext_free = await _read_volume(client, EXT_PATH)

    int_used_pct = _used_pct(int_total, int_free)
    ext_used_pct = _used_pct(ext_total, ext_free)
    ext_present = ext_total > 0

    int_top_dirs = await _list_top_dirs(client, INT_PATH)
    ext_top_dirs = await _list_top_dirs(client, EXT_PATH) if ext_present else []

    if int_total > 0:
        int_free_pct = 100.0 - int_used_pct
        if int_free_pct < INT_FREE_PCT_WARN:
            warnings.append(
                f"/int free is {int_free_pct:.1f}% (< {INT_FREE_PCT_WARN}% threshold)"
            )
    else:
        warnings.append("/int storage_info returned no data")

    if ext_present:
        ext_free_pct = 100.0 - ext_used_pct
        if ext_free_pct < EXT_FREE_PCT_WARN:
            warnings.append(
                f"/ext free is {ext_free_pct:.1f}% (< {EXT_FREE_PCT_WARN}% threshold)"
            )
    # No warning for /ext absent — that's a valid configuration.

    elapsed_ms = int((time.monotonic() - started) * 1000)

    return StorageHealthReport(
        int_total=int_total,
        int_free=int_free,
        int_used_pct=int_used_pct,
        ext_total=ext_total,
        ext_free=ext_free,
        ext_used_pct=ext_used_pct,
        ext_present=ext_present,
        int_top_dirs=int_top_dirs,
        ext_top_dirs=ext_top_dirs,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


if __name__ == "__main__":
    # Manual smoke test: requires a real connected Flipper.
    # Usage: python -m missions.llmdr.missions.storage_health_check
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
            print(f"int_top_dirs: {report.int_top_dirs}")
            print(f"ext_top_dirs: {report.ext_top_dirs}")
            print(f"elapsed_ms: {report.elapsed_ms}")
        finally:
            await client.disconnect()
        return 0

    raise SystemExit(asyncio.run(_main()))
