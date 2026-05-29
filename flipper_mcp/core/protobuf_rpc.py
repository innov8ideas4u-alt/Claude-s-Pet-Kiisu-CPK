"""Flipper Zero Protobuf RPC implementation.

This module implements the Flipper Zero RPC protocol using Protocol Buffers
based on the official protobuf schemas from:
https://github.com/flipperdevices/flipperzero-protobuf

Uses generated protobuf code from proto/ directory.
"""

import asyncio
import logging
import os
import struct
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from .transport.base import FlipperTransport

_log = logging.getLogger(__name__)

# --- Phase 3 reader-task constants (DAY11 spec §13.4) ---
#
# These are the canonical values for the Phase 3 single-reader-task pattern.
# In Cook 1 the reader infrastructure exists but is not yet wired into the
# existing RPC flow (which still uses _send_rpc_message + direct
# _receive_main_message calls). Cook 1.5 migrates the existing tools.
#
# Sourced from DAY11_PHASE3_SPEC.md §13.4 — do NOT redefine elsewhere.

RPC_TIMEOUT_S: float = 5.0
READER_POLL_S: float = 0.1
CFC_MAX_FRAME_SIZE: int = 884
CFC_HEADER_LEN: int = 16
CFC_MAX_TRANSACTION_BYTES: int = 8192
SUBSCRIPTION_QUEUE_DEPTH: int = 16

# --- M3: transaction_id namespace partition (Cook 2 adversarial-review mandate) ---
#
# The 32-bit CFC transaction_id space is split so a firmware-initiated broadcast
# can NEVER collide with a host-initiated request and resolve the wrong Future:
#   - Host request txns: 0x00000000–0x7FFFFFFF (high bit CLEAR)
#   - Firmware broadcast txns: 0x80000000–0xFFFFFFFF (high bit SET)
# The host allocator masks with 0x7FFFFFFF (see modules/cfc/module.py
# _next_transaction_id); the FAP ORs in the high bit for every broadcast. The
# dispatcher (_deliver_cfc) asserts the partition: a response on a high-bit txn
# or a broadcast on a low-bit txn is dropped + logged as a protocol bug.
CFC_BROADCAST_TXN_BIT: int = 0x80000000

# CFC frame header layout — must mirror modules/cfc/module.py exactly so the
# reader can demux CFC traffic without importing the CFC module (which would
# create a circular import: cfc/module.py already reaches into ProtobufRPC).
_CFC_MAGIC: int = 0x4346
_CFC_VERSION: int = 0x01
_CFC_HEADER_FMT: str = "<HBBIHHI"  # magic u16, version u8, op u8, txn u32, frag_idx u16, frag_total u16, payload_length u32
assert struct.calcsize(_CFC_HEADER_FMT) == CFC_HEADER_LEN


def parse_cfc_header(payload: bytes) -> Optional[tuple]:
    """Parse a CFC frame header off the front of ``payload``.

    Returns ``(magic, version, op_code, transaction_id, frag_idx, frag_total,
    payload_length)`` or ``None`` if the payload is too short or has bad
    magic/version. Used by the Phase 3 reader to demux app_data_exchange
    frames by their inner CFC transaction_id (the outer Main.command_id is
    garbage due to the Momentum uninit-malloc bug — see
    ``MOMENTUM_RPC_EXCHANGE_DATA_FIXED`` in modules/cfc/module.py §3).
    """
    if payload is None or len(payload) < CFC_HEADER_LEN:
        return None
    try:
        hdr = struct.unpack(_CFC_HEADER_FMT, payload[:CFC_HEADER_LEN])
    except struct.error:
        return None
    magic, version, op, txn, frag_idx, frag_total, payload_length = hdr
    if magic != _CFC_MAGIC or version != _CFC_VERSION:
        return None
    return hdr


class CfcProtocolDesyncError(Exception):
    """Raised by the Phase 3 reader when it observes a content tag that has
    no defined route. Indicates wire-state corruption — the RPC session must
    be torn down for a clean reconnect.

    Mirrors (intentionally) the exception of the same name in
    modules/cfc/module.py so existing CFC callers see a single type.
    """


# --- Phase 3 reader-task allowlist of content tags ---
#
# CFC traffic (tag == 'app_data_exchange_request') is handled separately via
# CFC-header demux. The remaining tags fall into three buckets:
#   - SYNC_REPLY_TAGS: synchronous RPC reply tags; route by outer cmd_id
#     to the per-request future in `_pending`.
#   - ASYNC_EVENT_TAGS: server-pushed event frames that may arrive at any
#     time and are not associated with a specific outbound request. In Cook 1
#     they are silently consumed (no subscription dispatch yet; Cook 2 wires
#     the worker side, Cook 3 wires real subscribers).
#
# Any tag not in either set raises CfcProtocolDesyncError. Adding a new
# firmware tag means deciding which bucket it belongs in.
_SYNC_REPLY_TAGS: frozenset = frozenset({
    "empty",
    "system_ping_response",
    "system_device_info_response",
    "system_get_datetime_response",
    "system_update_response",
    "system_power_info_response",
    "system_protobuf_version_response",
    "storage_info_response",
    "storage_stat_response",
    "storage_list_response",
    "storage_read_response",
    "storage_md5sum_response",
    "storage_backup_create_response",
    "storage_backup_restore_response",
    "property_get_response",
    "app_get_error_response",
    "app_lock_status_response",
    "gui_screen_frame",  # also async, see below — but cmd_id-tagged variants are sync
    "gui_start_virtual_display_request",
    "gui_stop_virtual_display_request",
})
_ASYNC_EVENT_TAGS: frozenset = frozenset({
    "app_state_response",
    "desktop_status",
})


@dataclass
class _Subscription:
    """Per-op_code subscription state (Phase 3 — Cook 2).

    Cook 2 concurrency mandates (M1/M2 from the adversarial review):

    * **M1 — the reader never blocks.** The reader is the SOLE consumer of the
      wire; if it ever ``await``-ed a full queue it would suspend, USB would
      stop being read, and every pending request would hang. Delivery into a
      subscription is therefore the synchronous, non-blocking :meth:`push`
      (no ``await``).
    * **M2 — drop-oldest is atomic.** The buffer is a ``collections.deque`` with
      ``maxlen=SUBSCRIPTION_QUEUE_DEPTH``: appending to a full deque evicts the
      oldest element at the data-structure level, with no check-then-act window
      for a consumer to steal the slot (the bug the older ``asyncio.Queue`` +
      ``get_nowait``/``put_nowait`` pattern had).

    The consumer (``flipper_cfc_listen``) waits on :attr:`event` then drains
    :attr:`buffer`. ``overflow_count`` counts host-side drops (distinct from the
    FAP-side ``overflow_since_last`` carried inside each event payload).
    """
    op_code: int
    buffer: "deque" = field(
        default_factory=lambda: deque(maxlen=SUBSCRIPTION_QUEUE_DEPTH)
    )
    event: asyncio.Event = field(default_factory=asyncio.Event)
    overflow_count: int = 0
    subscribed_at_ms: int = 0  # §13.2 Q1 belt-and-suspenders
    closed: bool = False  # set by unsubscribe so a blocked listener returns promptly

    def push(self, item: tuple) -> None:
        """Append an event, atomically dropping the oldest if full (M1/M2).

        Synchronous and non-blocking — safe to call from the reader task. A
        full ``deque(maxlen=N)`` evicts its oldest element on ``append`` at the
        data-structure level, so there is no window for a concurrent consumer to
        steal the freed slot. There are no ``await`` points here, so this is
        atomic with respect to other coroutines. ``overflow_count`` is bumped
        whenever an eviction occurs, then the consumer is woken via ``event``.
        """
        if self.buffer.maxlen is not None and len(self.buffer) >= self.buffer.maxlen:
            # Appending now will evict the oldest — count it as a host-side drop.
            self.overflow_count += 1
        self.buffer.append(item)
        self.event.set()


@dataclass(frozen=True)
class AppRpcResult:
    """
    Result of an Application-service RPC call (app_start, app_load_file, app_exit).

    Carries the firmware's CommandStatus instead of collapsing to bool so callers
    can distinguish "OK" from the specific failure reason (ERROR_APP_CANT_START,
    ERROR_INVALID_PARAMETERS, ERROR_APP_SYSTEM_LOCKED, etc.).

    Truthy iff the firmware reported OK, so existing `if await app_start(...)` sites
    continue to work unchanged.
    """
    ok: bool
    status_code: int
    status_name: str

    def __bool__(self) -> bool:
        return self.ok


# Import generated protobuf classes
try:
    from .protobuf_gen import flipper_pb2, system_pb2, property_pb2, storage_pb2, application_pb2, gui_pb2, desktop_pb2
    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False
    if TYPE_CHECKING:
        # For type checking only
        from .protobuf_gen import flipper_pb2, system_pb2, property_pb2, storage_pb2, application_pb2, gui_pb2, desktop_pb2
    else:
        flipper_pb2 = None
        system_pb2 = None
        property_pb2 = None
        storage_pb2 = None
        application_pb2 = None


