"""Cook 2 live integration: subscribe(0x42) -> listen sees a MOCK NFC broadcast.

Operator script (NOT a pytest test — run it directly). Validates the end-to-end
vertical slice against AmorPoee with the Cook 2 FAP deployed at
/ext/apps/Tools/cfc.fap:

    1. launch cfc in RPC mode
    2. flipper_cfc_subscribe(OP_NFC_EVENT)  -> arms the FAP worker (op 0x40 ack)
    3. flipper_cfc_listen(OP_NFC_EVENT)     -> a mock broadcast arrives in ~2s
    4. assert the broadcast txn has the M3 high bit SET, and the payload matches
       the mock contract (fake uid/type/rssi; REAL timestamp_ms + overflow)
    5. flipper_cfc_unsubscribe(OP_NFC_EVENT) -> disarms the worker
    6. exit cfc

No card tap is needed — the worker emits a mock every ~2s while armed.

Run:  C:\\Python313\\python.exe tests\\phase3\\live_fire_nfc_mock.py
"""

from __future__ import annotations

import asyncio
import sys

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.protobuf_rpc import CFC_BROADCAST_TXN_BIT
from flipper_mcp.core.transport.usb import USBTransport
from flipper_mcp.modules.cfc.module import (
    OP_NFC_EVENT,
    flipper_cfc_listen,
    flipper_cfc_subscribe,
    flipper_cfc_unsubscribe,
)

CFC_FAP_PATH = "/ext/apps/Tools/cfc.fap"


async def main() -> int:
    transport = USBTransport({"baudrate": 115200})
    client = FlipperClient(transport)
    if not await client.connect():
        print(f"FAIL: could not connect ({client.last_connection_error})")
        return 1

    client.rpc._ensure_protobuf_rpc()
    rpc = client.rpc.protobuf_rpc
    try:
        await rpc.app_exit()
        await asyncio.sleep(0.3)
        start = await rpc.app_start(CFC_FAP_PATH, "RPC")
        if not start:
            print(f"FAIL: app_start(cfc, RPC) -> {start.status_name}")
            return 1
        await asyncio.sleep(0.4)

        print("subscribe(0x42) ...")
        sub = await flipper_cfc_subscribe(client, OP_NFC_EVENT)
        print(f"  -> {sub}")
        assert sub["subscribed"] and sub["armed"], "subscribe did not arm the FAP"

        print("listen(0x42, 4000ms) — expecting a mock broadcast within ~2-3s ...")
        ev = await flipper_cfc_listen(client, OP_NFC_EVENT, timeout_ms=4000)
        print(f"  -> {ev}")
        assert ev is not None, "no mock broadcast arrived within 4s"

        txn = ev["txn"]
        payload = ev["payload"]
        assert txn & CFC_BROADCAST_TXN_BIT, f"broadcast txn {txn:#010x} missing M3 high bit"
        assert payload["uid"] == b"\xde\xad\xbe\xef", f"bad mock uid: {payload['uid']!r}"
        assert payload["type"] == "iso14443a-4", f"bad mock type: {payload['type']!r}"
        assert payload["rssi"] is None, f"rssi should be null (mock), got {payload['rssi']!r}"
        assert payload["timestamp_ms"] > 0, "timestamp_ms must be a real tick"
        assert "overflow_since_last" in payload, "missing overflow_since_last"

        print("unsubscribe(0x42) ...")
        unsub = await flipper_cfc_unsubscribe(client, OP_NFC_EVENT)
        print(f"  -> {unsub}")

        print("\nPASS: mock NFC broadcast received with M3 high-bit txn and valid payload.")
        return 0
    finally:
        try:
            await rpc.app_exit()
        except Exception:
            pass
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
