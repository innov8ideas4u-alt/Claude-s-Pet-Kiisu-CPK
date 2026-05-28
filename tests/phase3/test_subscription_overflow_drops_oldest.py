"""Cook 2 / M1+M2 — subscription buffer is a bounded deque that drops the
OLDEST event atomically when full, and exposes the host-side drop count.

The reader (sole wire consumer) must NEVER block on a full buffer (M1), so
delivery is the synchronous, non-blocking ``_Subscription.push``. The buffer is
a ``collections.deque(maxlen=N)`` so eviction is atomic at the data-structure
level (M2) — no check-then-act window. This test overfills the buffer through
the live reader path (synthesized broadcasts fed via the mocked
``_receive_main_message``) and verifies: length caps at the depth, the oldest
events are the ones dropped, and ``overflow_count_so_far`` surfaces the drops.
"""

from __future__ import annotations

import asyncio

import msgpack

from flipper_mcp.core.protobuf_rpc import _Subscription, SUBSCRIPTION_QUEUE_DEPTH
from flipper_mcp.modules.cfc.module import OP_NFC_EVENT, flipper_cfc_listen
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)


def _nfc_payload(i: int) -> bytes:
    return msgpack.packb(
        {
            "i": i,
            "uid": b"\xde\xad\xbe\xef",
            "type": "iso14443a-4",
            "rssi": None,
            "timestamp_ms": i,
            "overflow_since_last": 0,
        },
        use_bin_type=True,
    )


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)


async def test_overflow_drops_oldest_and_counts():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()
    try:
        depth = SUBSCRIPTION_QUEUE_DEPTH
        extra = 5
        total = depth + extra
        for i in range(total):
            payload = _nfc_payload(i)
            # Broadcast txns MUST have the high bit set (M3). Garbage outer
            # command_id (Momentum uninit-malloc) — routing ignores it.
            txn = 0x80000000 + i + 1
            frame = pack_cfc(OP_NFC_EVENT, txn, 0, 1, len(payload), payload)
            feed(make_app_data_main(frame, command_id=0xDEADBEEF))

        sub = rpc._subscriptions[OP_NFC_EVENT]
        await _wait_until(lambda: sub.overflow_count == extra and len(sub.buffer) == depth)

        assert len(sub.buffer) == depth, f"buffer should cap at {depth}, got {len(sub.buffer)}"
        assert sub.overflow_count == extra, f"expected {extra} drops, got {sub.overflow_count}"

        # The OLDEST `extra` events were evicted, so the first event the consumer
        # sees is i == extra (the events 0..extra-1 were dropped).
        ev = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=2000)
        assert ev is not None
        assert ev["payload"]["i"] == extra
        assert ev["overflow_count_so_far"] == extra
    finally:
        await rpc._stop_reader()
