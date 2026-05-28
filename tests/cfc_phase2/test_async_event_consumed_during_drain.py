"""§4.5b — async/sync-reply event frames are consumed by the reader; the CFC
response that follows is still delivered (Cook 1.5 reader model).

Phase 2.5 verified the inline drain consumed allowlisted events then returned
the next CFC data frame. Cook 1.5 moves this into the single reader task: an
async-event tag (``app_state_response`` / ``desktop_status``) or a sync-reply tag
with no matching waiter (``gui_screen_frame`` / ``empty``) is consumed/dropped,
and the subsequent ``app_data_exchange`` frame for our txn is delivered to the
CFC future. ``_cfc_send_one_frame`` then returns the reconstructed CFC frame.
"""

from __future__ import annotations

import asyncio

import pytest

from flipper_mcp.modules.cfc.module import (
    CFC_HEADER_SIZE,
    OP_PING,
    _cfc_send_one_frame,
)
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    make_tagged_main,
    pack_cfc,
)


@pytest.mark.parametrize("field_name", [
    "app_state_response",
    "gui_screen_frame",
    "desktop_status",
    "empty",
])
def test_async_event_consumed_then_cfc_data_returned(field_name):
    async def _run():
        rpc, feed = make_rpc_with_mock_receive()
        rpc._rpc_session_started = True
        txn = 0x00770077
        outbound = pack_cfc(OP_PING, txn, 0, 1, 4, b"req")
        response = pack_cfc(OP_PING, txn, 0, 1, 4, b"data")
        try:
            task = asyncio.create_task(_cfc_send_one_frame(rpc, outbound))
            await asyncio.sleep(0.1)
            # Event frame first (no matching waiter → consumed/dropped by reader),
            # then the real CFC response (routed to our txn future).
            feed(make_tagged_main(field_name, command_id=0))
            feed(make_app_data_main(response, command_id=0xDEADBEEF))
            return await asyncio.wait_for(task, timeout=2.0)
        finally:
            await rpc._stop_reader()

    result = asyncio.run(_run())
    assert result is not None, (
        f"async event {field_name} was not consumed; CFC response not delivered"
    )
    assert result[CFC_HEADER_SIZE:] == b"data"
