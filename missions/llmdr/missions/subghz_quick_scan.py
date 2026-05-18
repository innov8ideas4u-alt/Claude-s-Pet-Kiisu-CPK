"""Sub-GHz quick scan — RSSI sample across 5 ISM frequencies.

Listens on 315, 433.92, 868, 915, 925 MHz, sampling RSSI 10 times each.
Pure RX. Computes avg / max / min per band host-side so the report
shows you "where the noise floor is" right now.

HOW TO FIRE (Victor + Claude Desktop):
    Ask Claude: "Run the Sub-GHz quick scan mission"

WHAT YOU SHOULD HEAR/SEE:
    - First beep + screen wake
    - ~5 seconds of silent activity (no LED — RX-only)
    - Second beep at end
    - Claude reports per-band avg/max RSSI; quiet bands tend to sit
      around -110 to -120 dBm, anything notably higher = something
      transmitting near you.

EXPECTED LOG SHAPE (CSV-style after the header):
    mission=subghz_quick_scan
    step=loaded
    # freq_hz,sample_idx,rssi_dbm
    315000000,0,-118
    315000000,1,-117
    ...
    433920000,0,-95
    ...
    freqs_scanned=5
    samples_per_freq=10
    finished=true

NOTES:
    - Frequencies are clamped to CC1101 supported bands at the firmware
      level. setFrequency returns the actual clamped value, so the log
      uses the actual frequency, not the requested one.
    - 925 MHz is the upper edge of CC1101's third band. If your
      region's regulations forbid it, swap for 868 below.
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
    / "subghz_quick_scan.js"
)
JS_SOURCE = _JS_PATH.read_text(encoding="utf-8")

MISSION_NAME = "subghz_quick_scan"
DEFAULT_WAIT_SECONDS = 8.0  # 5 freqs * 10 samples * 50ms + setup overhead


@dataclass
class BandStats:
    freq_hz: int
    samples: list[int] = field(default_factory=list)

    @property
    def avg_dbm(self) -> float:
        return sum(self.samples) / len(self.samples) if self.samples else 0.0

    @property
    def min_dbm(self) -> int:
        return min(self.samples) if self.samples else 0

    @property
    def max_dbm(self) -> int:
        return max(self.samples) if self.samples else 0


@dataclass
class SubghzQuickScanReport:
    bands: list[BandStats] = field(default_factory=list)
    freqs_scanned: int = 0
    samples_per_freq: int = 0
    finished: bool = False
    raw_log: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def summary(self) -> str:
        if not self.bands:
            return f"no bands captured (warnings: {'; '.join(self.warnings) or 'none'})"
        rows = []
        for b in sorted(self.bands, key=lambda x: x.freq_hz):
            rows.append(
                f"{b.freq_hz / 1e6:.2f} MHz: avg {b.avg_dbm:.1f} dBm "
                f"(min {b.min_dbm}, max {b.max_dbm}, n={len(b.samples)})"
            )
        head = (
            f"Sub-GHz quick scan, {self.freqs_scanned} bands x "
            f"{self.samples_per_freq} samples"
        )
        if not self.finished:
            head += " (NOT FINISHED — script aborted)"
        body = "\n  ".join(rows)
        out = f"{head}\n  {body}"
        if self.warnings:
            out += "\nwarnings: " + "; ".join(self.warnings)
        return out


def _parse_csv_lines(raw: str) -> dict[int, list[int]]:
    """Pull the # freq_hz,sample_idx,rssi_dbm rows out of the log."""
    per_band: dict[int, list[int]] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" in line:
            continue
        # CSV row: freq_hz,sample_idx,rssi_dbm
        parts = line.split(",")
        if len(parts) != 3:
            continue
        try:
            freq = int(parts[0])
        except ValueError:
            continue
        rssi_raw = parts[2]
        if rssi_raw == "undefined":
            continue
        try:
            rssi = int(float(rssi_raw))
        except ValueError:
            continue
        per_band.setdefault(freq, []).append(rssi)
    return per_band


async def run(
    client: Any,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
) -> SubghzQuickScanReport:
    """Run the Sub-GHz quick scan. Returns a `SubghzQuickScanReport`."""
    raw, parsed, elapsed_ms, warnings = await run_js_mission(
        client=client,
        mission_name=MISSION_NAME,
        js_source=JS_SOURCE,
        wait_seconds=wait_seconds,
    )

    per_band = _parse_csv_lines(raw)
    bands = [BandStats(freq_hz=f, samples=s) for f, s in per_band.items()]

    rep = SubghzQuickScanReport(
        bands=bands,
        finished=parsed.get("finished") == "true",
        raw_log=raw,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )
    try:
        rep.freqs_scanned = int(parsed.get("freqs_scanned", "0"))
        rep.samples_per_freq = int(parsed.get("samples_per_freq", "0"))
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
