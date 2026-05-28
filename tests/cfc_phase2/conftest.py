"""Shared fixtures for CFC Phase 2 live-hardware tests.

The fixture launches the CFC FAP on AmorPoee (mntm-dev) and provides a
connected ``FlipperClient`` for the test, then exits the FAP on teardown.

Auto-skip when no Flipper hardware is reachable: set env CFC_REQUIRE_HW=1 to
force tests to error out instead of being skipped.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import pytest

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.usb import USBTransport

CFC_FAP_PATH = "/ext/apps/Tools/cfc.fap"


def _bool_env(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "").lower() in ("1", "true", "yes", "on")


async def _make_client() -> FlipperClient:
    port_override = os.environ.get("CFC_FLIPPER_PORT")  # optional manual override
    config: dict[str, Any] = {"baudrate": 115200}
    if port_override:
        config["port"] = port_override
    transport = USBTransport(config)
    client = FlipperClient(transport)
    ok = await client.connect()
    if not ok:
        raise RuntimeError(
            f"could not open Flipper transport (port={transport.port}); "
            f"last_error={client.last_connection_error}"
        )
    return client


async def _launch_cfc(client: FlipperClient) -> None:
    """app_start('cfc', 'RPC') — firmware rewrites args to pass the RpcAppSystem pointer."""
    client.rpc._ensure_protobuf_rpc()
    rpc = client.rpc.protobuf_rpc
    if rpc is None:
        raise RuntimeError("ProtobufRPC unavailable (protobuf_gen import failed?)")
    # Best-effort: exit any prior CFC instance so we land in a known clean state.
    # Phase 3: use the public app_exit() (reader-driven, acquires the wire lock
    # itself) rather than manually holding _wire_lock then calling
    # _send_rpc_message — the latter would now self-deadlock (the migrated
    # _send_rpc_message acquires the non-reentrant wire lock for its send).
    try:
        await rpc.app_exit()
        await asyncio.sleep(0.2)
    except Exception:
        pass
    result = await rpc.app_start(CFC_FAP_PATH, "RPC")
    if not result:
        raise RuntimeError(
            f"app_start(cfc, RPC) failed: status_name={result.status_name}"
        )
    # Small grace period for the FAP to call rpc_system_app_send_started()
    await asyncio.sleep(0.4)


async def _exit_cfc(client: FlipperClient) -> None:
    """Send AppExit RPC so the FAP terminates cleanly."""
    try:
        rpc = client.rpc.protobuf_rpc
        if rpc is None:
            return
        # Public app_exit() is reader-driven and acquires the wire lock itself.
        await rpc.app_exit()
    except Exception:  # best-effort
        pass
    await asyncio.sleep(0.2)


@pytest.fixture
def cfc_client():
    """Per-test fixture: opens transport, starts CFC FAP, yields client, exits FAP."""

    async def _setup():
        client = await _make_client()
        try:
            await _launch_cfc(client)
        except Exception:
            await client.disconnect()
            raise
        return client

    require_hw = _bool_env("CFC_REQUIRE_HW", default=False)

    try:
        client = asyncio.run(_setup())
    except Exception as e:
        if require_hw:
            raise
        pytest.skip(f"CFC hardware unavailable: {e}")

    yield client

    try:
        asyncio.run(_exit_cfc(client))
    finally:
        try:
            asyncio.run(client.disconnect())
        except Exception:
            pass


@pytest.fixture
def cfc_call(cfc_client):
    """Sync wrapper around flipper_cfc_call so tests don't all juggle asyncio.run."""
    from flipper_mcp.modules.cfc.module import flipper_cfc_call

    def _call(op_code: int, payload: Any = None, timeout_s: float = 10.0) -> dict:
        return asyncio.run(flipper_cfc_call(cfc_client, op_code, payload, timeout_s))

    return _call


@pytest.fixture
def cfc_send_raw(cfc_client):
    """Sync wrapper around cfc_send_raw_frame for negative tests."""
    from flipper_mcp.modules.cfc.module import cfc_send_raw_frame

    def _send(raw: bytes):
        return asyncio.run(cfc_send_raw_frame(cfc_client, raw))

    return _send


def _decode_msgpack_or_none(data: bytes):
    import msgpack

    try:
        return msgpack.unpackb(data, raw=False, strict_map_key=False)
    except Exception:
        return None


@pytest.fixture
def decode_resp():
    """Helper: given raw inbound bytes (CFC frame), return (op_code, txn, decoded_dict_or_none)."""
    from flipper_mcp.modules.cfc.module import (
        CFC_HEADER_SIZE,
        CFC_MAGIC,
        CFC_VERSION,
        parse_cfc_header,
    )

    def _decode(raw: bytes):
        assert raw is not None, "no response from FAP"
        assert len(raw) >= CFC_HEADER_SIZE, f"response too short: {len(raw)} bytes"
        magic, version, op, txn, frag_idx, frag_total, payload_length = parse_cfc_header(raw)
        assert magic == CFC_MAGIC, f"bad magic 0x{magic:04x}"
        assert version == CFC_VERSION, f"bad version 0x{version:02x}"
        payload = raw[CFC_HEADER_SIZE:]
        return op, txn, _decode_msgpack_or_none(payload)

    return _decode
