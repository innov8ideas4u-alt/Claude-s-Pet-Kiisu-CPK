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

# --- Phase 3 Cook 2: NFC subscription opcodes (spec §6.1) ---
OP_NFC_SUBSCRIBE_CAPTURE: int = 0x40  # host -> FAP: arm the NFC capture worker
OP_NFC_UNSUBSCRIBE: int = 0x41        # host -> FAP: disarm the worker
OP_NFC_EVENT: int = 0x42              # FAP -> host: capture broadcast (command_id == 0)

# --- Phase 3 Cook 3.2: NFC diagnostic broadcast op_code (the live-fire reroute) ---
# FAP -> host: detect-cb / poll-outcome diagnostics, on a SEPARATE op_code from
# OP_NFC_EVENT so they route to a distinct subscription buffer and can never
# pollute the real-event assertions (live_fire_nfc._check_real_event reads 0x42
# only). Deliberately has NO entry in _SUBSCRIBE_ARM_OP below: subscribing to it
# registers a host-side buffer WITHOUT sending a FAP arm request (the worker is
# already armed by the OP_NFC_EVENT subscribe; the diag stream rides that same
# armed worker). Broadcasts on this op carry the M3 high-bit txn like any other.
OP_NFC_DIAG: int = 0x4F              # FAP -> host: diagnostic broadcast (command_id == 0)

ERR_BAD_FRAME: int = 1
ERR_BAD_FRAGMENT: int = 2
ERR_PAYLOAD_TOO_LARGE: int = 3
ERR_OUT_OF_MEMORY: int = 4
ERR_BUSY: int = 5
ERR_BAD_PAYLOAD: int = 6
ERR_UNKNOWN_OPCODE: int = 7
ERR_INTERNAL: int = 99

# --- Phase 3 Cook 2: subscription error codes (spec §6.2) ---
# Distinct from the Phase 2 assembling-state ERR_BUSY (== 5): these are the
# subscription-layer codes the FAP returns for the NFC vertical slice.
ERR_SUB_BUSY: int = 0x10        # Q2 exclusive: op_code already subscribed / worker armed
ERR_NOT_SUBSCRIBED: int = 0x11  # unsubscribe with no active subscription
ERR_WORKER_BUSY: int = 0x12     # worker-thread stop in flight

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


class CfcNotSubscribedError(Exception):
    """Raised by ``flipper_cfc_listen`` when there is no active subscription for
    the requested op_code. The caller must ``flipper_cfc_subscribe`` first."""

    def __init__(self, op_code: int) -> None:
        super().__init__(f"no active subscription for op_code 0x{op_code:02x}")
        self.op_code = op_code


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
    """Allocate a host-initiated request transaction_id.

    M3 namespace partition (Cook 2 adversarial-review mandate): host request
    txns occupy 0x00000000–0x7FFFFFFF (high bit CLEAR); firmware-initiated
    broadcast txns occupy 0x80000000–0xFFFFFFFF (high bit SET). Masking with
    0x7FFFFFFF guarantees a request txn can never collide with a broadcast txn,
    so a broadcast frame can never resolve a pending request Future. The
    dispatcher (protobuf_rpc._deliver_cfc) re-asserts the partition.
    """
    with _txn_lock:
        return next(_txn_counter) & 0x7FFFFFFF


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


# Phase 3 (Cook 1.5): unify the desync exception with the reader's. The single
# reader task (protobuf_rpc.ProtobufRPC._reader_loop) raises
# CfcProtocolDesyncError on an unroutable inbound tag and fails every pending
# future with it, so a CFC caller awaiting its txn future receives that exact
# class. Re-exported here so existing `from ...cfc.module import
# CfcProtocolDesyncError` call sites and tests keep resolving one shared type.
from flipper_mcp.core.protobuf_rpc import (  # noqa: F401
    CfcProtocolDesyncError,
    _Subscription,
)


