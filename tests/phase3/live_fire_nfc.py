"""Cook 3 live integration: subscribe(0x42) -> tap a REAL card -> real UID host-side.

Operator script (NOT a pytest test — run it directly, with a card in hand).
Validates the Cook 3 vertical slice against AmorPoee with the Cook 3 FAP deployed
at /ext/apps/Tools/cfc.fap. This exercises the full gate (a-f):

    1. launch cfc in RPC mode
    2. flipper_cfc_subscribe(OP_NFC_EVENT)  -> arms the real NFC scanner (op 0x40 ack)
    3. TAP card #1 -> flipper_cfc_listen delivers the REAL UID within ~1s
       - txn has the M3 high bit SET
       - uid is NOT the Cook 2 mock DE:AD:BE:EF (a real read)
       - type indicates an ISO14443-3A card
       - first tap fires notification.success() on the device (beep + screen wake)
    4. TAP card #2 (different) WITHOUT re-subscribing -> second real UID delivered
       (proves the greedy continuous scan: no re-arm between taps)
    5. flipper_cfc_unsubscribe(OP_NFC_EVENT) -> disarms + nfc_free() releases the HAL
    6. exit cfc; afterwards the stock NFC app must be usable again

Deploy the freshly built FAP first (from repo root):
    cd cfc && uvx ufbt          # build
    # copy cfc/dist/cfc.fap to /ext/apps/Tools/cfc.fap on the AmorPoee SD card
    #   (qFlipper, or the host storage_write tool)

Run:  C:\\Python313\\python.exe tests\\phase3\\live_fire_nfc.py
"""

from __future__ import annotations

import asyncio
import sys

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.protobuf_rpc import CFC_BROADCAST_TXN_BIT
from flipper_mcp.core.transport.usb import USBTransport
from flipper_mcp.modules.cfc.module import (
    OP_NFC_DIAG,
    OP_NFC_EVENT,
    flipper_cfc_listen,
    flipper_cfc_subscribe,
    flipper_cfc_unsubscribe,
)

CFC_FAP_PATH = "/ext/apps/Tools/cfc.fap"
MOCK_UID = b"\xde\xad\xbe\xef"  # Cook 2 sentinel — a real read must NOT equal this
TAP_TIMEOUT_MS = 30000  # generous: a human is tapping


def _check_real_event(label: str, ev: dict | None) -> bytes:
    """Assert ev is a real NFC broadcast; return its UID bytes."""
    assert ev is not None, f"{label}: no broadcast arrived (tap not detected?)"
    txn = ev["txn"]
    payload = ev["payload"]
    uid = payload["uid"]
    assert txn & CFC_BROADCAST_TXN_BIT, f"{label}: txn {txn:#010x} missing M3 high bit"
    assert uid != MOCK_UID, f"{label}: got the Cook 2 mock UID — mock not swapped out"
    assert len(uid) in (4, 7, 10), f"{label}: implausible UID length {len(uid)}: {uid!r}"
    assert "iso14443" in payload["type"].lower(), f"{label}: unexpected type {payload['type']!r}"
    assert payload["timestamp_ms"] > 0, f"{label}: timestamp_ms must be a real tick"
    assert "overflow_since_last" in payload, f"{label}: missing overflow_since_last"
    print(f"  {label}: uid={uid.hex(':')} type={payload['type']} txn={txn:#010x}")
    return uid


