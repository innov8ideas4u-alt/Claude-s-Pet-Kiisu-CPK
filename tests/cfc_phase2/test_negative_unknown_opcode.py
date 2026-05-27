"""op_code=0xAA (unused) → ERROR code=UNKNOWN_OPCODE (7)."""

import asyncio

import msgpack

from flipper_mcp.modules.cfc.module import (
    ERR_UNKNOWN_OPCODE,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_unknown_opcode(cfc_client, decode_resp):
    payload = msgpack.packb({})
    frame = pack_cfc_frame(
        op_code=0xAA,
        transaction_id=0xDEAD6,
        fragment_index=0,
        fragment_total=1,
        payload_length=len(payload),
        fragment_data=payload,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_UNKNOWN_OPCODE
