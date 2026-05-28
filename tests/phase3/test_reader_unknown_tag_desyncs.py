"""§4.3 / §13.1 — reader raises CfcProtocolDesyncError on an unknown
content tag, fails every pending future, and stops cleanly.

The Phase 2.5 ``test_non_cfc_frame_raises_desync`` already pins this for
the direct ``_cfc_send_one_frame`` path. This test pins the same
behavior for the new reader-task path: if a frame with an unclassified
content tag reaches the reader, it surfaces as desync so callers don't
hang forever on futures the reader can no longer fulfill.

Note: ``system_ping_response`` IS in ``_SYNC_REPLY_TAGS`` (it's a legit
synchronous RPC reply), so it doesn't trigger desync — it just gets
routed to ``_pending[cmd_id]`` if there's a waiter, or logged-and-dropped
if there isn't. To trigger desync we use a tag that's neither in the
sync-reply set nor the async-event set — e.g. ``stop_session``, which
is an outbound request tag that should never appear inbound.
"""

from __future__ import annotations

import asyncio

import pytest

from flipper_mcp.core.protobuf_rpc import CfcProtocolDesyncError
from tests.phase3._helpers import make_rpc_with_mock_receive, make_tagged_main


@pytest.mark.asyncio
async def test_reader_unknown_tag_fails_all_pending():
    rpc, feed = make_rpc_with_mock_receive()

    fut_main: asyncio.Future = asyncio.get_running_loop().create_future()
    fut_cfc: asyncio.Future = asyncio.get_running_loop().create_future()
    rpc._pending[7] = fut_main
    rpc._cfc_pending[0xABCDABCD] = fut_cfc

    try:
        await rpc._ensure_reader_started()
        # stop_session is an outbound request tag — never legitimately inbound.
        feed(make_tagged_main("stop_session", command_id=999))

        # Both waiters should be failed with CfcProtocolDesyncError.
        with pytest.raises(CfcProtocolDesyncError):
            await asyncio.wait_for(fut_main, timeout=2.0)
        with pytest.raises(CfcProtocolDesyncError):
            await asyncio.wait_for(fut_cfc, timeout=2.0)

        # Reader records the error and stops.
        assert rpc._reader_desync_error is not None
        assert rpc._reader_stop.is_set()
    finally:
        await rpc._stop_reader()


@pytest.mark.asyncio
async def test_reader_sync_reply_routes_by_cmd_id():
    """Non-CFC sync reply (e.g. system_ping_response) with matching cmd_id
    populates ``_pending[cmd_id]``; with no match, gets logged-and-dropped
    (not desync)."""
    rpc, feed = make_rpc_with_mock_receive()

    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    rpc._pending[42] = fut

    try:
        await rpc._ensure_reader_started()
        feed(make_tagged_main("system_ping_response", command_id=42))

        main = await asyncio.wait_for(fut, timeout=2.0)
        assert main.command_id == 42
        assert main.WhichOneof("content") == "system_ping_response"
    finally:
        await rpc._stop_reader()