async def _drain_diags(client) -> None:
    """Cook 3.2: non-asserting background reader for the 0x4F diagnostic stream.

    Prints every diagnostic broadcast as it arrives so the operator's terminal
    self-diagnoses which half is broken in ONE run:
      [diag] detect_cb protocol=Iso14443-3A count=1   -> scanner detected
      [diag] poll_ok uid_len=4                          -> poll read a UID
      [diag] poll_failed reason=timeout|poller_error|no_uid -> detection ok, poll is the bug
    If NO detect_cb ever prints during a tap → the scanner still is not detecting.

    This NEVER asserts and NEVER touches the 0x42 real-event buffer; it only
    reads OP_NFC_DIAG. Run as a task during the tap-wait windows; cancel after.
    """
    # NEVER let this task die silently — a dead drainer recreates the exact
    # Cook 3.1 blind state (a diagnostic that exists but is invisible). Cancel is
    # the only clean exit; any other error is PRINTED and we keep draining so one
    # malformed frame can't kill the whole stream.
    while True:
        try:
            ev = await flipper_cfc_listen(client, OP_NFC_DIAG, timeout_ms=1000)
        except asyncio.CancelledError:
            return  # clean shutdown — the caller cancelled us
        except Exception as e:
            print(f"  [diag] DRAINER ERROR (continuing): {type(e).__name__}: {e}",
                  file=sys.stderr)
            try:
                await asyncio.sleep(0.2)  # avoid a hot error-spin
            except asyncio.CancelledError:
                return
            continue
        if ev is None:
            continue  # no diag this slice — keep draining until cancelled
        p = ev.get("payload") or {}
        kind = p.get("event", "?")
        if kind == "detect_cb":
            print(f"  [diag] detect_cb protocol={p.get('protocol')} "
                  f"count={p.get('protocol_count')}")
        elif kind == "poll_ok":
            print(f"  [diag] poll_ok uid_len={p.get('uid_len')}")
        elif kind == "poll_failed":
            print(f"  [diag] poll_failed reason={p.get('reason')}")
        else:
            print(f"  [diag] {p}")


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

        # Cook 3.2: register the DIAGNOSTIC buffer (0x4F) FIRST. It has no FAP-side
        # arm op, so this is a pure host-buffer registration (armed=False, no wire
        # round-trip) — doing it before the 0x42 subscribe that arms the worker
        # guarantees no diagnostic can be emitted before its buffer exists.
        print("subscribe(0x4F diag) ...")
        subd = await flipper_cfc_subscribe(client, OP_NFC_DIAG)
        print(f"  -> {subd}")
        assert subd["subscribed"], "diag subscribe failed"

        print("subscribe(0x42) ...")
        sub = await flipper_cfc_subscribe(client, OP_NFC_EVENT)
        print(f"  -> {sub}")
        assert sub["subscribed"] and sub["armed"], "subscribe did not arm the FAP"

        # Drain + print the 0x4F diagnostic stream concurrently with the tap waits,
        # so the operator sees detect-vs-poll live. Cook 3.1's bug was exactly that
        # this signal existed but was invisible to this harness.
        diag_task = asyncio.create_task(_drain_diags(client))
        try:
            print(f"\n>>> TAP CARD #1 on AmorPoee now (waiting up to {TAP_TIMEOUT_MS//1000}s) ...")
            print("    (watch for [diag] lines — detect_cb means the scanner saw the card)")
            ev1 = await flipper_cfc_listen(client, OP_NFC_EVENT, timeout_ms=TAP_TIMEOUT_MS)
            uid1 = _check_real_event("tap#1", ev1)
            print("  (device should have beeped — first-tap notification.success)")

            print(f"\n>>> TAP CARD #2 (a DIFFERENT card) now — NO re-subscribe ...")
            ev2 = await flipper_cfc_listen(client, OP_NFC_EVENT, timeout_ms=TAP_TIMEOUT_MS)
            uid2 = _check_real_event("tap#2", ev2)
            if uid1 == uid2:
                print("  NOTE: tap#2 UID equals tap#1 — same card re-tapped; continuous "
                      "scan still proven (a second event with no re-subscribe).")
        finally:
            diag_task.cancel()
            # Belt-and-suspenders: if the drainer somehow exited with a
            # non-Cancelled error, surface it LOUDLY — never let a dead diag
            # stream pass for "no diagnostics" (the Cook 3.1 failure mode).
            for r in await asyncio.gather(diag_task, return_exceptions=True):
                if isinstance(r, BaseException) and not isinstance(r, asyncio.CancelledError):
                    print(f"  [diag] WARNING: diag drainer exited with "
                          f"{type(r).__name__}: {r}", file=sys.stderr)

        print("\nunsubscribe(0x42) ...")
        unsub = await flipper_cfc_unsubscribe(client, OP_NFC_EVENT)
        print(f"  -> {unsub}")
        print("unsubscribe(0x4F diag) ...")
        unsubd = await flipper_cfc_unsubscribe(client, OP_NFC_DIAG)
        print(f"  -> {unsubd}")

        print("\nPASS: real NFC UIDs delivered host-side; continuous scan confirmed.")
        print("MANUAL CHECK: open the stock NFC app and read a card — it must work")
        print("              (proves nfc_free() released the HAL on unsubscribe).")
        return 0
    finally:
        try:
            await rpc.app_exit()
        except Exception:
            pass
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