class ProtobufRPC:
    """
    Flipper Zero Protobuf RPC client.
    
    Implements the RPC protocol using protobuf messages as defined in
    the flipperzero-protobuf repository.
    """
    
    def __init__(self, transport: FlipperTransport):
        """
        Initialize Protobuf RPC client.
        
        Args:
            transport: Transport layer for communication
        """
        if not PROTOBUF_AVAILABLE:
            raise ImportError("Protobuf generated code not available. Run 'protoc' to generate Python code from .proto files.")
        
        self.transport = transport
        self.command_id = 0
        self.debug = os.environ.get("FLIPPER_DEBUG", "").lower() in ("1", "true", "yes", "on")
        self._rpc_session_started = False
        # One lock per RPC instance. Phase 3: a SEND-ONLY mutex — held only for
        # the brief moment of writing framed bytes to the wire (see
        # _send_rpc_message / _send_rpc_stream). The single reader task is the
        # sole reader and does not take this lock.
        self._wire_lock = asyncio.Lock()

        # --- Phase 3 reader-task state (Cook 1 — infrastructure only) ---
        #
        # In Cook 1 these fields exist but the reader is not started by the
        # existing RPC flow. New code paths (e.g. Phase 3 subscribe/listen,
        # added in Cook 2+) opt in via _ensure_reader_started(). Until then,
        # existing _send_rpc_message + direct _receive_main_message paths run
        # exactly as in Phase 2.5.
        #
        # Routing rules (operator clarification, DAY11 Cook 1 scope):
        #   - Non-CFC: outer Main.command_id → _pending[cmd_id] (asyncio.Future[Main])
        #   - CFC: inner CFC header.transaction_id → _cfc_pending[txn]
        #     (asyncio.Future[(op_code, transaction_id, assembled_payload_bytes,
        #     payload_length)]). Outer command_id is IGNORED for CFC traffic
        #     (Momentum uninit-malloc bug — see MOMENTUM_RPC_EXCHANGE_DATA_FIXED).
        #
        # _cfc_assembling holds in-flight multi-fragment response state keyed
        # by transaction_id. _broadcast_assembling does the same for
        # command_id == 0 broadcast frames (§13.1).
        self._pending: Dict[int, "asyncio.Future"] = {}
        self._cfc_pending: Dict[int, "asyncio.Future"] = {}
        self._cfc_assembling: Dict[int, dict] = {}
        self._broadcast_assembling: Dict[int, dict] = {}
        self._subscriptions: Dict[int, _Subscription] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._reader_stop: asyncio.Event = asyncio.Event()
        self._reader_start_lock: asyncio.Lock = asyncio.Lock()
        self._reader_desync_error: Optional[Exception] = None
    
    def _get_next_command_id(self) -> int:
        """Get next command ID for RPC calls."""
        self.command_id = (self.command_id + 1) % 0xFFFFFFFF
        return self.command_id

    # =========================================================================
    # Phase 3 single-reader-task infrastructure (Cook 1 — scaffolding only)
    # =========================================================================
    #
    # The reader is the SOLE consumer of self._receive_main_message when it
    # is running. In Cook 1 it is NOT started by the existing RPC flow, so
    # no contention with the Phase 2.5 direct-receive paths. Cook 1.5 will
    # migrate _send_rpc_message and CFC to use the reader.
    #
    # Public callers (Cook 2 subscribe/listen API) call _ensure_reader_started
    # exactly once when they need broadcast routing. _stop_reader is called
    # at disconnect to cancel cleanly.

    async def _ensure_reader_started(self) -> None:
        """Start the single reader task if not already running.

        Idempotent. Safe to call from multiple coroutines concurrently
        (start race is closed by _reader_start_lock).
        """
        if self._reader_task is not None and not self._reader_task.done():
            return
        async with self._reader_start_lock:
            if self._reader_task is not None and not self._reader_task.done():
                return
            self._reader_stop.clear()
            self._reader_desync_error = None
            self._reader_task = asyncio.create_task(
                self._reader_loop(), name="protobuf-rpc-reader"
            )

    async def _ensure_session_and_reader(self) -> None:
        """Establish the RPC session, then start the single reader task.

        This is the Phase 3 (Cook 1.5) entry point every send path calls before
        touching the wire. Ordering matters: ``_ensure_rpc_session_started``
        does direct probe reads (ping → response) to negotiate CLI→RPC mode,
        and the reader — once running — is the SOLE consumer of inbound frames.
        So the reader MUST NOT start until session negotiation has finished, or
        the reader would steal the probe's response. The reader is therefore
        started only after ``_rpc_session_started`` is True.

        Idempotent and cheap on the hot path: after the first call,
        ``_ensure_rpc_session_started`` returns immediately and
        ``_ensure_reader_started`` no-ops if the reader is already running in
        this event loop.
        """
        await self._ensure_rpc_session_started()
        if self._rpc_session_started:
            await self._ensure_reader_started()

    async def _stop_reader(self) -> None:
        """Cancel the reader task and wait for it to exit cleanly.

        Safe to call when the reader is not running. Always clears
        ``_reader_task`` regardless of which path closed it (cancel,
        natural exit, or desync). Fails any pending futures with
        :class:`asyncio.CancelledError` so awaiters unblock instead of
        hanging forever after disconnect.
        """
        self._reader_stop.set()
        task = self._reader_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._reader_task = None
        # Drain pending futures so callers don't hang waiting on a stopped reader.
        self._fail_all_pending(asyncio.CancelledError("reader stopped"))

    def _fail_all_pending(self, error: BaseException) -> None:
        """Resolve every pending waiter with ``error`` and clear assembly state.

        Used by the reader on a fatal protocol desync and by ``_stop_reader``
        on clean shutdown so callers awaiting on response futures don't hang
        forever. Idempotent on already-done futures.

        ``_pending`` entries are either single-shot ``asyncio.Future`` (most
        methods) or ``asyncio.Queue`` (has_next stream methods — §16.1). For a
        Queue we enqueue the exception object; the streaming drain loop treats
        a dequeued ``BaseException`` as "reader gone, stop draining".
        """
        for waiter in list(self._pending.values()):
            if isinstance(waiter, asyncio.Queue):
                try:
                    waiter.put_nowait(error)
                except asyncio.QueueFull:
                    pass
            elif not waiter.done():
                waiter.set_exception(error)
        self._pending.clear()
        for fut in list(self._cfc_pending.values()):
            if not fut.done():
                fut.set_exception(error)
        self._cfc_pending.clear()
        self._cfc_assembling.clear()
        self._broadcast_assembling.clear()

    async def _reader_loop(self) -> None:
        """Single reader task — sole consumer of inbound Main frames (§13.1).

        Reads each Main off the wire and routes by content tag:
          - app_data_exchange_request → CFC demux (txn-keyed, multi-fragment)
          - sync reply tags (with matching cmd_id) → _pending[cmd_id] future
          - async event tags → consumed (Cook 2 will route to subscriptions)
          - unknown tag → CfcProtocolDesyncError → stop + fail-all-pending

        Exceptions other than ``CfcProtocolDesyncError`` and
        ``CancelledError`` are logged and the loop continues. A single bad
        frame must not starve subsequent calls (§10.2).
        """
        while not self._reader_stop.is_set():
            poll_start = time.monotonic()
            try:
                main = await self._receive_main_message(timeout=READER_POLL_S)
                if main is None:
                    # No frame in the poll window; loop and check stop flag.
                    # CPU-SPIN GUARD (R7 / "CPU cooking" bug): a healthy idle port
                    # makes _receive_main_message BLOCK ~READER_POLL_S before
                    # returning None. But a dead/closed/grabbed port makes the
                    # underlying serial read fast-FAIL, so None comes back almost
                    # instantly — an unguarded `continue` then spins this loop at
                    # 100% of a core (orphaned readers were each pegging a full core
                    # for hours, cooking the CPU and masquerading as a mystery load).
                    # Sleep out the remainder of the poll window so the loop rate is
                    # capped at ~1/READER_POLL_S no matter how fast the read failed.
                    elapsed = time.monotonic() - poll_start
                    if elapsed < READER_POLL_S:
                        await asyncio.sleep(READER_POLL_S - elapsed)
                    continue
                self._dispatch_main(main)
            except asyncio.CancelledError:
                break
            except CfcProtocolDesyncError as e:
                self._reader_desync_error = e
                self._fail_all_pending(e)
                self._reader_stop.set()
                if self.debug:
                    print(f"[reader-loop] desync: {e}", file=sys.stderr)
                return
            except Exception as e:
                if self.debug:
                    print(
                        f"[reader-loop] exception (continuing): {type(e).__name__}: {e}",
                        file=sys.stderr,
                    )
                # CPU-SPIN GUARD: if the read keeps raising (e.g. the port closed
                # under us), back off so the error path can't spin a core either.
                await asyncio.sleep(READER_POLL_S)

    def _dispatch_main(self, main: Any) -> None:
        """Route one inbound Main message to the right waiter.

        See class-doc / __init__ comments for routing rules. CFC traffic
        is handled separately because outer command_id is garbage for it
        (Momentum bug); everything else routes by outer cmd_id.
        """
        tag = main.WhichOneof("content")
        cmd_id = main.command_id

        if tag == "app_data_exchange_request":
            self._dispatch_cfc(main)
            return

        if tag in _ASYNC_EVENT_TAGS:
            # Cook 1: silently consume. Cook 2+ will route by event-type to
            # active subscriptions (§4.4).
            if self.debug:
                print(
                    f"[reader] consumed async event tag={tag} cmd_id={cmd_id}",
                    file=sys.stderr,
                )
            return

        if tag in _SYNC_REPLY_TAGS:
            waiter = self._pending.get(cmd_id)
            if waiter is None:
                if self.debug:
                    print(
                        f"[reader] stale sync reply tag={tag} cmd_id={cmd_id} "
                        f"(no pending waiter — likely cancelled caller)",
                        file=sys.stderr,
                    )
            elif isinstance(waiter, asyncio.Queue):
                # has_next stream (§16.1): caller drains the queue until it
                # sees a frame with has_next == False.
                waiter.put_nowait(main)
            elif not waiter.done():
                waiter.set_result(main)
            return

        # Unknown tag — wire-lock invariant says this is impossible. If a new
        # firmware tag appears, add it to _SYNC_REPLY_TAGS or _ASYNC_EVENT_TAGS
        # after confirming whether it carries a matching cmd_id.
        raise CfcProtocolDesyncError(
            f"reader: unknown content tag={tag} cmd_id={cmd_id}. "
            f"Add to _SYNC_REPLY_TAGS or _ASYNC_EVENT_TAGS once classified."
        )

    def _dispatch_cfc(self, main: Any) -> None:
        """Route one inbound CFC (``app_data_exchange_request``) frame.

        Uses the inner CFC header's ``transaction_id`` for routing — outer
        ``Main.command_id`` is IGNORED because the Momentum
        rpc_system_app_exchange_data malloc-uninit bug fills it with
        garbage (see ``MOMENTUM_RPC_EXCHANGE_DATA_FIXED`` in modules/cfc/
        module.py §3).

        Multi-fragment responses accumulate per §13.1; the future is set
        only when all fragments arrive. Single-fragment responses fire
        immediately.

        Broadcasts (``command_id == 0``) and responses (``command_id != 0``)
        currently share the same txn-keyed delivery path — the operator's
        clarification: "IGNORE outer command_id entirely for CFC traffic."
        Cook 2 will introduce a subscription dispatcher; until then, an
        unsolicited broadcast that happens to have a txn nobody is waiting
        on is logged and dropped.
        """
        cmd_id = main.command_id  # unused for routing; kept for logs
        payload = bytes(main.app_data_exchange_request.data)

        hdr = parse_cfc_header(payload)
        if hdr is None:
            # Short/empty/bad-magic frame. Phase 2.5 mock tests round-trip
            # tiny payloads through here as a degenerate-case smoke; in real
            # CFC traffic the FAP never emits these. Log and drop.
            if self.debug:
                print(
                    f"[reader] CFC frame too short or bad header "
                    f"(len={len(payload)}, cmd_id={cmd_id}) — dropping",
                    file=sys.stderr,
                )
            return

        magic, version, op, txn, frag_idx, frag_total, payload_length = hdr
        body = payload[CFC_HEADER_LEN:]

        if frag_total == 0:
            # Defensive: matches the Phase 2.5 negative test for
            # zero_fragment_total. Drop, don't crash.
            if self.debug:
                print(
                    f"[reader] CFC frame frag_total=0 op=0x{op:02x} txn={txn} — dropping",
                    file=sys.stderr,
                )
            return

        if frag_total == 1:
            # Single-fragment: deliver immediately.
            self._deliver_cfc(txn, op, body, payload_length)
            return

        # Multi-fragment: accumulate. Per §13.1. Key by txn ONLY. The FAP emits
        # each fragment via a separate rpc_system_app_exchange_data() call, so
        # the outer Main.command_id can differ between fragments of the SAME
        # txn (Momentum uninit-malloc bug). Selecting an assembly map by
        # cmd_id==0 would split a single response's fragments across two maps
        # and they'd never reassemble — so route assembly purely by txn.
        assembly_map = self._cfc_assembling
        asm = assembly_map.setdefault(txn, {
            "fragments": [None] * frag_total,
            "fragment_total": frag_total,
            "op": op,
            "payload_length": payload_length,
        })
        # Frame consistency: total/op/payload_length should not change mid-txn.
        if asm["fragment_total"] != frag_total or asm["op"] != op:
            if self.debug:
                print(
                    f"[reader] CFC reassembly inconsistency for txn={txn}: "
                    f"frag_total {asm['fragment_total']}!={frag_total} "
                    f"or op 0x{asm['op']:02x}!=0x{op:02x} — dropping txn",
                    file=sys.stderr,
                )
            assembly_map.pop(txn, None)
            return
        if frag_idx < 0 or frag_idx >= frag_total:
            if self.debug:
                print(
                    f"[reader] CFC bad frag_idx={frag_idx}/{frag_total} for txn={txn} — dropping txn",
                    file=sys.stderr,
                )
            assembly_map.pop(txn, None)
            return
        asm["fragments"][frag_idx] = body

        if all(f is not None for f in asm["fragments"]):
            full = b"".join(asm["fragments"])
            assembly_map.pop(txn, None)
            self._deliver_cfc(txn, op, full, asm["payload_length"])

    def _deliver_cfc(
        self,
        txn: int,
        op: int,
        body: bytes,
        payload_length: int,
    ) -> None:
        """Hand a fully-assembled CFC payload to its waiter (M1–M4).

        Resolution order (per Cook 1.5): per-txn future in ``_cfc_pending``
        first (a host-initiated request awaiting its response), then the per-op
        subscription buffer (an unsolicited firmware broadcast). If neither
        exists the frame is logged and dropped.

        **M3 namespace partition.** Host request txns have the high bit CLEAR;
        firmware broadcast txns have it SET. This makes a broadcast structurally
        unable to resolve a pending request's Future (their txn ranges are
        disjoint), and lets the dispatcher reject the impossible cases as
        protocol bugs:
          - a response (matched a pending future) whose txn has the high bit SET
          - a broadcast (matched a subscription) whose txn has the high bit CLEAR

        **M1/M2.** Delivery into a subscription is the synchronous, non-blocking,
        atomic-drop-oldest :meth:`_Subscription.push` — the reader never awaits.

        **M4.** The subscription reference is snapshotted and the push is guarded
        so a subscriber that vanished (raced unsubscribe) can never crash the
        reader and freeze the wire.
        """
        high_bit_set = bool(txn & CFC_BROADCAST_TXN_BIT)

        # --- Response path: a host-initiated request awaits this txn. ---
        fut = self._cfc_pending.get(txn)
        if fut is not None:
            if high_bit_set:
                # M3: a response must use a host-namespace (high-bit-clear) txn.
                # A pending future keyed by a high-bit txn is impossible under the
                # partition — treat as firmware/protocol corruption, drop + log.
                if self.debug:
                    print(
                        f"[reader] M3 violation: response txn={txn:#010x} has "
                        f"broadcast high-bit set op=0x{op:02x} — dropping",
                        file=sys.stderr,
                    )
                return
            if not fut.done():
                fut.set_result((op, txn, body, payload_length))
            return

        # --- Broadcast path: no pending request future for this txn. ---
        sub = self._subscriptions.get(op)  # M4: snapshot the reference
        if sub is not None:
            if not high_bit_set:
                # M3: a broadcast must use a firmware-namespace (high-bit-set) txn.
                # A "broadcast" on a request-range txn is a firmware bug — a real
                # response would have matched a pending future above. Drop + log;
                # never let it masquerade as a legitimate event.
                if self.debug:
                    print(
                        f"[reader] M3 violation: broadcast op=0x{op:02x} "
                        f"txn={txn:#010x} missing high-bit — dropping",
                        file=sys.stderr,
                    )
                return
            try:
                # M1/M2: non-blocking, atomic drop-oldest. M4: guarded so a
                # vanished/closed subscription can never crash the reader.
                sub.push((op, txn, body, payload_length))
            except Exception as e:  # pragma: no cover — defensive (M4)
                if self.debug:
                    print(
                        f"[reader] subscription push failed op=0x{op:02x} "
                        f"txn={txn:#010x}: {type(e).__name__}: {e}",
                        file=sys.stderr,
                    )
            return

        if self.debug:
            print(
                f"[reader] stale CFC frame op=0x{op:02x} txn={txn:#010x} "
                f"len={len(body)} (no waiter, no subscription)",
                file=sys.stderr,
            )

    # =========================================================================
    # End Phase 3 reader infrastructure
    # =========================================================================

    @staticmethod
    def _encode_varint(n: int) -> bytes:
        out = bytearray()
        while True:
            b = n & 0x7F
            n >>= 7
            if n:
                out.append(b | 0x80)
            else:
                out.append(b)
                break
        return bytes(out)

    async def _read_varint(self, timeout: float = 2.5) -> Optional[int]:
        """
        Read a protobuf varint from the transport.

        Flipper firmware uses nanopb's PB_ENCODE_DELIMITED / PB_DECODE_DELIMITED,
        meaning each message is encoded as: [varint length][protobuf bytes].
        """
        try:
            value = 0
            shift = 0
            # Varint for message sizes should be small; cap at 5 bytes (32-bit).
            for _ in range(5):
                b = await self.transport.receive_exact(1, timeout=timeout)
                if not b:
                    return None
                byte = b[0]
                value |= (byte & 0x7F) << shift
                if not (byte & 0x80):
                    return value
                shift += 7
            return None
        except Exception:
            return None

    async def _receive_main_message(self, timeout: float = 2.5) -> Optional[Any]:  # Optional[flipper_pb2.Main]
        """Receive one nanopb-delimited Main message: [varint length][payload]."""
        try:
            payload_len = await self._read_varint(timeout=timeout)
            if payload_len is None or payload_len <= 0 or payload_len > 1_000_000:
                return None

            payload = await self.transport.receive_exact(payload_len, timeout=timeout)
            if not payload or len(payload) != payload_len:
                return None

            if self.debug:
                # stdout is reserved for MCP JSON-RPC when running under stdio.
                print(f"[protobuf] rx delimited len={payload_len}", file=sys.stderr)

            msg = flipper_pb2.Main()
            msg.ParseFromString(payload)
            return msg
        except Exception:
            return None

    async def _ensure_rpc_session_started(self) -> None:
        """
        Ensure the device is in RPC session mode.

        On firmware 1.4.3, the USB CDC port starts in CLI mode. The CLI command
        `start_rpc_session` switches the same port into nanopb-delimited RPC mode.

        Important detail: send the command terminated by CR-only ('\\r'), not CRLF,
        otherwise the trailing '\\n' can be consumed as the first byte of the first
        delimited message length and cause an immediate ERROR_DECODE + session close.
        """
        if self._rpc_session_started:
            return

        async def drain_host_rx(max_seconds: float = 0.6) -> None:
            """
            Drain any pending device->host bytes (CLI banner/prompt/echo).

            If we don't drain this before the first RPC call, we may misinterpret
            CLI output bytes as the first RPC response varint length prefix.
            """
            try:
                import time

                end = time.monotonic() + max_seconds
                while time.monotonic() < end:
                    chunk = await self.transport.receive(timeout=0.05)
                    if not chunk:
                        # Keep draining until the deadline to avoid stopping in the middle
                        # of a multi-chunk CLI banner/echo.
                        time.sleep(0.01)
                        continue
            except Exception as _e:  # silent_except_logged
                if self.debug:
                    print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
                pass

        # Best-effort: clear any buffered host-side bytes.
        try:
            self.transport.clear_receive_buffer()
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        # Give the device a moment to finish emitting the CLI banner/prompt after opening the port.
        try:
            import asyncio
            await asyncio.sleep(0.3)
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        async def probe_rpc(timeout: float = 0.4) -> bool:
            """
            Best-effort probe: send a protobuf ping request and see if we get a valid
            nanopb-delimited PB.Main ping response back.

            This is safer than trying to infer mode from idle output, because the CLI can
            be silent until the first keystroke.
            """
            try:
                # Clear any pending bytes so we only look at the probe response.
                try:
                    self.transport.clear_receive_buffer()
                except Exception as _e:  # silent_except_logged
                    if self.debug:
                        print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
                    pass
                await drain_host_rx(max_seconds=0.2)

                probe = flipper_pb2.Main()
                probe.command_id = 1
                probe.has_next = False
                probe.system_ping_request.CopyFrom(system_pb2.PingRequest(data=b"mcp"))
                payload = probe.SerializeToString()
                await self.transport.send(self._encode_varint(len(payload)) + payload)

                # Robustly read one nanopb-delimited message.
                msg = await self._receive_main_message(timeout=timeout)
                return (
                    bool(msg)
                    and msg.HasField("system_ping_response")
                    and msg.system_ping_response.data == b"mcp"
                )
            except Exception:
                # If we probed while in CLI mode, the device may have emitted text output;
                # drain it so it doesn't interfere with subsequent session negotiation.
                await drain_host_rx(max_seconds=0.5)
                return False

        force_start = os.environ.get("FLIPPER_FORCE_START_RPC_SESSION", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        # WiFi Dev Board transport already speaks nanopb-delimited protobuf over TCP (no CLI mode).
        # Attempting to send `start_rpc_session` bytes would corrupt the session.
        try:
            transport_name = ""
            if hasattr(self.transport, "get_name"):
                transport_name = str(self.transport.get_name() or "")
            is_wifi_transport = "wifi" in transport_name.lower() or hasattr(self.transport, "host")
        except Exception:
            is_wifi_transport = False

        # For WiFi transport, there is no CLI->RPC mode switch. Treat the session as started
        # and avoid sending any probe pings here (those can race with the caller's real ping
        # and cause false negatives in health checks).
        if is_wifi_transport:
            self._rpc_session_started = True
            return

        if not force_start:
            # WiFi can have slightly higher latency; probe longer before deciding it's not RPC.
            probe_timeout = 1.2 if is_wifi_transport else 0.4
            if await probe_rpc(timeout=probe_timeout):
                self._rpc_session_started = True
                return

            # On WiFi transport, do NOT attempt CLI session switching.
            if is_wifi_transport:
                self._rpc_session_started = False
                return

        # Switch to RPC mode via CLI command (CR-only) and verify by probing.
        # Important: do NOT assume the mode switch succeeded; if it didn't, subsequent
        # protobuf reads will interpret CLI output as varint framing and fail hard.
        async def start_session_attempt() -> bool:
            try:
                # Cancel any partially typed CLI input that could prevent the command
                # from being recognized (the CLI may remain open across host reconnects).
                await self.transport.send(b"\x03\r")
                await self.transport.send(b"start_rpc_session\r")
            except Exception as _e:  # silent_except_logged
                if self.debug:
                    print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
                pass

            await drain_host_rx(max_seconds=0.4)
            try:
                self.transport.clear_receive_buffer()
            except Exception as _e:  # silent_except_logged
                if self.debug:
                    print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
                pass
            # Give the device a moment to switch modes before probing.
            try:
                import asyncio
                await asyncio.sleep(0.2)
            except Exception as _e:  # silent_except_logged
                if self.debug:
                    print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
                pass

            return await probe_rpc(timeout=1.2)

        # One or two attempts is usually enough; keep it bounded to avoid long hangs.
        ok = await start_session_attempt()
        if not ok:
            ok = await start_session_attempt()
        if not ok:
            ok = await start_session_attempt()

        self._rpc_session_started = bool(ok)

        # The probe pings above used command_id=1. Advance our counter past that
        # so the next real call's id can never collide with a leftover probe reply
        # still buffered on the wire (would otherwise look like a valid match).
        if ok:
            self.command_id = max(self.command_id, 1)
    
    async def _send_rpc_message(
        self,
        main_message: Any  # flipper_pb2.Main
    ) -> Optional[Any]:  # Optional[flipper_pb2.Main]
        """
        Send a single-response protobuf RPC and await its reply (Phase 3 model).

        Reader-driven (DAY11 §4.2): the wire lock is held only for the brief
        send; the response is delivered by the single background reader task,
        which routes inbound frames to ``_pending[command_id]`` by the request's
        command_id. This replaces the Phase 2.5 "send then loop on
        _receive_main_message under the wire lock" pattern — the reader is now
        the SOLE caller of ``_receive_main_message``.

        The caller MUST NOT hold ``_wire_lock`` (this method acquires it for the
        send). Stale-reply discarding is no longer needed: the reader matches
        replies to requests by command_id, so a future only ever receives its
        own reply; mismatched frames are dropped by the reader.

        Args:
            main_message: Main protobuf message to send (command_id already set)

        Returns:
            Main response message, or None on timeout / transport error.
        """
        try:
            await self._ensure_session_and_reader()
            cmd_id = main_message.command_id
            fut = asyncio.get_event_loop().create_future()
            self._pending[cmd_id] = fut
            try:
                message_data = main_message.SerializeToString()
                message = self._encode_varint(len(message_data)) + message_data
                async with self._wire_lock:  # held only for the send
                    await self.transport.send(message)
                return await asyncio.wait_for(fut, timeout=RPC_TIMEOUT_S)
            finally:
                self._pending.pop(cmd_id, None)
        except Exception:
            return None

    async def _send_rpc_stream(
        self,
        main_message: Any,  # flipper_pb2.Main
        per_frame_timeout: float = 2.5,
    ) -> List[Any]:  # List[flipper_pb2.Main]
        """
        Send a request whose reply is a ``has_next`` chain and return all frames.

        Reader-driven streaming (DAY11 §16.1): methods like ``get_device_info``,
        ``storage_list``, and ``storage_read`` pull MULTIPLE response frames per
        call, all sharing one command_id, until a frame arrives with
        ``has_next == False``. A single-shot Future cannot model this, so
        ``_pending[command_id]`` holds an ``asyncio.Queue`` that the reader feeds
        frame-by-frame; this method drains it until the chain ends (or a frame
        gap longer than ``per_frame_timeout`` occurs).

        Returns the list of response Main frames in arrival order (possibly
        empty on transport error). Callers interpret command_status / payloads.
        """
        frames: List[Any] = []
        try:
            await self._ensure_session_and_reader()
            cmd_id = main_message.command_id
            queue: "asyncio.Queue" = asyncio.Queue()
            self._pending[cmd_id] = queue
            try:
                message_data = main_message.SerializeToString()
                message = self._encode_varint(len(message_data)) + message_data
                async with self._wire_lock:  # held only for the send
                    await self.transport.send(message)
                while True:
                    try:
                        item = await asyncio.wait_for(
                            queue.get(), timeout=per_frame_timeout
                        )
                    except asyncio.TimeoutError:
                        break  # no further frame arrived in the window
                    if isinstance(item, BaseException):
                        break  # reader stopped / desynced — end the stream
                    frames.append(item)
                    if not getattr(item, "has_next", False):
                        break  # terminal frame of the chain
            finally:
                self._pending.pop(cmd_id, None)
        except Exception:
            pass
        return frames

    async def ping(self, data: bytes = b"ping") -> Optional[bytes]:
        """
        Send a protobuf ping request.

        Returns the echoed bytes (if any) or None on failure.
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False
            ping_req = system_pb2.PingRequest()
            ping_req.data = data
            main_request.system_ping_request.CopyFrom(ping_req)

            resp = await self._send_rpc_message(main_request)
            if resp and resp.command_status == flipper_pb2.CommandStatus.OK and resp.HasField("system_ping_response"):
                return resp.system_ping_response.data
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        return None

    def _make_app_result(self, resp) -> AppRpcResult:
        """
        Build an AppRpcResult from a Main response message.

        On the wire, every Application-service RPC reply carries a CommandStatus enum
        in the envelope. We surface the enum *name* (e.g. 'ERROR_APP_CANT_START')
        instead of throwing it away, so callers can distinguish failure modes.
        """
        if resp is None:
            return AppRpcResult(False, -1, "NO_RESPONSE")
        try:
            code = int(resp.command_status)
        except Exception:
            return AppRpcResult(False, -1, "BAD_RESPONSE")
        try:
            name = flipper_pb2.CommandStatus.Name(code)
        except Exception:
            name = f"CODE_{code}"
        ok = code == flipper_pb2.CommandStatus.OK
        return AppRpcResult(ok, code, name)

    async def app_start(self, name: str, args: str = "") -> AppRpcResult:
        """
        Start an application via protobuf RPC (PB_App.StartRequest).

        Returns AppRpcResult(ok, status_code, status_name). The object is truthy iff
        the firmware accepted the request, so `if await app_start(...)` continues to
        work. On failure, inspect `.status_name` to see why (ERROR_APP_CANT_START,
        ERROR_INVALID_PARAMETERS, ERROR_APP_SYSTEM_LOCKED, etc.). For verbose error
        text, follow up with `app_get_error()`.

        Note: On some firmwares, starting certain apps (e.g. BadUSB) may change USB mode
        and disrupt the current transport (especially USB CDC). Callers should be prepared
        for the connection to drop even if the start succeeded.
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = application_pb2.StartRequest()
            req.name = name
            req.args = args or ""
            main_request.app_start_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            return self._make_app_result(resp)
        except Exception as e:
            return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")

    async def app_load_file(self, path: str) -> AppRpcResult:
        """
        Open a file with whichever app the firmware associates with that file type
        (PB_App.AppLoadFileRequest).

        Returns AppRpcResult(ok, status_code, status_name). Same idiom as app_start —
        truthy on success, but `.status_name` carries the failure reason on reject.

        On stock OFW this is the proper way to launch a JS script (`.js`), an NFC
        dump (`.nfc`), a sub-GHz capture (`.sub`), or an IR file (`.ir`). The device
        picks the correct handler app based on extension and runs it with the file
        as input.

        Many forks (Momentum, etc.) also accept this; some prefer `app_start` with
        an explicit app name. Callers should try `app_load_file` first when launching
        files; fall back to `app_start` if it returns False.
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = application_pb2.AppLoadFileRequest()
            req.path = path
            main_request.app_load_file_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            return self._make_app_result(resp)
        except Exception as e:
            return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")

    async def app_exit(self) -> AppRpcResult:
        """
        Ask the currently-running app to exit (equivalent to user pressing Back-to-exit).

        Plain English: this is the "close whatever's open" RPC. The firmware sends the
        same signal it would generate from a Back button press, so the app can save
        state cleanly. Returns ERROR_APP_NOT_RUNNING if nothing is open.

        Note: `app_state_response` is a server-initiated message the firmware emits
        when an app's state changes. We do not subscribe to it here; that's a future
        receive-loop feature. For now this method just blocks until the firmware
        acks the exit request.
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = application_pb2.AppExitRequest()
            main_request.app_exit_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            return self._make_app_result(resp)
        except Exception as e:
            return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")

    async def app_get_error(self) -> tuple[int, str]:
        """
        Read the firmware's verbose error info for the most recent failed app operation.

        Returns (code, text). On clean state both are typically (0, '').
        After a failed app_start / app_load_file, this carries the firmware-side
        explanation as a human-readable string.
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = application_pb2.GetErrorRequest()
            main_request.app_get_error_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            if resp is None or not resp.HasField("app_get_error_response"):
                return (-1, "no response")
            r = resp.app_get_error_response
            return (int(r.code), str(r.text))
        except Exception as e:
            return (-1, f"exception: {type(e).__name__}: {e}")

    async def app_lock_status(self) -> Optional[bool]:
        """
        Query whether the desktop is currently locked.

        Returns True if locked (RPC may refuse some operations), False if unlocked,
        None on transport/protocol error. Useful as a pre-flight check before
        attempting to launch apps that need an unlocked desktop.
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = application_pb2.LockStatusRequest()
            main_request.app_lock_status_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            if resp is None or not resp.HasField("app_lock_status_response"):
                return None
            return bool(resp.app_lock_status_response.locked)
        except Exception:
            return None

    # InputKey enum values (PB_Gui.InputKey): canonical names callers should use.
    _INPUT_KEY_MAP = {
        "UP": 0, "DOWN": 1, "RIGHT": 2, "LEFT": 3, "OK": 4, "BACK": 5,
    }
    # InputType enum values (PB_Gui.InputType).
    _INPUT_TYPE_MAP = {
        "PRESS": 0, "RELEASE": 1, "SHORT": 2, "LONG": 3, "REPEAT": 4,
    }

    async def desktop_is_locked(self) -> Optional[bool]:
        """
        Query whether the Flipper desktop lock-screen is currently active.

        NB: This is the *real* desktop lock state, distinct from `app_lock_status`
        which is actually the app-loader mutex (returns LOCKED whenever *any* app
        is running, including the lockscreen app itself — making it useless for
        distinguishing "screen is locked" from "another app is open").

        Returns True if the lockscreen is showing, False if a regular app or the
        unlocked desktop is showing, None on transport error.

        Per Momentum source: when the lockscreen is showing, the lockscreen scene
        IS the running app. So a `True` return from this AND a LOCKED return from
        `app_lock_status` means "definitely the lockscreen"; a `False` here with
        LOCKED in app_lock_status means "some other app is open."
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = desktop_pb2.IsLockedRequest()
            main_request.desktop_is_locked_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            if resp is None:
                return None
            # The firmware encodes the answer in command_status: OK means locked, ERROR means not locked.
            # This is unusual but it's what the Momentum source does — see desktop/desktop.c.
            code = int(resp.command_status)
            if code == flipper_pb2.CommandStatus.OK:
                return True
            return False
        except Exception:
            return None

    async def desktop_unlock(self) -> AppRpcResult:
        """
        Dismiss the Flipper desktop lockscreen via direct RPC.

        Canonical alternative to synthesizing a UP press via gui_send_input.
        Works regardless of whether the Momentum unlock combo is configured;
        the RPC bypasses the lock-prompt UI entirely.

        Returns AppRpcResult truthy on success. Failures typically mean either
        the device wasn't locked to begin with (still OK from firmware POV) or
        a PIN is configured (RPC cannot supply a PIN — physical entry required).
        """
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = desktop_pb2.UnlockRequest()
            main_request.desktop_unlock_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            return self._make_app_result(resp)
        except Exception as e:
            return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")

    async def gui_send_input_event(self, key: str, event_type: str = "SHORT") -> AppRpcResult:
        """
        Synthesize a physical button event at the GUI input layer.

        Unlike `app_button_press` (which only reaches apps that registered an RPC
        callback), this RPC injects at the lowest input layer — so any running app
        sees the event as if the user had pressed the button. Use this to exit
        sticky apps (like JS Runner, which doesn't have an RPC callback), navigate
        menus, or drive demo flows.

        NOTE: For the common "tap a button" case, prefer `gui_send_input_full_press`
        which emits the full PRESS→SHORT→RELEASE triplet in one call. This method
        sends only a single event — useful for advanced cases (holding a button,
        emitting REPEAT events, etc.) but most apps require the full triplet to
        register a press.

        Args:
            key: one of UP, DOWN, RIGHT, LEFT, OK, BACK (case-insensitive)
            event_type: one of PRESS, RELEASE, SHORT, LONG, REPEAT (default SHORT).
                A real hardware button generates PRESS → SHORT → RELEASE in sequence;
                most apps require all three to count as a press.

        Returns AppRpcResult — truthy on firmware OK, .status_name on failure.
        """
        k = self._INPUT_KEY_MAP.get(key.upper()) if key else None
        t = self._INPUT_TYPE_MAP.get(event_type.upper()) if event_type else None
        if k is None:
            return AppRpcResult(False, -1, f"BAD_KEY:{key!r}")
        if t is None:
            return AppRpcResult(False, -1, f"BAD_TYPE:{event_type!r}")

        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = gui_pb2.SendInputEventRequest()
            req.key = k
            req.type = t
            main_request.gui_send_input_event_request.CopyFrom(req)

            resp = await self._send_rpc_message(main_request)
            return self._make_app_result(resp)
        except Exception as e:
            return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")

    async def gui_send_input_full_press(self, key: str) -> AppRpcResult:
        """
        Emit a full PRESS → SHORT → RELEASE triplet for a key.

        This is the canonical "tap a button" primitive. Use this instead of three
        separate `gui_send_input_event` calls — empirically (mntm-dev, May 2026):
        a lone SHORT is silently absorbed by most app scenes. The firmware
        expects the full triplet to register a real button press.

        Validated working for: UP (Momentum menu), DOWN (File Browser),
        LEFT (Clock), RIGHT (Passport), OK (main menu), BACK (exit current scene).

        Args:
            key: one of UP, DOWN, RIGHT, LEFT, OK, BACK (case-insensitive)

        Returns the AppRpcResult of the SHORT event (the one apps actually react to).
        If PRESS or RELEASE fails, the failure is captured in `.status_name`.
        """
        if not key or key.upper() not in self._INPUT_KEY_MAP:
            return AppRpcResult(False, -1, f"BAD_KEY:{key!r}")

        # PRESS first — sets the key-down state
        r1 = await self.gui_send_input_event(key, "PRESS")
        if not r1.ok:
            return AppRpcResult(False, r1.status_code, f"PRESS_FAIL:{r1.status_name}")

        # SHORT — the event apps actually listen for
        r2 = await self.gui_send_input_event(key, "SHORT")
        if not r2.ok:
            # Still try RELEASE to avoid leaving the firmware in a stuck-pressed state
            await self.gui_send_input_event(key, "RELEASE")
            return AppRpcResult(False, r2.status_code, f"SHORT_FAIL:{r2.status_name}")

        # RELEASE — completes the triplet
        r3 = await self.gui_send_input_event(key, "RELEASE")
        if not r3.ok:
            return AppRpcResult(False, r3.status_code, f"RELEASE_FAIL:{r3.status_name}")

        return r2  # SHORT result is the canonical answer

    async def cli_command(self, command: str, timeout_s: float = 5.0, expect_prompt: bool = True) -> str:
        """
        Run a CLI command on the Flipper and return its raw text output.

        Plain English: the Flipper's USB serial port has two modes:
          1. CLI mode  — typed commands, human-readable output, ends with `>: ` prompt
          2. RPC mode  — protobuf-framed binary messages

        Most of this client lives in RPC mode. This method:
          1. Sends a protobuf StopSession message to leave RPC mode cleanly
          2. Waits and aggressively drains pending bytes (banner, prompt, ANSI color codes)
          3. Sends a Ctrl-C + CR to clear any partial input state on the device side
          4. Drains again
          5. Writes the command text + CR over the same transport
          6. Reads bytes until the next CLI prompt `>: ` (or timeout)
          7. Restarts the RPC session via `start_rpc_session\\r` so subsequent
             RPC calls work
          8. Returns the captured output (with the echoed command and prompt stripped)

        On firmwares without a `js_app` exposed to app_start (stock OFW + Momentum mntm-dev,
        as of 2026), this is the only way to launch a JS script via USB. The CLI command
        is `js <path>` per the Momentum docs.

        WARNING: while this method holds the channel in CLI mode, NO other RPC calls can
        be made. It serializes its work but the caller's own concurrency model still
        needs to ensure it isn't racing storage_* or similar.

        Args:
            command: text command to run (no trailing CR; we append \\r)
            timeout_s: max time to wait for CLI output to settle
            expect_prompt: if True, read until `>: ` is seen; if False, just read for timeout_s

        Returns:
            captured text output (best-effort decoded as UTF-8, ANSI colors stripped)
        """
        # Reject embedded newlines/carriage returns/control chars - they desync the
        # prompt parser (a stray '\\n' makes the device see two commands and emit
        # two prompts, our reader returns after the first one mid-second-command).
        if any(c in command for c in ("\r", "\n", "\x00")):
            raise ValueError(
                f"cli_command: command must not contain CR/LF/NUL "
                f"(got {command!r})"
            )

        # §16.3: cli_command leaves protobuf-RPC mode for CLI text mode. While in
        # CLI mode the wire carries text, not protobuf frames, so the single
        # reader MUST be stopped first — otherwise it parses CLI bytes as protobuf
        # and desyncs. Stop the reader, hold the wire lock for the entire CLI
        # interaction (no other send may interleave), then restart the session +
        # reader at the end (inside _cli_command_locked via _ensure_session_and_reader).
        await self._stop_reader()
        await self._wire_lock.acquire()
        try:
            return await self._cli_command_locked(
                command, timeout_s=timeout_s, expect_prompt=expect_prompt
            )
        finally:
            self._wire_lock.release()

    async def _cli_command_locked(
        self, command: str, timeout_s: float = 5.0, expect_prompt: bool = True
    ) -> str:
        """CLI-mode body of :meth:`cli_command` (§16.3).

        Runs with the single reader STOPPED and the wire lock HELD, so all wire
        I/O here is direct (no reader contention). Restarts the RPC session and
        the reader before returning. Returns captured CLI text output.
        """
        import asyncio
        import re
        import time

        # 1. Ask the RPC server to gracefully end the session.
        try:
            main = flipper_pb2.Main()
            main.command_id = self._get_next_command_id()
            main.has_next = False
            main.stop_session.SetInParent()  # set the empty StopSession message
            payload = main.SerializeToString()
            await self.transport.send(self._encode_varint(len(payload)) + payload)
        except Exception as _e:  # silent_except_logged
            # Even if this fails, attempt to fall through and switch via best-effort.
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py:cli_command stop_session] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        self._rpc_session_started = False

        # 2. Give the firmware time to drop back to CLI and emit its banner/prompt.
        #    Momentum can take ~500ms to fully settle and emit the prompt.
        await asyncio.sleep(0.5)

        async def aggressive_drain(seconds: float) -> None:
            """Drain everything for `seconds`, even between idle gaps."""
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                chunk = await self.transport.receive(timeout=0.05)
                # Loop continues regardless; we're just consuming bytes.
                if not chunk:
                    await asyncio.sleep(0.02)

        # Aggressive drain of the post-stop banner + prompt + any color codes.
        await aggressive_drain(0.6)
        try:
            self.transport.clear_receive_buffer()
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        # 3. Send Ctrl-C + CR to make absolutely sure no partial command/input remains
        #    on the device's CLI line buffer (would prepend to our command otherwise).
        try:
            await self.transport.send(b"\x03\r")
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        await asyncio.sleep(0.15)
        await aggressive_drain(0.3)
        try:
            self.transport.clear_receive_buffer()
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        # 4. Send the command. CR-only line ending matches what start_rpc_session uses.
        cmd_bytes = (command + "\r").encode("utf-8", errors="replace")
        await self.transport.send(cmd_bytes)

        # 5. Read until prompt + quiet window, or timeout.
        #
        # PREVIOUS BUG: original code broke on FIRST occurrence of ">: " anywhere
        # in the buffer. If the script's stdout itself contained ">: " (a log
        # path, debug print, status line, etc.), we'd truncate mid-stream.
        # Tested fix: keep reading after first prompt-sighting until QUIET_WINDOW_S
        # of no new bytes elapses. Real prompts are at end-of-output (followed by
        # silence). In-output prompts are followed by more bytes, so we don't exit
        # at them. See C:\Temp\test_cli_prompt_fix.py for unit tests covering this.
        QUIET_WINDOW_S = 0.2
        captured = bytearray()
        prompt_marker = b">: "
        deadline = time.monotonic() + max(0.5, timeout_s)
        last_byte_time = None  # When did we last receive any bytes?
        prompt_seen = False    # Has ">: " appeared in the buffer at all?
        while time.monotonic() < deadline:
            chunk = await self.transport.receive(timeout=0.1)
            now = time.monotonic()
            if chunk:
                captured.extend(chunk)
                last_byte_time = now
                if expect_prompt and prompt_marker in captured:
                    prompt_seen = True
            else:
                # Idle slice. If we've already seen the prompt and the line has
                # been quiet for QUIET_WINDOW_S, we can finalize.
                if (
                    expect_prompt
                    and prompt_seen
                    and last_byte_time is not None
                    and now - last_byte_time >= QUIET_WINDOW_S
                ):
                    break

        # 6. Restart the RPC session AND the reader for subsequent calls (§16.3).
        #    Delegate to _ensure_session_and_reader() which re-probes / re-negotiates
        #    CLI→RPC and then restarts the single reader task. This ensures we don't
        #    return until RPC is genuinely re-established and the reader is live.
        self._rpc_session_started = False
        try:
            self.transport.clear_receive_buffer()
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        try:
            await self._ensure_session_and_reader()
        except Exception as _e:  # silent_except_logged
            # If session restart genuinely failed, leave _rpc_session_started=False so
            # the next call will try again. The user's CLI output is still returned below.
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py:cli_command rpc_restart] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        # 6b. Settle delay. If the CLI command was a script that wrote files
        # (e.g. `js <path>`), the firmware's storage layer may still be flushing
        # to SD when we hand control back to the caller. Without this delay, an
        # immediate storage_read can return a partial file (we observed truncation
        # to the last ~50% of a freq_analyzer log on Momentum).
        # Cheap insurance: 250ms is well below human-noticeable, well above flush time.
        await asyncio.sleep(0.25)

        # 7. Decode, strip ANSI escape sequences, then strip echoed cmd + prompt.
        text = captured.decode("utf-8", errors="replace")
        # Strip ANSI color escape codes like \x1b[31m and \x1b[0m
        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
        # Strip the echoed command line if present at the start
        # (CLI may echo with leading whitespace, CR, or LF)
        text = text.lstrip("\r\n \t")
        if text.startswith(command):
            text = text[len(command):].lstrip("\r\n")
        # Strip trailing prompt
        idx = text.rfind(">: ")
        if idx >= 0:
            text = text[:idx].rstrip("\r\n \t")
        return text
    
    async def get_device_info(self) -> Dict[str, Any]:
        """
        Get device information using system.get_device_info RPC.
        
        DeviceInfo returns multiple key-value pairs, so we need to
        collect all responses until has_next is false.
        
        Returns:
            Dictionary of device information key-value pairs
        """
        info = {}
        
        # Add overall timeout to prevent hanging
        import asyncio
        try:
            return await asyncio.wait_for(self._get_device_info_internal(), timeout=6.0)
        except (asyncio.TimeoutError, Exception):
            return info
    
    async def _get_device_info_internal(self) -> Dict[str, Any]:
        """Internal implementation of get_device_info."""
        info = {}
        
        try:
            # Build Main message with DeviceInfoRequest
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False
            main_request.system_device_info_request.CopyFrom(system_pb2.DeviceInfoRequest())

            # DeviceInfo streams key/value pairs as a has_next chain (§16.1):
            # the reader feeds every response frame; collect while OK.
            frames = await self._send_rpc_stream(main_request, per_frame_timeout=2.5)
            for main_response in frames:
                if main_response.command_status != flipper_pb2.CommandStatus.OK:
                    break
                if main_response.HasField('system_device_info_response'):
                    device_info = main_response.system_device_info_response
                    if device_info.key and device_info.value:
                        info[device_info.key] = device_info.value

        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass

        # If we didn't get info from DeviceInfo, try property.get for common keys
        if not info:
            property_keys = [
                'firmware_version',
                'hardware_model',
                'hardware_version',
                'serial_number',
                'firmware_build_date',
                'firmware_git_hash'
            ]

            for key in property_keys:
                try:
                    value = await self._get_property_internal(key)
                    if value:
                        info[key] = value
                except Exception as _e:  # silent_except_logged
                    if self.debug:
                        print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
                    pass
        
        return info
    
    async def get_property(self, key: str) -> Optional[str]:
        """
        Get a property value using property.get RPC.
        
        Args:
            key: Property key
            
        Returns:
            Property value or None
        """
        # Add overall timeout to prevent hanging
        import asyncio
        try:
            return await asyncio.wait_for(self._get_property_internal(key), timeout=2.0)
        except (asyncio.TimeoutError, Exception):
            return None
    
    async def _get_property_internal(self, key: str) -> Optional[str]:
        """Internal implementation of get_property."""
        try:
            # Build Main message with Property.GetRequest
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False
            
            # Set property_get_request
            get_request = property_pb2.GetRequest()
            get_request.key = key
            main_request.property_get_request.CopyFrom(get_request)
            
            # Send request and get response
            main_response = await self._send_rpc_message(main_request)
            
            if main_response and main_response.command_status == flipper_pb2.CommandStatus.OK:
                if main_response.HasField('property_get_response'):
                    return main_response.property_get_response.value
            
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        
        return None

    async def storage_list(
        self, path: str, include_md5: bool = False, filter_max_size: int = 0
    ) -> list[str]:
        """
        List entries in a directory via protobuf storage_list_request.

        Returns a list of names (files/dirs). If the device streams results using has_next,
        we collect all frames.
        """
        names: list[str] = []
        import asyncio
        try:
            return await asyncio.wait_for(
                self._storage_list_internal(path, include_md5=include_md5, filter_max_size=filter_max_size),
                timeout=3.0,
            )
        except Exception:
            return names

    async def storage_list_detailed(
        self, path: str, include_md5: bool = False, filter_max_size: int = 0
    ) -> list[dict[str, Any]]:
        """
        List entries in a directory via protobuf storage_list_request (detailed).

        Returns a list of dicts with:
        - name: entry name
        - type: "FILE" | "DIR"
        - size: uint32 size (0 for dirs on most firmwares)
        - md5sum: optional md5 (only when include_md5=True and device provides it)
        """
        entries: list[dict[str, Any]] = []
        import asyncio
        try:
            return await asyncio.wait_for(
                self._storage_list_detailed_internal(
                    path, include_md5=include_md5, filter_max_size=filter_max_size
                ),
                timeout=3.0,
            )
        except Exception:
            return entries

    async def _storage_list_internal(
        self, path: str, include_md5: bool = False, filter_max_size: int = 0
    ) -> list[str]:
        names: list[str] = []
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = storage_pb2.ListRequest()
            req.path = path
            req.include_md5 = include_md5
            if filter_max_size:
                req.filter_max_size = int(filter_max_size)
            main_request.storage_list_request.CopyFrom(req)

            # storage_list streams directory entries as a has_next chain (§16.1).
            frames = await self._send_rpc_stream(main_request, per_frame_timeout=2.5)
            for resp in frames:
                if resp.command_status != flipper_pb2.CommandStatus.OK:
                    break
                if resp.HasField("storage_list_response"):
                    for f in resp.storage_list_response.file:
                        if f.name:
                            names.append(f.name)

        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        return names

    async def _storage_list_detailed_internal(
        self, path: str, include_md5: bool = False, filter_max_size: int = 0
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = storage_pb2.ListRequest()
            req.path = path
            req.include_md5 = include_md5
            if filter_max_size:
                req.filter_max_size = int(filter_max_size)
            main_request.storage_list_request.CopyFrom(req)

            # storage_list (detailed) streams entries as a has_next chain (§16.1).
            frames = await self._send_rpc_stream(main_request, per_frame_timeout=2.5)
            for resp in frames:
                if resp.command_status != flipper_pb2.CommandStatus.OK:
                    break
                if resp.HasField("storage_list_response"):
                    for f in resp.storage_list_response.file:
                        if not f.name:
                            continue
                        ftype = "DIR" if f.type == storage_pb2.File.DIR else "FILE"
                        item: dict[str, Any] = {"name": f.name, "type": ftype, "size": int(f.size)}
                        if include_md5 and getattr(f, "md5sum", ""):
                            item["md5sum"] = f.md5sum
                        entries.append(item)
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        return entries

    async def storage_read(self, path: str) -> bytes:
        """
        Read a file via protobuf storage_read_request.

        Handles chunked responses (firmware streams files >512B across multiple
        Main messages with has_next=True). Concatenates all chunks before returning.
        """
        import asyncio
        try:
            # Generous timeout: large files chunked at 512B can need 30+ chunks.
            return await asyncio.wait_for(self._storage_read_internal(path), timeout=30.0)
        except Exception:
            return b""

    async def _storage_read_internal(self, path: str) -> bytes:
        """
        Read a file via protobuf storage_read_request.

        Files larger than ~512 bytes get chunked across multiple response messages
        (firmware sets has_next=True on all but the last). We loop and concatenate
        until has_next is False — same pattern as storage_list.
        """
        chunks: list[bytes] = []
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = storage_pb2.ReadRequest()
            req.path = path
            main_request.storage_read_request.CopyFrom(req)

            # Files >512B stream as a has_next chain (§16.1); the reader feeds
            # every chunk frame. Concatenate while command_status is OK.
            frames = await self._send_rpc_stream(main_request, per_frame_timeout=2.5)
            for resp in frames:
                if resp.command_status != flipper_pb2.CommandStatus.OK:
                    break
                if resp.HasField("storage_read_response"):
                    chunks.append(bytes(resp.storage_read_response.file.data))

        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        return b"".join(chunks)

    async def storage_info(self, path: str) -> Optional[tuple[int, int]]:
        """
        Query storage info for a path (e.g. /ext for SD card).

        Returns (total_space, free_space) or None on failure.
        """
        import asyncio
        try:
            return await asyncio.wait_for(self._storage_info_internal(path), timeout=3.0)
        except Exception:
            return None

    async def _storage_info_internal(self, path: str) -> Optional[tuple[int, int]]:
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = storage_pb2.InfoRequest()
            req.path = path
            main_request.storage_info_request.CopyFrom(req)

            main_response = await self._send_rpc_message(main_request)
            if (
                main_response
                and main_response.command_status == flipper_pb2.CommandStatus.OK
                and main_response.HasField("storage_info_response")
            ):
                r = main_response.storage_info_response
                return int(r.total_space), int(r.free_space)
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py] {type(_e).__name__}: {_e}", file=sys.stderr)
            pass
        return None

    async def storage_mkdir(self, path: str) -> bool:
        import asyncio
        try:
            return await asyncio.wait_for(self._storage_mkdir_internal(path), timeout=3.0)
        except Exception:
            return False

    async def _storage_mkdir_internal(self, path: str) -> bool:
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = storage_pb2.MkdirRequest()
            req.path = path
            main_request.storage_mkdir_request.CopyFrom(req)

            main_response = await self._send_rpc_message(main_request)
            return bool(main_response and main_response.command_status == flipper_pb2.CommandStatus.OK)
        except Exception:
            return False

    async def storage_delete(self, path: str, recursive: bool = False) -> bool:
        import asyncio
        try:
            return await asyncio.wait_for(
                self._storage_delete_internal(path, recursive=recursive), timeout=3.0
            )
        except Exception:
            return False

    async def _storage_delete_internal(self, path: str, recursive: bool = False) -> bool:
        try:
            main_request = flipper_pb2.Main()
            main_request.command_id = self._get_next_command_id()
            main_request.has_next = False

            req = storage_pb2.DeleteRequest()
            req.path = path
            req.recursive = recursive
            main_request.storage_delete_request.CopyFrom(req)

            main_response = await self._send_rpc_message(main_request)
            return bool(main_response and main_response.command_status == flipper_pb2.CommandStatus.OK)
        except Exception:
            return False

    async def storage_write(self, path: str, content: bytes) -> bool:
        import asyncio
        try:
            # Generous timeout: chunked writes of ~30KB take 60+ round-trips,
            # each potentially 50-100ms on real hardware. 30s gives headroom.
            return await asyncio.wait_for(self._storage_write_internal(path, content), timeout=30.0)
        except Exception:
            return False

    async def _storage_write_internal(self, path: str, content: bytes) -> bool:
        """
        Write a file via protobuf storage_write_request, chunking when needed.

        Plain English: the Flipper's nanopb receive buffer is roughly 1 KB. If we
        ship a 2 KB JS mission as one big WriteRequest, the firmware silently
        truncates it. So we chunk into 512-byte payloads.

        Firmware ACK semantics (see docs/KIISU_DEEP_KNOWLEDGE.md §5.2, source
        rpc_storage.c `send_response = !request->has_next;`): the firmware sends
        ZERO responses for intermediate chunks. It only emits one PB_Main with
        CommandStatus after the final chunk (has_next=false) arrives.

        Bug history (R5, fixed 2026-05-17): an earlier version of this function
        believed every chunk got an ACK, and waited for one after each chunk.
        Result: multi-chunk writes (>512 bytes) timed out waiting for chunk 1's
        non-existent ACK, returned False, and the file on disk was truncated to
        the bytes from just chunk 1 — the worst kind of "Write failed but actually
        partially succeeded" bug. Empirically reproduced and traced against
        AmorPoee on mntm-dev before this fix.

        Correct pattern (mirrors the upstream Python reference client
        flipperzero_protobuf_py/flipper_storage.py): fire all chunks back-to-back
        with shared command_id, has_next=True on every chunk except the last, then
        read exactly one ACK after the final chunk.

        Phase 3 reader model (§16.2): ONE command_id spans every chunk, with a
        SINGLE terminal ack. So we register exactly ONE future for that cmd_id
        BEFORE sending, hold the wire lock across all chunk sends (so no other
        method interleaves a frame mid-transfer), then release the lock and await
        the one ack the reader routes back. The future's cmd_id entry is cleaned
        up ONLY after the final ack (in finally) — the naive
        "finally: pop between chunks" pattern from §4.2 is WRONG here because it
        would orphan the in-flight transfer.
        """
        try:
            # Accept str or bytes for backwards compatibility - some call sites
            # (rpc.py wrapper) already encode; others pass str directly.
            if isinstance(content, str):
                content = content.encode("utf-8", errors="replace")

            CHUNK_SIZE = 512
            # Even an empty file goes through one WriteRequest with empty data so
            # the firmware truncates the existing file. Iterate from 0 and always
            # send at least one chunk.
            total_len = len(content)
            cmd_id = self._get_next_command_id()

            # Ensure RPC session is alive AND the reader is running before we
            # start streaming. Done once outside the loop so we don't re-probe
            # mid-transaction.
            await self._ensure_session_and_reader()

            # ONE future for the whole multi-chunk transfer (§16.2). Registered
            # before the send so the reader can match the single terminal ack.
            fut = asyncio.get_event_loop().create_future()
            self._pending[cmd_id] = fut
            try:
                async with self._wire_lock:  # exclusive wire for all chunk sends
                    offset = 0
                    while True:
                        end = min(offset + CHUNK_SIZE, total_len)
                        chunk = content[offset:end]
                        is_last = end >= total_len

                        main_request = flipper_pb2.Main()
                        main_request.command_id = cmd_id
                        main_request.has_next = not is_last

                        req = storage_pb2.WriteRequest()
                        req.path = path
                        f = storage_pb2.File()
                        f.data = chunk
                        req.file.CopyFrom(f)
                        main_request.storage_write_request.CopyFrom(req)

                        message_data = main_request.SerializeToString()
                        framed = self._encode_varint(len(message_data)) + message_data
                        await self.transport.send(framed)

                        if is_last:
                            break
                        offset = end

                # Lock released. The firmware sends ZERO acks for intermediate
                # chunks; the single ack arrives only after the final chunk. Wait
                # generously: long writes to /int can stall on LittleFS GC.
                final_response = await asyncio.wait_for(fut, timeout=10.0)
                if (
                    not final_response
                    or final_response.command_id != cmd_id
                    or final_response.command_status != flipper_pb2.CommandStatus.OK
                ):
                    return False
                return True
            finally:
                # §16.2: clean up the cmd_id ONLY now (after the terminal ack),
                # never between chunks.
                self._pending.pop(cmd_id, None)
        except Exception as _e:  # silent_except_logged
            if self.debug:
                print(f"[silent-except @ protobuf_rpc.py:storage_write] {type(_e).__name__}: {_e}", file=sys.stderr)
            return False
