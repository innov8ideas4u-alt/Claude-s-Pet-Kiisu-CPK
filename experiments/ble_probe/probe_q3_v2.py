"""
BLE Capability Probe - Day 1, Q3 (v2): storage round-trip with OVERFLOW backpressure
======================================================================================

Q3v1 failed because we wrote 1KB at 20-byte MTU without honoring the
Flipper's flow control. Q3v2 adds OVERFLOW handling.

OVERFLOW protocol (from Flipper forum/firmware):
  - Subscribe to OVERFLOW characteristic (notify)
  - Each notify carries a little-endian uint32: "bytes the Flipper is ready to receive"
  - Wait for the FIRST notify to know the initial budget
  - Decrement budget locally as we send bytes
  - When budget runs out, BLOCK on next notify before sending more

Plain English: the Kiisu yells out a number = how many sticky notes will
fit in its inbox right now. We send up to that many, then wait for it to
yell again before sending more.
"""

from __future__ import annotations
import asyncio
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from bleak import BleakClient

from flipper_mcp.core.transport.base import FlipperTransport
from flipper_mcp.core.protobuf_rpc import ProtobufRPC

AMORPOEE_MAC = "80:E1:26:EA:3D:5A"
TO_FLIPPER   = "19ed82ae-ed21-4c9d-4145-228e62fe0000"
FROM_FLIPPER = "19ed82ae-ed21-4c9d-4145-228e61fe0000"
OVERFLOW_CH  = "19ed82ae-ed21-4c9d-4145-228e63fe0000"

TEST_PATH = "/ext/apps_data/ble_probe_q3.bin"
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
# BLE transport with OVERFLOW backpressure
# ---------------------------------------------------------------------------

