"""Send frag 1 of a 2-frag txn, RESET, then PING — buffer must be cleaned."""

import asyncio

import msgpack

from flipper_mcp.modules.cfc.module import (
    CFC_MAX_FRAGMENT_PAYLOAD,
    OP_PING,
    OP_RESET,
    pack_cfc_frame,
    cfc_send_raw_frame,
    flipper_cfc_call,
)


def test_reset_during_assembling(cfc_client):
    # Build a 2-fragment outbound transaction (payload_length > 884 bytes)
    fake_payload = msgpack.packb({"echo": "x" * 1000})
    payload_length = len(fake_payload)
    assert payload_length > CFC_MAX_FRAGMENT_PAYLOAD

    chunk_a = fake_payload[:CFC_MAX_FRAGMENT_PAYLOAD]
    frag1 = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xCAFE0001,
        fragment_index=0,
        fragment_total=2,
        payload_length=payload_length,
        fragment_data=chunk_a,
    )
    # Send fragment 1 — no response expected, FAP enters ASSEMBLING
    asyncio.run(cfc_send_raw_frame(cfc_client, frag1))

    # Now RESET via the normal call API (different txn)
    resp = asyncio.run(flipper_cfc_call(cfc_client, OP_RESET, None, timeout_s=10.0))
    assert resp.get("status") == "ok"

    # PING should succeed (buffer cleared)
    resp2 = asyncio.run(flipper_cfc_call(cfc_client, OP_PING, {"echo": "clean"}, timeout_s=10.0))
    assert resp2.get("status") == "ok"
    assert resp2.get("echo") == "clean"
