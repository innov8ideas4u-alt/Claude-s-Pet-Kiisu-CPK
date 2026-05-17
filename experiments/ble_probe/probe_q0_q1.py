"""
BLE Capability Probe - Day 1, Q0 & Q1
=======================================

This script answers the first two questions in our BLE capability ladder
WITHOUT importing flippermcp. Bare bleak only - we want to test the BLE
channel itself, not our adapters around it.

Q0: Does AmorPoee advertise over BLE?
Q1: Can we connect and enumerate GATT services?

Hardware target:
  AmorPoee - Kiisu V4B + Momentum mntm-dev - paired to OnTopDesk's
  built-in Bluetooth adapter. Windows MAC: 80:E1:26:EA:3D:5A
  (Bleak shows MACs as colon-separated uppercase; same device.)

Output: writes raw findings to PROBE_RESULTS.md so we can attach it to
the Day 1 architecture-decision doc.
"""

from __future__ import annotations
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

from bleak import BleakScanner, BleakClient

# Hardware constants
AMORPOEE_MAC = "80:E1:26:EA:3D:5A"
AMORPOEE_NAME = "AmorPoee"

# Known Flipper BLE GATT UUIDs from research (last chat).
# Used only to LABEL findings, not to filter - we want to see EVERYTHING.
KNOWN_UUIDS = {
    "8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000": "FLIPPER_SERIAL_SERVICE (research)",
    "19ed82ae-ed21-4c9d-4145-228e62fe0000": "FLIPPER_TX (Flipper->us notify)",
    "19ed82ae-ed21-4c9d-4145-228e61fe0000": "FLIPPER_RX (us->Flipper write)",
    "19ed82ae-ed21-4c9d-4145-228e63fe0000": "FLIPPER_OVERFLOW (backpressure)",
    "19ed82ae-ed21-4c9d-4145-228e64fe0000": "FLIPPER_RPC_STATE",
    "0000180a-0000-1000-8000-00805f9b34fb": "Device Information Service (standard)",
    "0000180f-0000-1000-8000-00805f9b34fb": "Battery Service (standard)",
}

OUT_DIR = Path(__file__).parent
RESULTS_FILE = OUT_DIR / "PROBE_RESULTS.md"


def log(line: str) -> None:
    """Print and append to results file."""
    print(line)
    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def banner(title: str) -> None:
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


# ---------------------------------------------------------------------------
# Q0: Discovery scan
# ---------------------------------------------------------------------------

async def q0_scan() -> bool:
    """Returns True if AmorPoee is advertising."""
    banner("Q0 - Does AmorPoee advertise over BLE?")
    log(f"[{datetime.now():%H:%M:%S}] Scanning for 10 seconds...")

    found_amorpoee = False
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    log(f"[{datetime.now():%H:%M:%S}] Scan complete. {len(devices)} devices total.")
    log("")
    log("Device MAC                | Name                     | RSSI | Notes")
    log("-" * 76)
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or "(no name)"
        rssi = adv.rssi if adv.rssi is not None else "?"
        notes = []
        if AMORPOEE_NAME.lower() in (name or "").lower():
            notes.append("** AMORPOEE **")
            found_amorpoee = True
        if addr.upper() == AMORPOEE_MAC.upper():
            notes.append("** MATCHES TARGET MAC **")
            found_amorpoee = True
        notes_str = " ".join(notes)
        log(f"{addr} | {name[:24]:24} | {str(rssi):>4} | {notes_str}")

    log("")
    if found_amorpoee:
        log("Q0 RESULT: PASS - AmorPoee is advertising and discoverable.")
    else:
        log("Q0 RESULT: FAIL - AmorPoee NOT seen in scan.")
        log("Possible causes:")
        log("  - BT toggled off on Kiisu screen")
        log("  - Already connected to another central (only one allowed at a time)")
        log("  - Pairing prompt blocking on Kiisu screen")
    return found_amorpoee


# ---------------------------------------------------------------------------
# Q1: GATT enumeration
# ---------------------------------------------------------------------------

