# Notebook 4 — CPK Current Build (Phase 2.5 SHIPPED)

**Snapshot date:** 2026-05-27 (commit `6bf1d32` on `origin/main`)
**Purpose:** Ground-truth source artifacts of what CPK has *actually built* so far, for use during Phase 3 planning and adversarial review. Notebooks 1–3 cover firmware truth / host-side patterns / design context; this notebook covers **our own code**.

**Why it exists:** Without these, NotebookLM is planning Phase 3 from spec docs and inference. Reviewers keep asking "how does X work currently?" — this notebook lets them cite source instead of guessing.

---

## Sources

### 01 — cfc/cfc.c → 01_cfc_fap_source.txt
The CPK Companion FAP source (~618 lines, ~25KB). FlipperAppType.EXTERNAL single-FAP architecture (Path A). Contains the RPC callback, transaction state machine (IDLE → ASSEMBLING → COMPLETE), and cfc_send_response_multi for multi-fragment outbound (Phase 2.5).
**Phase 3 relevance:** This is where the FuriThread worker, message queue, and broadcast-emit code will be added. Reviewers should ground all FAP-side design questions in this file.

### 02 — cfc/application.fam → 02_cfc_application_fam.txt
FAP build manifest. Currently sets stack_size and entry point. Phase 3 may need stack bump for the worker thread.

### 03 — flipper_mcp/modules/cfc/module.py → 03_cfc_host_module.txt
Host-side CFC client (~472 lines, ~23KB). Contains _cfc_send_one_frame (the Phase 2.5 route-by-tag drain pattern), cfc_recv_response_assembled (multi-fragment reassembly helper), the 5-frame allowlist, and CfcProtocolDesyncError.
**Phase 3 relevance:** flipper_cfc_listen will sit alongside this code. The route-by-tag drain is the foundation the listener extends.

### 04 — flipper_mcp/core/protobuf_rpc.py → 04_protobuf_rpc_transport.txt
Transport layer (~1321 lines, ~66KB). Contains _send_main_raw (the Phase 2.5 bypass), _send_rpc_message (the strict matcher), the wire-mutex decorator (@_with_wire_lock), command_id matching, stale-frame discard, varint framing.
**Phase 3 relevance:** The listener hooks in at this transport level — needs to coexist with the strict matcher without stealing frames intended for it.

### 05 — docs/decisions/DAY8_FAP_PHASE1_SPEC.md → 05_DAY8_FAP_PHASE1_SPEC.md
The Phase 1 spec, v5.1 (~33KB). 16-byte CFC header, msgpack payload, 8KB transaction cap, opcode allocations, error codes, §6.5 Phase 3 forward-compat notes. §6.4 corrected to void return in Phase 2.5.
**Phase 3 relevance:** §6.5 is the explicit forward-compat for broadcasts/subscriptions. Phase 3 spec will extend this.

### 06 — docs/decisions/DAY9_PHASE2_COOK_LOG.md → 06_DAY9_PHASE2_COOK_LOG.md
Phase 2 cook log (~9KB). What got built, what halted, the uninit-malloc discovery, the firmware-rewrites-args-to-"RPC %08lX" finding, why ship at 17/18.

### 07 — docs/decisions/DAY10_PHASE2_5_DESIGN.md → 07_DAY10_PHASE2_5_DESIGN.md
Phase 2.5 design doc, v8.4 (~85KB, 1464 lines). The most authoritative current-state doc. Documents the 4-attempt / 6-halt cook, all spec discoveries, the multi-fragment outbound design, and **§6 Phase 3 forward-compat notes**.
**Phase 3 relevance:** Mandatory pre-read for any Phase 3 reviewer. §6 tells them what Phase 2.5 left specifically for Phase 3 to inherit.

### 08 — tests/cfc_phase2/*.py (24 files concatenated) → 08_cfc_phase2_tests_bundle.txt
All 27 test cases (some parametrized so file count is 24). 17 from Phase 2 + 5 new from Phase 2.5 + 5 negative paths. Each separated by =============== FILE: <name> ===============.
**Phase 3 relevance:** Reviewers can see test patterns Phase 3 will extend (especially test_broadcast_path_mock which is the mock skeleton that Phase 3 makes real).

---

## What this notebook is NOT for

- Firmware questions about Momentum/OFW internals (use notebook 1)
- Host-side ecosystem patterns from qFlipper/pyflipper/etc. (use notebook 2)
- Design rationale, decision history, project mission (use notebook 3)
- General Flipper Zero documentation (use notebook 3)

Use this notebook **only** for questions about CPK's own code as it stands today.

---

## Refresh policy

This notebook is a snapshot. Refresh whenever CPK ships a phase (e.g., re-upload after Phase 3 ships). Keep the file numbering stable so reviewer citations don't break across refreshes.
