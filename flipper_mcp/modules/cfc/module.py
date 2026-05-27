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
import logging
import struct
import threading
import time
from typing import Any, Optional

import msgpack

from flipper_mcp.core.protobuf_gen import flipper_pb2, application_pb2

_log = logging.getLogger(__name__)

# --- Protocol constants (spec §4) ---

CFC_MAGIC: int = 0x4346
CFC_VERSION: int = 0x01
CFC_HEADER_SIZE: int = 16
CFC_MAX_FRAGMENT_PAYLOAD: int = 884
CFC_MAX_TRANSACTION: int = 8192

# Set to True once Momentum (or any firmware fork CPK supports) merges the fix
# for rpc_system_app_exchange_data uninitialized PB_Main. When True, the host
# will use strict command_id matching for app_data_exchange frames (recommended:
# command_id == 0 routes to broadcast handler, matching id routes to reply,
# else drop).
#
# Current state (2026-05-27): Momentum mntm-dev unfixed. Set to False so
# _cfc_send_one_frame accepts any command_id on inbound app_data_exchange.
#
# Sunset gate: see docs/decisions/DAY10_PHASE2_5_DESIGN.md §3.
#
# Phase 2.5: NOT CONSULTED by _cfc_send_one_frame. The constant exists as
# forward-declaration so Phase 3+ can gate strict-match behind it. Flipping
# this to True in Phase 2.5 has NO behavioral effect — the workaround path
# is unconditional. (v8 addition per Arena Model A.)
MOMENTUM_RPC_EXCHANGE_DATA_FIXED: bool = False

# Gemini v3 finding #3: prevent the workaround from becoming forgotten legacy
# code. Emit a one-shot warning at module import if the workaround is active,
# so every CPK boot reminds the operator that the upstream fix is still pending.
if not MOMENTUM_RPC_EXCHANGE_DATA_FIXED:
    _log.warning(
        "CFC workaround active: accepting any command_id on inbound "
        "app_data_exchange frames. This is a bridge for the Momentum "
        "rpc_system_app_exchange_data uninitialized-malloc bug. "
        "See docs/decisions/DAY10_PHASE2_5_DESIGN.md §3 for sunset conditions."
    )

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


class CfcProtocolDesyncError(Exception):
    """Raised when CFC observes wire state that should be impossible under
    the wire-lock invariant. Indicates the RPC session is corrupted and
    must be torn down for a clean reconnect.

    This is intentionally fatal. Callers should NOT catch and ignore this —
    it means another tool's response leaked into CFC's drain window despite
    the wire lock being held, which is a state-machine corruption that
    cannot be safely recovered from in-place.
    """


