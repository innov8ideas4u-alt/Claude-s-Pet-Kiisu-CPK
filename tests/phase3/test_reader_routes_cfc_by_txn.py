"""§3 / operator clarification — reader routes CFC frames by inner
transaction_id, IGNORING outer Main.command_id.

The Momentum ``rpc_system_app_exchange_data`` uninitialized-malloc bug
fills the outer command_id with garbage on inbound app_data_exchange
frames. The reader must therefore never use that field for routing CFC
traffic. This test interleaves two concurrent txns and verifies each
future receives only its own body.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)


@pytest.mark.asyncio
async def test_reader_routes_cfc_by_txn_not_cmd_id():
    rpc, feed = make_rpc_with_mock_receive()

    txn_a = 0x11111111
    txn_b = 0x22222222
    body_a = b"AAA-body-for-txn-a"
    body_b = b"BBB-body-for-txn-b"

    fut_a: asyncio.Future = asyncio.get_running_loop().create_future()
    fut_b: asyncio.Future = asyncio.get_running_loop().create_future()
    rpc._cfc_pending[txn_a] = fut_a
    rpc._cfc_pending[txn_b] = fut_b

    try:
        await rpc._ensure_reader_started()

        # Feed B before A — outer command_ids deliberately swapped and
        # nonsensical to prove they are not used for routing.
        frame_b = pack_cfc(
            op=0x42, txn=txn_b, frag_idx=0, frag_total=1,
            payload_length=len(body_b), body=body_b,
        )
        frame_a = pack_cfc(
            op=0x42, txn=txn_a, frag_idx=0, frag_total=1,
            payload_length=len(body_a), body=body_a,
        )
        feed(make_app_data_main(frame_b, command_id=0xAAAAAAAA))
        feed(make_app_data_main(frame_a, command_id=0xBBBBBBBB))

        op_a, txn_out_a, body_out_a, _ = await asyncio.wait_for(fut_a, timeout=2.0)
        op_b, txn_out_b, body_out_b, _ = await asyncio.wait_for(fut_b, timeout=2.0)

        assert (txn_out_a, body_out_a) == (txn_a, body_a)
        assert (txn_out_b, body_out_b) == (txn_b, body_b)
    finally:
        await rpc._stop_reader()


@pytest.mark.asyncio
async def test_reader_drops_short_cfc_frame_without_crash():
    """A frame shorter than CFC_HEADER_LEN (16) is logged-and-dropped, not
    fatal. Phase 2.5's ``test_broadcast_path_mock`` exercised a 5-byte
    payload; this test pins the same defensive behavior in the new reader.
    """
    rpc, feed = make_rpc_with_mock_receive()
    try:
        await rpc._ensure_reader_started()
        feed(make_app_data_main(b"short", command_id=0))
        # Reader runs; nothing crashes. Give it a beat to consume.
        await asyncio.sleep(0.2)
        assert rpc._reader_task is not None
        assert not rpc._reader_task.done()
    finally:
        await rpc._stop_reader()
