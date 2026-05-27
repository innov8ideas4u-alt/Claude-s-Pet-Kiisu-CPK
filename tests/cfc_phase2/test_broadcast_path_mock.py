"""§4.4 — broadcast path accepts command_id == 0 (incl. empty payload).

Pure unit test (no hardware). Uses the §4.0 scaffold verbatim.
Validates v5's empty-payload fix: a CFC frame with structurally present
``app_data_exchange_request`` and ``data=b""`` returns ``b""``, NOT None,
NOT raises ``CfcProtocolDesyncError``.
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


def test_broadcast_path_returns_data():
    rpc = _build_mock_rpc([_make_app_data_exchange_main(b"hello", command_id=0)])
    result = asyncio.run(_cfc_send_one_frame(rpc, b"frame_bytes"))
    assert result == b"hello"


def test_broadcast_path_returns_empty_bytes_not_none():
    """v5 fix: structurally present app_data_exchange_request with empty bytes
    payload must return b"", not fall through to defensive desync branch."""
    rpc = _build_mock_rpc([_make_app_data_exchange_main(b"", command_id=0)])
    result = asyncio.run(_cfc_send_one_frame(rpc, b"frame_bytes"))
    assert result == b""
    assert result is not None
