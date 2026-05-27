"""CFC host-side module — Phase 2 skeleton.

Speaks the CFC wire protocol (DAY8_FAP_PHASE1_SPEC v5.1) on top of CPK's
internal protobuf transport. Single MCP tool surface: ``flipper_cfc_call``.

Imports:
- ``flipper_mcp.core.protobuf_gen.flipper_pb2`` / ``application_pb2``
- ``flipper_mcp.core.protobuf_rpc.ProtobufRPC._wire_lock`` / ``_send_rpc_message``
  / ``_get_next_command_id``

External ``flipperzero-protobuf`` PyPI is NOT used — see spec §7.1 v5.1.
"""

from __future__ import annotations

import asyncio
import itertools
import struct
import threading
import time
from typing import Any, Optional

import msgpack

from flipper_mcp.core.protobuf_gen import flipper_pb2, application_pb2

# --- Protocol constants (spec §4) ---

CFC_MAGIC: int = 0x4346
CFC_VERSION: int = 0x01
CFC_HEADER_SIZE: int = 16
CFC_MAX_FRAGMENT_PAYLOAD: int = 884
CFC_MAX_TRANSACTION: int = 8192

OP_PING: int = 0x00
OP_META_CAPABILITIES: int = 0x01
OP_META_VERSION: int = 0x02
OP_RESET: int = 0xFE
OP_ERROR: int = 0xFF

ERR_BAD_FRAME: int = 1
ERR_BAD_FRAGMENT: int = 2
ERR_PAYLOAD_TOO_LARGE: int = 3
ERR_OUT_OF_MEMORY: int = 4
ERR_BUSY: int = 5
ERR_BAD_PAYLOAD: int = 6
ERR_UNKNOWN_OPCODE: int = 7
ERR_INTERNAL: int = 99

# --- Exceptions ---


class CfcRemoteError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"CFC remote error {code}: {message}")
        self.code = code
        self.message = message


class CfcTimeoutError(Exception):
    pass


class CfcProtocolError(Exception):
    pass


# --- Header pack/unpack ---

_HEADER_FMT = "<HBBIHHI"  # magic u16, version u8, op u8, txn u32, frag_idx u16, frag_total u16, payload_len u32

assert struct.calcsize(_HEADER_FMT) == CFC_HEADER_SIZE


def pack_cfc_frame(
    op_code: int,
    transaction_id: int,
    fragment_index: int,
    fragment_total: int,
    payload_length: int,
    fragment_data: bytes,
) -> bytes:
    """Build a single CFC frame (header + fragment bytes). No msgpack involvement."""
    header = struct.pack(
        _HEADER_FMT,
        CFC_MAGIC,
        CFC_VERSION,
        op_code & 0xFF,
        transaction_id & 0xFFFFFFFF,
        fragment_index & 0xFFFF,
        fragment_total & 0xFFFF,
        payload_length & 0xFFFFFFFF,
    )
    return header + fragment_data


def parse_cfc_header(frame: bytes) -> tuple[int, int, int, int, int, int, int]:
    """Return (magic, version, op_code, transaction_id, frag_idx, frag_total, payload_length)."""
    if len(frame) < CFC_HEADER_SIZE:
        raise CfcProtocolError(f"frame {len(frame)} < header {CFC_HEADER_SIZE}")
    return struct.unpack(_HEADER_FMT, frame[:CFC_HEADER_SIZE])


# --- transaction_id allocator: thread-safe monotonic counter per spec §7.2 ---

_txn_lock = threading.Lock()
_txn_counter = itertools.count(1)


def _next_transaction_id() -> int:
    with _txn_lock:
        return next(_txn_counter) & 0xFFFFFFFF


def _get_protobuf_rpc(client: Any) -> Any:
    """Resolve a ProtobufRPC instance from a FlipperClient or a ProtobufRPC directly."""
    if hasattr(client, "_wire_lock") and hasattr(client, "_send_rpc_message"):
        return client
    rpc = getattr(client, "rpc", None)
    if rpc is not None and hasattr(rpc, "protobuf_rpc") and rpc.protobuf_rpc is not None:
        return rpc.protobuf_rpc
    if rpc is not None and hasattr(rpc, "_wire_lock"):
        return rpc
    raise CfcProtocolError(
        "could not resolve a ProtobufRPC instance from the given client"
    )