class BLEProbeTransportV2(FlipperTransport):
    """
    Adds OVERFLOW-driven flow control to v1.

    State variables:
      _credit:        bytes we're allowed to send right now
      _credit_event:  signaled whenever credit is replenished
    """

    def __init__(self, client: BleakClient):
        super().__init__(config={})
        self.client = client
        self.connected = True
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._chunk_size = 20  # MTU 23 - 3 ATT header
        self._notify_started = False
        self._overflow_started = False
        self._credit = 0
        self._credit_event = asyncio.Event()
        self._overflow_log: list[int] = []

    def _on_indication(self, _sender, data: bytearray) -> None:
        # Verbose: log every fragment we receive
        log(f"  [indicate] +{len(data)}B  hex: {bytes(data).hex()}")
        self._rx_queue.put_nowait(bytes(data))

    def _on_overflow(self, _sender, data: bytearray) -> None:
        # Flipper sends a uint32 LE = bytes it's ready to receive
        if len(data) >= 4:
            ready = struct.unpack("<I", bytes(data[:4]))[0]
            self._credit = ready
            self._credit_event.set()
            self._overflow_log.append(ready)

    async def connect(self) -> bool:
        if not self._notify_started:
            await self.client.start_notify(FROM_FLIPPER, self._on_indication)
            self._notify_started = True
        if not self._overflow_started:
            await self.client.start_notify(OVERFLOW_CH, self._on_overflow)
            self._overflow_started = True
            # Read the current value once - some firmwares post it on read,
            # not just notify. This seeds initial credit before any traffic.
            try:
                initial = await self.client.read_gatt_char(OVERFLOW_CH)
                if len(initial) >= 4:
                    self._credit = struct.unpack("<I", bytes(initial[:4]))[0]
                    self._credit_event.set()
                    self._overflow_log.append(self._credit)
                    log(f"  [overflow] initial read: {self._credit} bytes credit")
            except Exception as e:
                log(f"  [overflow] initial read failed (may be notify-only): {e!r}")
        return self.client.is_connected

    async def disconnect(self) -> None:
        try:
            if self._notify_started:
                await self.client.stop_notify(FROM_FLIPPER)
            if self._overflow_started:
                await self.client.stop_notify(OVERFLOW_CH)
        except Exception:
            pass
        self.connected = False

    async def send(self, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            # Wait for some credit before sending the next chunk
            while self._credit <= 0:
                self._credit_event.clear()
                try:
                    await asyncio.wait_for(self._credit_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    log(f"  [overflow] credit timeout — fw not advertising space; "
                        f"falling back to small chunk")
                    self._credit = self._chunk_size  # try one tentative chunk
                    break
            chunk_len = min(self._chunk_size, self._credit, len(data) - offset)
            chunk = data[offset:offset + chunk_len]
            await self.client.write_gatt_char(TO_FLIPPER, chunk, response=False)
            self._credit -= chunk_len
            offset += chunk_len

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
        return "BLEProbeV2"


# ---------------------------------------------------------------------------
# Q3v2
# ---------------------------------------------------------------------------

async def q3v2() -> bool:
    banner("Q3 v2 - storage round-trip WITH OVERFLOW backpressure")
    log(f"  Test path:  {TEST_PATH}")
    log(f"  Payload:    {len(TEST_PAYLOAD)} bytes")
    log(f"  Fragments:  ~{(len(TEST_PAYLOAD) + 19) // 20} BLE writes at 20B MTU")

    log(f"\n[{datetime.now():%H:%M:%S}] Connecting BLE...")
    t0 = time.monotonic()
    try:
        async with BleakClient(AMORPOEE_MAC, timeout=20.0) as client:
            log(f"  Connected in {time.monotonic() - t0:.2f}s. MTU={client.mtu_size}")

            transport = BLEProbeTransportV2(client)
            await transport.connect()
            log(f"  Notify + OVERFLOW subscriptions active. "
                f"Initial credit: {transport._credit}")

            rpc = ProtobufRPC(transport)
            rpc.debug = True  # Enable verbose error logging

            # PRE-FLIGHT: ping to establish session cleanly before storage ops
            log(f"\n[{datetime.now():%H:%M:%S}] preflight ping...")
            preflight = await rpc.ping(b"preflight")
            log(f"  ping returned: {preflight!r}")
            if preflight != b"preflight":
                log("Q3v2 RESULT: FAIL — preflight ping didn't echo")
                await transport.disconnect()
                return False

            # WRITE
            log(f"\n[{datetime.now():%H:%M:%S}] storage_write START")
            t_w = time.monotonic()
            write_ok = await rpc.storage_write(TEST_PATH, TEST_PAYLOAD)
            t_w_elapsed = time.monotonic() - t_w
            log(f"  returned: {write_ok!r}")
            log(f"  wall: {t_w_elapsed:.2f}s ({len(TEST_PAYLOAD) / t_w_elapsed:.0f} B/s)")
            log(f"  overflow notifications received: {len(transport._overflow_log)}")
            log(f"  overflow log first 10: {transport._overflow_log[:10]}")
            if not write_ok:
                log("Q3v2 RESULT: FAIL on write")
                await transport.disconnect()
                return False

            # READ
            log(f"\n[{datetime.now():%H:%M:%S}] storage_read START")
            t_r = time.monotonic()
            got = await rpc.storage_read(TEST_PATH)
            t_r_elapsed = time.monotonic() - t_r
            log(f"  bytes back: {len(got) if got else 0}  wall: {t_r_elapsed:.2f}s")
            if not got:
                log("Q3v2 RESULT: FAIL on read")
                await transport.disconnect()
                return False

            # VERIFY
            if got == TEST_PAYLOAD:
                log("\nQ3v2 RESULT: PASS — bytes match exactly")
                log("  *** OVERFLOW backpressure works. Storage path solid over BLE. ***")
                ok = True
            else:
                diff_idx = next((i for i in range(min(len(got), len(TEST_PAYLOAD)))
                                if got[i] != TEST_PAYLOAD[i]), None)
                log(f"\nQ3v2 RESULT: PARTIAL — sent {len(TEST_PAYLOAD)}B got {len(got)}B "
                    f"first diff @ {diff_idx}")
                ok = False

            # CLEANUP
            try:
                await rpc.storage_delete(TEST_PATH)
                log("  cleanup: deleted")
            except Exception as e:
                log(f"  cleanup failed (ignorable): {e!r}")

            await transport.disconnect()
            return ok

    except Exception as e:
        log(f"Q3v2 RESULT: ERROR — {type(e).__name__}: {e}")
        return False


async def main() -> int:
    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## Q3v2 run @ {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
    ok = await q3v2()
    log("")
    log(f"Day 1 Q3v2 status: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
