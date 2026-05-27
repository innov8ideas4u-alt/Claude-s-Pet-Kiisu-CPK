"""fragment_total=0 → ERROR code=BAD_FRAGMENT (2)."""

import asyncio

from flipper_mcp.modules.cfc.module import (
    ERR_BAD_FRAGMENT,
    OP_PING,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_zero_fragment_total(cfc_client, decode_resp):
    frame = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xDEAD7,
        fragment_index=0,
        fragment_total=0,
        payload_length=10,
        fragment_data=b"x" * 4,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_FRAGMENT
