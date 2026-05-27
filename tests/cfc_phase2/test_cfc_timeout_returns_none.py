"""§4.4b — timeout returns None (v8 addition).

Pure unit test. Validates the timeout-math branch (``remaining <= 0: return None``)
which has historically been a v1 bug surface. Per Arena Model A — closes the
most likely timeout-math bug surface.
"""

from __future__ import annotations

import asyncio
import itertools
import time

from unittest.mock import AsyncMock, MagicMock

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


def test_timeout_returns_none_no_hang():
    # _receive_main_message returns None on every call (infinite); drain loop
    # must honor wall-clock deadline and return None. itertools.repeat is used
    # instead of a fixed-length list because mocked returns are instantaneous,
    # so a tight Python loop can iterate thousands of times in 0.5s.
    rpc = _build_mock_rpc(itertools.repeat(None))

    start = time.monotonic()
    result = asyncio.run(_cfc_send_one_frame(rpc, b"frame_bytes", followup_timeout=0.5))
    elapsed = time.monotonic() - start

    assert result is None
    # Wall-clock should be within roughly followup_timeout + one PER_READ_TIMEOUT (0.5s) of slack.
    assert elapsed < 2.0, f"timeout drain looped past deadline: {elapsed:.2f}s"
