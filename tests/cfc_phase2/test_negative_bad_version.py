"""version=0x99 → ERROR code=BAD_FRAME (1)."""

import asyncio
import struct

from flipper_mcp.modules.cfc.module import (
    CFC_MAGIC,
    ERR_BAD_FRAME,
    cfc_send_raw_frame,
)


def test_bad_version(cfc_client, decode_resp):
    frame = struct.pack("<HBBIHHI", CFC_MAGIC, 0x99, 0x00, 0xDEAD2, 0, 1, 0)
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF
    assert body.get("code") == ERR_BAD_FRAME
