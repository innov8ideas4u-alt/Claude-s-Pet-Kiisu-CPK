"""
BLE Capability Probe - Day 1, Q2: Protobuf ping over BLE
==========================================================

Q2: Can we send a protobuf ping and get a PONG back over BLE?

This is the moment of truth - it tells us whether the Flipper's BLE
serial GATT service speaks the same protobuf RPC language as USB.

Strategy:
  1. Connect to AmorPoee
  2. Subscribe to indicate notifications on the FROM_FLIPPER characteristic
     (...61fe0000 — the one with `indicate` property; Flipper pushes data here)
  3. Build a real protobuf system_ping_request (using the flippermcp-shipped
     protobuf bindings - no hand-rolling)
  4. Write it varint-prefixed to the TO_FLIPPER characteristic
     (...62fe0000 — the one with `write` property; we push data here)
  5. Wait for an indicate to fire with a parseable PONG response

Key insight from the GATT dump:
  - Last chat's "TX/RX" labels were from firmware POV. We use function names:
    TO_FLIPPER (we write) and FROM_FLIPPER (we receive).
  - The receive direction uses INDICATE, not NOTIFY. Bleak handles this
    transparently via start_notify(), but it means each packet has an
    implicit ACK round-trip - slower but more reliable.
  - MTU is 23 bytes (20 payload). A ping is small, so no chunking needed.

A/B baseline: Same ping over USB at COM9 must succeed first. If USB fails
too, our probe is wrong - not the BLE channel.
"""

from __future__ import annotations
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

# Wire flippermcp protobuf bindings into path
SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from bleak import BleakClient

from flipper_mcp.core.protobuf_gen import flipper_pb2, system_pb2

# --- Hardware constants ---
AMORPOEE_MAC = "80:E1:26:EA:3D:5A"

# --- GATT UUIDs (function-named, see header comment) ---
SERIAL_SERVICE = "8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000"
TO_FLIPPER     = "19ed82ae-ed21-4c9d-4145-228e62fe0000"  # write here
FROM_FLIPPER   = "19ed82ae-ed21-4c9d-4145-228e61fe0000"  # subscribe here (indicate)
OVERFLOW       = "19ed82ae-ed21-4c9d-4145-228e63fe0000"  # backpressure (Q3+ uses this)
RPC_STATE      = "19ed82ae-ed21-4c9d-4145-228e64fe0000"  # session state

# --- Output ---
OUT_DIR = Path(__file__).parent
RESULTS_FILE = OUT_DIR / "PROBE_RESULTS.md"
PING_PAYLOAD = b"BLE-PING-Q2"  # echoed back inside ping response


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
# Varint helpers (mirror flippermcp's protobuf_rpc encoding)
# ---------------------------------------------------------------------------

def encode_varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def try_decode_varint(buf: bytearray) -> tuple[int | None, int]:
    """Returns (value, bytes_consumed). value is None if buffer too short."""
    value = 0
    shift = 0
    for i, b in enumerate(buf):
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, i + 1
        shift += 7
        if shift >= 64:
            raise ValueError("varint too long")
    return None, 0


# ---------------------------------------------------------------------------
# Q2: BLE ping
# ---------------------------------------------------------------------------