async def _cfc_send_one_frame(
    client: Any,
    frame_bytes: bytes,
    wait_for_response: bool = True,
    followup_timeout: float = 2.5,
) -> Optional[bytes]:
    """Send one CFC frame; receive at most one app_data_exchange response.

    Holds the ProtobufRPC ``_wire_lock`` for the duration of the send+receive.

    Route-by-tag drain (v6/v8.2 design): inbound frames are routed by their
    ``which_content`` tag. ``app_data_exchange_request`` returns its payload
    bytes. The Q6 closed set of asynchronous event frames
    (``app_state_response``, ``gui_screen_frame``, ``desktop_status``) and
    the per-request synchronous RPC ack frame (``empty``, command_id matches
    our outbound request — previously absorbed by _send_rpc_message's strict
    matcher) are consumed silently and the drain continues. Any other content
    tag during CFC's drain window means the wire-lock invariant was violated
    and is raised as ``CfcProtocolDesyncError`` so callers can tear down the
    RPC session for a clean reconnect.
    """
    rpc = _get_protobuf_rpc(client)
    async with rpc._wire_lock:
        # Build outbound Main
        main_request = flipper_pb2.Main()
        main_request.command_id = rpc._get_next_command_id()
        main_request.has_next = False
        req = application_pb2.DataExchangeRequest()
        req.data = frame_bytes
        main_request.app_data_exchange_request.CopyFrom(req)

        # Send raw (bypass strict matcher)
        ok = await rpc._send_main_raw(main_request)
        if not ok:
            return None

        if not wait_for_response:
            return None

        # Drain inbound: accept app_data_exchange regardless of command_id
        # (workaround for Momentum bug — see §3 sunset). Non-CFC frames are
        # protocol desync (wire lock should prevent them) and raise loudly.
        deadline = time.monotonic() + followup_timeout
        PER_READ_TIMEOUT = 0.5

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None  # legitimate timeout — no frame arrived in window
            this_timeout = min(PER_READ_TIMEOUT, remaining)
            resp = await rpc._receive_main_message(timeout=this_timeout)
            if resp is None:
                continue  # transport returned nothing; keep waiting

            # v6/v8.2: route-by-tag pattern (matches qFlipper's canonical
            # implementation per NotebookLM Round 3 Q8). Check which_content
            # tag FIRST. CFC's data frame returns. Known asynchronous event
            # frames (per Round 3 Q6 — closed set of 4) and the per-request
            # synchronous RPC ack frame (`empty`, command_id matches our
            # outbound request — v8.2 addition) are consumed and the drain
            # continues. Truly unknown content raises desync.
            if resp.HasField("app_data_exchange_request"):
                # v5 fix preserved: decouple type-check from payload-check.
                # Empty bytes (b"") is falsy in Python; structure alone
                # determines CFC-ness, an empty payload is still a valid
                # CFC frame.
                payload_bytes = resp.app_data_exchange_request.data
                return bytes(payload_bytes) if payload_bytes else b""

            if resp.HasField("empty"):
                # Synchronous RPC ack-reply from the Flipper RPC dispatcher.
                # Every request gets one of these with command_id matching
                # the request, when the registered handler has no specific
                # reply payload. Previously absorbed by _send_rpc_message's
                # strict matcher; visible here because _send_main_raw bypasses
                # matching. (v8.2 addition per cook attempt #1 empirical
                # finding — Q6 enumeration missed sync-reply category.)
                continue

            if resp.HasField("app_state_response"):
                # APP_STARTED / APP_CLOSED event with garbage command_id
                # (Momentum bug — see §3, mirrors the app_data_exchange
                # one). Per Round 3 Q7, these arrive AFTER the app_start
                # reply, so they naturally land here. Consume and continue
                # draining — the host's real reply may follow.
                continue

            if resp.HasField("gui_screen_frame"):
                # Screen streaming event. command_id is clean per Q6 but
                # the frame is still asynchronous; consume and continue.
                # NOTE: if GUI streaming is somehow active during CFC ops,
                # screen-frame flooding could starve the CFC response within
                # the followup_timeout budget. Per Arena Model A — acceptable
                # risk for Phase 2.5 (GUI streaming and CFC don't normally
                # coexist). Phase 3 may need a frame-budget guard here.
                continue

            if resp.HasField("desktop_status"):
                # Desktop lock/unlock event. command_id is clean per Q6;
                # consume and continue.
                continue

            # Truly unknown content tag during CFC drain. The wire lock
            # should make non-event, non-CFC frames unreachable. If this
            # fires, the wire-lock invariant was violated or the firmware
            # is emitting a frame type that wasn't in the Q6/v8.2 allowlist —
            # either way, surface as fatal protocol desync.
            field = resp.WhichOneof('content')
            raise CfcProtocolDesyncError(
                f"unknown content tag during CFC drain (wire lock held): "
                f"command_id={resp.command_id}, content_field={field}. "
                f"RPC session must be torn down. If this is a legitimate "
                f"new firmware event type, add it to the v8.2 allowlist."
            )


async def cfc_send_raw_frame(
    client: Any,
    raw_bytes: bytes,
    wait_for_response: bool = True,
) -> Optional[bytes]:
    """Public negative-test helper: send already-built frame bytes (no checks)."""
    return await _cfc_send_one_frame(client, raw_bytes, wait_for_response=wait_for_response)


