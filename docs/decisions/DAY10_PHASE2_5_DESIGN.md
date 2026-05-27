# DAY 10 — Phase 2.5 Design Doc v8.4

**Status:** DRAFT v8.4 — Cook attempt #3 succeeded 26/27 (96.3%). One legacy
test needs a helper to handle multi-fragment outbound; helper added. COOK-READY.
**Author:** Claude Desktop + Victor + cc (caught all four iterations)
**Date:** 2026-05-27
**Supersedes:** v7 (same file path). Review history:
  - Sherpa v1 review: `E:\Sherpa\working\reviews\DAY10_PHASE2_5_DESIGN\20260527-130548\`
  - NotebookLM Round 1: 2 questions, segmented corpus (firmware-side + host-side)
  - Gemini v1 reflection: pasted into chat 2026-05-27 mid-afternoon
  - Sherpa v2 review: `E:\Sherpa\working\reviews\DAY10_PHASE2_5_DESIGN\20260527-132707\`
  - Gemini v2 reflection: pasted into chat 2026-05-27 late afternoon
  - NotebookLM Round 2: 5 fact-check questions, unified corpus (70 sources)
  - NotebookLM Round 3: 3 implementation-detail questions, unified corpus
  - Arena.ai Model B critique: pasted into chat 2026-05-27 evening (HasField verification, §0 contradiction)
  - Arena.ai Model A critique: pasted into chat 2026-05-27 evening (test count, mock scaffold, _get_protobuf_rpc gap, etc.)
    (Model B initial cook-confidence: 73%, Model A: ~75%, projected ~95% with v8 fixes)
  - Momentum PR draft: `D:\Dev\scratch\day10_momentum_pr_draft.md` (parallel artifact)

---

## v1 → v2 changelog

Sherpa v1 (Grok / DeepSeek / MiMo, three SHIP_WITH_FIXES verdicts) flagged 7 issues:

1. **§0's "FAP-side workaround" is a phantom.** The FAP physically cannot fix this; the firmware owns the malloc. v2 removes that promise.
2. **Cross-tool interference risk.** v1's drain loop held the wire lock and silently
   discarded non-CFC frames. If a concurrent flipper-mcp tool's response arrived,
   CFC ate it. v2 redesigns the drain to never discard non-CFC frames.
3. **Polling-loop timeout bug.** v1 reused `followup_timeout` as both per-read and
   deadline. v2 uses `min(per_read, remaining_deadline)`.
4. **No stop conditions / rollback.** v2 adds explicit halt criteria and a §10
   rollback plan.
5. **`_send_main_raw` unsourced.** v2 names the exact file
   (`flipper_mcp/core/protobuf_rpc.py`), shows the extraction, and specifies the
   wire framing it must produce.
6. **No test for the broadcast path itself.** v2 adds a unit test injecting a mock
   `command_id == 0` response.
7. **Wide-vs-narrow ambiguity in §2.2.** v2 picks one explicitly: **accept any
   inbound `app_data_exchange_request` regardless of command_id**, with the
   sunset condition gating return to strict-match.

---

## v2 → v3 changelog

Gemini 3.1 Pro extended-thinking reflection found three critical issues v2 missed:

1. **Internal contradiction between §0 and §2.2.** v2 TL;DR claimed non-CFC frames
   would be "routed back into the transport buffer," but §2.2 code comments
   admitted there is no API to do this. cc would have either halted confused
   or invented a buffer-push API. v3 resolves by **explicitly declaring
   non-CFC frames during CFC drain are consumed and lost (Path A)**, and
   moving Path B (a real frame queue) to a Phase 3 decision.
2. **`return None` on the defensive branch is a beginner trap.** v2 silently
   converted "impossible" state-machine corruption into a generic
   `CfcTimeoutError` upstream, hiding genuine protocol desyncs as phantom
   timeouts. v3 introduces `CfcProtocolDesyncError`, raises it loudly on the
   defensive branch, and tears down the RPC session for clean reconnection.
3. **Sunset-gate fragility.** Static `MOMENTUM_RPC_EXCHANGE_DATA_FIXED = False`
   with no reminder = forgotten code. v3 adds a one-shot `logging.warning` on
   module import when the flag is False, keeping the upstream PR top-of-mind
   every CPK boot.

---

## v3 → v4 changelog

Sherpa v2 (Grok / DeepSeek / MiMo, three SHIP_WITH_FIXES verdicts — all
nit-level, no structural problems) flagged three convergent real issues:

1. **Test filename mismatch.** §4.5 named the test `test_non_cfc_frame_raises_desync.py`
   but §5 step 6 still used the v2 filename `test_non_cfc_frame_not_consumed.py`.
   v4 makes §5 step 6 match §4.5.
2. **Halt-criterion contradiction on `test_chunked_ping_roundtrip`.** §4.3 said
   "halt on failure" but §9 said "cc does NOT halt" for the same test.
   v4 removes the §9 exception and adds the test to §9's explicit halt list.
3. **Import paths unsourced.** `flipper_pb2`, `application_pb2`,
   `_get_next_command_id`, `_receive_main_message`'s `timeout` kwarg, and the
   `transport.send` method name were referenced without canonical paths. cc
   would have had to grep the codebase. v4 adds §1.4 with all paths verified
   from the actual source at commit 0899964.

Two issues v4 explicitly does NOT fix (with rationale):
- **No wire-framing unit test for `_send_main_raw`.** The function is 5 lines
  extracted verbatim from `_send_rpc_message`'s send half; the 17 existing
  hardware tests exercise the framing through `_send_rpc_message`. Adding a
  separate unit test would test the same code twice.
- **No import-time-warning test.** Manual smoke check is sufficient; not worth
  unit-test budget.

---

## v4 → v5 changelog

Gemini v2 extended-thinking reflection (cook-confidence 65% → 95% with these
fixes) caught two issues every prior reviewer missed:

1. **Empty-payload logic bomb in `_cfc_send_one_frame`.** The v4 check
   `if resp.HasField("app_data_exchange_request") and resp.app_data_exchange_request.data:`
   uses Python's truthiness on bytes. An empty bytes payload (`b""`) is falsy,
   so a perfectly valid zero-byte CFC frame would fall through to the
   defensive branch and raise `CfcProtocolDesyncError`, tearing down the RPC
   session over a legal empty response. v5 decouples the type-check from the
   payload-check: any frame with `HasField("app_data_exchange_request")` is
   accepted as CFC regardless of whether its payload is empty or not.
2. **Import gap in §1.4.** v4 claimed `_send_main_raw` needed no new imports.
   The code block uses `sys.stderr` and type hints `Any` / `Optional`. v5
   verifies (and §1.4 now states explicitly) that both `import sys` and
   `from typing import Optional, ..., Any, ...` are present in
   `flipper_mcp/core/protobuf_rpc.py` at the time of writing.

Gemini v2 also confirmed the architecture is "solidifying beautifully" and
declared v5 cook-ready. Sherpa v3 is optional — fire-and-forget for catching
anything Gemini missed, but the architectural reviews have converged.

---

## v5 → v6 changelog

NotebookLM Round 2 (5 fact-check questions against the unified 70-source corpus)
confirmed v5's empirical claims AND surfaced a new finding that materially
changes v6's architecture. NotebookLM Round 3 (3 follow-up questions) locked
down the implementation details.

**Round 2 Q1-Q4 confirmations (no design changes needed):**
- v5's empty-payload fix targets a real serialization scenario (Q1: nanopb
  emits the field tag with zero-byte content; Python sees `HasField=True,
  data=b""`).
- The empty-payload case is defensive hardening, not blocking a real bug
  in production code (Q2: no FAP or host client currently sends empty
  payloads as a control signal).
- CPK's `_wire_lock` model is consistent with qFlipper and the official
  Python bindings (Q3: all reference clients effectively wire-lock).
- `app_data_exchange_request` flows both directions; no separate response
  type exists (Q4: confirmed against `application.proto` and `flipper.proto`).

**Round 2 Q5 — material new finding:**
- `rpc_system_app_send_state_response` has the SAME uninit-malloc bug as
  `rpc_system_app_exchange_data`. It fires on every FAP launch (`APP_STARTED`)
  and exit (`APP_CLOSED`), with garbage `command_id`. Every `app_start` call
  in CFC tests indirectly produces one of these frames.

**Round 3 Q6 — complete async event-frame enumeration:**
Four asynchronous PB_Main frame types exist firmware-wide:
| Frame type | command_id state | Source |
|---|---|---|
| `app_data_exchange_request` | garbage (bug) | `rpc_system_app_exchange_data` |
| `app_state_response` | garbage (bug) | `rpc_system_app_send_state_response` |
| `gui_screen_frame` | clean (calloc / explicit 0) | GUI RPC service |
| `desktop_status` | clean (explicit 0) | Desktop RPC service |

No hidden frame types. The set is closed.

**Round 3 Q7 — APP_STARTED timing (explains why Phase 2 already passes):**
The firmware emits `APP_STARTED` AFTER replying to the host's `app_start`
request. By the time CFC's drain loop runs, the strict matcher in
`_send_rpc_message` has already discarded the orphan frame on the next
unrelated RPC call. There is no observable bug in Phase 2's existing tests
because the timing happens to be benign. v6 still needs to handle this
correctly because future code paths could expose it.

**Round 3 Q8 — qFlipper's canonical pattern:**
qFlipper routes inbound `PB_Main` frames by `which_content` tag FIRST,
intercepting known asynchronous events (`app_data_exchange_request`,
`gui_screen_frame`, `app_state_response`) and emitting Qt signals for them.
Only frames that are NOT known async event types get matched against the
current operation's `command_id`. **This is the canonical reference pattern
v6 should adopt.**

**v6 architectural shift (vs v5):**

v5's drain loop was: "accept `app_data_exchange_request`, raise
`CfcProtocolDesyncError` on anything else." This is too aggressive — it
would have raised on legitimate `app_state_response` frames every time
the test harness called `app_start`.

v6's drain loop is: "route by `which_content` tag first. Known event types
(per Q6 allowlist) get consumed-and-continue. CFC-data frames return.
Genuinely unknown content tags raise `CfcProtocolDesyncError`." This matches
qFlipper's canonical pattern and is empirically complete per Q6.

The v6 code is **smaller** than v5's drain loop because the allowlist is
clean and named. The v5 → v6 delta is approximately 8 lines of new code in
`_cfc_send_one_frame` plus the allowlist constant.

**Momentum PR scope (now covers both buggy functions):**
The PR (drafted at `D:\Dev\scratch\day10_momentum_pr_draft.md`) patches BOTH
`rpc_system_app_exchange_data` and `rpc_system_app_send_state_response` with
the same fix (`memset` after `malloc`, or switch to `calloc`). One patch,
two functions, higher review value. Still deferred — Phase 2.5 ships
without it.

---

## v6 → v7 changelog

Arena.ai random-model critique (Model B, identity unknown — likely Opus-class
or GPT-class given response depth) gave v6 a cook-confidence of **73%**, lower
than Gemini v2's 95% for v5 because **v6's architectural shift to the
route-by-tag allowlist introduced new failure surfaces v5 didn't have.** Two
risks scored above 10%:

**Failure Mode Alpha (35% risk): `HasField` field name mismatch.** Model B
flagged that the protobuf-generated Python field names for `app_state_response`,
`gui_screen_frame`, and `desktop_status` were never empirically verified
against the actual `flipper_pb2.Main` descriptor. If even one name is wrong,
`HasField` silently returns False, the frame falls through to the defensive
branch, and desync raises on every `app_start`.

**v7 closes this by empirical verification, not just doc fix.** Ran:
```
from flipper_mcp.core.protobuf_gen import flipper_pb2
m = flipper_pb2.Main()
for f in ['app_data_exchange_request', 'app_state_response',
          'gui_screen_frame', 'desktop_status', 'system_ping_response']:
    m.HasField(f)  # all return False without raising ValueError
