"""Cook 1 (Sub-GHz vertical) — host-side mock tests, no hardware.

Covers the REAL host code added this cook:
  * ``decode_subghz_event`` — the thin 0x52 shape decoder, including the P6
    uint64 high-bit-key contract and malformed-payload rejection.
  * the generic subscription routing applied to the 0x52 event op — a synthesized
    broadcast fed through the live single-reader task is routed to the 0x52
    subscription buffer and delivered by ``flipper_cfc_listen`` (M3 high-bit txn),
    then decoded.
  * M1 — the 0x52 ``_Subscription`` deque drops the OLDEST event under flood and
    surfaces the host-side overflow count.

The FAP-side **G5** accept/reject gate (Princeton-only allowlist, ``key != 0``,
``bits`` in [8, 64]) lives in C (``cfc.c`` rx-cb) and cannot run in a host-only
mock; the authoritative check is the live-fire harness. We pin its documented
boundary contract here via a reference gate so a constant drift is caught in
review — see ``_fap_accepts`` and ``test_g5_and_allowlist_gate``.
"""

from __future__ import annotations

import asyncio

import msgpack
import pytest

from flipper_mcp.core.protobuf_rpc import (
    CFC_BROADCAST_TXN_BIT,
    SUBSCRIPTION_QUEUE_DEPTH,
    _Subscription,
)
from flipper_mcp.modules.cfc.module import (
    SUBGHZ_KEY_MAX,
    CfcProtocolError,
    OP_SUBGHZ_EVENT,
    decode_subghz_event,
    flipper_cfc_listen,
)
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)

# FAP-side G5 + allowlist gate, mirrored from cfc.c rx-cb (CFC_SUBGHZ_MIN_BITS=8,
# CFC_SUBGHZ_MAX_BITS=64, Princeton-only allowlist, key != 0). This is the contract
# the live-fire verifies on hardware; KEEP IN SYNC with cfc.c if the constants move.
_SUBGHZ_MIN_BITS = 8
_SUBGHZ_MAX_BITS = 64


def _fap_accepts(protocol: str, bits: int, key: int) -> bool:
    return (
        protocol == "Princeton"
        and key != 0
        and _SUBGHZ_MIN_BITS <= bits <= _SUBGHZ_MAX_BITS
    )


def _subghz_payload(
    *,
    protocol: str = "Princeton",
    bits: int = 24,
    key: int = 0xABC123,
    frequency: int = 433920000,
    timestamp_ms: int = 1234,
    drops: int = 0,
) -> bytes:
    return msgpack.packb(
        {
            "protocol": protocol,
            "bits": bits,
            "key": key,
            "frequency": frequency,
            "timestamp_ms": timestamp_ms,
            "drops": drops,
        },
        use_bin_type=True,
    )


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)


# --------------------------------------------------------------------------- #
# decode_subghz_event — real host code
# --------------------------------------------------------------------------- #


def test_decode_happy_path():
    ev = decode_subghz_event(msgpack.unpackb(_subghz_payload(), raw=False))
    assert ev == {
        "protocol": "Princeton",
        "bits": 24,
        "key": 0xABC123,
        "frequency": 433920000,
        "timestamp_ms": 1234,
        "drops": 0,
    }


def test_decode_high_bit_uint64_key():
    """P6: a key with the high bit set (> INT64_MAX, up to 2**64-1) must round-trip
    as an unsigned int — never truncated or misread as signed."""
    hi = 0xFFFFFFFFFFFFFFFF
    raw = msgpack.unpackb(_subghz_payload(key=hi), raw=False)
    assert raw["key"] == hi  # msgpack itself preserves a uint64
    ev = decode_subghz_event(raw)
    assert ev["key"] == hi == SUBGHZ_KEY_MAX
    assert ev["key"] > (1 << 63)  # genuinely high-bit set

    # A mid-range high-bit value too (not just the ceiling).
    mid = 0x8000000000000001
    ev2 = decode_subghz_event(msgpack.unpackb(_subghz_payload(key=mid), raw=False))
    assert ev2["key"] == mid


@pytest.mark.parametrize(
    "bad",
    [
        {"protocol": "Princeton", "bits": 24, "key": -1, "frequency": 1, "timestamp_ms": 1, "drops": 0},
        {"protocol": "Princeton", "bits": 24, "key": 1 << 64, "frequency": 1, "timestamp_ms": 1, "drops": 0},
        {"protocol": "Princeton", "bits": 24, "frequency": 1, "timestamp_ms": 1, "drops": 0},  # missing key
        {"protocol": 123, "bits": 24, "key": 1, "frequency": 1, "timestamp_ms": 1, "drops": 0},  # protocol not str
        {"protocol": "Princeton", "bits": True, "key": 1, "frequency": 1, "timestamp_ms": 1, "drops": 0},  # bool bits
        "not-a-dict",
    ],
)
def test_decode_rejects_malformed(bad):
    with pytest.raises(CfcProtocolError):
        decode_subghz_event(bad)


