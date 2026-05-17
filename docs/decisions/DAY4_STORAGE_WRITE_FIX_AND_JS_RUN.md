# Day 4 Decision Document — R5 storage_write Fix + flipper_js_run Helper

**Date:** 2026-05-17
**Hardware:** AmorPoee (Kiisu V4B + Momentum `mntm-dev`), serial `5A3DEA0027E18000`, COM9
**Builds on:** Day 1 (BLE probe), Day 2 (app-RPC + synthetic input), Day 3 (desktop RPC + universal cleanup)

---

## TL;DR

Two surgical changes:

1. **R5 fixed.** `storage_write` no longer false-reports "Write failed" on multi-chunk writes. The bug was an ACK-per-chunk assumption that contradicted the firmware's actual behavior (only the final chunk gets an ACK).
2. **`flipper_js_run` added.** One MCP tool that wraps the validated launch + cleanup recipe (lock check → unlock → app_start → wait → BACK → optional log read). Replaces 5 manual tool calls per mission with 1.

Module bumped: `app_lifecycle` v0.4.0 → v0.5.0.

---

## 1. R5 — storage_write false-failure (FIXED)

### What was wrong

`flipper_mcp/core/protobuf_rpc.py:_storage_write_internal` chunked content into 512-byte payloads (correct) and **waited for an ACK after every chunk** (wrong).

```python
# OLD — wrong
if first_chunk:
    last_response = await self._send_rpc_message(main_request)  # waits 2.5s for ACK
    if not last_response or last_response.command_status != OK:
        return False
else:
    await self.transport.send(framed)
    last_response = await self._receive_main_message(timeout=2.5)  # waits 2.5s for ACK
    if not last_response or last_response.command_id != cmd_id or ... != OK:
        return False
```

Per `docs/KIISU_DEEP_KNOWLEDGE.md §5.2` and the upstream `rpc_storage.c` source:

```c
// inside rpc_system_storage_write_process()
send_response = !request->has_next;
```

→ **The firmware sends ZERO responses for intermediate chunks.** Only one `PB_Main` with `CommandStatus` after the final chunk (`has_next=false`) arrives.

For multi-chunk writes (>512 bytes):
1. Host sent chunk 1 with `has_next=True`.
2. Host waited 2.5s for an ACK that never came (firmware was waiting for more chunks).
3. Host returned `False` with no further chunks sent.
4. **On-disk file was truncated to chunk-1 bytes** — looked like "Write failed but partially succeeded."

### What we did

Rewrote `_storage_write_internal` to mirror the upstream Python reference client (`flipperzero_protobuf_py/flipperzero_protobuf/flipper_storage.py`): fire all chunks back-to-back with shared `command_id`, `has_next=True` on every chunk except the last, then read exactly one ACK after the final chunk.

```python
# NEW — correct
while True:
    ...
    main_request.has_next = not is_last
    ...
    framed = self._encode_varint(len(message_data)) + message_data
    await self.transport.send(framed)

    if is_last:
        final_response = await self._receive_main_message(timeout=5.0)
        if not final_response or final_response.command_id != cmd_id or ... != OK:
            return False
        return True
    offset = end
```

Bumped final-ACK timeout to 5.0s (from 2.5s) to give LittleFS GC on `/int` headroom for sustained writes.

### Empirical reproduction (pre-fix)

Reproduced bug before fixing, using the running flipper-mcp's `storage_write` against AmorPoee:

| Size | Returned | File on disk |
|---|---|---|
| 102 chars | "Wrote 102 chars" | full content |
| 445 chars | "Wrote 445 chars" | full content |
| 613 chars | **"Write failed"** | **truncated to ~512 bytes** (no `_END605` marker present) |

### Validation status

- ✅ Code review against KB §5.2 and rpc_storage.c source quoted there
- ✅ Unit-style smoke test (imports, class instantiation, registry)
- ✅ **Live end-to-end validation COMPLETE** (post-cook, Day 4 session continuation, ran against AmorPoee on COM9 via the live MCP `storage_write` tool):

| Size | Tool result | Roundtripped intact? |
|---|---|---|
| 109 chars | "Wrote 109 chars" | ✅ yes |
| 594 chars (previously failed) | "Wrote 594 chars" | ✅ yes, end-marker present at tail |
| 3721 chars (~7 chunks, well past 512-byte boundary) | "Wrote 3721 chars" | ✅ yes, `_end_marker_xyz` present at tail |

The fix matches the upstream reference client and the firmware source. **Confidence: confirmed.**

### Files changed

- `flipper_mcp/core/protobuf_rpc.py` — `_storage_write_internal` rewritten + new docstring documenting the R5 root cause and the upstream pattern we mirror.

---

## 2. `flipper_js_run` — mission helper

### What it does

Wraps the validated 5-step recipe in one MCP tool:

```
1. flipper_desktop_is_locked            # if locked, call flipper_desktop_unlock
2. flipper_app_start(JS_RUNNER_FAP_PATH, script_path)
3. asyncio.sleep(wait_seconds)
4. flipper_gui_send_input("BACK")       # universal cleanup
5. (optional) storage_read(log_path)    # include log in response
```

Arguments:
- `script_path` (required) — absolute path to the `.js` on the SD card
- `wait_seconds` (default 5) — script runtime + slack
- `read_log` (default True) — read back log file after run
- `log_path` (optional) — explicit log path; inferred from `script_path` if omitted (`/ext/apps_data/mcp_missions/<stem>.js` → `/ext/apps_data/mcp_logs/<stem>.log`)