```
All five field names are present in the generated descriptor. `HasField` works
exactly as v6 §2.2 expects. **The Alpha risk is closed at the source, not
in the doc.** §5 step 1 also gains an explicit pre-flight grep so cc
re-verifies before cooking.

**Failure Mode Bravo (15% risk): §0 TL;DR contradicts §2.2.** §0 still
said "non-CFC frames raise desync" (language inherited from v5). v6's
§2.2 actually consumes the three known async events and continues — only
*unknown* content tags raise desync. cc reading §0 as authoritative could
have "corrected" the §2.2 allowlist to match §0. v7 rewrites §0 to match
§2.2's true behavior.

**Lower-priority cleanup also applied:**
- v5→v6 changelog claim "code is smaller" is removed — v6 has more `if`
  branches than v5, not fewer (code is more correct, not shorter).
- v2→v3 changelog phrase "consumed and lost (Path A)" stale — v6 consumes-
  and-continues, which is different. v7 notes this is superseded.
- §6 review questions were v3-era — v7 replaces with questions relevant
  to v7's allowlist architecture.
- §2.4 pytest-noise concern (Gemini v3 question 3) is now answered:
  pytest captures `logging.warning` by default, surfaces only on failures.
  No noise issue.

**Cook-confidence after v7 fixes: ~92%** per Model B's projection. The
residual 8% is firmware-side surprises that no design doc can preempt
(unexpected wire behavior at cook time).

---

## v7 → v8 changelog

Arena.ai delivered a second response (Model A) after Model B's review. Model A
gave a 75% baseline confidence with a slightly different risk profile —
overlapped with Model B on the §0 contradiction (already fixed in v7) but
caught **nine items B missed**, three of which are halt-risks:

**Must-fix (would halt cook or produce wrong code):**

1. **§5 step 11 test count: 21/21 → 22/22.** v6 added `test_async_event_consumed_during_drain.py` (§4.5b) but the implementation-order test count didn't update. With 17 prior + `test_stale_transaction` + 4 new tests, total is 22.
2. **`_get_protobuf_rpc` missing from §1.4.** `_cfc_send_one_frame` calls this helper but it was never catalogued. cc would have had to grep. **Verified empirically at line 115 of `flipper_mcp/modules/cfc/module.py`** — now added to §1.4.

**Should-fix (significantly reduces halt probability):**

3. **§4.0 mock-test scaffold added.** Model A correctly identified mock-test
   authoring as the highest-risk authoring task in the cook (~10% halt
   risk). The doc previously described tests at requirements level only.
   v8 adds a concrete scaffold showing AsyncMock-based `_wire_lock`,
   ProtobufRPC mocking, and `_receive_main_message` side_effect chaining.
4. **Timeout-path test added** to §4.4: validates that when
   `_receive_main_message` returns `None` until the deadline expires,
   `_cfc_send_one_frame` returns `None` (not raises, not hangs). This is
   the timeout-math branch — historically a v1 bug surface.
5. **`system_ping_response` field name verified** (already done in v7 §1.5
   empirical check — confirmed present in `flipper_pb2.Main` descriptor).

**Nice-to-fix (consistency):**

6. **§4.7 budget: 17 → 18 minutes** (accounts for §4.5b).
7. **§5 step 3 clarification:** `CfcProtocolDesyncError` is module-level,
   not inside any class. `_cfc_send_one_frame` is also module-level.
8. **GUI screen-frame flooding note:** added inline comment in §2.2 code
   block. Acceptable risk per Phase 2.5 scope; mitigate if it bites.
9. **`MOMENTUM_RPC_EXCHANGE_DATA_FIXED` "not consulted" callout** added
   to §2.4 comment so future maintainers don't expect behavior changes
   from flipping the flag in Phase 2.5.

**Cook-confidence after v8 fixes: ~95%** per Model A's projection plus
Model B's HasField empirical close. The residual 5% is genuine codebase
unknowns and hardware flakiness.

---

## v8 → v8.1 changelog (cook halt #1)

cc's first cook attempt halted at unit tests. The §4.0 scaffold's "Usage
examples per test" wrapped the rpc mock in `MagicMock(rpc=MagicMock(protobuf_rpc=rpc))`.
But `_get_protobuf_rpc(client)` at `cfc/module.py:115` has a first branch:
```python
if hasattr(client, "_wire_lock") and hasattr(client, "_send_rpc_message"):
    return client
```
A bare `MagicMock` auto-satisfies `hasattr` for any name (a known Python quirk),
so the wrapper got returned as the rpc — losing our AsyncMock setup. `await
rpc._send_main_raw(...)` then threw "object MagicMock can't be used in 'await'".

**v8.1 fix:** scaffold usage examples now pass `rpc` directly as the client
parameter. `_build_mock_rpc` returns a `MagicMock` with `_wire_lock` explicitly
configured as `AsyncMock` — passing it directly hits the first branch correctly
and returns our properly-configured mock.

**Lesson:** scaffold code is code. "Verified by reading source" is not "verified
by running it." Future scaffolds in design docs should be empirically tested
before shipping. (Adding this to Sherpa skill notes.)

After v8.1: 7/7 unit tests passed cleanly. Cook resumed to §5 step 10.

---

## v8.1 → v8.2 changelog (cook halt #2 — empirical surprise)

Hardware run revealed v6's Q6 enumeration was **incomplete**. NotebookLM Round
3 Q6 catalogued "asynchronous PB_Main event frame types emitted by firmware
paths via `rpc_send_and_release`." Four were named. But cc's `test_stale_transaction`
10× run failed identically 10/10 with:

```
CfcProtocolDesyncError: unknown content tag during CFC drain (wire lock held):
  command_id=3, content_field=empty.
```

**The new finding:** the Flipper RPC dispatcher itself emits an `empty`-content
Main with matching `command_id` as a synchronous acknowledgment for EVERY host
RPC request. This goes through `rpc_send_and_release_empty` (which Q6 noted
existed, but in the context of explicit-command_id replies, not as a
universal protocol-layer ack).

This frame was previously invisible: `_send_rpc_message`'s strict matcher
absorbed it silently because `command_id` matched the outbound request, then
read the next frame as the "real" response. Every existing flipper-mcp tool
has been relying on this silent absorption without anyone documenting it.

v6's pivot to `_send_main_raw` bypasses the strict matcher, exposing this
category for the first time. The `empty` Main now lands in CFC's drain loop
and trips the defensive desync raise.

**v8.2 fix:** add one branch to the §2.2 drain loop:
```python
if resp.HasField("empty"):
    # Synchronous RPC dispatcher ack with matching command_id. Every
    # host-initiated request gets one of these before the actual
    # response payload. Previously absorbed by _send_rpc_message's
    # strict matcher; now visible because _send_main_raw bypasses
    # matching. Consume and continue draining for the actual CFC frame.
    continue
