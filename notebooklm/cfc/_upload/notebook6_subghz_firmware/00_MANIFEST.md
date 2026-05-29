# notebook6_subghz_firmware — MANIFEST

**Purpose:** Ground NotebookLM in the real Momentum Sub-GHz receive/decode source so it
can answer Cook-1 design questions (worker→receiver→environment wiring, what `get_string`
returns, fixed-code vs rolling-code setup) without burning Claude Desktop tokens.

**Source:** Momentum firmware mirror at `D:\Dev\Projects\_reference\Momentum-dev\`
commit `d3ba597` (READ-ONLY, AGPL — pattern reference only, write original code).
Version-matched to the firmware AmorPoee runs.

**Files:**
| # | File | What it answers |
|---|------|-----------------|
| 01 | receiver.h | rx callback typedef + `subghz_receiver_set_rx_callback` + filter (the "I decoded something" hook — NFC's detect_cb analog) |
| 02 | receiver.c | how/when the callback fires on successful decode |
| 03 | subghz_worker.h | the worker that feeds air samples into the receiver |
| 04 | protocols/base.h | `SubGhzProtocolDecoderBase` + `get_string` contract (what we broadcast) |
| 05 | environment.h | protocol registry + keystore (the rolling-code question) |
| 06 | subghz_txrx.c [REFERENCE_LOOP] | cross_remote helper: full alloc→set_frequency→load_preset→worker_start→set_rx_callback wiring in one file |
| 07 | rolling_flaws_receive.c | minimal single-file receive + get_string exemplar |
| 08 | furi_thread.h | FuriThread plumbing (reused from NFC worker) |
| 09 | furi_message_queue.h | cross-thread result marshaling (reused from NFC worker) |

**Curate, don't bulk-dump.** If a design question can't be answered from these, grep the
mirror for the specific file and add it here as the next NN_*.txt — do NOT dump whole dirs.