# --- Wire-level primitive: send one CFC-framed envelope, receive one envelope's bytes ---


async def _cfc_send_one_frame(
    client: Any,
    frame_bytes: bytes,
    wait_for_response: bool = True,
    followup_timeout: float = 2.5,
) -> Optional[bytes]:
    """Send one CFC frame in a single app_data_exchange envelope. Return response bytes or None.

    Holds the ProtobufRPC ``_wire_lock`` for the duration of the send+receive.

    Set ``wait_for_response=False`` for non-final-fragment sends where the FAP
    is expected to NOT send back any application-layer response; the host then
    only waits for the RPC confirm (cheap, ~ms) and returns immediately.
    """
    rpc = _get_protobuf_rpc(client)
    async with rpc._wire_lock:
        main_request = flipper_pb2.Main()
        main_request.command_id = rpc._get_next_command_id()
        main_request.has_next = False
        req = application_pb2.DataExchangeRequest()
        req.data = frame_bytes
        main_request.app_data_exchange_request.CopyFrom(req)

        resp = await rpc._send_rpc_message(main_request)
        if resp is None:
            return None
        if resp.HasField("app_data_exchange_request") and resp.app_data_exchange_request.data:
            return bytes(resp.app_data_exchange_request.data)

        if not wait_for_response:
            return None

        followup = await rpc._receive_main_message(timeout=followup_timeout)
        if followup is None:
            return None
        if followup.HasField("app_data_exchange_request") and followup.app_data_exchange_request.data:
            return bytes(followup.app_data_exchange_request.data)
        return None


async def cfc_send_raw_frame(
    client: Any,
    raw_bytes: bytes,
    wait_for_response: bool = True,
) -> Optional[bytes]:
    """Public negative-test helper: send already-built frame bytes (no checks)."""
    return await _cfc_send_one_frame(client, raw_bytes, wait_for_response=wait_for_response)


# --- High-level call API ---


def _decode_msgpack(buf: bytes) -> Any:
    try:
        return msgpack.unpackb(buf, raw=False, strict_map_key=False)
    except Exception as e:
        raise CfcProtocolError(f"malformed msgpack response: {e}") from e