```

Also extend §4.5b's parametrize to include `empty` in the async-event allowlist
test, so the regression case has unit coverage.

**Strategic note:** cc's diagnosis raised a fair question — "if `empty` was
missed empirically, other sync-reply or rare-frame variants may exist (72
oneof fields total in PB_Main.content)." We acknowledge this risk but don't
gate Phase 2.5 on enumerating all 72. Each unknown variant trips the same
loud desync raise we just hit. The pipeline works: cc halted correctly,
diagnosed precisely, and patching is a one-line surgical change. Future
unknown variants follow the same playbook.

A NotebookLM round 4 question is queued (not blocking): "enumerate ALL frame
types — sync AND async — the firmware emits in response to host RPC requests,
including dispatcher-layer acks." Findings fold into Phase 3 if any.

**Cook-confidence after v8.2: ~92%.** Slight reduction from v8's ~95% because
the "Q6 closed set" assumption was empirically wrong — there could be more.
Still well within shippable range; remaining risks are fail-loud and
diagnosable.

---

## v8.2 → v8.3 changelog (cook halt #3 — scope correction)

After v8.2 unlocked the wire layer, `test_stale_transaction` ran end-to-end
for the first time ever and revealed a pre-existing FAP-side bug at
`cfc/cfc.c:296`:

```
DIAG: txn1 frag2 → op=0xff body={'code': 99, 'message': 'ping echo too large'}
```

The PING handler in `cfc/cfc.c` allocates a stack buffer
`uint8_t response[CFC_MAX_FRAGMENT_PAYLOAD]` (884 bytes) and refuses any
echo payload that exceeds it. The `test_stale_transaction` echo is 950 bytes,
chosen specifically to force two-fragment INBOUND assembly. Once both
fragments assemble, the PING handler tries to build a single-fragment
OUTBOUND response containing the 950-byte echo + msgpack overhead, hits
the 884-byte ceiling, and returns `CFC_ERR_INTERNAL`.

**Why we didn't see this in Phase 2:** Phase 2's wire halts (the firmware
bugs surfaced in v6/v8.2) blocked the test before fragment-2 ever
assembled. The PING handler's outbound limit was an unexposed bug, dormant
behind a wire-layer issue. v8.2's fix made fragment-2 actually arrive,
which unmasked the PING handler problem.

**Scope determination — this IS Phase 2.5 work:** Spec §6.4 is literally
titled "Sending fragmented responses (Phase 2.5+)" and spec line 341 reads
*"Phase 2.5: Chunked outbound validation (>884-byte response roundtrip)."*
Multi-fragment outbound was always Phase 2.5's scope; v6's design doc
focused exclusively on the host-side wire layer and didn't carry the
FAP-side §6.4 work forward. v8.3 corrects this scope gap.

**v8.3 fix — see new §2.6 below for full design:**
1. Add `cfc_send_response_multi` to `cfc/cfc.c` — fragments any payload
   ≤ `CFC_MAX_TRANSACTION` (8192 bytes) into 884-byte chunks, sends each
   with correct CFC frame header (fragment_index, fragment_total,
   payload_length consistent across all fragments per spec §4).
2. Refactor PING handler to use heap-allocated output buffer sized by
   inbound payload, then send via `cfc_send_response_multi`.
3. Keep single-fragment `cfc_send_response_frame` for META/ERROR/STATUS
   handlers (their payloads fit comfortably in 884 bytes).
4. Add §6.4-mandated `furi_delay_ms(1)` inter-frame yield between
   fragments to give the firmware's RPC scheduler breathing room.

**Lesson:** "Phase 2.5 is host-only" framing in v6's §0 was wrong. The
DAY10 doc inherited a Phase-2 assumption (FAP complete) that was true
only because Phase 2 never exercised the multi-fragment outbound path.
v8.3 §0 corrected.

**Cook-confidence after v8.3: ~88%.** The FAP-side work is more
substantial than the host-side delta (~60 lines of new C code), introduces
its own failure surface (off-by-one in fragment indexing, malloc lifetime,
furi delay primitive availability). Mitigated by:
- Spec §6.4 already specifies the exact algorithm.
- Existing `cfc_send_response_frame` provides the header-write template.
- The fragmentation logic mirrors the INBOUND assembly logic already
  battle-tested in Phase 2.
- Two hardware tests (`test_stale_transaction` and `test_chunked_ping_roundtrip`)
  validate both small and large multi-fragment paths.

---

## v8.3 → v8.4 changelog (cook attempt #3 — 26/27 success, legacy test gap)

cc's third cook attempt completed end-to-end on hardware:

**Results:** 26 passed, 1 failed. Wall-clock 253s for full suite. The 26
included `test_chunked_ping_roundtrip` — the test that actually validates
Phase 2.5's whole multi-fragment outbound feature. It passed first try.

**The architecture is sound.** v8.3's `cfc_send_response_multi` works
exactly as designed: fragments outbound payloads up to `CFC_MAX_TRANSACTION`,
correctly indexes each fragment, applies inter-frame yield, host
reassembles in `flipper_cfc_call`. 950-byte echo round-trips cleanly.

**The one failure (`test_stale_transaction`) is a legacy-test problem,
not an architectural one.** Diagnostic confirmed:
- BUSY response (txn2): correctly single-fragment, op=0xff.
- PING completion (txn1): correctly multi-fragment, frag_idx=0/2, frag_total=2.
- Payload bytes decode correctly as `{status: "ok", echo: <950 bytes>}`.

The test calls `cfc_send_raw_frame` (a low-level helper that returns ONE
fragment's bytes) for the final `frag2_txn1` send. It then runs `decode_resp`
on what it gets back. Pre-v8.3 this worked because PING responses were
always single-fragment. Post-v8.3, `cfc_send_raw_frame` returns only
fragment 0/2 (884 bytes), `decode_resp` sees truncated msgpack, returns
None, test fails.

**Why the test can't just swap to `flipper_cfc_call`:** The test's whole
point is the interleaved fragment dance — send frag1_txn1, then
frag1_txn2 (the "interrupting" transaction that should get BUSY), then
frag2_txn1 (completing the original). That choreography requires
low-level frame-by-frame control. `flipper_cfc_call` would send all
fragments of a transaction atomically, defeating the test's purpose.

**v8.4 fix — see new §2.7 below:**
1. Add `cfc_recv_response_assembled` helper to `flipper_mcp/modules/cfc/module.py`.
   Takes a `client` and the already-received first fragment bytes; reads
   additional fragments off the wire as needed; returns the complete
   reassembled payload bytes (header from frag 0 + concatenated payloads).
2. Update `test_stale_transaction.py` to call the new helper on the
   `frag2_txn1` response (the only multi-fragment response in the test).
   Other low-level sends stay raw — the orchestration is still correct.

**Why a new helper not inline reassembly:** Phase 3 will add more
multi-fragment integration tests (`flipper_cfc_listen`, broadcast paths,
hardware-streaming responses). A reusable helper pays back the work.
The factoring also keeps `test_stale_transaction.py` readable: the test
expresses its intent (send-send-send-receive-multi) rather than
fragment-assembly mechanics.

**Cook-confidence after v8.4: ~96%.** Same as the empirical result of
v8.3's cook (26/27 = 96.3%); v8.4 is a surgical addition to convert the
27th test from failing to passing, with no host-protocol or FAP changes.

**Real lesson from this cook arc:** The doc's predicted-vs-actual
confidence converged sharply over the iterations. v8 predicted 95% and
hit ~73% (Arena Model B's number, before v8.1 fixes). v8.1-v8.2 predicted
92% and hit roughly that for unit tests but unmasked the FAP scope gap.
v8.3 predicted 88% and hit 96.3% — slightly under-confident, the design
was more correct than we credited. v8.4 prediction is ~96% (essentially
matching v8.3's empirical result plus one targeted test fix).

---

## 0 — TL;DR (v7, corrected per Arena.ai critique)

Phase 2's `test_stale_transaction` halt root-caused to: **the firmware function
`rpc_system_app_exchange_data` does not initialize `PB_Main.command_id`**,
leaving it as garbage from `malloc`. NotebookLM Round 2 Q5 surfaced that
`rpc_system_app_send_state_response` has the SAME bug, firing on every FAP
launch (`APP_STARTED`) and exit (`APP_CLOSED`).

NotebookLM Round 3 Q6 enumerated the complete set of four asynchronous frame
types the firmware emits: `app_data_exchange_request`, `app_state_response`,
`gui_screen_frame`, `desktop_status`. Round 3 Q8 confirmed qFlipper's
canonical handling pattern: **route inbound frames by `which_content` tag
first**, intercepting known async events into dedicated handlers, and
matching by `command_id` only on non-async frames.

Phase 2.5 ships **host-side only**, adopting qFlipper's pattern:

1. **`_send_main_raw` helper** added to `ProtobufRPC` (~10 lines in
   `flipper_mcp/core/protobuf_rpc.py`) — sends without entering the strict
   command_id matcher.
2. **`_cfc_send_one_frame` rewritten** in `flipper_mcp/modules/cfc/module.py`:
   - Sends via `_send_main_raw` (no strict matcher in the path).
   - Drain loop routes by `which_content` tag:
     * `app_data_exchange_request` → return its payload bytes (CFC's data).
     * `app_state_response`, `gui_screen_frame`, `desktop_status` → consume
       silently and continue draining (known async events per Q6 allowlist).
     * Anything else → raise `CfcProtocolDesyncError` (genuinely unexpected).
   - Timeouts (deadline expired without any frame) → return None normally.
3. **`CfcProtocolDesyncError` exception** defined in
   `flipper_mcp/modules/cfc/module.py`. On raise, the caller is expected to
   tear down the RPC session and force a clean reconnect.
4. **Spec §6.4 patch.** Firmware function `rpc_system_app_exchange_data`
   returns `void`, not `bool` (the spec sample code was wrong; correcting
   it).
5. **`MOMENTUM_RPC_EXCHANGE_DATA_FIXED = False`** constant in
   `flipper_mcp/modules/cfc/module.py` with documented sunset conditions,
   plus a one-shot `logging.warning` on module import while False.
6. **Momentum PR drafted but not in scope.** Draft at
   `D:\Dev\scratch\day10_momentum_pr_draft.md`. Patches both buggy firmware
   functions. cc does NOT touch the Momentum repo or open PRs in Phase 2.5.

After this: `test_stale_transaction` passes deterministically, the 17 prior
tests don't regress, cross-tool concurrency is preserved by the wire lock,
known async events are silently consumed (not surfaced as desync), and the
architecture matches qFlipper's canonical implementation. Phase 3's
`flipper_cfc_listen` can reuse the same route-by-tag dispatch.

---

## 1 — Empirical inputs (unchanged from v1)

### 1.1 — The firmware code

From `notebooklm/cfc/_upload/notebook1_firmware_side/01_rpc_service_all.txt:1117-1136`
(corpus file uploaded to NotebookLM, also present on disk):

```c
void rpc_system_app_exchange_data(RpcAppSystem* rpc_app, const uint8_t* data, size_t data_size) {
    furi_check(rpc_app);

    PB_Main* request = malloc(sizeof(PB_Main));

    request->which_content = PB_Main_app_data_exchange_request_tag;
    PB_App_DataExchangeRequest* content = &request->content.app_data_exchange_request;

    if(data && data_size) {
        content->data = malloc(PB_BYTES_ARRAY_T_ALLOCSIZE(data_size));
        content->data->size = data_size;
        memcpy(content->data->bytes, data, data_size);
    } else {
        content->data = NULL;
    }

    rpc_send_and_release(rpc_app->session, request);

    free(request);
}
```

`malloc(sizeof(PB_Main))` returns uninitialized memory. Only `which_content` and
`content.app_data_exchange_request` are set. **`command_id`, `command_status`,
`has_next`, and all other PB_Main fields are garbage.**

### 1.2 — Other firmware paths set command_id correctly

From NotebookLM 1 verdict citing same source: `rpc_system_app_set_last_command`,
`rpc_system_app_confirm` (asserts `last_command_id != 0`),
`rpc_system_app_send_error_response(uint32_t command_id, ...)`, and
`rpc_send_and_release_empty(session, uint32_t command_id, ...)` all explicitly handle
command_id. The bug is isolated to `rpc_system_app_exchange_data`.

### 1.3 — Host-client convention (from NotebookLM 2)

qFlipper C++: `command_id == 0` → broadcast handler; matching id → operation handler;
else → drop. Python bindings: synchronous strict matcher, deadlocks on mismatch.
**Universal:** strict-match for non-zero, broadcast for zero. No client treats
app_data_exchange as unconditionally unsolicited.

### 1.4 — Canonical import paths (verified from current source, 2026-05-27)

For cc to use directly without code-archeology. All paths verified by grep against
the codebase at commit 0899964:

**In `flipper_mcp/modules/cfc/module.py` (already present, do NOT duplicate):**
```python
from flipper_mcp.core.protobuf_gen import flipper_pb2, application_pb2
```

**In `flipper_mcp/core/protobuf_rpc.py` (already present, do NOT duplicate):**
- `_get_next_command_id`: method on `ProtobufRPC`, defined ~line 127
- `_encode_varint`: staticmethod on `ProtobufRPC`, defined ~line 133
- `_receive_main_message(timeout: float = 2.5)`: method on `ProtobufRPC`, defined
  ~line 169. **Confirmed accepts `timeout` kwarg.**
- `_ensure_rpc_session_started`: method on `ProtobufRPC`, defined ~line 189
- `transport.send(bytes)`: method on the transport object. **Method name is `send`,
  not `write`.** Confirmed ~line 267.

**Imports already present in `flipper_mcp/core/protobuf_rpc.py` at commit 0899964**
(verified by `Select-String -Pattern "^import sys|^from typing"`):
- `import sys` — present, no action needed
- `from typing import Optional, Dict, Any, List, TYPE_CHECKING` — `Optional` and
  `Any` both already in scope, no action needed

`_send_main_raw` uses `sys.stderr`, type hints `Any` / `Optional`, and standard
Python constructs (`await`, `try/except`). All names already resolved — cc adds
the method without modifying the import block.

**Imports `_cfc_send_one_frame` will need (verified present in `cfc/module.py`):**
- `time` — already imported
- `flipper_pb2`, `application_pb2` — already imported
- `Any`, `Optional` from `typing` — already imported
- `CfcProtocolDesyncError` — new exception, defined in the same file (no import
  needed; in-file class).
- `logging` — NEW: §2.4 introduces a module-level logger. cc must add
  `import logging` to the imports block of `cfc/module.py` if not already
  present (verified absent at commit 0899964 — cc must add).

**Helpers `_cfc_send_one_frame` calls (verified present in `cfc/module.py`):**
- `_get_protobuf_rpc(client) -> Any` at **line 115**. Module-level function.
  Resolves a `ProtobufRPC` instance from a `FlipperClient` or a direct
  `ProtobufRPC`. cc must NOT redefine this — use as-is. (v8 addition per
  Arena Model A.)

cc does NOT need to grep for any of these. They are stated here so cc proceeds
directly to implementation.

### 1.5 — Protobuf field-name verification (v7 addition per Arena critique)

The v6 → v7 changelog Failure Mode Alpha required empirical verification that
the protobuf-generated Python field names for the Q6 async event allowlist
actually exist on `flipper_pb2.Main` and that `HasField` accepts them without
raising `ValueError`.

**Verified empirically on 2026-05-27 against the current `flipper_pb2`:**

```python
from flipper_mcp.core.protobuf_gen import flipper_pb2
m = flipper_pb2.Main()
for f in ['app_data_exchange_request', 'app_state_response',
          'gui_screen_frame', 'desktop_status', 'system_ping_response']:
    m.HasField(f)
