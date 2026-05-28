"""§4.4 — CFC response delivery through the single reader task (Cook 1.5).

Phase 2.5 mocked ``_cfc_send_one_frame``'s internal ``_receive_main_message``
drain and asserted it returned the raw ``app_data_exchange`` payload. Cook 1.5
makes ``_cfc_send_one_frame`` reader-driven: the background reader demuxes
inbound frames by inner CFC ``transaction_id`` and reassembles them, then
``_cfc_send_one_frame`` reconstructs a single-fragment CFC frame (header + body).

These rewrites inject the response frame VIA the reader (mocked
``_receive_main_message`` fed from a queue) and assert on the public result —
the returned frame's body. Validates v5's empty-payload fix too: an empty
inner payload returns a valid frame with a 0-byte body, not None.
"""

from __future__ import annotations

import asyncio

from flipper_mcp.modules.cfc.module import (
    CFC_HEADER_SIZE,
    OP_PING,
    _cfc_send_one_frame,
    parse_cfc_header,
)
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)


async def _roundtrip(resp_body: bytes, txn: int = 0x12340001) -> bytes:
    """Drive _cfc_send_one_frame and feed it a CFC response via the reader."""
    rpc, feed = make_rpc_with_mock_receive()
    rpc._rpc_session_started = True  # skip CLI probe; reader uses mocked receive
    outbound = pack_cfc(OP_PING, txn, 0, 1, len(resp_body), b"req")
    response = pack_cfc(OP_PING, txn, 0, 1, len(resp_body), resp_body)
    try:
        task = asyncio.create_task(_cfc_send_one_frame(rpc, outbound))
        # Let the call register _cfc_pending[txn] + start the reader, then feed
        # the response (outer command_id deliberately garbage — routed by txn).
        await asyncio.sleep(0.1)
        feed(make_app_data_main(response, command_id=0xDEADBEEF))
        return await asyncio.wait_for(task, timeout=2.0)
    finally:
        await rpc._stop_reader()


def test_broadcast_path_returns_data():
    result = asyncio.run(_roundtrip(b"hello"))
    assert result is not None
    _magic, _ver, op, _txn, _fi, frag_total, _plen = parse_cfc_header(result)
    assert op == OP_PING
    assert frag_total == 1
    assert result[CFC_HEADER_SIZE:] == b"hello"


def test_broadcast_path_returns_empty_bytes_not_none():
    """v5 fix preserved: an empty inner payload is still a valid CFC response —
    a frame with a 0-byte body, NOT None."""
    result = asyncio.run(_roundtrip(b""))
    assert result is not None
    assert result[CFC_HEADER_SIZE:] == b""
