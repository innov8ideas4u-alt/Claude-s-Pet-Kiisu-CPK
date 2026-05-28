"""Cook 2 — public subscription surface: subscribe / listen / unsubscribe.

These exercise the host-side lifecycle WITHOUT hardware. The happy-path tests
use a host-only op_code (one with no FAP-side producer to arm), so subscribe is
pure buffer registration and no wire round-trip is needed. The arm path (event
op_code 0x42 → request op_code 0x40) is verified separately by patching
``flipper_cfc_call``.
"""

from __future__ import annotations

import asyncio

import msgpack
import pytest

import flipper_mcp.modules.cfc.module as cfc_mod
from flipper_mcp.modules.cfc.module import (
    ERR_SUB_BUSY,
    OP_NFC_EVENT,
    OP_NFC_SUBSCRIBE_CAPTURE,
    CfcNotSubscribedError,
    CfcRemoteError,
    flipper_cfc_listen,
    flipper_cfc_subscribe,
    flipper_cfc_unsubscribe,
)
from tests.phase3._helpers import (
    make_app_data_main,
    make_rpc_with_mock_receive,
    pack_cfc,
)

# A host-only op_code with no entry in _SUBSCRIBE_ARM_OP — subscribing to it
# registers a buffer without touching the FAP, isolating the host lifecycle.
HOST_ONLY_OP = 0x55


def _ready_rpc():
    """An rpc wired to the mocked reader, session pre-marked started so
    subscribe's _ensure_session_and_reader starts the (mocked) reader without a
    real CLI probe."""
    rpc, feed = make_rpc_with_mock_receive()
    rpc._rpc_session_started = True
    return rpc, feed


async def test_subscribe_listen_unsubscribe_host_only():
    rpc, feed = _ready_rpc()
    try:
        res = await flipper_cfc_subscribe(rpc, HOST_ONLY_OP)
        assert res["subscribed"] is True
        assert res["armed"] is False
        assert HOST_ONLY_OP in rpc._subscriptions

        payload = msgpack.packb({"hello": "world"}, use_bin_type=True)
        txn = 0x80000042  # broadcast: high bit set
        frame = pack_cfc(HOST_ONLY_OP, txn, 0, 1, len(payload), payload)
        feed(make_app_data_main(frame, command_id=0xFFFFFFFF))

        ev = await flipper_cfc_listen(rpc, HOST_ONLY_OP, timeout_ms=2000)
        assert ev is not None
        assert ev["op_code"] == HOST_ONLY_OP
        assert ev["txn"] == txn
        assert ev["payload"] == {"hello": "world"}

        unsub = await flipper_cfc_unsubscribe(rpc, HOST_ONLY_OP)
        assert unsub["was_subscribed"] is True
        assert HOST_ONLY_OP not in rpc._subscriptions

        with pytest.raises(CfcNotSubscribedError):
            await flipper_cfc_listen(rpc, HOST_ONLY_OP, timeout_ms=100)
    finally:
        await rpc._stop_reader()


async def test_subscribe_q2_exclusive_busy():
    rpc, feed = _ready_rpc()
    try:
        await flipper_cfc_subscribe(rpc, HOST_ONLY_OP)
        with pytest.raises(CfcRemoteError) as ei:
            await flipper_cfc_subscribe(rpc, HOST_ONLY_OP)
        assert ei.value.code == ERR_SUB_BUSY
    finally:
        await rpc._stop_reader()


async def test_listen_without_subscribe_raises():
    rpc, _feed = _ready_rpc()
    try:
        with pytest.raises(CfcNotSubscribedError):
            await flipper_cfc_listen(rpc, HOST_ONLY_OP, timeout_ms=100)
    finally:
        await rpc._stop_reader()


async def test_listen_timeout_returns_none():
    rpc, _feed = _ready_rpc()
    try:
        await flipper_cfc_subscribe(rpc, HOST_ONLY_OP)
        ev = await flipper_cfc_listen(rpc, HOST_ONLY_OP, timeout_ms=200)
        assert ev is None
    finally:
        await rpc._stop_reader()


async def test_unsubscribe_idempotent():
    rpc, _feed = _ready_rpc()
    try:
        # Never subscribed: idempotent no-op, not an error.
        first = await flipper_cfc_unsubscribe(rpc, HOST_ONLY_OP)
        assert first["was_subscribed"] is False
        assert first["unsubscribed"] is False

        await flipper_cfc_subscribe(rpc, HOST_ONLY_OP)
        second = await flipper_cfc_unsubscribe(rpc, HOST_ONLY_OP)
        assert second["was_subscribed"] is True

        # Unsubscribe again — back to the idempotent no-op.
        third = await flipper_cfc_unsubscribe(rpc, HOST_ONLY_OP)
        assert third["was_subscribed"] is False
    finally:
        await rpc._stop_reader()


async def test_unsubscribe_wakes_blocked_listener():
    """A listener blocked on the subscription Event must return promptly when the
    subscription is cancelled — not hang out its full timeout (closed flag)."""
    rpc, _feed = _ready_rpc()
    try:
        await flipper_cfc_subscribe(rpc, HOST_ONLY_OP)
        listen_task = asyncio.create_task(
            flipper_cfc_listen(rpc, HOST_ONLY_OP, timeout_ms=10_000)
        )
        await asyncio.sleep(0.1)  # let the listener block on the Event
        await flipper_cfc_unsubscribe(rpc, HOST_ONLY_OP)
        # 2s ≪ the 10s listen timeout — proves the close woke it, not the timeout.
        result = await asyncio.wait_for(listen_task, timeout=2.0)
        assert result is None
    finally:
        await rpc._stop_reader()


async def test_subscribe_arms_fap_producer(monkeypatch):
    """subscribe(OP_NFC_EVENT) must arm the FAP via OP_NFC_SUBSCRIBE_CAPTURE."""
    rpc, _feed = _ready_rpc()
    calls = []

    async def fake_call(client, op_code, payload, timeout_s=30.0):
        calls.append(op_code)
        return {"status": "ok"}

    monkeypatch.setattr(cfc_mod, "flipper_cfc_call", fake_call)
    try:
        res = await flipper_cfc_subscribe(rpc, OP_NFC_EVENT)
        assert res["armed"] is True
        assert calls == [OP_NFC_SUBSCRIBE_CAPTURE]
        assert OP_NFC_EVENT in rpc._subscriptions
    finally:
        await rpc._stop_reader()


async def test_subscribe_arm_failure_rolls_back(monkeypatch):
    """If arming the FAP fails, the host subscription must be rolled back so the
    host never believes it's subscribed to a stream the FAP never started."""
    rpc, _feed = _ready_rpc()

    async def boom(client, op_code, payload, timeout_s=30.0):
        raise CfcRemoteError(ERR_SUB_BUSY, "worker already armed")

    monkeypatch.setattr(cfc_mod, "flipper_cfc_call", boom)
    try:
        with pytest.raises(CfcRemoteError):
            await flipper_cfc_subscribe(rpc, OP_NFC_EVENT)
        assert OP_NFC_EVENT not in rpc._subscriptions
    finally:
        await rpc._stop_reader()
