"""Declared payload_length=500 but sends 800 bytes → ERROR code=BAD_FRAGMENT (2)."""

import asyncio

from flipper_mcp.modules.cfc.module import (
    ERR_BAD_FRAGMENT,
    OP_PING,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_oversized_frame_data(cfc_client, decode_resp):
    # Reset first
    from flipper_mcp.modules.cfc.module import flipper_cfc_call, OP_RESET
    asyncio.run(flipper_cfc_call(cfc_client, OP_RESET, None, timeout_s=10.0))

    frame = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xDEAD9,
        fragment_index=0,
        fragment_total=1,
        payload_length=500,
        fragment_data=b"x" * 800,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_FRAGMENT