# --------------------------------------------------------------------------- #
# G5 + allowlist gate contract (mirrors cfc.c rx-cb; live-fire authoritative)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "protocol,bits,key,accepted",
    [
        ("Princeton", 24, 0xABC123, True),  # the live-fire case
        ("Princeton", 24, 0, False),  # G5: key == 0 dropped
        ("Princeton", 7, 0xABC, False),  # G5: bits < 8 dropped
        ("Princeton", 65, 0xABC, False),  # G5: bits > 64 dropped
        ("Princeton", 8, 0xABC, True),  # G5: lower boundary accepted
        ("Princeton", 64, 0xABC, True),  # G5: upper boundary accepted
        ("KeeLoq", 64, 0xABC, False),  # allowlist: non-Princeton dropped
    ],
)
def test_g5_and_allowlist_gate(protocol, bits, key, accepted):
    assert _fap_accepts(protocol, bits, key) is accepted


# --------------------------------------------------------------------------- #
# End-to-end: synthesized 0x52 broadcast routed through the live reader
# --------------------------------------------------------------------------- #


async def test_listen_delivers_decoded_event():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_SUBGHZ_EVENT] = _Subscription(op_code=OP_SUBGHZ_EVENT)
    await rpc._ensure_reader_started()
    try:
        payload = _subghz_payload(key=0xDEADBEEFCAFE)
        txn = CFC_BROADCAST_TXN_BIT | 7  # M3 broadcast namespace: high bit set
        frame = pack_cfc(OP_SUBGHZ_EVENT, txn, 0, 1, len(payload), payload)
        # Garbage outer command_id (Momentum uninit-malloc); routing ignores it.
        feed(make_app_data_main(frame, command_id=0xFFFFFFFF))

        ev = await flipper_cfc_listen(rpc, OP_SUBGHZ_EVENT, timeout_ms=2000)
        assert ev is not None
        assert ev["op_code"] == OP_SUBGHZ_EVENT
        assert ev["txn"] & CFC_BROADCAST_TXN_BIT, f"txn {ev['txn']:#010x} missing M3 high bit"

        decoded = decode_subghz_event(ev["payload"])
        assert decoded["protocol"] == "Princeton"
        assert decoded["bits"] == 24
        assert decoded["key"] == 0xDEADBEEFCAFE
        assert decoded["frequency"] == 433920000
        assert decoded["drops"] == 0
    finally:
        await rpc._stop_reader()


# --------------------------------------------------------------------------- #
# M1: the 0x52 subscription deque drops the OLDEST under flood
# --------------------------------------------------------------------------- #


async def test_subghz_overflow_drops_oldest_and_counts():
    rpc, feed = make_rpc_with_mock_receive()
    rpc._subscriptions[OP_SUBGHZ_EVENT] = _Subscription(op_code=OP_SUBGHZ_EVENT)
    await rpc._ensure_reader_started()
    try:
        depth = SUBSCRIPTION_QUEUE_DEPTH
        extra = 5
        for i in range(depth + extra):
            payload = _subghz_payload(key=0x1000 + i)  # distinct keys per event
            txn = CFC_BROADCAST_TXN_BIT + i + 1  # high bit set (M3)
            frame = pack_cfc(OP_SUBGHZ_EVENT, txn, 0, 1, len(payload), payload)
            feed(make_app_data_main(frame, command_id=0xDEADBEEF))

        sub = rpc._subscriptions[OP_SUBGHZ_EVENT]
        await _wait_until(lambda: sub.overflow_count == extra and len(sub.buffer) == depth)

        assert len(sub.buffer) == depth, f"buffer should cap at {depth}, got {len(sub.buffer)}"
        assert sub.overflow_count == extra, f"expected {extra} drops, got {sub.overflow_count}"

        # The OLDEST `extra` events were evicted, so the first one the consumer
        # sees is i == extra (events 0..extra-1 dropped).
        ev = await flipper_cfc_listen(rpc, OP_SUBGHZ_EVENT, timeout_ms=2000)
        assert ev is not None
        decoded = decode_subghz_event(ev["payload"])
        assert decoded["key"] == 0x1000 + extra
        assert ev["overflow_count_so_far"] == extra
    finally:
        await rpc._stop_reader()
