"""Phase 3 reader-test helpers (importable; sibling to conftest.py).

Pytest's ``conftest.py`` is plugin-loaded and not always importable as a
regular module from arbitrary test paths, so the synthesizer/builder
helpers live here. Tests import from ``tests.phase3._helpers``; fixtures
(if any) live in ``conftest.py``.
"""

from __future__ import annotations

import asyncio
import struct
from typing import Any, Optional

from flipper_mcp.core.protobuf_gen import flipper_pb2
from flipper_mcp.core.protobuf_rpc import (
    CFC_HEADER_LEN,
    ProtobufRPC,
    _CFC_HEADER_FMT,
    _CFC_MAGIC,
    _CFC_VERSION,
)


class NullTransport:
    """Minimal stand-in for FlipperTransport — the reader's
    ``_receive_main_message`` is patched, so transport methods are never
    reached. Methods are no-ops sufficient to satisfy
    ``ProtobufRPC.__init__`` and any incidental call paths."""

    async def send(self, data: bytes) -> None:
        return None

    async def receive(self, timeout: float = 0.1) -> bytes:
        await asyncio.sleep(timeout)
        return b""

    async def receive_exact(self, n: int, timeout: float = 0.1) -> bytes:
        await asyncio.sleep(timeout)
        return b""

    def clear_receive_buffer(self) -> None:
        return None


def make_app_data_main(payload: bytes, command_id: int = 0) -> Any:
    """Build a Main with an ``app_data_exchange_request`` carrying ``payload``."""
    m = flipper_pb2.Main()
    m.command_id = command_id
    m.app_data_exchange_request.data = payload
    return m


def make_tagged_main(field_name: str, command_id: int = 0) -> Any:
    """Build a Main with the given content tag set (empty submessage).

    Useful for testing reader routing of sync-reply tags vs async-event tags
    vs unknown tags.
    """
    m = flipper_pb2.Main()
    m.command_id = command_id
    sub = getattr(m, field_name)
    sub.SetInParent()
    return m


def pack_cfc(
    op: int,
    txn: int,
    frag_idx: int,
    frag_total: int,
    payload_length: int,
    body: bytes,
) -> bytes:
    """Build a single CFC-framed bytes blob (header + this fragment's body).

    Mirrors ``modules/cfc/module.py:pack_cfc_frame`` but inlined so Phase 3
    tests don't import the CFC module surface (which already imports from
    ProtobufRPC; round-tripping through it at test-collection time would
    couple unrelated modules).
    """
    hdr = struct.pack(
        _CFC_HEADER_FMT,
        _CFC_MAGIC,
        _CFC_VERSION,
        op & 0xFF,
        txn & 0xFFFFFFFF,
        frag_idx & 0xFFFF,
        frag_total & 0xFFFF,
        payload_length & 0xFFFFFFFF,
    )
    return hdr + body


def make_rpc_with_mock_receive():
    """Return ``(rpc, feed)`` where ``feed(main_or_None)`` enqueues a Main
    for the next ``_receive_main_message`` call (or ``None`` to simulate
    a poll-timeout).

    Tests should call this inside the async test body so the queue binds
    to the running event loop. Cancel the reader on exit via
    ``await rpc._stop_reader()`` in a ``try/finally``.
    """
    rpc = ProtobufRPC(NullTransport())
    queue: "asyncio.Queue[Optional[Any]]" = asyncio.Queue()

    async def _mock_receive(timeout: float = 0.1):
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    rpc._receive_main_message = _mock_receive  # type: ignore[assignment]

    def feed(main_or_none) -> None:
        queue.put_nowait(main_or_none)

    return rpc, feed