async def flipper_cfc_call(
    client: Any,
    op_code: int,
    payload: Any,
    timeout_s: float = 30.0,
) -> dict:
    """Send one logical CFC request, wait for the assembled response.

    - msgpack-encodes payload
    - fragments to ≤884-byte chunks (single-fragment in Phase 2 typical use)
    - sends frames sequentially under the wire lock (one at a time)
    - reassembles inbound fragments matching the outbound transaction_id
    - raises CfcRemoteError on op_code=0xFF response
    """
    if payload is None:
        payload_bytes = b""
    else:
        payload_bytes = msgpack.packb(payload, use_bin_type=True)

    payload_length = len(payload_bytes)
    if payload_length > CFC_MAX_TRANSACTION:
        raise CfcProtocolError(
            f"outbound payload {payload_length} > {CFC_MAX_TRANSACTION} (CFC_MAX_TRANSACTION)"
        )

    txn = _next_transaction_id()

    # Fragmentation (Phase 2 usually single-fragment; code path exercised for completeness)
    if payload_length <= CFC_MAX_FRAGMENT_PAYLOAD:
        fragments = [payload_bytes]
    else:
        fragments = [
            payload_bytes[i : i + CFC_MAX_FRAGMENT_PAYLOAD]
            for i in range(0, payload_length, CFC_MAX_FRAGMENT_PAYLOAD)
        ]
    total = max(1, len(fragments))

    response_buffers: list[bytes] = []  # collected fragment payloads (post-header)
    response_expected_total: Optional[int] = None
    response_expected_op: Optional[int] = None
    response_payload_length: Optional[int] = None
    response_fragments_seen: int = 0

    deadline = time.monotonic() + timeout_s

    for idx, frag in enumerate(fragments):
        if time.monotonic() > deadline:
            raise CfcTimeoutError("timeout before sending all outbound fragments")

        frame_bytes = pack_cfc_frame(
            op_code=op_code,
            transaction_id=txn,
            fragment_index=idx,
            fragment_total=total,
            payload_length=payload_length,
            fragment_data=frag,
        )

        resp_bytes = await _cfc_send_one_frame(client, frame_bytes)
        if resp_bytes is None:
            # On the LAST outbound fragment we expect at least one response frame.
            # On earlier fragments, the FAP sends no response (still assembling).
            if idx == total - 1:
                raise CfcTimeoutError(
                    f"no response after final outbound fragment (txn={txn})"
                )
            continue

        # Validate inbound frame header
        if len(resp_bytes) < CFC_HEADER_SIZE:
            raise CfcProtocolError(f"short inbound frame ({len(resp_bytes)} bytes)")
        (
            magic,
            version,
            r_op,
            r_txn,
            r_frag_idx,
            r_frag_total,
            r_payload_length,
        ) = parse_cfc_header(resp_bytes)
        if magic != CFC_MAGIC or version != CFC_VERSION:
            raise CfcProtocolError(f"bad inbound magic/version: {magic:#x}/{version:#x}")

        fragment_data = resp_bytes[CFC_HEADER_SIZE:]

        if r_txn != txn:
            # txn mismatch on response — protocol violation
            raise CfcProtocolError(f"response txn={r_txn} != request txn={txn}")

        if response_expected_op is None:
            response_expected_op = r_op
            response_expected_total = r_frag_total
            response_payload_length = r_payload_length

        response_buffers.append(fragment_data)
        response_fragments_seen += 1

        deadline = time.monotonic() + timeout_s  # refresh per H9

        if response_fragments_seen >= (response_expected_total or 1):
            break

    # Drain remaining response fragments if outbound was multi-fragment and inbound
    # is also multi-fragment.
    while (
        response_expected_total is not None
        and response_fragments_seen < response_expected_total
    ):
        if time.monotonic() > deadline:
            raise CfcTimeoutError("timeout assembling inbound fragments")
        rpc = _get_protobuf_rpc(client)
        async with rpc._wire_lock:
            followup = await rpc._receive_main_message(timeout=2.5)
        if followup is None:
            raise CfcTimeoutError("inbound fragment drain timeout")
        if not followup.HasField("app_data_exchange_request"):
            raise CfcProtocolError("unexpected non-data-exchange Main during drain")
        resp_bytes = bytes(followup.app_data_exchange_request.data)
        (magic, version, r_op, r_txn, r_frag_idx, r_frag_total, r_payload_length) = parse_cfc_header(
            resp_bytes
        )
        if magic != CFC_MAGIC or version != CFC_VERSION:
            raise CfcProtocolError(f"bad drain magic/version: {magic:#x}/{version:#x}")
        if r_txn != txn:
            raise CfcProtocolError(f"drain frame txn={r_txn} != {txn}")
        response_buffers.append(resp_bytes[CFC_HEADER_SIZE:])
        response_fragments_seen += 1
        deadline = time.monotonic() + timeout_s

    assembled = b"".join(response_buffers)
    if response_payload_length is not None and len(assembled) != response_payload_length:
        # Tolerate one-frame off-by-one (final fragment can be short) but flag obvious mismatches.
        if len(assembled) < response_payload_length:
            raise CfcProtocolError(
                f"assembled {len(assembled)} < declared payload_length {response_payload_length}"
            )

    try:
        decoded = _decode_msgpack(assembled)
    except CfcProtocolError:
        raise

    if response_expected_op == OP_ERROR:
        if isinstance(decoded, dict):
            code = int(decoded.get("code", -1))
            message = str(decoded.get("message", ""))
        else:
            code = -1
            message = str(decoded)
        raise CfcRemoteError(code, message)

    if not isinstance(decoded, dict):
        raise CfcProtocolError(f"response is not a dict: {type(decoded).__name__}")

    return decoded
