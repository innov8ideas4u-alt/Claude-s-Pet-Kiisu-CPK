"""
BLE Capability Probe - Day 1, Q4: Is the CLI prompt accessible over BLE?
========================================================================

THE STRATEGIC QUESTION. If this fails, JS missions cannot run over BLE
without architecture changes (separate launcher app, or rewriting JS
missions as pure-RPC).

Strategy:
  1. Connect via BLE
  2. Subscribe to FROM_FLIPPER (indicate)
  3. Build & send a stop_session protobuf RPC over the BLE serial channel
  4. Drain bytes for ~1.5 seconds, dumping everything as both hex and ASCII
  5. Look for any sign of a CLI prompt:
     - The string ">: " (Flipper's CLI prompt)
     - The string "Welcome to Flipper Zero" (banner)
     - Any printable ASCII at all

If we see ">: " → CLI is reachable. JS missions can work over BLE.
If we see only zeros / nothing / pure protobuf bytes → CLI is NOT exposed
over BLE's serial-RPC characteristic. This is the architecture-pivot moment.

Plain English:
  USB has two modes. RPC mode (the protobuf channel) and CLI mode (a text
  shell where you can type 'js /ext/foo.js'). They share the same wire on
  USB - we send a special command to flip between them. Q4 is asking
  whether the same flip works over Bluetooth, or whether Bluetooth's
  RPC channel is sealed off from the text shell.
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

from flipper_mcp.core.protobuf_gen import flipper_pb2

AMORPOEE_MAC = "80:E1:26:EA:3D:5A"
TO_FLIPPER   = "19ed82ae-ed21-4c9d-4145-228e62fe0000"
FROM_FLIPPER = "19ed82ae-ed21-4c9d-4145-228e61fe0000"

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


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def to_printable(data: bytes) -> str:
    """Replace non-printable bytes with dots for ASCII view."""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


# ---------------------------------------------------------------------------

async def q4_can_we_reach_cli() -> bool:
    banner("Q4 - Can we reach the CLI prompt over BLE?")
    log("  Strategy: send stop_session RPC, drain raw bytes for 1.5s, look for prompt")

    rx_buffer = bytearray()

    def on_indication(_sender, data: bytearray):
        rx_buffer.extend(data)

    log(f"\n[{datetime.now():%H:%M:%S}] Connecting BLE...")
    t0 = time.monotonic()
    try:
        async with BleakClient(AMORPOEE_MAC, timeout=20.0) as client:
            log(f"  Connected in {time.monotonic() - t0:.2f}s. MTU={client.mtu_size}")

            await client.start_notify(FROM_FLIPPER, on_indication)
            log("  Notify subscription active.")

            # --- Phase A: confirm we're in RPC mode by sending a ping first ---
            log(f"\n[{datetime.now():%H:%M:%S}] Phase A: ping to confirm RPC mode")
            ping = flipper_pb2.Main()
            ping.command_id = 99
            ping.has_next = False
            ping.system_ping_request.data = b"q4-pre"
            payload = ping.SerializeToString()
            framed = encode_varint(len(payload)) + payload
            rx_buffer.clear()
            await client.write_gatt_char(TO_FLIPPER, framed, response=False)
            await asyncio.sleep(0.5)
            log(f"  ping response: {len(rx_buffer)}B  hex: {bytes(rx_buffer).hex()}")
            if not rx_buffer:
                log("Q4: aborting — RPC ping got no response, BLE not in usable state")
                await client.stop_notify(FROM_FLIPPER)
                return False
            log("  RPC mode confirmed.")

            # --- Phase B: send stop_session ---
            log(f"\n[{datetime.now():%H:%M:%S}] Phase B: send stop_session RPC")
            stop_msg = flipper_pb2.Main()
            stop_msg.command_id = 100
            stop_msg.has_next = False
            stop_msg.stop_session.SetInParent()  # marks the oneof field as set
            payload = stop_msg.SerializeToString()
            framed = encode_varint(len(payload)) + payload
            log(f"  stop_session framed: {framed.hex()} ({len(framed)}B)")

            rx_buffer.clear()
            await client.write_gatt_char(TO_FLIPPER, framed, response=False)
            log(f"  stop_session sent at {datetime.now():%H:%M:%S.%f}")

            # --- Phase C: drain and inspect for ~1.5 seconds ---
            log(f"\n[{datetime.now():%H:%M:%S}] Phase C: draining for 1.5s, looking for CLI text")
            drain_end = time.monotonic() + 1.5
            last_size = 0
            while time.monotonic() < drain_end:
                await asyncio.sleep(0.1)
                if len(rx_buffer) != last_size:
                    delta = bytes(rx_buffer[last_size:])
                    log(f"  +{len(delta)}B  hex: {delta.hex()}")
                    log(f"           ascii: {to_printable(delta)!r}")
                    last_size = len(rx_buffer)

            # --- Phase D: try poking with a CR to see if a CLI responds ---
            log(f"\n[{datetime.now():%H:%M:%S}] Phase D: send raw CR, look for prompt")
            mark = len(rx_buffer)
            await client.write_gatt_char(TO_FLIPPER, b"\r", response=False)
            await asyncio.sleep(0.8)
            after_cr = bytes(rx_buffer[mark:])
            log(f"  after CR: +{len(after_cr)}B")
            log(f"           hex:   {after_cr.hex()}")
            log(f"           ascii: {to_printable(after_cr)!r}")

            # --- Phase E: try a known CLI command (help) ---
            log(f"\n[{datetime.now():%H:%M:%S}] Phase E: send 'help\\r', look for command listing")
            mark = len(rx_buffer)
            await client.write_gatt_char(TO_FLIPPER, b"help\r", response=False)
            await asyncio.sleep(1.5)
            after_help = bytes(rx_buffer[mark:])
            log(f"  after 'help': +{len(after_help)}B")
            log(f"           hex first 200:   {after_help[:200].hex()}")
            log(f"           ascii first 400: {to_printable(after_help[:400])!r}")

            # --- Verdict ---
            full = bytes(rx_buffer)
            ascii_full = to_printable(full)
            log(f"\nFull rx after all phases: {len(full)} bytes")
            log(f"Full ASCII view: {ascii_full!r}")

            saw_prompt = ">: " in ascii_full
            saw_banner = "Welcome to Flipper" in ascii_full or "Flipper Zero" in ascii_full
            saw_help_listing = "help" in ascii_full.lower() or "command" in ascii_full.lower()
            saw_any_text = sum(32 <= b < 127 for b in full) > 8

            log(f"\nCLI prompt '>: ' seen:    {saw_prompt}")
            log(f"Banner/Welcome seen:      {saw_banner}")
            log(f"Help-listing text seen:   {saw_help_listing}")
            log(f"Any printable ASCII (>8): {saw_any_text}")

            cli_reachable = saw_prompt or saw_banner or (saw_help_listing and saw_any_text)
            if cli_reachable:
                log("\nQ4 RESULT: PASS - CLI is reachable over BLE")
                log("  *** JS missions architecturally workable over BLE ***")
            else:
                log("\nQ4 RESULT: FAIL - No CLI prompt or banner detected over BLE")
                log("  *** ARCHITECTURE PIVOT REQUIRED for JS missions ***")
                log("  Implication: Flipper's BLE serial-RPC characteristic is RPC-only.")
                log("  Options: split-mode (USB for JS, BLE for RPC), pure-RPC mission rewrite,")
                log("           or build a custom Flipper app that exposes JS launching via RPC.")

            await client.stop_notify(FROM_FLIPPER)
            return cli_reachable

    except Exception as e:
        log(f"Q4 RESULT: ERROR - {type(e).__name__}: {e}")
        return False


async def main() -> int:
    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## Q4 run @ {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
    ok = await q4_can_we_reach_cli()
    log("")
    log(f"Day 1 Q4 status: {'PASS — CLI reachable' if ok else 'FAIL — RPC-only over BLE'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