async def _cfc_send_one_frame(
    client: Any,
    frame_bytes: bytes,
    wait_for_response: bool = True,
    followup_timeout: float = 2.5,
) -> Optional[bytes]:
    """Send one CFC frame; return the inbound CFC response frame bytes, or None.

    Phase 3 reader-driven (DAY11 §15.1 / §16). The single background reader task
    owns ALL inbound reads and demultiplexes CFC traffic by the inner CFC
    header's ``transaction_id`` — the outer ``Main.command_id`` is garbage
    (Momentum ``rpc_system_app_exchange_data`` uninit-malloc bug). This function:

      1. Parses the OUTBOUND frame's transaction_id directly from the header
         (offset 4, u32 LE) WITHOUT validating magic/version — the negative
         tests deliberately send bad-magic / bad-version frames, and the FAP
         still echoes their txn in its error response (cfc.c cfc_send_error).
      2. Registers a per-txn future with the reader (``_cfc_pending[txn]``).
      3. Sends the ``app_data_exchange`` Main while holding the wire lock only
         for the brief send.
      4. Awaits the reader's reassembled ``(op, txn, body, payload_length)`` and
         reconstructs a SINGLE-fragment CFC frame (header + reassembled body) so
         existing callers (``flipper_cfc_call`` / ``cfc_recv_response_assembled``
         / ``decode_resp``) parse it unchanged — the reader already did any
         multi-fragment reassembly (§13.1).

    With ``wait_for_response=False`` the frame is fired and ``None`` returned
    without registering/awaiting (used for non-final outbound fragments, which
    the FAP never answers).

    On a protocol desync, the reader fails the txn future with
    ``CfcProtocolDesyncError``; that propagates out of this function (it is NOT a
    timeout) so callers can tear the session down.
    """
    rpc = _get_protobuf_rpc(client)

    # Read the outbound transaction_id straight from the header. parse_cfc_header
    # would reject bad magic (negative tests), but the FAP echoes the txn anyway.
    if frame_bytes is not None and len(frame_bytes) >= 8:
        txn = struct.unpack_from("<I", frame_bytes, 4)[0]
    else:
        txn = 0

    main_request = flipper_pb2.Main()
    main_request.command_id = rpc._get_next_command_id()
    main_request.has_next = False
    req = application_pb2.DataExchangeRequest()
    req.data = frame_bytes
    main_request.app_data_exchange_request.CopyFrom(req)

    await rpc._ensure_session_and_reader()
    message_data = main_request.SerializeToString()
    framed = rpc._encode_varint(len(message_data)) + message_data

    if not wait_for_response:
        async with rpc._wire_lock:
            await rpc.transport.send(framed)
        return None

    fut = asyncio.get_event_loop().create_future()
    rpc._cfc_pending[txn] = fut
    try:
        async with rpc._wire_lock:  # held only for the send
            await rpc.transport.send(framed)
        try:
            op, r_txn, body, payload_length = await asyncio.wait_for(
                fut, timeout=followup_timeout
            )
        except asyncio.TimeoutError:
            return None  # legitimate timeout — no frame arrived in the window

        # Reconstruct a single-fragment CFC frame from the reader's reassembled
        # payload. body has the inner CFC header stripped, so re-add one; callers
        # that re-parse the header (flipper_cfc_call, cfc_recv_response_assembled,
        # decode_resp) then work exactly as before.
        return pack_cfc_frame(
            op_code=op,
            transaction_id=r_txn,
            fragment_index=0,
            fragment_total=1,
            payload_length=payload_length,
            fragment_data=body,
        )
    finally:
        rpc._cfc_pending.pop(txn, None)


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

    body = first_fragment_bytes[CFC_HEADER_SIZE:]

    # Phase 3 (Cook 1.5): the single reader task reassembles multi-fragment CFC
    # responses BEFORE delivery, so a caller always receives a single-fragment
    # frame (frag_total == 1) whose body IS the complete payload. This function
    # therefore no longer reads the wire itself (the reader is the sole reader);
    # it just validates and returns the body. A frag_total > 1 reaching here means
    # the reader's reassembly contract was violated.
    if frag_total != 1:
        raise CfcProtocolError(
            f"cfc_recv_response_assembled: frag_total={frag_total} (expected 1); "
            f"the reader reassembles multi-fragment responses before delivery "
            f"(txn={txn})"
        )
    return body


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

        # Only the FINAL outbound fragment gets a response; the FAP stays silent
        # while assembling. Fire non-final fragments without awaiting so all
        # fragments land well inside the FAP's 5s ASSEMBLING window (reader-driven
        # waits would otherwise add ~followup_timeout per non-final fragment).
        is_final = idx == total - 1
        resp_bytes = await _cfc_send_one_frame(
            client, frame_bytes, wait_for_response=is_final
        )
        if resp_bytes is None:
            if is_final:
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

    # Phase 3 (Cook 1.5): the reader reassembles multi-fragment CFC responses, so
    # _cfc_send_one_frame returns a single reconstructed frame (frag_total == 1)
    # carrying the full payload. The old inbound multi-fragment drain loop (which
    # read the wire directly via _receive_main_message) is therefore gone — there
    # is never more than one inbound "frame" to collect here.

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


