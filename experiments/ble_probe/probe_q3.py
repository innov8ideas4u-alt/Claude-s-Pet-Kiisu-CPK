"""
BLE Capability Probe - Day 1, Q3: Storage read/write over BLE
==============================================================

Q3: Can we do storage_write + storage_read over BLE?

This is the first probe that stresses the BLE channel with real volume.
A 1KB payload at 20-byte MTU = ~50 BLE fragments. If OVERFLOW backpressure
matters, we'll see it here.

Strategy:
  1. Connect to AmorPoee via BLE
  2. Wrap the live BleakClient in a tiny FlipperTransport-shaped adapter
     so we can reuse flippermcp's existing ProtobufRPC logic verbatim
  3. Call rpc.storage_write_file(...) with 1KB of known content
  4. Call rpc.storage_read_file(...) and verify byte-for-byte match
  5. Clean up: storage_delete

The adapter is the smallest possible thing that satisfies FlipperTransport:
  - send(data): write_gatt_char to TO_FLIPPER, chunked to MTU
  - receive(timeout): drain from an asyncio.Queue fed by the indicate handler
  - is_connected(): True while the BleakClient is alive

We do NOT subscribe to OVERFLOW yet. If Q3 fails on writes, that's our
diagnosis: backpressure needs to be implemented. If Q3 passes, we got lucky
on this payload size and OVERFLOW becomes a Day-2 concern.
"""

from __future__ import annotations
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from bleak import BleakClient

from flipper_mcp.core.transport.base import FlipperTransport
from flipper_mcp.core.protobuf_rpc import ProtobufRPC

# --- Constants ---
AMORPOEE_MAC = "80:E1:26:EA:3D:5A"
TO_FLIPPER   = "19ed82ae-ed21-4c9d-4145-228e62fe0000"  # we write here
FROM_FLIPPER = "19ed82ae-ed21-4c9d-4145-228e61fe0000"  # subscribe (indicate)

TEST_PATH = "/ext/apps_data/ble_probe_q3.bin"
# 1KB of pseudo-random but deterministic bytes (so failures are reproducible)
TEST_PAYLOAD = bytes((i * 31 + 7) & 0xFF for i in range(1024))

OUT_DIR = Path(__file__).parent
RESULTS_FILE = OUT_DIR / "PROBE_RESULTS.md"


def log(line: str) -> None:
    print(line)
    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def banner(title: str) -> None:
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


# ---------------------------------------------------------------------------
# Minimal BLE transport adapter (probe-only — final transport will be richer)
# ---------------------------------------------------------------------------

class BLEProbeTransport(FlipperTransport):
    """
    Bare-minimum FlipperTransport over an already-connected BleakClient.
    Q3-only: no reconnect, no OVERFLOW handling, no flow control.
    """

    def __init__(self, client: BleakClient):
        super().__init__(config={})
        self.client = client
        self.connected = True
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._chunk_size = 20  # MTU 23 - 3 ATT header
        self._notify_started = False

    def _on_indication(self, _sender, data: bytearray) -> None:
        # Bleak callback — push every fragment into our queue
        self._rx_queue.put_nowait(bytes(data))

    async def connect(self) -> bool:
        if not self._notify_started:
            await self.client.start_notify(FROM_FLIPPER, self._on_indication)
            self._notify_started = True
        return self.client.is_connected

    async def disconnect(self) -> None:
        if self._notify_started:
            try:
                await self.client.stop_notify(FROM_FLIPPER)
            except Exception:
                pass
            self._notify_started = False
        self.connected = False

    async def send(self, data: bytes) -> None:
        # Chunk to MTU. write-without-response (props confirmed in Q1).
        for i in range(0, len(data), self._chunk_size):
            chunk = data[i:i + self._chunk_size]
            await self.client.write_gatt_char(TO_FLIPPER, chunk, response=False)

    async def receive(self, timeout: float | None = None) -> bytes:
        try:
            if timeout is None:
                return await self._rx_queue.get()
            return await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return b""

    async def is_connected(self) -> bool:
        return self.client.is_connected and self.connected

    def get_name(self) -> str:
        return "BLEProbe"


