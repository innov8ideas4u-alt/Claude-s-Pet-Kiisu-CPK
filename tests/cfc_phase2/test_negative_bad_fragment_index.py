"""fragment_index=5, fragment_total=3 → ERROR code=BAD_FRAGMENT (2)."""

import asyncio

from flipper_mcp.modules.cfc.module import (
    ERR_BAD_FRAGMENT,
    OP_PING,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_bad_fragment_index(cfc_client, decode_resp):
    frame = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xDEAD4,
        fragment_index=5,
        fragment_total=3,
        payload_length=10,
        fragment_data=b"\x00" * 4,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_FRAGMENT
