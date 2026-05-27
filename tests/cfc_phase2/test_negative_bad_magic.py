"""magic=0x0000 → ERROR code=BAD_FRAME (1)."""

import asyncio
import struct

from flipper_mcp.modules.cfc.module import (
    CFC_VERSION,
    ERR_BAD_FRAME,
    cfc_send_raw_frame,
)


def test_bad_magic(cfc_client, decode_resp):
    frame = struct.pack("<HBBIHHI", 0x0000, CFC_VERSION, 0x00, 0xDEAD1, 0, 1, 0)
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, frame))
    op, _txn, body = decode_resp(raw)
    assert op == 0xFF, f"expected ERROR, got 0x{op:02x}"
    assert isinstance(body, dict)
    assert body.get("code") == ERR_BAD_FRAME