async def q1_enumerate() -> bool:
    """Connect to AmorPoee and dump every service + characteristic + descriptor."""
    banner("Q1 - Can we connect and enumerate GATT services?")
    log(f"[{datetime.now():%H:%M:%S}] Connecting to {AMORPOEE_MAC}...")

    t0 = time.monotonic()
    try:
        async with BleakClient(AMORPOEE_MAC, timeout=20.0) as client:
            t_connect = time.monotonic() - t0
            log(f"[{datetime.now():%H:%M:%S}] Connected in {t_connect:.2f}s")
            log(f"  is_connected: {client.is_connected}")
            try:
                mtu = client.mtu_size
                log(f"  MTU: {mtu} bytes (payload = {mtu - 3})")
            except Exception as e:
                log(f"  MTU lookup failed: {e!r}")

            log("")
            log("--- GATT services & characteristics ---")
            log("")

            services = client.services
            service_count = 0
            char_count = 0
            flipper_serial_seen = False
            tx_seen = rx_seen = overflow_seen = rpc_state_seen = False

            for svc in services:
                service_count += 1
                label = KNOWN_UUIDS.get(svc.uuid.lower(), "")
                if "FLIPPER_SERIAL" in label:
                    flipper_serial_seen = True
                log(f"[Service] {svc.uuid}  {label}")
                log(f"  handle={svc.handle}")
                for ch in svc.characteristics:
                    char_count += 1
                    ch_label = KNOWN_UUIDS.get(ch.uuid.lower(), "")
                    if "FLIPPER_TX" in ch_label:
                        tx_seen = True
                    if "FLIPPER_RX" in ch_label:
                        rx_seen = True
                    if "FLIPPER_OVERFLOW" in ch_label:
                        overflow_seen = True
                    if "FLIPPER_RPC_STATE" in ch_label:
                        rpc_state_seen = True
                    props = ",".join(ch.properties)
                    try:
                        max_w = ch.max_write_without_response_size
                    except Exception:
                        max_w = "?"
                    log(f"    [Char] {ch.uuid}  props=[{props}]  handle={ch.handle}  max_write_no_resp={max_w}  {ch_label}")
                    for d in ch.descriptors:
                        log(f"        [Desc] {d.uuid}  handle={d.handle}")

            log("")
            log(f"Totals: {service_count} services, {char_count} characteristics")
            log("")
            log("Critical-UUID checklist (against research from last chat):")
            log(f"  FLIPPER_SERIAL_SERVICE present: {flipper_serial_seen}")
            log(f"  TX char present:                {tx_seen}")
            log(f"  RX char present:                {rx_seen}")
            log(f"  OVERFLOW char present:          {overflow_seen}")
            log(f"  RPC_STATE char present:         {rpc_state_seen}")
            log("")
            if all([flipper_serial_seen, tx_seen, rx_seen]):
                log("Q1 RESULT: PASS - Flipper serial GATT service present with TX+RX. Day 1 can proceed to Q2-Q6.")
            elif flipper_serial_seen:
                log("Q1 RESULT: PARTIAL - Service present but TX/RX UUIDs differ. Need to identify by properties (notify=TX, write=RX) before proceeding.")
            else:
                log("Q1 RESULT: FAIL - Flipper serial GATT service NOT present. Momentum may have changed UUIDs OR the BT-RPC path is qFlipper-encrypted. Re-test against IlsaTheo (OFW, COM8) before reconsidering architecture.")
            return all([flipper_serial_seen, tx_seen, rx_seen])

    except Exception as e:
        log(f"Q1 RESULT: ERROR - {type(e).__name__}: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    # Wipe results file fresh
    RESULTS_FILE.write_text(
        f"# BLE Probe Results - {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
        f"Target: AmorPoee ({AMORPOEE_MAC}) - Kiisu V4B / Momentum mntm-dev\n"
        f"Adapter: OnTopDesk built-in MB Bluetooth\n\n",
        encoding="utf-8",
    )

    q0_ok = await q0_scan()
    if not q0_ok:
        log("")
        log("Stopping here - Q0 must pass before Q1 can run.")
        return 1

    q1_ok = await q1_enumerate()
    log("")
    log(f"Day 1 status after Q0+Q1: Q0={'PASS' if q0_ok else 'FAIL'}  Q1={'PASS' if q1_ok else 'FAIL/PARTIAL'}")
    return 0 if q1_ok else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
