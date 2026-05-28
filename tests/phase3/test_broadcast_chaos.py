"""Cook 2 / M5 — CHAOS MOCKS for the broadcast dispatcher.

Rule (adversarial review): if the firmware CAN send it, the test must send it.
These tests drive the live reader path (synthesized frames fed through a mocked
``_receive_main_message``) with adversarial broadcasts and pin the dispatcher's
behaviour:

  * high-bit-set txn broadcast → delivered (M3 correct namespace)
  * high-bit-CLEAR txn "broadcast" → dropped + logged (M3 violation)
  * response frame on a high-bit txn → never resolves the Future (M3 inverse)
  * out-of-order multi-fragment broadcast → reassembled correctly
  * duplicate fragment → tolerated, still reassembles once
  * zero-length payload broadcast → delivered with payload == None
  * garbage / mismatched outer command_id on every frame → ignored (routing is
    by inner txn only, per the Momentum uninit-malloc bug)
"""

from __future__ import annotations

import asyncio

import msgpack

from flipper_mcp.core.protobuf_rpc import _Subscription
from flipper_mcp.modules.cfc.module import OP_NFC_EVENT, flipper_cfc_listen
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)


def _nfc_payload(**over) -> bytes:
    body = {
        "uid": b"\xde\xad\xbe\xef",
        "type": "iso14443a-4",
        "rssi": None,
        "timestamp_ms": 12345,
        "overflow_since_last": 0,
    }
    body.update(over)
    return msgpack.packb(body, use_bin_type=True)


async def test_broadcast_high_bit_txn_is_delivered():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()
    try:
        payload = _nfc_payload()
        txn = 0x80000001  # high bit SET — legal broadcast namespace
        frame = pack_cfc(OP_NFC_EVENT, txn, 0, 1, len(payload), payload)
        # command_id deliberately garbage — broadcasts route by inner txn only.
        feed(make_app_data_main(frame, command_id=0xCAFEF00D))

        ev = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=2000)
        assert ev is not None
        assert ev["op_code"] == OP_NFC_EVENT
        assert ev["txn"] == txn
        assert ev["payload"]["uid"] == b"\xde\xad\xbe\xef"
        assert ev["payload"]["type"] == "iso14443a-4"
        assert ev["payload"]["rssi"] is None
    finally:
        await rpc._stop_reader()


async def test_broadcast_low_bit_txn_is_dropped():
    """A 'broadcast' arriving on a host-namespace (high-bit-CLEAR) txn with no
    pending request future is a firmware/protocol bug — it must be dropped, never
    delivered to the subscription (M3)."""
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()
    try:
        payload = _nfc_payload()
        txn = 0x00000123  # high bit CLEAR — illegal for a broadcast
        frame = pack_cfc(OP_NFC_EVENT, txn, 0, 1, len(payload), payload)
        feed(make_app_data_main(frame, command_id=0))

        ev = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=400)
        assert ev is None  # dropped, never delivered
        assert len(rpc._subscriptions[OP_NFC_EVENT].buffer) == 0
    finally:
        await rpc._stop_reader()


async def test_response_on_high_bit_txn_does_not_resolve_future():
    """M3 inverse: a response (matched a pending future) whose txn has the high
    bit SET is impossible under the partition and must be dropped, not used to
    resolve the Future with garbage."""
    rpc, feed = make_rpc_with_mock_receive()
    await rpc._ensure_reader_started()
    txn = 0x80000005  # high bit SET — illegal for a response
    fut = asyncio.get_running_loop().create_future()
    rpc._cfc_pending[txn] = fut
    try:
        frame = pack_cfc(OP_NFC_EVENT, txn, 0, 1, 3, b"abc")
        feed(make_app_data_main(frame, command_id=0))
        await asyncio.sleep(0.3)
        assert not fut.done(), "high-bit txn must not resolve a pending request future"
    finally:
        rpc._cfc_pending.pop(txn, None)
        await rpc._stop_reader()


async def test_broadcast_out_of_order_fragments_reassemble():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()
    try:
        big = _nfc_payload(pad="Z" * 600)  # forces a 2-fragment split (>884 total)
        txn = 0x80000007
        half = len(big) // 2
        f0, f1 = big[:half], big[half:]
        frag0 = pack_cfc(OP_NFC_EVENT, txn, 0, 2, len(big), f0)
        frag1 = pack_cfc(OP_NFC_EVENT, txn, 1, 2, len(big), f1)
        # Feed OUT OF ORDER (frag1 first) with differing garbage command_ids:
        # each fragment is a separate exchange_data call, so the FAP's uninit
        # command_id can differ between fragments of the SAME txn.
        feed(make_app_data_main(frag1, command_id=0x11111111))
        feed(make_app_data_main(frag0, command_id=0x00000000))

        ev = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=2000)
        assert ev is not None
        assert ev["txn"] == txn
        assert ev["payload"]["uid"] == b"\xde\xad\xbe\xef"
        assert ev["payload"]["pad"] == "Z" * 600
    finally:
        await rpc._stop_reader()


async def test_broadcast_duplicate_fragment_tolerated():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()
    try:
        big = _nfc_payload(pad="Q" * 600)
        txn = 0x80000008
        half = len(big) // 2
        f0, f1 = big[:half], big[half:]
        frag0 = pack_cfc(OP_NFC_EVENT, txn, 0, 2, len(big), f0)
        frag1 = pack_cfc(OP_NFC_EVENT, txn, 1, 2, len(big), f1)
        # frag0, frag0 (duplicate — overwrites the same index), then frag1.
        feed(make_app_data_main(frag0, command_id=0xAAAA0000))
        feed(make_app_data_main(frag0, command_id=0xBBBB0000))
        feed(make_app_data_main(frag1, command_id=0xCCCC0000))

        ev = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=2000)
        assert ev is not None
        assert ev["payload"]["pad"] == "Q" * 600

        # Exactly ONE event delivered — no phantom second event from the dup.
        again = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=300)
        assert again is None
    finally:
        await rpc._stop_reader()


async def test_broadcast_zero_length_payload_delivered_as_none():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()
    try:
        txn = 0x80000009
        frame = pack_cfc(OP_NFC_EVENT, txn, 0, 1, 0, b"")  # empty body
        feed(make_app_data_main(frame, command_id=0))

        ev = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=2000)
        assert ev is not None
        assert ev["txn"] == txn
        assert ev["payload"] is None  # empty body decodes to None, not a crash
    finally:
        await rpc._stop_reader()
