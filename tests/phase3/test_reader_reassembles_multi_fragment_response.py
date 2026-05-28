"""§13.1 / §13.6 — reader accumulates multi-fragment CFC responses and
fires the per-transaction future only on the last fragment.

The original §4.3 reader sketch called ``future.set_result(main)`` on every
inbound frame, which would have broken every existing CFC tool the moment
fragmentation kicked in. §13.1 added the assembly buffer; this test pins
that behavior so a future "simplification" can't regress it.
"""

from __future__ import annotations

import asyncio
import msgpack

import pytest

from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)


@pytest.mark.asyncio
async def test_reader_reassembles_multi_fragment_response():
    rpc, feed = make_rpc_with_mock_receive()

    # Build a 3-fragment response payload. Op_code 0x00 (PING), txn 0xCAFEBABE.
    op = 0x00
    txn = 0xCAFEBABE
    body_full = b"A" * 1500
    chunk_size = 600
    chunks = [body_full[i : i + chunk_size] for i in range(0, len(body_full), chunk_size)]
    assert len(chunks) == 3

    # Register the txn future BEFORE feeding frames (real callers register
    # before sending; sequence here mirrors that).
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    rpc._cfc_pending[txn] = fut

    try:
        await rpc._ensure_reader_started()

        # Feed all 3 fragments in order. Outer command_id is deliberately
        # garbage (mimics the Momentum uninit-malloc bug); reader must
        # ignore it and route purely by inner CFC header.transaction_id.
        for idx, chunk in enumerate(chunks):
            frame = pack_cfc(
                op=op,
                txn=txn,
                frag_idx=idx,
                frag_total=len(chunks),
                payload_length=len(body_full),
                body=chunk,
            )
            feed(make_app_data_main(frame, command_id=0xDEADBEEF))

        # The reader should accumulate the first two silently and fire the
        # future when fragment 2 arrives. Allow a generous wait_for in case
        # the asyncio scheduler is slow on Windows.
        op_out, txn_out, body_out, payload_length_out = await asyncio.wait_for(
            fut, timeout=2.0
        )

        assert op_out == op
        assert txn_out == txn
        assert body_out == body_full
        assert payload_length_out == len(body_full)
        # Assembly state must be cleaned up once delivered.
        assert txn not in rpc._cfc_assembling
    finally:
        await rpc._stop_reader()


@pytest.mark.asyncio
async def test_reader_single_fragment_fires_immediately():
    """Sanity: single-fragment path delivers without buffering."""
    rpc, feed = make_rpc_with_mock_receive()

    op = 0x01  # META_CAPABILITIES
    txn = 0x12345678
    payload = msgpack.packb({"hello": "world"})

    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    rpc._cfc_pending[txn] = fut

    try:
        await rpc._ensure_reader_started()
        frame = pack_cfc(
            op=op,
            txn=txn,
            frag_idx=0,
            frag_total=1,
            payload_length=len(payload),
            body=payload,
        )
        feed(make_app_data_main(frame, command_id=0))

        op_out, txn_out, body_out, payload_length_out = await asyncio.wait_for(
            fut, timeout=2.0
        )
        assert op_out == op
        assert txn_out == txn
        assert body_out == payload
        assert payload_length_out == len(payload)
        # No multi-fragment state should ever have been allocated for txn.
        assert txn not in rpc._cfc_assembling
    finally:
        await rpc._stop_reader()