# --- Phase 3 Cook 2: subscription dispatcher public surface (spec §4.5) ---
#
# A subscription is identified by the EVENT op_code the caller wants to receive
# (e.g. OP_NFC_EVENT 0x42). Arming the FAP-side producer is a separate request
# op_code (NFC_SUBSCRIBE_CAPTURE 0x40 / NFC_UNSUBSCRIBE 0x41). This map routes
# event op -> arm/disarm request op. Cook 2 ships one stream (NFC); a host-only
# op_code with no entry registers a buffer without touching the FAP (used by the
# chaos/overflow unit tests, which feed broadcasts directly through the reader).
_SUBSCRIBE_ARM_OP: dict[int, int] = {OP_NFC_EVENT: OP_NFC_SUBSCRIBE_CAPTURE}
_SUBSCRIBE_DISARM_OP: dict[int, int] = {OP_NFC_EVENT: OP_NFC_UNSUBSCRIBE}


async def flipper_cfc_subscribe(
    client: Any,
    op_code: int,
    *,
    arm_timeout_s: float = 5.0,
) -> dict:
    """Subscribe to unsolicited CFC broadcast events for ``op_code`` (spec §4.5).

    Registers a host-side subscription buffer (``deque`` + ``Event``, M1/M2) keyed
    by the event ``op_code`` and — if that op_code maps to a FAP-side producer —
    arms it by sending the corresponding capture request and awaiting the ack.

    Q2 exclusive (spec §3): a second subscribe to an already-subscribed op_code
    raises ``CfcRemoteError(ERR_SUB_BUSY)`` without touching the FAP.

    The host buffer is registered BEFORE the arm request is sent, so no broadcast
    the FAP emits after its ack (it delays arming 20 ms past the ack per §13.2)
    can be missed. If arming fails the host subscription is rolled back so state
    stays consistent.

    Returns a dict describing the subscription; raises on a busy op_code or an
    arm failure.
    """
    rpc = _get_protobuf_rpc(client)
    await rpc._ensure_session_and_reader()

    if op_code in rpc._subscriptions:
        raise CfcRemoteError(
            ERR_SUB_BUSY, f"op_code 0x{op_code:02x} already subscribed (Q2 exclusive)"
        )

    sub = _Subscription(op_code=op_code, subscribed_at_ms=int(time.monotonic() * 1000))
    rpc._subscriptions[op_code] = sub

    arm_op = _SUBSCRIBE_ARM_OP.get(op_code)
    if arm_op is None:
        # No FAP-side producer to arm — a host-only subscription is sufficient.
        return {"op_code": op_code, "subscribed": True, "armed": False}

    try:
        ack = await flipper_cfc_call(client, arm_op, None, timeout_s=arm_timeout_s)
    except Exception:
        # Arm failed — roll back so the host doesn't think it's subscribed to a
        # stream the FAP never started.
        rpc._subscriptions.pop(op_code, None)
        raise

    return {"op_code": op_code, "subscribed": True, "armed": True, "ack": ack}