```

Output (all return False on empty Main, no exceptions):
```
HasField('app_data_exchange_request'): False
HasField('app_state_response'): False
HasField('gui_screen_frame'): False
HasField('desktop_status'): False
HasField('system_ping_response'): False
```

All five field names exist in the descriptor. `HasField` works exactly as
§2.2's drain loop expects. **cc can use the names verbatim from §2.2.**

---

## 2 — The architectural decision (v2)

### 2.1 — Why we accept any command_id (not just zero) as a transitional workaround

The wire protocol convention says: `command_id == 0` is a broadcast.
`command_id == <outstanding>` is a reply. Anything else is an orphan.

The firmware bug means every outbound app_data_exchange frame has `command_id ==
<garbage>` — typically neither 0 nor matching. Strict matching drops them all.

**Two ways to make the wire convention apply:**

- **(a) Upstream fix:** `memset(request, 0, sizeof(PB_Main))` after the malloc in
  `rpc_system_app_exchange_data`. Then `command_id = 0`. Then strict matchers treat
  these as broadcasts. **Architecturally correct. Not in CPK scope to land.**
- **(b) Host-side bridge:** until (a) merges and Victor's Momentum build includes
  it, the host must accept arbitrary command_ids on inbound `app_data_exchange_request`
  frames. This is a deliberate workaround, scoped narrowly, gated behind a constant
  that flips back to strict matching once the bug is fixed.

**Why (b) accepts *any* command_id, not just zero:** because the firmware bug doesn't
generate zero — it generates garbage. A workaround that only accepts zero would still
drop every real frame the buggy firmware emits, defeating the purpose. The workaround
must accept what the bug produces, then transition to strict-match when the bug is
gone.

**The scope is narrow in two ways:**
- Only applies to frames of type `app_data_exchange_request` (not any other Main
  frame type).
- Only inside `_cfc_send_one_frame`'s receive path (not in the global
  `_send_rpc_message`, which keeps strict matching for all synchronous RPCs).

### 2.2 — Host-side implementation: two changes

#### Change A — New primitive `_send_main_raw` on `ProtobufRPC`

**File:** `flipper_mcp/core/protobuf_rpc.py`
**Location:** as a new method on the `ProtobufRPC` class, placed immediately
above the existing `_send_rpc_message` method (currently at line 365).

**Purpose:** Provide a way to send a Main message on the wire **without** entering
the strict command_id matching loop. The caller is responsible for receiving the
response (or not).

```python
async def _send_main_raw(self, main_message: Any) -> bool:
    """
    Serialize and send one Main protobuf message on the wire. Does NOT wait
    for or match a response — the caller handles inbound frames separately.

    Use this when the caller needs custom inbound-frame matching semantics
    (e.g., CFC's app_data_exchange workaround). For ordinary synchronous
    RPCs, use _send_rpc_message instead.

    Returns True on successful wire send, False on transport failure.

    Caller must hold rpc._wire_lock for the full send + receive sequence.
    """
    try:
        await self._ensure_rpc_session_started()
        message_data = main_message.SerializeToString()
        message = self._encode_varint(len(message_data)) + message_data
        await self.transport.send(message)
        return True
    except Exception as _e:
        if self.debug:
            print(f"[silent-except @ protobuf_rpc.py:_send_main_raw] {type(_e).__name__}: {_e}", file=sys.stderr)
        return False
