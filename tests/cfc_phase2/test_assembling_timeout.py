"""Frag 1 of 2-frag txn, wait 6s, send frag 2 → frag 2 rejected (timer cleaned state)."""

import asyncio
import time

from flipper_mcp.modules.cfc.module import (
    CFC_MAX_FRAGMENT_PAYLOAD,
    ERR_BAD_FRAGMENT,
    OP_PING,
    OP_RESET,
    cfc_send_raw_frame,
    flipper_cfc_call,
    pack_cfc_frame,
)


def test_assembling_timeout(cfc_client, decode_resp):
    # Reset first to ensure IDLE
    asyncio.run(flipper_cfc_call(cfc_client, OP_RESET, None, timeout_s=10.0))

    txn = 0xABBA0001
    chunk = b"\x00" * 100
    payload_length = len(chunk) + 50  # 50 more bytes expected in fragment 2

    frag1 = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=txn,
        fragment_index=0,
        fragment_total=2,
        payload_length=payload_length,
        fragment_data=chunk,
    )
    asyncio.run(cfc_send_raw_frame(cfc_client, frag1))

    # Wait for 5s ASSEMBLING timer to expire
    time.sleep(6.0)

    frag2 = pack_cfc_frame(
        op_code=OP_PING,
        transaction_id=txn,
        fragment_index=1,
        fragment_total=2,
        payload_length=payload_length,
        fragment_data=b"\x00" * 50,
    )
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frag2))
    op, _txn, body = decode_resp(raw)
    # Timer cleared state -> FAP is IDLE -> frag_idx=1 is an orphan fragment
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_FRAGMENT