Returns a structured text response with:
- `✅ flipper_js_run(...) completed in Nms`
- Log content (truncated to 4000 chars in display, full content in the buffer)
- Any non-fatal warnings (e.g. BACK cleanup non-OK, log file empty)

Hard-failures (returns immediately, no cleanup attempted):
- `RPC not connected`
- `desktop_unlock` failed (PIN configured — needs physical unlock)
- `app_start` returned non-OK (firmware error from `app_get_error` included)

### Why

The recipe is 5 manual tool calls today. Every mission script Victor writes (and every mission cc writes in future cooks) repeats this pattern. One tool call instead of five:
- 5x reduction in tool-call volume per probe
- Error handling lives in one place (improve once, applies everywhere)
- Recipe stays consistent (can't accidentally skip BACK cleanup)
- New mission authors don't have to learn the 5 steps

### Design choices

- **No retry logic.** If app_start fails, return the firmware error and let the caller decide. The spec was explicit about this.
- **No JS-side coordination.** The wait is wall-clock; the helper doesn't poll for a "finished=true" log marker or anything similar. Mission scripts are expected to be small and time-bound.
- **`asyncio.sleep`, not blocking sleep.** Yields the event loop while waiting.
- **BACK is always sent** (even if app_start failed? no — wait. Re-read: BACK is only sent after a successful app_start. If app_start fails, no app launched, no cleanup needed. This is correct.)
- **Warnings vs failures.** BACK cleanup non-OK is a warning, not a failure (the script's primary task already completed). Log file unreadable is a warning. Anything that prevents the script from running is a failure.

### Validation status

- ✅ Code review
- ✅ Smoke test: tool registered, schema validated, `_infer_log_path` unit tests pass for 4 path shapes
- ✅ **Live end-to-end validation COMPLETE** (post-cook, Day 4 session continuation, ran against AmorPoee on COM9 via the live MCP `flipper_js_run` tool):
  - `flipper_js_run("/ext/apps_data/mcp_missions/ping.js")` → ✅ completed in 20040ms; log returned: `mission=ping`, `runtime=mJS`, `ok=true`, `finished=true`. Device returned to clean unlocked state after.
  - `flipper_js_run("/ext/apps_data/mcp_missions/probe_big.js", wait_seconds=4)` → ✅ 2705-char script ran cleanly, all 40 lines + `finished=true` present in returned log. No mJS crash, no USB-CDC drop.

**R6 (large-script crash) is subsumed by R5.** cc's hypothesis confirmed: the "mJS parser crash on ~1500+ char scripts" was downstream of R5's truncation. With R5 fixed, large scripts land intact and execute normally.

Live test sequence (run after Desktop closes):

```
1. flipper_js_run(script_path="/ext/apps_data/mcp_missions/ping.js")
   → expect: ✅, log content with "finished=true", BACK pressed, screen wakes via notification.success()
```

### Files changed

- `flipper_mcp/modules/app_lifecycle/module.py` — added `flipper_js_run` tool definition + dispatch + `_js_run` handler + `_infer_log_path` static helper; version 0.4.0 → 0.5.0

---

## Environment change (out-of-band, needs migration completion)

The editable install at `D:\Dev\Projects\Kiisu\.venv\Lib\site-packages\__editable__.flipper_mcp-0.1.0.pth` was re-pointed from `D:\Dev\Projects\flipperzero-mcp\src` to `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK`. This was needed so the running MCP server (Claude Desktop + cc) loads code from CPK.

Backup saved at `__editable__.flipper_mcp-0.1.0.pth.bak`.

Future migration steps to complete the CPK takeover:
1. Create a dedicated CPK venv (`D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\.venv\`) and `pip install -e .` from CPK.
2. Update both Claude Desktop's and Claude Code's MCP config to point at the new venv.
3. Archive `D:\Dev\Projects\flipperzero-mcp\src` once nothing references it.

---

## What's still open

- **R6 — RESOLVED (subsumed by R5).** Confirmed live: a 2705-char script ran end-to-end via `flipper_js_run` with no parse crash and no USB-CDC drop. cc's hypothesis was correct — the "mJS parser crash" was downstream of R5's truncation, not an independent firmware bug.
- **R7 — orphan flipper-mcp processes.** cc terminated cleanly this session (no orphans). The root cause appears related to the harness's spawn-on-disconnect logic, not anything in CPK; deferring to future investigation if the pattern recurs.
- **CPK venv migration** — the editable install band-aid works, but the clean fix (a dedicated `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\.venv\` with its own `pip install -e .`) is still pending. Low priority; current setup is functionally correct.

---

## Files in this delivery

| File | Change |
|---|---|
| `flipper_mcp/core/protobuf_rpc.py` | R5 fix: rewrote `_storage_write_internal` to match firmware ACK semantics |
| `flipper_mcp/modules/app_lifecycle/module.py` | v0.4.0 → v0.5.0; added `flipper_js_run` tool + handler + `_infer_log_path` |
| `docs/decisions/DAY4_STORAGE_WRITE_FIX_AND_JS_RUN.md` | This file |

Branch: `experiment/day4-storage-fix-and-mission-helper`
Commits: two logical units (R5 first, `flipper_js_run` second)