```

**Wire framing notes:** This produces the exact same `[varint length][payload]`
nanopb-delimited framing as `_send_rpc_message`'s send half (which it's extracted
from). Verified by comparison: lines 392-399 of current `protobuf_rpc.py`.

**No changes to `_send_rpc_message`.** It continues to use strict command_id
matching for every existing flipper-mcp tool.

#### Change B — Rewrite `_cfc_send_one_frame`

**File:** `flipper_mcp/modules/cfc/module.py`
**Replaces:** existing `_cfc_send_one_frame` (lines roughly 132-167 in current
source — read the file at cook time to confirm).

```python
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

    Path A frame handling (Gemini v3 design): non-CFC frames appearing during
    drain are NOT re-buffered (no transport API for that). They are treated
    as fatal protocol desync because the wire lock should make them
    unreachable. Returning None on this branch would silently mask the
    desync as a phantom CfcTimeoutError upstream — see Sherpa v2 review
    and DAY10_PHASE2_5_DESIGN v2→v3 changelog.
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

            # v6 + v8.2: route-by-tag pattern (matches qFlipper's canonical
            # implementation per NotebookLM Round 3 Q8). Check which_content
            # tag FIRST. CFC's data frame returns. Known transport-layer
            # and asynchronous event frames are consumed and the drain
            # continues. Truly unknown content raises desync.
            #
            # Allowlist (5 known non-CFC frames):
            #   - `empty` (v8.2): sync RPC dispatcher ack with matching cmd_id
            #   - `app_state_response` (Q6): APP_STARTED/APP_CLOSED events
            #   - `gui_screen_frame` (Q6): screen streaming events
            #   - `desktop_status` (Q6): lock/unlock events
            #   - (`app_data_exchange_request` returns rather than continues —
            #      it's CFC's own data carrier)
            if resp.HasField("app_data_exchange_request"):
                # v5 fix preserved: decouple type-check from payload-check.
                # Empty bytes (b"") is falsy in Python; structure alone
                # determines CFC-ness, an empty payload is still a valid
                # CFC frame.
                payload_bytes = resp.app_data_exchange_request.data
                return bytes(payload_bytes) if payload_bytes else b""

            if resp.HasField("empty"):
                # v8.2: Synchronous RPC dispatcher ack with matching command_id.
                # Every host-initiated RPC request gets one of these `empty`
                # Mains before the actual response payload arrives. Previously
                # invisible because _send_rpc_message's strict matcher absorbed
                # it silently (matched command_id, no useful payload). Now
                # visible because _send_main_raw bypasses matching. Consume
                # and continue draining for the real CFC data frame.
                # See v8.1 → v8.2 changelog for the empirical discovery.
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
            # is emitting a frame type that wasn't in the Q6 enumeration —
            # either way, surface as fatal protocol desync.
            field = resp.WhichOneof('content')
            raise CfcProtocolDesyncError(
                f"unknown content tag during CFC drain (wire lock held): "
                f"command_id={resp.command_id}, content_field={field}. "
                f"RPC session must be torn down. If this is a legitimate "
                f"new firmware event type, add it to the Q6 allowlist."
            )
```

**Key invariants preserved:**

1. `rpc._wire_lock` is held for the entire send-and-receive duration. The lock
   prevents other tools from issuing RPCs concurrently, so by construction no
   other tool's response should appear during CFC's drain window.
2. `_receive_main_message` is the same primitive `_send_rpc_message` uses — same
   transport.receive_exact path. No protocol-level changes.
3. **The non-CFC-frame branch is fatal.** If reached, the wire-lock invariant
   was violated — that's a bug worth surfacing immediately, not absorbing.
   `CfcProtocolDesyncError` propagates up through `flipper_cfc_call` and
   ultimately to the MCP tool result, where Claude or the calling test will
   see it loudly.

### 2.3 — Spec §6.4 patch

Update the spec sample code reflecting `void` return type:

> Per `rpc_app.h:220`, `rpc_system_app_exchange_data()` returns `void`. The FAP
> cannot synchronously detect transport-level failures. If a send fails (e.g.,
> host disconnected mid-transaction), the next host-side request times out at the
> Python layer; there is no callback or return value for the FAP to inspect.
> Backpressure / failure-detection require Phase 3's listener architecture.

### 2.4 — `MOMENTUM_RPC_EXCHANGE_DATA_FIXED` constant + import-time warning

In `flipper_mcp/modules/cfc/module.py`, add near the protocol constants:

```python
import logging
_log = logging.getLogger(__name__)

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
```

The constant is **not consulted** by `_cfc_send_one_frame` in Phase 2.5 — it's
defined now so the symbol exists for Phase 3+ to gate strict-matching behavior
behind. Phase 2.5 unconditionally uses the workaround path. The import-time
warning is the operator-facing reminder until the workaround is removed.

### 2.5 — What is NOT changed in Phase 2.5

- `_send_rpc_message` — unchanged. Every other flipper-mcp tool uses it as-is.
- ~~`cfc/cfc.c` — unchanged.~~ **v8.3 supersedes this: cfc/cfc.c DOES change.**
  See §2.6 below for FAP-side multi-fragment outbound work (spec §6.4 Phase 2.5
  scope that v6 didn't carry forward).
- Momentum firmware — not touched in this scope. Upstream PR drafted as separate
  side-task; cc does NOT open external-repo PRs.
- The `wait_for_response=False` parameter (added during Phase 2 cook) — preserved
  as-is.

---

### 2.6 — FAP-side implementation: multi-fragment outbound (v8.3 — spec §6.4 scope)

**The empirical problem (cook attempt #2 finding):** The PING handler at
`cfc/cfc.c:283` uses a stack buffer `uint8_t response[CFC_MAX_FRAGMENT_PAYLOAD]`
(884 bytes) for outbound responses. `test_stale_transaction`'s 950-byte echo
plus msgpack map overhead exceeds 884, so the handler returns
`CFC_ERR_INTERNAL: "ping echo too large"` at line 296.

**Why this is Phase 2.5 scope:** Spec §6.4 ("Sending fragmented responses
(Phase 2.5+)") and spec line 341 ("Phase 2.5: Chunked outbound validation
(>884-byte response roundtrip)") explicitly assigned multi-fragment outbound
to Phase 2.5. v6's design doc inherited a wrong assumption that Phase 2.5
was host-only.

**Change C: new `cfc_send_response_multi` function in `cfc/cfc.c`.**

Place between existing `cfc_send_response_frame` (line 177) and
`cfc_send_error` (line 197), at module scope. Spec §6.4's exact algorithm:

```c
/**
 * Send a response that may exceed CFC_MAX_FRAGMENT_PAYLOAD (884 bytes)
 * by fragmenting into multiple frames per spec §6.4. Each fragment carries
 * the same op_code, transaction_id, and total payload_length; only
 * frag_idx changes across frames.
 *
 * Caller owns the payload buffer; this function does not free it.
 * Inter-frame furi_delay_ms(1) yield per spec §6.4 — gives the firmware
 * RPC scheduler breathing room between fragments.
 *
 * No return value: rpc_system_app_exchange_data is void per
 * docs/decisions/DAY8_FAP_PHASE1_SPEC.md §6.4. Transport-level failures
 * are detected host-side via timeout.
 */
static void cfc_send_response_multi(
    CfcContext* cfc,
    uint8_t op_code,
    uint32_t transaction_id,
    const uint8_t* payload,
    size_t payload_len) {
    if(payload_len > CFC_MAX_TRANSACTION) {
        FURI_LOG_E(TAG, "send_multi: payload %zu > CFC_MAX_TRANSACTION; dropping", payload_len);
        return;
    }

    // Single-fragment fast path: avoid the loop + delay when not needed.
    if(payload_len <= CFC_MAX_FRAGMENT_PAYLOAD) {
        cfc_send_response_frame(cfc, op_code, transaction_id, payload, payload_len);
        return;
    }

    uint32_t total_frags = (payload_len + CFC_MAX_FRAGMENT_PAYLOAD - 1) / CFC_MAX_FRAGMENT_PAYLOAD;
    uint8_t buf[CFC_HEADER_SIZE + CFC_MAX_FRAGMENT_PAYLOAD];

    for(uint32_t frag_idx = 0; frag_idx < total_frags; frag_idx++) {
        size_t offset = frag_idx * CFC_MAX_FRAGMENT_PAYLOAD;
        size_t this_frag_len = (payload_len - offset > CFC_MAX_FRAGMENT_PAYLOAD)
                                   ? CFC_MAX_FRAGMENT_PAYLOAD
                                   : (payload_len - offset);

        cfc_write_header(buf, op_code, transaction_id, frag_idx, total_frags, (uint32_t)payload_len);
        memcpy(buf + CFC_HEADER_SIZE, payload + offset, this_frag_len);
        rpc_system_app_exchange_data(cfc->rpc_app, buf, CFC_HEADER_SIZE + this_frag_len);

        // Inter-frame yield per spec §6.4. Gives the RPC scheduler time
        // to drain its outbound queue before we push the next fragment.
        if(frag_idx + 1 < total_frags) {
            furi_delay_ms(1);
        }
    }
}
```

**Change D: PING handler refactor (`cfc_handle_ping`, around line 275-304).**

Replace the stack buffer with heap-allocated buffer sized for worst-case
output (full inbound echo + msgpack map overhead). Send via
`cfc_send_response_multi`.

Replace the block from `uint8_t response[CFC_MAX_FRAGMENT_PAYLOAD];` through
the final `cfc_send_response_frame(...)` call with:

```c
    /* Build response: {status: "ok", echo: <verbatim>} (or {status: "ok"} if no echo key).
     * v8.3: allocate output buffer on heap, sized for inbound echo + msgpack map overhead.
     * Map overhead: fixmap(1B) + "status"(7B) + "ok"(3B) + "echo"(5B) + str-prefix(≤5B) = ~21B.
     * Pad to 64B for safety. */
    size_t echo_len = found_echo ? (echo_end - echo_start) : 0;
    size_t out_capacity = echo_len + 64;
    if(out_capacity > CFC_MAX_TRANSACTION) {
        cfc_send_error(cfc, txn, CFC_ERR_BAD_PAYLOAD, "ping echo exceeds CFC_MAX_TRANSACTION");
        return;
    }

    uint8_t* response = malloc(out_capacity);
    if(!response) {
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping malloc failed");
        return;
    }

    CfcWriteBuf wb = {.data = response, .pos = 0, .cap = out_capacity};
    cmp_ctx_t out;
    cmp_init(&out, &wb, NULL, NULL, cfc_cmp_writer);

    uint32_t out_size = found_echo ? 2 : 1;
    if(!cmp_write_map(&out, out_size)) {
        free(response);
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc map");
        return;
    }
    if(!cmp_write_str(&out, "status", 6) || !cmp_write_str(&out, "ok", 2)) {
        free(response);
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc status");
        return;
    }
    if(found_echo) {
        if(!cmp_write_str(&out, "echo", 4)) {
            free(response);
            cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc echo key");
            return;
        }
        // Direct memcpy of the verbatim msgpack-encoded echo value.
        // Buffer already sized to fit; no overflow check needed.
        size_t verbatim_len = echo_end - echo_start;
        memcpy(wb.data + wb.pos, msgpack + echo_start, verbatim_len);
        wb.pos += verbatim_len;
    }

    cfc_send_response_multi(cfc, CFC_OP_PING, txn, response, wb.pos);
    free(response);
}
```

**What stays single-fragment (`cfc_send_response_frame`):**

- `cfc_handle_meta_capabilities` — fixed `response[64]` buffer
- `cfc_handle_meta_version` — fixed small response
- `cfc_send_error` — fixed `payload[64]`
- `cfc_send_status` (if present) — fixed small response

Only PING (and future arbitrary-size payload handlers in Phase 3+) needs
multi-fragment outbound. Don't migrate META/ERROR handlers — their stack
buffers are correct and the function pointer overhead isn't worth it.

**Required includes for the new code:**
- `<furi.h>` provides `furi_delay_ms` and `FURI_LOG_E` — already included
  via existing `cfc/cfc.c` headers.
- `malloc`/`free` from `<stdlib.h>` — verify it's already in the includes.
  cc must add `#include <stdlib.h>` if absent. (`cfc/cfc.c` already uses
  malloc for the assemble buffer at line ~486, so it should be present.)