# ---------------------------------------------------------------------------
# Q3
# ---------------------------------------------------------------------------

async def q3_storage_round_trip() -> bool:
    banner("Q3 - storage write + read over BLE (1KB payload)")
    log(f"  Test path:  {TEST_PATH}")
    log(f"  Payload:    {len(TEST_PAYLOAD)} bytes (deterministic pattern)")
    log(f"  Fragments:  ~{(len(TEST_PAYLOAD) + 19) // 20} BLE writes at 20B MTU")

    log(f"\n[{datetime.now():%H:%M:%S}] Connecting BLE...")
    t0 = time.monotonic()
    try:
        async with BleakClient(AMORPOEE_MAC, timeout=20.0) as client:
            log(f"  Connected in {time.monotonic() - t0:.2f}s. MTU={client.mtu_size}")

            transport = BLEProbeTransport(client)
            await transport.connect()
            log("  Notify subscription active.")

            rpc = ProtobufRPC(transport)
            log(f"  ProtobufRPC adapter wrapped around BLE transport.")

            # --- WRITE ---
            log(f"\n[{datetime.now():%H:%M:%S}] storage_write_file START")
            t_write = time.monotonic()
            try:
                write_ok = await rpc.storage_write(TEST_PATH, TEST_PAYLOAD)
            except Exception as e:
                log(f"  WRITE EXCEPTION: {type(e).__name__}: {e}")
                await transport.disconnect()
                return False
            t_write_elapsed = time.monotonic() - t_write
            log(f"  storage_write_file returned: {write_ok!r}")
            log(f"  Wall time: {t_write_elapsed:.2f}s "
                f"({len(TEST_PAYLOAD) / t_write_elapsed:.0f} B/s)")
            if not write_ok:
                log("Q3 RESULT: FAIL - storage_write_file returned False")
                log("  Likely cause: OVERFLOW backpressure not honored; some chunks dropped")
                await transport.disconnect()
                return False

            # --- READ ---
            log(f"\n[{datetime.now():%H:%M:%S}] storage_read_file START")
            t_read = time.monotonic()
            try:
                got = await rpc.storage_read(TEST_PATH)
            except Exception as e:
                log(f"  READ EXCEPTION: {type(e).__name__}: {e}")
                await transport.disconnect()
                return False
            t_read_elapsed = time.monotonic() - t_read
            log(f"  storage_read_file returned: {len(got) if got else 'None/empty'} bytes")
            log(f"  Wall time: {t_read_elapsed:.2f}s")

            if got is None or len(got) == 0:
                log("Q3 RESULT: FAIL - storage_read_file returned empty/None")
                await transport.disconnect()
                return False

            # --- VERIFY ---
            if got == TEST_PAYLOAD:
                log("\nQ3 RESULT: PASS - bytes match exactly")
                log("  *** BLE handles real RPC payloads. Storage path is solid. ***")
                ok = True
            else:
                # Show where they differ
                diff_idx = next((i for i in range(min(len(got), len(TEST_PAYLOAD)))
                                if got[i] != TEST_PAYLOAD[i]), None)
                log(f"\nQ3 RESULT: PARTIAL - byte mismatch")
                log(f"  Sent {len(TEST_PAYLOAD)}B, got {len(got)}B")
                if diff_idx is not None:
                    log(f"  First diff at index {diff_idx}: "
                        f"sent={TEST_PAYLOAD[diff_idx]:02x} got={got[diff_idx]:02x}")
                ok = False

            # --- CLEANUP ---
            log(f"\n[{datetime.now():%H:%M:%S}] cleanup: storage_delete")
            try:
                deleted = await rpc.storage_delete(TEST_PATH)
                log(f"  delete result: {deleted!r}")
            except Exception as e:
                log(f"  delete failed (not critical): {type(e).__name__}: {e}")

            await transport.disconnect()
            return ok

    except Exception as e:
        log(f"Q3 RESULT: ERROR - {type(e).__name__}: {e}")
        return False


async def main() -> int:
    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## Q3 run @ {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")

    ok = await q3_storage_round_trip()
    log("")
    log(f"Day 1 Q3 status: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
