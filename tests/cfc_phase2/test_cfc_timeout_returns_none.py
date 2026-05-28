"""§4.4b — timeout returns None without hanging (Cook 1.5 reader model).

When the reader never delivers a frame for our txn, ``_cfc_send_one_frame``'s
``asyncio.wait_for(fut, followup_timeout)`` must time out and return None within
roughly ``followup_timeout`` — not hang. The mocked ``_receive_main_message``
returns None on every poll (no frame ever arrives), so the txn future is never
resolved.
"""

from __future__ import annotations

import asyncio
import time

from flipper_mcp.modules.cfc.module import OP_PING, _cfc_send_one_frame
from tests.phase3._helpers import make_rpc_with_mock_receive, pack_cfc


def test_timeout_returns_none_no_hang():
    async def _run():
        rpc, _feed = make_rpc_with_mock_receive()
        rpc._rpc_session_started = True
        outbound = pack_cfc(OP_PING, 0x00990099, 0, 1, 0, b"")
        start = time.monotonic()
        try:
            result = await _cfc_send_one_frame(rpc, outbound, followup_timeout=0.5)
        finally:
            await rpc._stop_reader()
        return result, time.monotonic() - start

    result, elapsed = asyncio.run(_run())
    assert result is None
    # Should resolve at ~followup_timeout; allow generous slack for Windows.
    assert elapsed < 2.0, f"timeout drain looped past deadline: {elapsed:.2f}s"