async def cfc_recv_response_assembled(
    client: Any,
    first_fragment_bytes: bytes,
    timeout_s: float = 10.0,
) -> bytes:
    """Take the first fragment of a CFC response and reassemble the full payload.

    Use this when a test (or other low-level caller) has already received
    fragment 0 via cfc_send_raw_frame or similar, and needs the complete
    multi-fragment response assembled.

    Returns the COMPLETE reassembled payload bytes (concatenation of all
    fragments' payload sections, without per-fragment CFC headers). The
    caller can then msgpack-decode the result.

    For single-fragment responses (frag_total == 1), returns the fragment's
    payload section unchanged — no additional reads.

    Raises CfcProtocolError on header inconsistencies (txn mismatch between
    fragments, payload_length mismatch, bad magic/version on follow-ups).
    Raises CfcTimeoutError if assembly times out.
    """
    if first_fragment_bytes is None or len(first_fragment_bytes) < CFC_HEADER_SIZE:
        raise CfcProtocolError(
            f"first_fragment_bytes too short: {len(first_fragment_bytes) if first_fragment_bytes else 0}"
        )

    (magic, version, op, txn, frag_idx, frag_total, payload_length) = parse_cfc_header(
        first_fragment_bytes
    )
    if magic != CFC_MAGIC or version != CFC_VERSION:
        raise CfcProtocolError(f"bad magic/version: {magic:#x}/{version:#x}")
    if frag_idx != 0:
        raise CfcProtocolError(
            f"first_fragment_bytes claims frag_idx={frag_idx}, expected 0"
        )

    # Collect fragment 0's payload section.
    payload_parts: list[bytes] = [first_fragment_bytes[CFC_HEADER_SIZE:]]

    # Single-fragment fast path: nothing more to receive.
    if frag_total == 1:
        return payload_parts[0]

    # Multi-fragment: read remaining frag_total - 1 fragments off the wire.
    deadline = time.monotonic() + timeout_s
    rpc = _get_protobuf_rpc(client)
    fragments_received = 1

    while fragments_received < frag_total:
        if time.monotonic() > deadline:
            raise CfcTimeoutError(
                f"reassembly timeout: got {fragments_received}/{frag_total} fragments"
            )

        async with rpc._wire_lock:
            followup = await rpc._receive_main_message(timeout=2.5)

        if followup is None:
            raise CfcTimeoutError(
                f"no fragment received: got {fragments_received}/{frag_total} so far"
            )
        if not followup.HasField("app_data_exchange_request"):
            # An unexpected non-data Main arrived. Could be a stray async event;
            # we don't try to be clever here — surface as protocol error and let
            # the test diagnose. (The wire lock should prevent foreign frames,
            # but defensive raise matches the §2.2 drain loop's discipline.)
            content_field = followup.WhichOneof("content")
            raise CfcProtocolError(
                f"unexpected non-data-exchange Main during reassembly: "
                f"content_field={content_field}"
            )

        resp_bytes = bytes(followup.app_data_exchange_request.data)
        if len(resp_bytes) < CFC_HEADER_SIZE:
            raise CfcProtocolError(f"reassembly fragment too short: {len(resp_bytes)}")

        (f_magic, f_version, f_op, f_txn, f_idx, f_total, f_plen) = parse_cfc_header(
            resp_bytes
        )
        if f_magic != CFC_MAGIC or f_version != CFC_VERSION:
            raise CfcProtocolError(
                f"reassembly bad magic/version: {f_magic:#x}/{f_version:#x}"
            )
        if f_txn != txn:
            raise CfcProtocolError(
                f"reassembly txn mismatch: got {f_txn}, expected {txn}"
            )
        if f_total != frag_total:
            raise CfcProtocolError(
                f"reassembly frag_total mismatch: got {f_total}, expected {frag_total}"
            )
        if f_plen != payload_length:
            raise CfcProtocolError(
                f"reassembly payload_length mismatch: got {f_plen}, expected {payload_length}"
            )

        payload_parts.append(resp_bytes[CFC_HEADER_SIZE:])
        fragments_received += 1

    assembled = b"".join(payload_parts)
    # Sanity check: total bytes should equal payload_length from the header.
    if len(assembled) != payload_length:
        raise CfcProtocolError(
            f"reassembly size mismatch: got {len(assembled)} bytes, "
            f"header claimed {payload_length}"
        )
    return assembled


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
