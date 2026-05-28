"""§4.5 — an unroutable inbound tag desyncs the reader, which fails the CFC
caller's pending future (Cook 1.5 reader model).

Phase 2.5 tested this on the direct ``_cfc_send_one_frame`` drain: a tag outside
the CFC allowlist raised ``CfcProtocolDesyncError`` inline. Cook 1.5 moves all
reads into the single reader task, which has a global tag allowlist
(``_SYNC_REPLY_TAGS`` / ``_ASYNC_EVENT_TAGS``). ``system_ping_response`` is now a
legitimate sync-reply tag, so it no longer desyncs — it is routed by command_id.
To trigger a desync we feed ``stop_session``, an OUTBOUND-only request tag that
must never appear inbound. The reader then fails every pending future
(including the CFC txn future) with ``CfcProtocolDesyncError``, which propagates
out of ``_cfc_send_one_frame``.
"""

from __future__ import annotations

import asyncio

import pytest

from flipper_mcp.modules.cfc.module import (
    CfcProtocolDesyncError,
    OP_PING,
    _cfc_send_one_frame,
)
from tests.phase3._helpers import (
    make_rpc_with_mock_receive,
    make_tagged_main,
    pack_cfc,
)


def test_unknown_content_tag_raises_desync():
    async def _run():
        rpc, feed = make_rpc_with_mock_receive()
        rpc._rpc_session_started = True
        outbound = pack_cfc(OP_PING, 0x00550055, 0, 1, 0, b"")
        try:
            task = asyncio.create_task(_cfc_send_one_frame(rpc, outbound))
            await asyncio.sleep(0.1)
            # stop_session is an outbound request tag — never legitimately inbound.
            feed(make_tagged_main("stop_session", command_id=999))
            with pytest.raises(CfcProtocolDesyncError):
                await asyncio.wait_for(task, timeout=2.0)
        finally:
            await rpc._stop_reader()

    asyncio.run(_run())
