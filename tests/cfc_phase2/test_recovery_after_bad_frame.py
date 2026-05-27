"""Bad-frame ERROR followed by a clean PING — proves recovery."""

import asyncio
import struct

from flipper_mcp.modules.cfc.module import (
    CFC_HEADER_SIZE,
    CFC_VERSION,
    OP_PING,
    cfc_send_raw_frame,
    flipper_cfc_call,
    parse_cfc_header,
)


def test_recovery_after_bad_frame(cfc_client, decode_resp):
    # Manually-crafted frame with bad magic
    bad = struct.pack("<HBBIHHI", 0x0000, CFC_VERSION, 0x00, 0xBAD1, 0, 1, 0)
    raw = asyncio.run(cfc_send_raw_frame(cfc_client, bad))
    op, txn, body = decode_resp(raw)
    assert op == 0xFF, f"expected ERROR opcode, got 0x{op:02x}"

    # Now PING — must succeed
    resp = asyncio.run(flipper_cfc_call(cfc_client, OP_PING, {"echo": "recovered"}, timeout_s=10.0))
    assert resp.get("status") == "ok"
    assert resp.get("echo") == "recovered"
