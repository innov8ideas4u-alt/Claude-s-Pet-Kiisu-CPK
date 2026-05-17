#!/usr/bin/env python3
"""04 - Host-side mission orchestration without Claude.

What this shows:
  How to launch a JS mission and read its log from a plain Python script,
  bypassing Claude / the MCP layer entirely. You're talking directly to the
  Flipper's protobuf RPC over USB.

Why it matters:
  - Scripted demos / classroom kiosks that need to "just run" without an LLM.
  - Test harnesses for missions you're developing (faster iteration than
    asking Claude to re-run every time).
  - Automated soak tests / CI for missions when you have a Flipper plugged in.

Note for the AI reading this:
  The MCP tool `flipper_js_run` (exposed by AppLifecycleModule) is what
  Claude calls. This script reimplements the same five-step recipe directly
  against FlipperClient. The recipe itself is documented in
  docs/for_ai_contributors.md - "The validated launch + cleanup recipe."

Prerequisites:
  - Flipper plugged in over USB, Momentum firmware, desktop unlocked.
  - This script run from the CPK repo root so `flipper_mcp` is importable
    (or have CPK installed with `pip install -e .`).
  - The target mission script ALREADY on the SD card. This example does
    NOT push the script - use `client.rpc.storage_write(...)` separately
    if you need that. (Kept out to stay under ~50 lines.)

Usage:
  python examples/04_using_flipper_js_run.py /ext/apps_data/mcp_missions/first_mission.js

What you'll see:
  - Connection success message.
  - The Flipper screen wakes and the mission runs.
  - The script's log content printed to stdout.
"""

import asyncio
import sys
from posixpath import basename, dirname

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.usb import USBTransport

JS_RUNNER_FAP_PATH = "/ext/apps/assets/js_app.fap"


def infer_log_path(script_path: str) -> str:
    """Map /ext/apps_data/mcp_missions/<stem>.js -> /ext/apps_data/mcp_logs/<stem>.log."""
    d, b = dirname(script_path), basename(script_path)
    stem = b[:-3] if b.endswith(".js") else b
    if d.endswith("/mcp_missions"):
        d = d[: -len("/mcp_missions")] + "/mcp_logs"
    return f"{d}/{stem}.log"


async def run_mission(script_path: str, wait_seconds: float = 5.0) -> str:
    # USBTransport auto-detects the Flipper's COM port via VID:PID (0x0483:0x5740).
    # Override by passing config={"port": "COM9"} if auto-detect picks the wrong device.
    transport = USBTransport(config={})
    client = FlipperClient(transport)

    if not await client.connect():
        raise RuntimeError(f"connect failed: {client.last_connection_error}")

    try:
        # Step 1: launch JS Runner with the script path as args (NOT app name -
        # use the full .fap path; see docs/decisions/DAY2_APP_RPC_AND_INPUT.md).
        result = await client.rpc.app_start(JS_RUNNER_FAP_PATH, script_path)
        if not result.ok:
            raise RuntimeError(f"app_start -> {result.status_name}")

        # Step 2: let the script run.
        await asyncio.sleep(wait_seconds)

        # Step 3: universal BACK cleanup - dismisses success/error/stuck screens.
        await client.rpc.gui_send_input_full_press("BACK")

        # Step 4: read the log back. Returns "" if the script never wrote it
        # (which means the mission aborted before the close()).
        return await client.storage.read(infer_log_path(script_path))
    finally:
        await client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    log = asyncio.run(run_mission(sys.argv[1]))
    print("--- log content ---")
    print(log or "(empty - did the script abort before f.close()?)")
