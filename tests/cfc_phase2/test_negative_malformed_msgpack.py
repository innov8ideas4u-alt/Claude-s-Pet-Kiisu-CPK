"""Valid frame, garbage msgpack payload → ERROR code=BAD_PAYLOAD (6)."""

import asyncio

from flipper_mcp.modules.cfc.module import (
    ERR_BAD_PAYLOAD,
    OP_PING,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_malformed_msgpack(cfc_client, decode_resp):
    # 0xC1 is reserved/unused in msgpack — guaranteed to fail decode as a map
    garbage = b"\xc1\xc1\xc1\xc1"
    frame = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xDEAD5,
        fragment_index=0,
        fragment_total=1,
        payload_length=len(garbage),
        fragment_data=garbage,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_PAYLOAD
