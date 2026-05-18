"""Shared JS-mission runner — internal helper for the Day 6 morning-kit missions.

Private module. Not part of the public mission API. Each morning-kit
mission helper (radio_handshake, subghz_quick_scan, gpio_full_read,
ble_passive_scan, flipper_info) uses `run_js_mission()` to:

  1. push the .js source to the Flipper's SD card (storage_write)
  2. execute the validated launch + cleanup recipe via direct RPC
     (the same recipe AppLifecycleModule._js_run implements)
  3. read the resulting log from /ext/apps_data/mcp_logs/
  4. parse the `key=value\\n` lines into a dict
  5. return (raw_log_text, parsed_dict, elapsed_ms, warnings)

The recipe is documented in docs/for_ai_contributors.md — "The validated
launch + cleanup recipe."

Why not just import AppLifecycleModule._js_run?
  - It's a private (underscore-prefixed) method on a different module.
  - The module returns MCP TextContent objects, not parsed data.
  - We want a Python-level function for programmatic use.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

JS_RUNNER_FAP_PATH = "/ext/apps/assets/js_app.fap"
MISSION_DIR = "/ext/apps_data/mcp_missions"
LOG_DIR = "/ext/apps_data/mcp_logs"


def parse_kv_log(text: str) -> dict[str, str]:
    """Parse a CPK structured log into a flat dict of string values.

    The log format is line-oriented `key=value\\n`. Repeated keys are
    accumulated into a list; everything else is a single string. Lines
    without an `=` are silently dropped (comment lines starting with `#`,
    blank lines, etc.).

    Callers cast values to the types they expect.
    """
    out: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in out:
            existing = out[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                out[key] = [existing, value]
        else:
            out[key] = value
    return out


async def run_js_mission(
    client: Any,
    mission_name: str,
    js_source: str,
    wait_seconds: float = 5.0,
    extra_warnings: Optional[list[str]] = None,
) -> tuple[str, dict[str, Any], int, list[str]]:
    """Run one JS mission end-to-end and return (log_text, parsed, elapsed_ms, warnings).

    Args:
        client: connected FlipperClient instance.
        mission_name: stem used for the on-device script + log paths.
            Script lands at /ext/apps_data/mcp_missions/<mission_name>.js
            Log expected at /ext/apps_data/mcp_logs/<mission_name>.log
        js_source: full JS text to execute.
        wait_seconds: how long to sleep after launch before cleaning up.
        extra_warnings: caller-supplied warnings to thread into the
            returned list (e.g. "BLE module not bound").

    Never raises — failures show up as warnings in the returned list and
    an empty/partial parsed dict.
    """
    started = time.monotonic()
    warnings: list[str] = list(extra_warnings or [])

    if getattr(client, "rpc", None) is None:
        warnings.append("RPC not connected — aborting before push.")
        return "", {}, 0, warnings

    script_path = f"{MISSION_DIR}/{mission_name}.js"
    log_path = f"{LOG_DIR}/{mission_name}.log"

    # Step 0: push the JS to the device. If the dirs don't exist yet,
    # storage_write returns False; mkdir + retry once. Best-effort —
    # this is the most likely failure mode on a fresh device, and we
    # surface it as a warning so morning-Victor knows.
    pushed = await client.storage.write(script_path, js_source)
    if not pushed:
        # Try creating the mission dir, then retry.
        try:
            await client.storage.mkdir(MISSION_DIR)
        except Exception as e:
            warnings.append(f"mkdir {MISSION_DIR!r} raised {type(e).__name__}: {e}")
        try:
            await client.storage.mkdir(LOG_DIR)
        except Exception as e:
            warnings.append(f"mkdir {LOG_DIR!r} raised {type(e).__name__}: {e}")
        pushed = await client.storage.write(script_path, js_source)
    if not pushed:
        warnings.append(f"storage_write to {script_path!r} returned False (firmware response bug or genuine failure — verify by reading back)")

    # Step 1: lock check + unlock if needed.
    try:
        locked = await client.rpc.desktop_is_locked()
    except Exception as e:
        warnings.append(f"desktop_is_locked raised {type(e).__name__}: {e}")
        locked = False
    if locked:
        try:
            unlock = await client.rpc.desktop_unlock()
            if not unlock.ok:
                warnings.append(
                    f"desktop_unlock returned {unlock.status_name} — if a PIN is set, the device must be unlocked physically before retry."
                )
        except Exception as e:
            warnings.append(f"desktop_unlock raised {type(e).__name__}: {e}")

    # Step 2: app_start the JS Runner FAP with the script as args.
    try:
        start_result = await client.rpc.app_start(JS_RUNNER_FAP_PATH, script_path)
    except Exception as e:
        warnings.append(f"app_start raised {type(e).__name__}: {e}")
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return "", {}, elapsed_ms, warnings
    if not start_result.ok:
        err_text = ""
        try:
            _code, err_text = await client.rpc.app_get_error()
        except Exception:
            pass
        warnings.append(
            f"app_start({script_path!r}) -> {start_result.status_name}; firmware error: {err_text!r}"
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return "", {}, elapsed_ms, warnings

    # Step 3: let the script run.
    await asyncio.sleep(max(0.0, wait_seconds))

    # Step 4: BACK cleanup — universal verb for success/error/stuck.
    try:
        back = await client.rpc.gui_send_input_full_press("BACK")
        if not back.ok:
            warnings.append(f"BACK cleanup returned {back.status_name}")
    except Exception as e:
        warnings.append(f"BACK cleanup raised {type(e).__name__}: {e}")

    # Step 5: read the log.
    log_text = ""
    try:
        log_text = await client.storage.read(log_path) or ""
    except Exception as e:
        warnings.append(f"log read at {log_path!r} raised {type(e).__name__}: {e}")

    parsed = parse_kv_log(log_text)

    # Sanity check: did the mission actually complete?
    if parsed.get("finished") != "true":
        warnings.append(
            "log is missing `finished=true` — script aborted before completion (mJS has no try/catch, so a thrown call ends the script silently)."
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return log_text, parsed, elapsed_ms, warnings