async def flipper_cfc_listen(
    client: Any,
    op_code: int,
    timeout_ms: int = 5000,
) -> Optional[dict]:
    """Wait for the next broadcast event matching ``op_code`` (spec §4.5).

    Returns the event as ``{"op_code", "txn", "payload", "overflow_count_so_far"}``
    or ``None`` if none arrives within ``timeout_ms``. ``overflow_count_so_far`` is
    the host-side drop count (deque evictions); the FAP's own per-event
    ``overflow_since_last`` lives inside ``payload``.

    Drains the subscription's ``deque`` (M2) and waits on its ``asyncio.Event``
    (M1) — never on a queue the reader would have to ``await put`` into. The
    empty-buffer wait uses a clear-then-recheck to close the set/clear race with
    the producing reader.

    Raises ``CfcNotSubscribedError`` if no subscription is active for ``op_code``.
    """
    rpc = _get_protobuf_rpc(client)
    sub = rpc._subscriptions.get(op_code)
    if sub is None:
        raise CfcNotSubscribedError(op_code)

    loop = asyncio.get_event_loop()
    deadline = loop.time() + max(0.0, timeout_ms / 1000.0)

    while True:
        if sub.buffer:
            ev_op, txn, body, _payload_length = sub.buffer.popleft()
            if not sub.buffer:
                sub.event.clear()
            payload = _decode_msgpack(body) if body else None
            return {
                "op_code": ev_op,
                "txn": txn,
                "payload": payload,
                "overflow_count_so_far": sub.overflow_count,
            }

        if sub.closed:
            # Unsubscribed out from under us — stop waiting.
            return None

        remaining = deadline - loop.time()
        if remaining <= 0:
            return None

        # Buffer empty: arm the wake, then re-check before sleeping so an event
        # appended between the empty-check and the clear is not lost.
        sub.event.clear()
        if sub.buffer or sub.closed:
            continue
        try:
            await asyncio.wait_for(sub.event.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            return None


async def flipper_cfc_unsubscribe(
    client: Any,
    op_code: int,
    *,
    disarm_timeout_s: float = 5.0,
) -> dict:
    """Cancel the subscription for ``op_code`` and disarm its FAP producer (§4.5).

    Idempotent (spec §9.2): unsubscribing an op_code with no active subscription
    is a no-op success, not an error. Removes the host subscription, wakes any
    blocked listener, and — if the op_code maps to a FAP producer — sends the
    disarm request (best-effort: the FAP's 5-min idle failsafe covers a lost
    disarm).
    """
    rpc = _get_protobuf_rpc(client)
    sub = rpc._subscriptions.pop(op_code, None)
    if sub is None:
        return {"op_code": op_code, "unsubscribed": False, "was_subscribed": False}

    # Wake any in-flight listener so it returns promptly instead of blocking out
    # its full timeout on a subscription that no longer exists.
    sub.closed = True
    sub.event.set()

    disarm_op = _SUBSCRIBE_DISARM_OP.get(op_code)
    disarmed = False
    if disarm_op is not None:
        try:
            await flipper_cfc_call(client, disarm_op, None, timeout_s=disarm_timeout_s)
            disarmed = True
        except Exception:
            # Host subscription is already gone; the FAP's idle auto-stop (§5.5)
            # disarms the worker if this request was lost.
            disarmed = False

    return {
        "op_code": op_code,
        "unsubscribed": True,
        "was_subscribed": True,
        "disarmed": disarmed,
    }
