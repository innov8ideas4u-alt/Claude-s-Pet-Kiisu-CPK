"""payload_length=8193 → ERROR code=PAYLOAD_TOO_LARGE (3)."""

import asyncio

from flipper_mcp.modules.cfc.module import (
    ERR_PAYLOAD_TOO_LARGE,
    OP_PING,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_oversized_payload(cfc_client, decode_resp):
    # Send first fragment with payload_length=8193 (claimed, doesn't matter how much data we attach)
    frame = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xDEAD3,
        fragment_index=0,
        fragment_total=1,
        payload_length=8193,
        fragment_data=b"x" * 4,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_PAYLOAD_TOO_LARGE
