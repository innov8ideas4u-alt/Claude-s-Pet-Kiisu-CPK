"""Cook 3.2 — the NFC diagnostic reroute is readable host-side AND distinguishable
from a real NFC event.

This is the unit-level proof the live-fire HALT lesson demanded: BEFORE we redo
the tap dance, prove that the harness can subscribe to BOTH 0x42 (real events)
and 0x4F (diagnostics), that a synthesized 0x4F diag broadcast actually reaches
``flipper_cfc_listen(OP_NFC_DIAG)``, and that it CANNOT leak into the 0x42
real-event buffer that ``live_fire_nfc._check_real_event`` asserts on.

Pattern mirrors the Cook 2 chaos tests: synthesized CFC frames are fed through a
mocked ``_receive_main_message`` and routed by the live reader. No hardware.
"""

from __future__ import annotations

import msgpack
import pytest

from flipper_mcp.core.protobuf_rpc import _Subscription
from flipper_mcp.modules.cfc.module import (
    OP_NFC_DIAG,
    OP_NFC_EVENT,
    flipper_cfc_listen,
    flipper_cfc_subscribe,
)
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)

# Import the real operator-harness assertion so we prove a diag genuinely fails
# it (i.e. is distinguishable from a real event). Guarded narrowly to ImportError
# only: live_fire_nfc is import-safe (top-level is pure imports; asyncio.run is
# behind __main__), and pyserial is a core dep — so a *missing* harness is a real
# env gap we tolerate, but any OTHER error must propagate loudly rather than
# silently skip the distinguishability proof (the Cook 3.1 silent-green trap).
try:
    from tests.phase3.live_fire_nfc import _check_real_event

    _HAVE_HARNESS = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAVE_HARNESS = False


def _diag_payload(**over) -> bytes:
    body = {"event": "detect_cb", "protocol": "ISO14443-3A", "protocol_count": 1}
    body.update(over)
    return msgpack.packb(body, use_bin_type=True)


def _real_event_payload(**over) -> bytes:
    body = {
        "uid": b"\x04\x11\x22\x33",
        "type": "ISO14443-3A",
        "rssi": None,
        "timestamp_ms": 999,
        "overflow_since_last": 0,
    }
    body.update(over)
    return msgpack.packb(body, use_bin_type=True)


def _ready_rpc():
    """rpc wired to the mocked reader, session pre-marked started so subscribe's
    _ensure_session_and_reader starts the (mocked) reader without a CLI probe."""
    rpc, feed = make_rpc_with_mock_receive()
    rpc._rpc_session_started = True
    return rpc, feed


async def _subscribe_both(rpc):
    """Subscribe 0x4F via the real public API (host-only buffer, no FAP arm), and
    register the 0x42 buffer directly (the arm round-trip is not under test here —
    the chaos tests cover it). Then start the reader."""
    res = await flipper_cfc_subscribe(rpc, OP_NFC_DIAG)
    # The diag op has no FAP-side producer to arm — pure host buffer registration.
    assert res["subscribed"] is True
    assert res["armed"] is False
    assert OP_NFC_DIAG in rpc._subscriptions
    rpc._subscriptions[OP_NFC_EVENT] = _Subscription(op_code=OP_NFC_EVENT)
    await rpc._ensure_reader_started()


async def test_diag_broadcast_reaches_diag_listener_not_real_buffer():
    """A 0x4F diag broadcast is delivered to the diag listener and NEVER lands in
    the 0x42 real-event buffer (so it can never reach _check_real_event)."""
    rpc, feed = _ready_rpc()
    try:
        await _subscribe_both(rpc)

        diag = _diag_payload()
        dtxn = 0x80000010  # broadcast namespace: M3 high bit SET
        feed(
            make_app_data_main(
                pack_cfc(OP_NFC_DIAG, dtxn, 0, 1, len(diag), diag),
                command_id=0xCAFEF00D,  # garbage outer id — routed by inner op/txn
            )
        )

        ev = await flipper_cfc_listen(rpc, OP_NFC_DIAG, timeout_ms=2000)
        assert ev is not None, "diag broadcast never reached the 0x4F listener"
        assert ev["op_code"] == OP_NFC_DIAG
        assert ev["txn"] == dtxn
        assert ev["payload"]["event"] == "detect_cb"
        assert ev["payload"]["protocol"] == "ISO14443-3A"
        assert ev["payload"]["protocol_count"] == 1

        # The diag must NOT have leaked into the real-event buffer.
        leaked = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=200)
        assert leaked is None, "diag broadcast leaked into the 0x42 real-event buffer"
        assert len(rpc._subscriptions[OP_NFC_EVENT].buffer) == 0
    finally:
        await rpc._stop_reader()


async def test_real_event_and_diag_route_to_separate_buffers():
    """Feed BOTH a 0x4F diag and a 0x42 real event. The real event reaches the
    0x42 listener and passes _check_real_event; the diag reaches the 0x4F listener
    and is distinguishable (it would FAIL _check_real_event — no uid key)."""
    rpc, feed = _ready_rpc()
    try:
        await _subscribe_both(rpc)

        diag = _diag_payload(event="poll_ok", protocol=None, protocol_count=0, uid_len=4)
        feed(
            make_app_data_main(
                pack_cfc(OP_NFC_DIAG, 0x80000020, 0, 1, len(diag), diag),
                command_id=0,
            )
        )
        real = _real_event_payload()
        feed(
            make_app_data_main(
                pack_cfc(OP_NFC_EVENT, 0x80000021, 0, 1, len(real), real),
                command_id=0,
            )
        )

        ev_real = await flipper_cfc_listen(rpc, OP_NFC_EVENT, timeout_ms=2000)
        assert ev_real is not None
        assert ev_real["payload"]["uid"] == b"\x04\x11\x22\x33"

        ev_diag = await flipper_cfc_listen(rpc, OP_NFC_DIAG, timeout_ms=2000)
        assert ev_diag is not None
        assert ev_diag["payload"]["event"] == "poll_ok"
        assert ev_diag["payload"]["uid_len"] == 4
        # The diag has no "uid" key — structurally not a real event.
        assert "uid" not in ev_diag["payload"]

        if _HAVE_HARNESS:
            # The operator harness assertion passes on the real event...
            uid = _check_real_event("unit-real", ev_real)
            assert uid == b"\x04\x11\x22\x33"
            # ...and rejects the diag (proves they are distinguishable streams).
            with pytest.raises((KeyError, AssertionError, TypeError)):
                _check_real_event("unit-diag", ev_diag)
    finally:
        await rpc._stop_reader()


async def test_poll_failed_diag_payload_roundtrips():
    """A poll_failed diag (the 'detection ok but poll is the new bug' signal)
    round-trips through the reader with its reason intact."""
    rpc, feed = _ready_rpc()
    try:
        await _subscribe_both(rpc)

        diag = _diag_payload(event="poll_failed", protocol=None, protocol_count=0, reason="timeout")
        feed(
            make_app_data_main(
                pack_cfc(OP_NFC_DIAG, 0x80000030, 0, 1, len(diag), diag),
                command_id=0xDEAD,
            )
        )

        ev = await flipper_cfc_listen(rpc, OP_NFC_DIAG, timeout_ms=2000)
        assert ev is not None
        assert ev["payload"]["event"] == "poll_failed"
        assert ev["payload"]["reason"] == "timeout"

        # Still nothing in the real-event buffer.
        assert len(rpc._subscriptions[OP_NFC_EVENT].buffer) == 0
    finally:
        await rpc._stop_reader()