**Why heap-allocate not stack-allocate:**
- `CFC_MAX_TRANSACTION = 8192` bytes. Flipper FAP stacks are typically 2-8KB
  total. An 8KB stack buffer in one handler would likely overflow.
- Existing `cfc.c` pattern uses `malloc` for the inbound assemble buffer
  (line ~486); same pattern for outbound is consistent.
- The single-fragment fast path in `cfc_send_response_multi` means small
  responses (≤884 bytes) avoid the heap allocation entirely.

**Build/deploy:** §5 step 8 now CHANGES — cc must rebuild the FAP via
`ufbt` and copy `dist/f7-C/cfc_<short_hash>.fap` to
`/ext/apps/Tools/cfc.fap` on the device. The "skip rebuild" v6 guidance
is invalidated.

---

### 2.7 — Host-side helper: `cfc_recv_response_assembled` (v8.4 — multi-fragment receive)

**The empirical problem (cook attempt #3 finding):** `test_stale_transaction`
uses the low-level `cfc_send_raw_frame` for the final fragment-2-of-txn1
send, expecting to get the complete response back as raw bytes. Pre-v8.3,
PING responses were always single-fragment, so this worked. Post-v8.3,
PING responses CAN be multi-fragment, and `cfc_send_raw_frame` returns
only the first fragment's bytes. The test's `decode_resp` then sees a
truncated msgpack stream and returns None.

**Why a new helper rather than smarter low-level helper:**
- `cfc_send_raw_frame` is a wire-layer primitive. Its contract is "put
  one CFC frame on the wire, return what came back." Adding reassembly
  logic violates the layer-of-abstraction.
- Phase 3 integration tests (`flipper_cfc_listen` tests, broadcast tests,
  hardware-streaming tests) will need the same reassembly capability.
- The factoring keeps test code readable: tests express intent ("send
  fragments, receive complete response") not mechanics ("loop reading
  frames until total reached").

**Change E: new `cfc_recv_response_assembled` function in `flipper_mcp/modules/cfc/module.py`.**

Place after `cfc_send_raw_frame` (around line 297) at module scope. Uses
the same wire-layer primitives `flipper_cfc_call` uses internally for its
multi-fragment receive (around lines 417-440) — but factored as a reusable
helper that takes the first fragment as input rather than sending its own.

```python
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
```

**Imports required** (verify present in `flipper_mcp/modules/cfc/module.py`):
- `time` — already imported (used by `flipper_cfc_call`)
- `Any` from `typing` — already imported
- `CfcTimeoutError`, `CfcProtocolError` — already defined in this file

cc adds nothing to imports; all dependencies are already in scope.

**Change F: update `tests/cfc_phase2/test_stale_transaction.py` to use the helper.**

Add `cfc_recv_response_assembled` to the import block alongside
`cfc_send_raw_frame` and `flipper_cfc_call`:

```python
from flipper_mcp.modules.cfc.module import (
    cfc_send_raw_frame,
    cfc_recv_response_assembled,  # v8.4 addition
    flipper_cfc_call,
    # ... existing imports
)
```

The test currently has at line ~68:
```python
raw_done = asyncio.run(cfc_send_raw_frame(cfc_client, frag2_txn1))
op_d, _txn_d, body_d = decode_resp(raw_done)
```

Change to:
```python
# v8.4: PING completions can now be multi-fragment (Phase 2.5 §6.4).
# cfc_send_raw_frame returns only fragment 0; assemble the rest via the
# new helper before decoding.
raw_done_frag0 = asyncio.run(cfc_send_raw_frame(cfc_client, frag2_txn1))
assembled_payload = asyncio.run(cfc_recv_response_assembled(cfc_client, raw_done_frag0))
# decode_resp expects bytes-with-header in legacy mode; for assembled mode
# we have only the payload section. Build a single-fragment-equivalent
# decoded result by parsing the first fragment's header and using the
# assembled payload as the body.
op_d, _txn_d, body_d = decode_resp(raw_done_frag0[:CFC_HEADER_SIZE] + assembled_payload)
```

**Open detail for cc to resolve at cook time:** the exact shape `decode_resp`
expects depends on the conftest. If `decode_resp` builds the response from
header+payload (likely from the snippet shown in earlier diagnostics), the
construction above works. If `decode_resp` already expects fully-assembled
payload bytes, simpler form: `op_d, _txn_d, body_d = decode_resp(assembled_payload, op_hint=OP_PING, txn_hint=t1)`.
cc reads `tests/cfc_phase2/conftest.py` to determine `decode_resp`'s
signature before deciding which form to use.

**Why this is the only test that needs the change:** Of the 27 tests in
the suite, only `test_stale_transaction` uses `cfc_send_raw_frame` to
receive a multi-fragment PING response. All other tests either:
- Use `flipper_cfc_call` (which has its own reassembly) — most integration tests.
- Send/expect responses that fit in single fragments — META, ERROR, small PING tests.
- Don't exercise outbound multi-fragment at all — unit tests with mocks.

`test_chunked_ping_roundtrip` (§4.3, new in Phase 2.5) goes through
`flipper_cfc_call` and already passes 1/1 per cook attempt #3.

---

## 3 — Sunset conditions for the workaround

The host-side command_id-accepting path stays in `_cfc_send_one_frame` until ALL
of these are true:

1. Momentum upstream merges a fix for `rpc_system_app_exchange_data` (probably the
   `memset` patch we draft separately).
2. AmorPoee is running a Momentum build that includes the merge.
3. CPK's minimum-supported-Momentum-version is documented and gates the strict
   path behind that build hash.
4. `MOMENTUM_RPC_EXCHANGE_DATA_FIXED` is set to `True` and `_cfc_send_one_frame`
   updated to consult it.

Until ALL FOUR: workaround stays. When met: strict-match returns and broadcast
(command_id == 0) becomes the canonical async-event path for Phase 3.

---

## 4 — Test plan (v2 — expanded per Sherpa v1 findings)

### 4.0 — Mock test scaffold (v8 addition per Arena Model A)

All four new unit tests (§4.4, §4.4b, §4.5, §4.5b) share the same mocking
shape. cc should use this scaffold verbatim, varying only the
`_receive_main_message` `side_effect` sequence per test. **This eliminates
~10% halt risk from mock-authoring complexity.**

```python
# conftest-style fixture, or inline at top of each test file
from unittest.mock import AsyncMock, MagicMock
import pytest

from flipper_mcp.core.protobuf_gen import flipper_pb2
from flipper_mcp.modules.cfc.module import (
    CFC_HEADER_SIZE,
    OP_PING,
    _cfc_send_one_frame,
    pack_cfc_frame,
)


def _build_mock_rpc(receive_side_effect):
    """Build a mock ProtobufRPC suitable for _cfc_send_one_frame tests.

    `receive_side_effect` is a list of Main messages (or None for timeout)
    that _receive_main_message will return on successive calls. Use this
    to script the wire's response sequence.
    """
    rpc = MagicMock()

    # async with rpc._wire_lock: ...
    # AsyncMock makes _wire_lock awaitable AND a context manager.
    rpc._wire_lock = AsyncMock()
    rpc._wire_lock.__aenter__ = AsyncMock(return_value=rpc._wire_lock)
    rpc._wire_lock.__aexit__ = AsyncMock(return_value=None)

    # _get_next_command_id returns a real int (the value doesn't matter for
    # the workaround path since command_id matching is bypassed).
    rpc._get_next_command_id = MagicMock(return_value=42)

    # _send_main_raw returns True (send succeeded) by default. Override
    # in tests that exercise the send-failure branch.
    rpc._send_main_raw = AsyncMock(return_value=True)

    # _receive_main_message returns the scripted sequence.
    rpc._receive_main_message = AsyncMock(side_effect=receive_side_effect)

    return rpc


def _make_app_data_exchange_main(payload: bytes, command_id: int = 0) -> "flipper_pb2.Main":
    """Build a Main with app_data_exchange_request set. Used to mock CFC's own data frames."""
    m = flipper_pb2.Main()
    m.command_id = command_id
    m.app_data_exchange_request.data = payload
    return m


def _make_async_event_main(field_name: str) -> "flipper_pb2.Main":
    """Build a Main with one of the Q6 allowlist async event fields set.

    field_name must be one of: 'app_state_response', 'gui_screen_frame',
    'desktop_status'. The exact sub-fields don't matter for the test —
    we only check that HasField returns True for the top-level oneof tag.
    """
    m = flipper_pb2.Main()
    # Simply touch a sub-field to make HasField(field_name) return True.
    # protobuf oneofs are "set" when any sub-field is assigned.
    sub = getattr(m, field_name)
    # Some messages have a 'data' or similar field we can poke; just make
    # the oneof visible. SetInParent() forces oneof selection without
    # touching any data field.
    sub.SetInParent()
    return m


def _make_system_ping_response_main() -> "flipper_pb2.Main":
    """Build a Main with system_ping_response set — used as a 'not in allowlist' test frame."""
    m = flipper_pb2.Main()
    m.system_ping_response.SetInParent()
    return m
```

**Usage examples per test** (v8.1 fix per cook halt: pass `rpc` directly as
the client, NOT a wrapped `MagicMock`. Reason: `_get_protobuf_rpc`'s first
branch checks `hasattr(client, "_wire_lock")` — a bare `MagicMock` wrapper
auto-satisfies `hasattr` for any name, so the wrapper would be returned
instead of the inner rpc mock. Passing the rpc mock directly hits the first
branch correctly and returns the properly-configured AsyncMock setup.):

- **§4.4** (broadcast path returns data):
  ```python
  rpc = _build_mock_rpc([_make_app_data_exchange_main(b"hello", command_id=0)])
  result = await _cfc_send_one_frame(rpc, b"frame_bytes")
  assert result == b"hello"
  ```

- **§4.4b** (timeout returns None — v8 test):
  ```python
  rpc = _build_mock_rpc([None, None, None, None, None])  # repeated timeouts
  result = await _cfc_send_one_frame(rpc, b"frame_bytes", followup_timeout=0.5)
  assert result is None
  ```

- **§4.5** (desync raises on unknown tag):
  ```python
  rpc = _build_mock_rpc([_make_system_ping_response_main()])
  with pytest.raises(CfcProtocolDesyncError, match="unknown content tag"):
      await _cfc_send_one_frame(rpc, b"frame_bytes")
  ```

- **§4.5b** (async event consumed, CFC data returned):
  ```python
  rpc = _build_mock_rpc([
      _make_async_event_main("app_state_response"),
      _make_app_data_exchange_main(b"data", command_id=0),
  ])
  result = await _cfc_send_one_frame(rpc, b"frame_bytes")
  assert result == b"data"
  ```

**Why pass the rpc mock directly:** `_get_protobuf_rpc` at `cfc/module.py:115`
has three branches; the FIRST is:
```python
if hasattr(client, "_wire_lock") and hasattr(client, "_send_rpc_message"):
    return client
```
Our `_build_mock_rpc` returns a `MagicMock` with `_wire_lock` explicitly
configured as an `AsyncMock` context manager. Passing it directly as
`client` hits this branch and returns it unchanged — preserving our
AsyncMock setup. The previous v8 scaffold's wrapper approach failed
because bare `MagicMock` satisfies `hasattr` for *any* attribute (a
Python MagicMock quirk), tricking the first branch into returning the
wrong object.

### 4.1 — Mandatory: `test_stale_transaction` passes 10/10

Run test 10 times in sequence on real AmorPoee. All must pass.
**Halt criterion:** any failure → halt cook, do not proceed to other tests.
**Estimated wall clock:** ~5 minutes.

### 4.2 — Mandatory: 17 prior tests all still pass

Run full Phase 2 suite. Every test that passed in Phase 2 (commit 35a9332) must
still pass.
**Halt criterion:** any regression → revert changes per §10 rollback, halt cook.
**Estimated wall clock:** ~5 minutes (full hardware run).

### 4.3 — New test: chunked PING roundtrip (Phase 2.5 Item B)

Create `tests/cfc_phase2/test_chunked_ping_roundtrip.py`:
- Build a ~2KB msgpack payload (nested dict, sentinel "echo" key).
- Send via `flipper_cfc_call(OP_PING, payload)`.
- Assert response decoded as dict with `echo` matching original (byte-identical).

The 884-byte limit comes from spec §4 (CFC_MAX_FRAGMENT_PAYLOAD, exported from
`flipper_mcp.modules.cfc.module`). 2KB ensures multi-fragment in both directions.
**Halt criterion:** test fails → halt, investigate before continuing.
**Estimated wall clock:** ~1 minute.

### 4.4 — New unit test: broadcast path accepts command_id == 0 (incl. empty payload)

Create `tests/cfc_phase2/test_broadcast_path_mock.py` — a pure unit test (no
hardware needed):
- Mock a `ProtobufRPC` whose `_receive_main_message` returns a `Main` with
  `command_id = 0` and `app_data_exchange_request.data = <test frame>`.
- Call `_cfc_send_one_frame(mock, b"...")`.
- Assert the test frame's data is returned (not None).

**v5 addition: include a second test case** for `app_data_exchange_request.data
= b""` (empty bytes). Assert the function returns `b""` (empty bytes), NOT
`None`, NOT raises `CfcProtocolDesyncError`. This validates the v5 fix for
the empty-payload logic bomb that Gemini v2 caught.

This proves the broadcast path works in isolation, including the legal-but-empty
case. When Phase 3 introduces true broadcasts, this test confirms the
architecture supports them.
**Halt criterion:** fails → halt, design wrong.
**Estimated wall clock:** ~30s.

### 4.4b — New unit test: timeout returns None (v8 addition per Arena Model A)

Create `tests/cfc_phase2/test_cfc_timeout_returns_none.py` — pure unit test.
Validates the timeout-math branch (`remaining <= 0: return None`) which has
historically been a v1 bug surface.

- Mock a `ProtobufRPC` whose `_receive_main_message` returns `None` on every
  call (simulating no frame arriving on the wire within deadline).
- Call `_cfc_send_one_frame(mock, b"...", followup_timeout=0.5)`.
- Assert the function returns `None` (not raises, not hangs).
- Optionally: assert wall-clock duration is roughly `followup_timeout` ±
  one `PER_READ_TIMEOUT` window.

This catches regressions in the timeout math if anyone re-touches the
drain loop. Per Arena Model A — closes the most likely timeout-math bug
surface.
**Halt criterion:** fails → halt, timeout math is broken.
**Estimated wall clock:** ~30s (mocked, no hardware).

### 4.5 — New unit test: unknown content tag raises CfcProtocolDesyncError

Create `tests/cfc_phase2/test_non_cfc_frame_raises_desync.py` — a pure unit
test:
- Mock a `ProtobufRPC` whose `_receive_main_message` returns a `Main` with
  `system_ping_response` set. **Important:** must be a tag NOT in the v6
  Q6 allowlist (i.e., NOT `app_data_exchange_request`, `app_state_response`,
  `gui_screen_frame`, or `desktop_status`). `system_ping_response` is a
  safe choice because it's a synchronous-reply tag that should never
  appear during CFC's drain window.
- Call `_cfc_send_one_frame(mock, b"...")` inside a `pytest.raises` block.
- Assert `CfcProtocolDesyncError` is raised, with message mentioning
  "unknown content tag" and the offending field name.

This proves v6's defensive branch fails loudly on genuinely unexpected
frame types, while the allowlisted async events get consumed silently.
Per NotebookLM Round 3 Q7-Q8 — matches qFlipper's canonical behavior.
**Halt criterion:** fails → halt, defensive path is broken.
**Estimated wall clock:** ~30s.

### 4.5b — New unit test: allowlisted async events are consumed during drain

Create `tests/cfc_phase2/test_async_event_consumed_during_drain.py` — pure
unit test. Critical for v6 correctness; the v5 design would have raised
desync on these frames.

For each of the four known allowlist tags that should be consumed and
ignored (`empty`, `app_state_response`, `gui_screen_frame`, `desktop_status`):
- Mock a `ProtobufRPC` whose `_receive_main_message` returns first that
  async event frame, then an `app_data_exchange_request` with test data,
  then `None` (timeout).
- Call `_cfc_send_one_frame(mock, b"...")`.
- Assert the test returns the `app_data_exchange_request` data — NOT
  None, NOT raising, NOT returning the async event's contents.

**v8.2 addition:** parametrize MUST include `empty`. The first cook attempt
revealed `empty` is the sync RPC dispatcher ack that fires on every host
request — without coverage here, regressions in the `empty` branch could
land silently if the allowlist ordering changes.

This validates the allowlist works end-to-end and catches regressions
if anyone later removes an entry from the allowlist.
**Halt criterion:** fails → halt, the architectural shift to route-by-tag
is broken.
**Estimated wall clock:** ~1 minute (four allowlist tags × ~15s each).

### 4.6 — Sanity: spec §6.4 patch lands

Confirm the spec file `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` §6.4 sample
code now uses `void` rather than `bool`.
**No halt criterion** — this is a documentation change, can be fixed in any
subsequent commit.

### 4.7 — Total test budget

- Unit tests (4.4, 4.4b, 4.5, 4.5b): ~3 minutes together (4 tests × ~30s-1min).
- Hardware tests (4.1, 4.2, 4.3): ~11 minutes total at one full pass each.
- 10× iteration of 4.1: ~5 minutes (test takes ~30s on the wire).
- Grand total budget: **~18 minutes wall clock** (v8: includes §4.4b + §4.5b
  unit tests). Within Phase 2.5's 1.5-2h cap.

**Per-failure overhead:** add ~5-10 minutes per investigation/rollback cycle.
If two tests fail and require investigation, budget realistically expands to
~30-40 minutes wall clock.

---

## 5 — Implementation order (v2 — explicit)

1. **Verify pre-flight:**
   - Confirm `flipper_mcp/core/protobuf_rpc.py` exists, contains `ProtobufRPC`
     class, has `_send_rpc_message` at ~line 365 and `_receive_main_message` at
     ~line 169.
   - Confirm `flipper_mcp/modules/cfc/module.py` exists, has
     `_cfc_send_one_frame` at ~lines 132-167.
   - Confirm `tests/cfc_phase2/` directory exists.
   - **v7 addition: re-verify protobuf field names** by running the §1.5
     snippet against the current `flipper_pb2`. All five HasField calls must
     return False without raising. If any raise `ValueError`, the field
     name has drifted — **halt and escalate to Victor** before proceeding.
   - **Halt if any verification fails** — design assumptions are wrong, escalate.

2. **Add `_send_main_raw` to `ProtobufRPC`** (Change A, §2.2).
   - Place above `_send_rpc_message`.
   - No changes to existing methods.

3. **Rewrite `_cfc_send_one_frame`** (Change B, §2.2).
   - Replace whole function body per the v2 implementation.
   - Confirm imports still match.
   - **v8 clarification:** `CfcProtocolDesyncError` is **module-level** (not
     inside any class). `_cfc_send_one_frame` is also module-level (confirmed
     by reading `cfc/module.py:132` — zero indentation). Place the exception
     class above the function definition at module scope.

3b. **v8.4 — add `cfc_recv_response_assembled` helper (§2.7).** Place after
    `cfc_send_raw_frame` (around line 297) at module scope. Full code in
    §2.7 Change E. No new imports needed; all dependencies already in scope.

4. **Add `MOMENTUM_RPC_EXCHANGE_DATA_FIXED = False`** constant to
   `flipper_mcp/modules/cfc/module.py` near top of file (§2.4).

4b. **v8.3 — FAP-side multi-fragment outbound (§2.6).** Apply Change C
    (`cfc_send_response_multi` new function) and Change D (PING handler
    refactor with heap buffer) to `cfc/cfc.c`. Verify `<stdlib.h>` is
    included (cc adds if missing). This is the spec §6.4 scope that v6
    missed.

5. **Patch spec §6.4** in `docs/decisions/DAY8_FAP_PHASE1_SPEC.md` (§2.3).
   **v8.3 note:** if already preserved per §10 from previous cook attempt,
   skip this step. cc reads `git status` to determine.

6. **Add new tests** (using §4.0 scaffold for all unit tests):
   - `tests/cfc_phase2/test_chunked_ping_roundtrip.py` (§4.3)
   - `tests/cfc_phase2/test_broadcast_path_mock.py` (§4.4)
   - `tests/cfc_phase2/test_cfc_timeout_returns_none.py` (§4.4b — v8 addition)
   - `tests/cfc_phase2/test_non_cfc_frame_raises_desync.py` (§4.5)
   - `tests/cfc_phase2/test_async_event_consumed_during_drain.py` (§4.5b)

6b. **v8.4 — update `tests/cfc_phase2/test_stale_transaction.py` (§2.7 Change F).**
    Add `cfc_recv_response_assembled` to imports; change the `frag2_txn1`
    response handling at line ~68 to assemble via the helper. cc reads
    `conftest.py` to verify `decode_resp`'s signature before deciding
    which form of the call to use. Full guidance in §2.7 Change F.

7. **Pre-flight hardware:** `flipper_connection_health` — must show
   `connected: true, rpc_responsive: true, last_error: null`.
   **Halt if unhealthy.**

8. **Build/deploy FAP (v8.3 REQUIRED — was skippable in v6-v8.2).**
   Run `ufbt` from the repo root to build `cfc.fap`. On success, copy
   `dist/f7-C/cfc_<short_hash>.fap` to `/ext/apps/Tools/cfc.fap` on
   AmorPoee via flipper-mcp's `storage_write` (binary) or a manual SD swap.
   **flipper-mcp must be toggled ON during deploy, then OFF before
   running pytest hardware tests** (same operational constraint that
   surfaced in cook attempt #1).
   **Halt criterion:** ufbt build fails → halt, surface compiler error.

9. **Run unit tests** (§4.4, §4.4b, §4.5, §4.5b). All must pass before touching
   hardware tests.
   **Halt criterion:** any unit test fails → §10 rollback.

10. **Run `test_stale_transaction` 10×** (§4.1). All 10 must pass.
    **Halt criterion:** any failure → §10 rollback.

11. **Run full Phase 2 suite** (§4.2). Expected count: **22/22** test files
    passing — 17 prior tests (including `test_stale_transaction`, which
    previously halted) + 5 new test files (`test_chunked_ping_roundtrip`,
    `test_broadcast_path_mock`, `test_cfc_timeout_returns_none`,
    `test_non_cfc_frame_raises_desync`, `test_async_event_consumed_during_drain`)
    = 22 test files total. Note: some test files contain multiple
    test functions; pytest collection count may be higher.
    **Halt criterion:** any regression in the 17 prior tests → §10 rollback.

12. **Commit when 22/22 pass.** Single commit, message describes the bug, the
    workaround, the sunset condition, and references this design doc.

---

## 6 — What this v3 design doc is asking Sherpa v2 to review

(Gemini reflection already incorporated as v2→v3 changelog.)

1. **Did v3 fully address Gemini's three findings?** Specifically: is the §0 ↔ §2.2
   contradiction fully resolved? Is `CfcProtocolDesyncError` semantics clear? Is
   the import-time warning correctly scoped?
2. **Is `CfcProtocolDesyncError` raising semantics correct?** Should the
   raise happen INSIDE the `async with rpc._wire_lock:` block, or should we
   release the lock before raising? Current code raises inside, which means the
   lock releases via context-manager unwind. Is that right for an async lock?
3. **Is the import-time `logging.warning` going to be too noisy in test runs?**
   Pytest may capture / surface it on every collection. Should it be gated
   behind a `__main__` check or a sentinel env var?
4. **Test plan completeness:** §4.4 and §4.5 are mock-based. Are the mocks
   realistic enough — specifically, does mocking `_receive_main_message` skip
   over `_wire_lock` acquire/release in a way that masks lock-related bugs?
5. **Phase 3 forward-compat:** does v3 make `flipper_cfc_listen` easier or
   harder than v2 did? Does raising `CfcProtocolDesyncError` from inside
   `_cfc_send_one_frame` create issues when Phase 3 expects unsolicited frames
   on a different code path?
6. **Anything Gemini and Sherpa v1 both missed.** Three reviewer LLMs and one
   reflection model later, this should be near cook-ready. What remains?

---

## 7 — Items deferred (with explicit cc-out-of-scope marking)

- **Momentum upstream PR text:** drafted separately, in a sibling doc
  (`docs/decisions/MOMENTUM_PR_DRAFT.md` or similar) after design is locked.
  **cc does not open external-repo PRs in Phase 2.5.**
- **`MOMENTUM_RPC_EXCHANGE_DATA_FIXED` consumer logic:** wait for upstream
  merge, then write Phase 3 listener that consults it.
- **Phase 3 host-listener architecture:** subject of its own design doc.
- **R7 mitigation (orphan flipper-mcp processes):** separate side-task.

---

## 8 — Open questions for Victor before cook

None blocking. v2 closes all v1 ambiguities.

---

## 9 — Stop conditions (consolidated, per Sherpa v1 finding #4)

cc halts and asks Victor when ANY of:

- Pre-flight verification (§5 step 1) fails.
- Hardware health check (§5 step 7) fails.
- Any unit test (§4.4, §4.4b, §4.5, §4.5b) fails.
- `test_stale_transaction` fails on any of 10 iterations after the change.
- `test_chunked_ping_roundtrip` (§4.3) fails — new functionality being validated.
- Any of the 17 prior tests regress.
- `_send_main_raw` cannot be added because `ProtobufRPC` doesn't match the
  expected structure (paths or method names differ).
- Spec patch (§5 step 5) cannot be applied because the file structure differs.

cc does NOT halt for:

- Documentation-only mismatches (e.g., spec §6.4 patch already partially applied).

(Note: a prior draft excluded `test_chunked_ping_roundtrip` from halt criteria.
v4 corrects this — chunked-ping IS halt-worthy per §4.3, because it validates
new Phase 2.5 functionality. Resolves Sherpa v2 §4.3-vs-§9 contradiction.)

---

## 10 — Rollback plan (per Sherpa v1 finding #4)

If ANY halt criterion fires after committing implementation changes:

1. `git stash` any uncommitted work.
2. `git diff HEAD` to confirm the state before reverting.
3. `git checkout HEAD -- flipper_mcp/core/protobuf_rpc.py flipper_mcp/modules/cfc/module.py`
   to revert just the two changed source files.
4. Leave new test files (`test_chunked_ping_roundtrip.py`, `test_broadcast_path_mock.py`,
   `test_non_cfc_frame_raises_desync.py`) in place — they don't break anything
   and may be useful for debugging.
5. Leave spec patch (`DAY8_FAP_PHASE1_SPEC.md`) in place — it's just doc.
6. Re-run Phase 2 test suite to confirm rollback returned to 17/18 baseline.
7. Tell Victor what halted, what was rolled back, what remains, and recommend
   next step (more design work? more diagnosis? give up and ship without
   `test_stale_transaction`?).

**The rollback explicitly preserves new tests and doc fixes.** It only reverts
the source-code changes that introduced the regression.
