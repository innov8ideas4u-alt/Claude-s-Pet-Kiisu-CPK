"""Frag 1 of txn 1, then frag 1 of txn 2 → BUSY for txn 2; txn 1 still completes."""

import asyncio
import time

import msgpack

from flipper_mcp.modules.cfc.module import (
    CFC_HEADER_SIZE,
    CFC_MAX_FRAGMENT_PAYLOAD,
    ERR_BUSY,
    OP_PING,
    OP_RESET,
    cfc_recv_response_assembled,  # v8.4 addition
    cfc_send_raw_frame,
    flipper_cfc_call,
    pack_cfc_frame,
)


def test_stale_transaction(cfc_client, decode_resp):
    asyncio.run(flipper_cfc_call(cfc_client, OP_RESET, None, timeout_s=10.0))

    txn1 = 0xCD000011
    txn2 = 0xCD000022

    # Build a 2-fragment payload for txn1
    big = msgpack.packb({"echo": "Y" * 950})
    assert len(big) > CFC_MAX_FRAGMENT_PAYLOAD
    chunk_a = big[:CFC_MAX_FRAGMENT_PAYLOAD]
    chunk_b = big[CFC_MAX_FRAGMENT_PAYLOAD:]
    payload_length = len(big)

    frag1_txn1 = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=txn1,
        fragment_index=0,
        fragment_total=2,
        payload_length=payload_length,
        fragment_data=chunk_a,
    )
    # No-wait: FAP won't send a response for this non-final fragment, so don't
    # burn 2.5s on a futile drain (we want txn2 to arrive well within the 5s
    # ASSEMBLING timer window).
    asyncio.run(cfc_send_raw_frame(cfc_client, frag1_txn1, wait_for_response=False))

    # Now hit FAP with a different txn — should get BUSY
    frag1_txn2 = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=txn2,
        fragment_index=0,
        fragment_total=1,
        payload_length=8,
        fragment_data=b"\x80\x80\x00\x00\x00\x00\x00\x00",  # not msgpack-relevant, won't be decoded
    )
    raw_busy = asyncio.run(cfc_send_raw_frame(cfc_client, frag1_txn2))
    op_b, _txn_b, body_b = decode_resp(raw_busy)
    assert op_b == 0xFF
    assert body_b.get("code") == ERR_BUSY

    # Finish txn1 before its 5s timer fires
    frag2_txn1 = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=txn1,
        fragment_index=1,
        fragment_total=2,
        payload_length=payload_length,
        fragment_data=chunk_b,
    )
    # v8.4: PING completions can now be multi-fragment (Phase 2.5 §6.4).
    # cfc_send_raw_frame returns only fragment 0; assemble the rest via the
    # new helper before decoding.
    raw_done_frag0 = asyncio.run(cfc_send_raw_frame(cfc_client, frag2_txn1))
    assembled_payload = asyncio.run(
        cfc_recv_response_assembled(cfc_client, raw_done_frag0)
    )
    # decode_resp expects header + payload bytes (header parsed, payload
    # msgpack-decoded). Synthesize that shape from frag0's header + assembled
    # payload.
    op_d, _txn_d, body_d = decode_resp(
        raw_done_frag0[:CFC_HEADER_SIZE] + assembled_payload
    )
    assert op_d == OP_PING, f"expected PING response for txn1, got 0x{op_d:02x}"
    assert body_d.get("status") == "ok"
    assert body_d.get("echo") == "Y" * 950
