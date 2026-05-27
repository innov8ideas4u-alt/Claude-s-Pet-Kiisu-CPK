"""§4.5b — allowlisted async events are consumed during drain.

Pure unit test. Critical for v6 correctness; the v5 design would have raised
desync on these frames. For each of the 3 known async event tags (Q6 allowlist
minus app_data_exchange_request itself), verify that the drain consumes the
event frame, continues draining, and returns the subsequent CFC data frame.
"""

from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from flipper_mcp.core.protobuf_gen import flipper_pb2
from flipper_mcp.modules.cfc.module import _cfc_send_one_frame


def _build_mock_rpc(receive_side_effect):
    rpc = MagicMock()
    rpc._wire_lock = AsyncMock()
    rpc._wire_lock.__aenter__ = AsyncMock(return_value=rpc._wire_lock)
    rpc._wire_lock.__aexit__ = AsyncMock(return_value=None)
    rpc._get_next_command_id = MagicMock(return_value=42)
    rpc._send_main_raw = AsyncMock(return_value=True)
    rpc._receive_main_message = AsyncMock(side_effect=receive_side_effect)
    return rpc


def _make_app_data_exchange_main(payload: bytes, command_id: int = 0):
    m = flipper_pb2.Main()
    m.command_id = command_id
    m.app_data_exchange_request.data = payload
    return m


def _make_async_event_main(field_name: str):
    m = flipper_pb2.Main()
    sub = getattr(m, field_name)
    sub.SetInParent()
    return m


@pytest.mark.parametrize("field_name", [
    "app_state_response",
    "gui_screen_frame",
    "desktop_status",
    "empty",
])
def test_async_event_consumed_then_cfc_data_returned(field_name):
    rpc = _build_mock_rpc([
        _make_async_event_main(field_name),
        _make_app_data_exchange_main(b"data", command_id=0),
    ])
    result = asyncio.run(_cfc_send_one_frame(rpc, b"frame_bytes"))
    assert result == b"data", (
        f"async event {field_name} was not consumed during drain; "
        f"got {result!r} instead of b'data'"
    )
