"""§4.5 — unknown content tag during CFC drain raises CfcProtocolDesyncError.

Pure unit test. ``system_ping_response`` is a synchronous-reply tag NOT in
the v6 Q6 allowlist (allowlist = app_data_exchange_request, app_state_response,
gui_screen_frame, desktop_status). If it appears during CFC's drain window
the wire-lock invariant was violated and the defensive branch must raise loudly.
"""

from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from flipper_mcp.core.protobuf_gen import flipper_pb2
from flipper_mcp.modules.cfc.module import (
    CfcProtocolDesyncError,
    _cfc_send_one_frame,
)


def _build_mock_rpc(receive_side_effect):
    rpc = MagicMock()
    rpc._wire_lock = AsyncMock()
    rpc._wire_lock.__aenter__ = AsyncMock(return_value=rpc._wire_lock)
    rpc._wire_lock.__aexit__ = AsyncMock(return_value=None)
    rpc._get_next_command_id = MagicMock(return_value=42)
    rpc._send_main_raw = AsyncMock(return_value=True)
    rpc._receive_main_message = AsyncMock(side_effect=receive_side_effect)
    return rpc


def _make_system_ping_response_main():
    m = flipper_pb2.Main()
    m.system_ping_response.SetInParent()
    return m


def test_unknown_content_tag_raises_desync():
    rpc = _build_mock_rpc([_make_system_ping_response_main()])
    with pytest.raises(CfcProtocolDesyncError, match="unknown content tag"):
        asyncio.run(_cfc_send_one_frame(rpc, b"frame_bytes"))
