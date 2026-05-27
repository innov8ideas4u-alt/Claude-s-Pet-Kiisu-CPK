"""fragment_index=1, fragment_total=2 to IDLE FAP → ERROR code=BAD_FRAGMENT (2)."""

import asyncio

from flipper_mcp.modules.cfc.module import (
    ERR_BAD_FRAGMENT,
    OP_PING,
    cfc_send_raw_frame,
    pack_cfc_frame,
)


def test_orphan_fragment(cfc_client, decode_resp):
    # Reset first to guarantee IDLE
    from flipper_mcp.modules.cfc.module import flipper_cfc_call, OP_RESET
    asyncio.run(flipper_cfc_call(cfc_client, OP_RESET, None, timeout_s=10.0))

    frame = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=0xDEAD8,
        fragment_index=1,
        fragment_total=2,
        payload_length=20,
        fragment_data=b"x" * 10,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_FRAGMENT