async def q2_ble_ping() -> bool:
    banner("Q2 - Can we send protobuf ping over BLE and get PONG?")

    rx_buffer = bytearray()
    response_event = asyncio.Event()

    def on_indication(_sender, data: bytearray):
        # Bleak callback - pushes received bytes into our buffer
        rx_buffer.extend(data)
        log(f"  [indicate] +{len(data)}B  total buffer: {len(rx_buffer)}B  raw: {bytes(data).hex()}")
        # Try to parse a complete message. If varint decodes and full payload
        # is present, signal ready.
        n, consumed = try_decode_varint(rx_buffer)
        if n is not None and len(rx_buffer) >= consumed + n:
            response_event.set()

    log(f"[{datetime.now():%H:%M:%S}] Connecting to AmorPoee BLE...")
    t0 = time.monotonic()
    try:
        async with BleakClient(AMORPOEE_MAC, timeout=20.0) as client:
            log(f"  Connected in {time.monotonic() - t0:.2f}s. MTU={client.mtu_size}")

            # Subscribe to indicate-direction characteristic
            log(f"  Subscribing to FROM_FLIPPER ({FROM_FLIPPER[-12:]})...")
            await client.start_notify(FROM_FLIPPER, on_indication)
            log("  Subscription active.")

            # Build a real protobuf ping request using flippermcp's bindings
            main = flipper_pb2.Main()
            main.command_id = 1
            main.has_next = False
            main.system_ping_request.data = PING_PAYLOAD
            payload = main.SerializeToString()
            framed = encode_varint(len(payload)) + payload
            log(f"  Built ping: {len(payload)}B protobuf, {len(framed)}B framed")
            log(f"  Framed bytes (hex): {framed.hex()}")

            # Write it. Ping is tiny (under MTU), no chunking needed.
            log(f"  Writing to TO_FLIPPER ({TO_FLIPPER[-12:]}) (response=False)...")
            t_send = time.monotonic()
            await client.write_gatt_char(TO_FLIPPER, framed, response=False)
            log(f"  Write completed in {(time.monotonic() - t_send) * 1000:.0f}ms")

            # Wait up to 5s for response
            log("  Waiting up to 5s for indicate response...")
            try:
                await asyncio.wait_for(response_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                log("Q2 RESULT: FAIL - no response within 5s")
                log(f"  Buffer state at timeout: {len(rx_buffer)}B  hex: {bytes(rx_buffer).hex()}")
                log("")
                log("  Diagnosis hints:")
                log("  - 0 bytes received: BLE write succeeded but Flipper didn't see it")
                log("    OR Flipper requires 'start_rpc_session' before accepting protobuf")
                log("  - some bytes received but not parseable: framing might differ from USB")
                await client.stop_notify(FROM_FLIPPER)
                return False

            # Parse response
            n, consumed = try_decode_varint(rx_buffer)
            log(f"  Decoded varint length: {n}, consumed: {consumed}")
            payload_bytes = bytes(rx_buffer[consumed:consumed + n])
            log(f"  Payload ({n}B): {payload_bytes.hex()}")

            try:
                resp = flipper_pb2.Main()
                resp.ParseFromString(payload_bytes)
                log(f"  Parsed response: command_id={resp.command_id}, status={resp.command_status}")
                if resp.HasField("system_ping_response"):
                    echoed = bytes(resp.system_ping_response.data)
                    log(f"  PingResponse data (hex): {echoed.hex()}")
                    log(f"  PingResponse data (str): {echoed!r}")
                    if echoed == PING_PAYLOAD:
                        log("Q2 RESULT: PASS - PONG received with matching payload echo!")
                        log("  *** BLE channel speaks Flipper protobuf RPC. ***")
                        await client.stop_notify(FROM_FLIPPER)
                        return True
                    else:
                        log(f"Q2 RESULT: PARTIAL - PONG arrived but payload mismatch (got {echoed!r}, sent {PING_PAYLOAD!r})")
                        await client.stop_notify(FROM_FLIPPER)
                        return False
                else:
                    log("Q2 RESULT: FAIL - response had no system_ping_response field")
                    log(f"  Full response: {resp}")
                    await client.stop_notify(FROM_FLIPPER)
                    return False
            except Exception as parse_err:
                log(f"Q2 RESULT: FAIL - response unparseable: {parse_err!r}")
                await client.stop_notify(FROM_FLIPPER)
                return False

    except Exception as e:
        log(f"Q2 RESULT: ERROR - {type(e).__name__}: {e}")
        return False


# ---------------------------------------------------------------------------
# A/B baseline: same ping over USB
# ---------------------------------------------------------------------------

async def usb_ping_baseline() -> bool:
    banner("Q2 USB BASELINE - Same ping over COM9")
    try:
        from flipper_mcp.core.transport.usb import USBTransport
        from flipper_mcp.core.protobuf_rpc import ProtobufRPC
    except Exception as e:
        log(f"  Cannot import flippermcp transport modules: {e!r}")
        log("  USB baseline SKIPPED - probe imports may need adjustment")
        return False

    transport = USBTransport({"port": "COM9", "baudrate": 230400, "timeout": 2.0})
    try:
        log("  Connecting to AmorPoee on COM9...")
        if not await transport.connect():
            log("  USB BASELINE FAIL: connect() returned False")
            return False
        rpc = ProtobufRPC(transport)
        log("  Sending system_ping...")
        result = await rpc.system_ping(PING_PAYLOAD, timeout=5.0)
        if result == PING_PAYLOAD:
            log(f"  USB BASELINE PASS: payload echoed correctly ({result!r})")
            return True
        log(f"  USB BASELINE FAIL: got {result!r}, expected {PING_PAYLOAD!r}")
        return False
    except Exception as e:
        log(f"  USB BASELINE ERROR: {type(e).__name__}: {e}")
        return False
    finally:
        try:
            await transport.disconnect()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    # Append-mode log entry
    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## Q2 run @ {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")

    # USB baseline first (if it fails, BLE result is meaningless)
    usb_ok = await usb_ping_baseline()
    log("")
    if not usb_ok:
        log("WARNING: USB baseline did not pass. BLE result interpretation will be ambiguous.")
        log("Proceeding with BLE probe anyway.")

    # The actual BLE test
    ble_ok = await q2_ble_ping()

    log("")
    log(f"Day 1 Q2 summary: USB baseline={'PASS' if usb_ok else 'FAIL'}, BLE ping={'PASS' if ble_ok else 'FAIL'}")
    return 0 if ble_ok else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
