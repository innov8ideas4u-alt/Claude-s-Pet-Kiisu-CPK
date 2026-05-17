"""
App Lifecycle module for Flipper Zero MCP.

Exposes the full Application-service RPC surface as MCP tools:
  flipper_app_start         — start an app by name with optional args
  flipper_app_load_file     — open a file with its associated handler app
  flipper_app_exit          — ask the running app to exit cleanly
  flipper_app_get_error     — read the firmware's verbose error from the last failed app op
  flipper_app_lock_status   — check whether the desktop is locked
  flipper_js_run            — launch a JS mission, wait, cleanup, return log (v0.5.0)

Why this exists:
  - js_runner uses app_start/app_load_file as fallbacks inside a cascade; you can't
    address them directly without going through that cascade.
  - Cross-device missions (LLMDR Path 2) need fine-grained primitives rather than
    monolithic mission tools.
  - BLE-mobility work (Day 1 doc) needs CLI-free launch paths.
  - Failures from app_start were opaque ("returned False") — get_error fixes that.

Risks (documented, not gated):
  - Starting BadUSB / USB-disk apps changes USB mode and will drop the host's CDC
    transport. The caller is responsible for understanding the consequences. We do
    NOT block these — observability beats protection here, especially for the EDGE
    classroom use case.
"""

import asyncio
import time
from posixpath import basename, dirname
from typing import Any, List, Optional, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule

JS_RUNNER_FAP_PATH = "/ext/apps/assets/js_app.fap"


class AppLifecycleModule(FlipperModule):
    """Direct app_start / app_load_file / app_exit / app_get_error / app_lock_status RPC primitives."""

    @property
    def name(self) -> str:
        return "app_lifecycle"

    @property
    def version(self) -> str:
        return "0.5.0"

    @property
    def description(self) -> str:
        return "Application + desktop + GUI input RPC primitives with full diagnostics (CLI-free)"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="flipper_app_start",
                description=(
                    "Start a Flipper app by name via protobuf RPC (no CLI). "
                    "Common app names: 'js_app' (JS Runner — pass script path in args), "
                    "'Sub-GHz', 'NFC', 'Infrared', 'Bad USB', 'GPIO'. "
                    "On failure, the response carries the firmware's CommandStatus name "
                    "(e.g. ERROR_APP_CANT_START, ERROR_INVALID_PARAMETERS, ERROR_APP_SYSTEM_LOCKED). "
                    "For verbose error text, call flipper_app_get_error right after. "
                    "NOTE: Starting USB-mode-changing apps (BadUSB, USB Disk) can drop the host transport."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "App identifier (e.g. 'js_app', 'Sub-GHz', 'NFC').",
                        },
                        "args": {
                            "type": "string",
                            "description": "Optional argument string passed to the app (e.g. a file path).",
                            "default": "",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="flipper_app_load_file",
                description=(
                    "Open a file with whichever app the firmware associates with that file type. "
                    "Examples: a .js path launches the JS Runner; a .nfc launches the NFC app pre-loaded "
                    "with the dump; a .sub launches Sub-GHz with the capture; a .ir launches Infrared. "
                    "On failure, response carries the CommandStatus name. Follow up with flipper_app_get_error."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full path to the file on the Flipper (e.g. '/ext/apps_data/mcp_missions/ping.js').",
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="flipper_app_exit",
                description=(
                    "Ask the currently running app to exit cleanly. Equivalent to the user pressing "
                    "Back-to-exit. Returns ERROR_APP_NOT_RUNNING if nothing is open. Useful for clearing "
                    "state before launching a fresh app."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="flipper_app_get_error",
                description=(
                    "Read the firmware's verbose error info for the most recent failed app operation. "
                    "Call after a flipper_app_start or flipper_app_load_file returns a non-OK status. "
                    "Returns the firmware-side error code and human-readable text."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="flipper_app_lock_status",
                description=(
                    "Check whether the Flipper desktop is locked. When locked, the device may refuse "
                    "RPC ops that need an unlocked desktop. Useful as a pre-flight before app launches."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="flipper_gui_send_input",
                description=(
                    "Synthesize a hardware button press at the GUI input layer. Unlike app_button_press "
                    "(which only reaches apps that registered an RPC callback), this injects at the lowest "
                    "input layer so any running app sees the event as if you pressed the physical button. "
                    "Critical for exiting apps that don't have an RPC callback (e.g. JS Runner). "
                    "\n\n"
                    "DEFAULT behavior: emits the full PRESS→SHORT→RELEASE triplet a real hardware button "
                    "produces. This is what apps actually listen for — a lone SHORT is silently absorbed "
                    "on most Momentum scenes (empirically verified). "
                    "\n\n"
                    "ADVANCED: set event_type to a specific value (PRESS/RELEASE/SHORT/LONG/REPEAT) AND "
                    "set single_event=True to send only that one event. Use for LONG holds, REPEAT events, "
                    "or manual triplet construction."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Button to press: UP, DOWN, RIGHT, LEFT, OK, BACK (case-insensitive). Default behavior emits full PRESS→SHORT→RELEASE triplet.",
                        },
                        "event_type": {
                            "type": "string",
                            "description": "ONLY honored when single_event=True. Event type: PRESS, RELEASE, SHORT, LONG, REPEAT.",
                            "default": "SHORT",
                        },
                        "single_event": {
                            "type": "boolean",
                            "description": "If True, send ONLY the event_type specified (advanced case). Default False = emit the full press triplet.",
                            "default": False,
                        },
                    },
                    "required": ["key"],
                },
            ),
            Tool(
                name="flipper_desktop_is_locked",
                description=(
                    "Check whether the desktop LOCKSCREEN is currently showing. "
                    "Distinct from flipper_app_lock_status — that one is the app-loader mutex (LOCKED whenever "
                    "ANY app is running, including the lockscreen itself), making it useless for distinguishing "
                    "'screen is locked' from 'another app is open.' This tool asks the firmware about the actual "
                    "lock scene. Use this as the canonical pre-flight check before app_start."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="flipper_desktop_unlock",
                description=(
                    "Dismiss the desktop lockscreen via direct RPC. Canonical alternative to synthesizing a UP "
                    "keypress through gui_send_input. Bypasses the unlock-prompt UI entirely. Returns OK even if "
                    "the device wasn't locked. Fails if a PIN is configured (can't supply PIN over RPC). "
                    "Use this as the standard recovery action when flipper_desktop_is_locked returns True."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="flipper_js_run",
                description=(
                    "Run a JS mission end-to-end with the validated launch + cleanup recipe in one call. "
                    "Wraps the 5 manual tool calls a mission normally requires:\n"
                    "  1. desktop_is_locked → desktop_unlock (only if locked)\n"
                    f"  2. app_start({JS_RUNNER_FAP_PATH!r}, script_path)\n"
                    "  3. wait <wait_seconds>\n"
                    "  4. gui_send_input(BACK) — universal cleanup, dismisses success/error/stuck\n"
                    "  5. (optional) storage_read the log file and include in the response\n"
                    "\n"
                    "Empirically validated against AmorPoee on mntm-dev. The recipe matches the Day-3 decision "
                    "doc and docs/for_ai_contributors.md.\n"
                    "\n"
                    "If read_log=True and log_path is omitted, infers the log path from the script path "
                    "(/ext/apps_data/mcp_missions/<stem>.js → /ext/apps_data/mcp_logs/<stem>.log).\n"
                    "\n"
                    "Does NOT retry on failure. If app_start fails, the firmware error is captured via "
                    "app_get_error and included in the response. If desktop_unlock fails (e.g. PIN configured), "
                    "returns immediately without launching."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "script_path": {
                            "type": "string",
                            "description": "Absolute path to the JS file on the Flipper SD card (e.g. '/ext/apps_data/mcp_missions/ping.js').",
                        },
                        "wait_seconds": {
                            "type": "number",
                            "description": "Seconds to wait between launch and cleanup. Default 5. Make this longer than your script's expected runtime + 1s of slack.",
                            "default": 5,
                        },
                        "read_log": {
                            "type": "boolean",
                            "description": "If True, read back a log file after the script runs and include its content in the response. Default True.",
                            "default": True,
                        },
                        "log_path": {
                            "type": "string",
                            "description": "Explicit log path. If omitted and read_log=True, inferred from script_path by remapping /mcp_missions/ → /mcp_logs/ and .js → .log.",
                        },
                    },
                    "required": ["script_path"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        args = arguments or {}

        if tool_name == "flipper_app_start":
            return await self._app_start(
                name=args.get("name", ""),
                args=args.get("args", "") or "",
            )
        if tool_name == "flipper_app_load_file":
            return await self._app_load_file(path=args.get("path", ""))
        if tool_name == "flipper_app_exit":
            return await self._app_exit()
        if tool_name == "flipper_app_get_error":
            return await self._app_get_error()
        if tool_name == "flipper_app_lock_status":
            return await self._app_lock_status()
        if tool_name == "flipper_gui_send_input":
            return await self._gui_send_input(
                key=args.get("key", ""),
                event_type=args.get("event_type", "SHORT") or "SHORT",
                single_event=bool(args.get("single_event", False)),
            )
        if tool_name == "flipper_desktop_is_locked":
            return await self._desktop_is_locked()
        if tool_name == "flipper_desktop_unlock":
            return await self._desktop_unlock()
        if tool_name == "flipper_js_run":
            return await self._js_run(
                script_path=args.get("script_path", "") or "",
                wait_seconds=float(args.get("wait_seconds", 5) or 5),
                read_log=bool(args.get("read_log", True)),
                log_path=args.get("log_path") or None,
            )

        return [TextContent(
            type="text",
            text=f"❌ Unknown app_lifecycle tool '{tool_name}'",
        )]

    async def _app_start(self, name: str, args: str) -> Sequence[TextContent]:
        if not name:
            return [TextContent(type="text", text="❌ app_start: 'name' is required")]
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ app_start: RPC not connected")]

        try:
            result = await self.flipper.rpc.app_start(name, args)
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ app_start({name!r}, {args!r}) raised {type(e).__name__}: {e}",
            )]

        if result.ok:
            return [TextContent(
                type="text",
                text=f"✅ app_start({name!r}, {args!r}) → OK",
            )]
        return [TextContent(
            type="text",
            text=(
                f"⚠️  app_start({name!r}, {args!r}) → {result.status_name} (code {result.status_code})\n"
                f"Call flipper_app_get_error for the firmware's verbose error text."
            ),
        )]

    async def _app_load_file(self, path: str) -> Sequence[TextContent]:
        if not path:
            return [TextContent(type="text", text="❌ app_load_file: 'path' is required")]
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ app_load_file: RPC not connected")]

        try:
            result = await self.flipper.rpc.app_load_file(path)
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ app_load_file({path!r}) raised {type(e).__name__}: {e}",
            )]

        if result.ok:
            return [TextContent(
                type="text",
                text=f"✅ app_load_file({path!r}) → OK (handler app launched)",
            )]
        return [TextContent(
            type="text",
            text=(
                f"⚠️  app_load_file({path!r}) → {result.status_name} (code {result.status_code})\n"
                f"Call flipper_app_get_error for the firmware's verbose error text."
            ),
        )]

    async def _app_exit(self) -> Sequence[TextContent]:
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ app_exit: RPC not connected")]

        try:
            result = await self.flipper.rpc.app_exit()
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ app_exit raised {type(e).__name__}: {e}",
            )]

        if result.ok:
            return [TextContent(type="text", text="✅ app_exit → OK (running app told to exit)")]
        return [TextContent(
            type="text",
            text=f"⚠️  app_exit → {result.status_name} (code {result.status_code})",
        )]

    async def _app_get_error(self) -> Sequence[TextContent]:
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ app_get_error: RPC not connected")]

        try:
            code, text = await self.flipper.rpc.app_get_error()
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ app_get_error raised {type(e).__name__}: {e}",
            )]

        return [TextContent(
            type="text",
            text=(
                f"Firmware error state:\n"
                f"  code: {code}\n"
                f"  text: {text!r}\n"
                f"(code=0 with empty text typically means clean state)"
            ),
        )]

    async def _app_lock_status(self) -> Sequence[TextContent]:
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ app_lock_status: RPC not connected")]

        try:
            locked = await self.flipper.rpc.app_lock_status()
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ app_lock_status raised {type(e).__name__}: {e}",
            )]

        if locked is None:
            return [TextContent(type="text", text="⚠️  app_lock_status returned no data (transport error)")]
        if locked:
            return [TextContent(type="text", text="🔒 Desktop is LOCKED — some RPC ops may be refused")]
        return [TextContent(type="text", text="🔓 Desktop is unlocked")]

    async def _gui_send_input(self, key: str, event_type: str, single_event: bool) -> Sequence[TextContent]:
        if not key:
            return [TextContent(type="text", text="❌ gui_send_input: 'key' is required (UP/DOWN/RIGHT/LEFT/OK/BACK)")]
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ gui_send_input: RPC not connected")]

        try:
            if single_event:
                result = await self.flipper.rpc.gui_send_input_event(key, event_type)
                mode_label = f"single({event_type.upper()})"
            else:
                result = await self.flipper.rpc.gui_send_input_full_press(key)
                mode_label = "full_press"
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ gui_send_input({key!r}, {mode_label if 'mode_label' in dir() else 'full_press'}) raised {type(e).__name__}: {e}",
            )]

        if result.ok:
            return [TextContent(
                type="text",
                text=f"✅ gui_send_input({key.upper()}, {mode_label}) → OK",
            )]
        return [TextContent(
            type="text",
            text=f"⚠️  gui_send_input({key!r}, {mode_label}) → {result.status_name} (code {result.status_code})",
        )]

    async def _desktop_is_locked(self) -> Sequence[TextContent]:
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ desktop_is_locked: RPC not connected")]

        try:
            locked = await self.flipper.rpc.desktop_is_locked()
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ desktop_is_locked raised {type(e).__name__}: {e}",
            )]

        if locked is None:
            return [TextContent(type="text", text="⚠️  desktop_is_locked returned no data (transport error)")]
        if locked:
            return [TextContent(
                type="text",
                text="🔒 Lockscreen is showing — call flipper_desktop_unlock to dismiss",
            )]
        return [TextContent(type="text", text="🔓 Lockscreen is NOT showing (device is on desktop or in an app)")]

    async def _desktop_unlock(self) -> Sequence[TextContent]:
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ desktop_unlock: RPC not connected")]

        try:
            result = await self.flipper.rpc.desktop_unlock()
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ desktop_unlock raised {type(e).__name__}: {e}",
            )]

        if result.ok:
            return [TextContent(type="text", text="✅ desktop_unlock → OK (lockscreen dismissed)")]
        return [TextContent(
            type="text",
            text=(
                f"⚠️  desktop_unlock → {result.status_name} (code {result.status_code})\n"
                f"If a PIN is configured, unlock requires physical entry. Otherwise, try "
                f"flipper_gui_send_input(UP, SHORT) as a fallback."
            ),
        )]

    @staticmethod
    def _infer_log_path(script_path: str) -> str:
        """Map /ext/apps_data/mcp_missions/<stem>.js → /ext/apps_data/mcp_logs/<stem>.log.

        Falls back to the script's own directory with .log extension if the path
        doesn't follow the convention.
        """
        d = dirname(script_path)
        b = basename(script_path)
        stem = b[:-3] if b.endswith(".js") else b
        if d.endswith("/mcp_missions"):
            d = d[: -len("/mcp_missions")] + "/mcp_logs"
        return f"{d}/{stem}.log"

    async def _js_run(
        self,
        script_path: str,
        wait_seconds: float,
        read_log: bool,
        log_path: Optional[str],
    ) -> Sequence[TextContent]:
        """Run the validated launch + cleanup recipe in one call.

        Reference: docs/decisions/DAY3_DESKTOP_RPC_AND_POLISH.md, the validated
        recipe section in docs/for_ai_contributors.md, and the Day 4 spec.
        """
        if not script_path:
            return [TextContent(type="text", text="❌ flipper_js_run: 'script_path' is required")]
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="❌ flipper_js_run: RPC not connected")]

        started = time.monotonic()
        warnings: List[str] = []

        # Step 1: lock check + unlock if needed
        try:
            locked = await self.flipper.rpc.desktop_is_locked()
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ flipper_js_run: desktop_is_locked raised {type(e).__name__}: {e}",
            )]
        if locked:
            try:
                unlock_result = await self.flipper.rpc.desktop_unlock()
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"❌ flipper_js_run: desktop_unlock raised {type(e).__name__}: {e}",
                )]
            if not unlock_result.ok:
                return [TextContent(
                    type="text",
                    text=(
                        f"❌ flipper_js_run: desktop is locked and unlock failed "
                        f"({unlock_result.status_name}). If a PIN is configured, unlock the device "
                        f"physically before retrying."
                    ),
                )]

        # Step 2: app_start the JS Runner FAP with the script as args
        try:
            start_result = await self.flipper.rpc.app_start(JS_RUNNER_FAP_PATH, script_path)
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ flipper_js_run: app_start raised {type(e).__name__}: {e}",
            )]
        if not start_result.ok:
            # Pull the firmware's verbose error text for the report
            err_text = ""
            try:
                _code, err_text = await self.flipper.rpc.app_get_error()
            except Exception:
                pass
            return [TextContent(
                type="text",
                text=(
                    f"❌ flipper_js_run: app_start({script_path!r}) → {start_result.status_name} "
                    f"(code {start_result.status_code})\n"
                    f"Firmware error: {err_text!r}"
                ),
            )]

        # Step 3: wait for the script to do its thing
        await asyncio.sleep(max(0.0, wait_seconds))

        # Step 4: BACK cleanup — universal verb, dismisses success/error/stuck
        try:
            back_result = await self.flipper.rpc.gui_send_input_full_press("BACK")
            if not back_result.ok:
                warnings.append(
                    f"BACK cleanup returned non-OK: {back_result.status_name} "
                    f"(code {back_result.status_code})"
                )
        except Exception as e:
            warnings.append(f"BACK cleanup raised {type(e).__name__}: {e}")

        # Step 5: optional log read
        log_content: Optional[str] = None
        resolved_log_path: Optional[str] = None
        if read_log:
            resolved_log_path = log_path or self._infer_log_path(script_path)
            try:
                log_content = await self.flipper.storage.read(resolved_log_path)
            except Exception as e:
                warnings.append(
                    f"log read raised {type(e).__name__}: {e} (path {resolved_log_path!r})"
                )

        elapsed_ms = int((time.monotonic() - started) * 1000)

        # Build the response
        lines = [
            f"✅ flipper_js_run({script_path!r}) completed in {elapsed_ms}ms",
        ]
        if read_log and resolved_log_path:
            if log_content:
                preview = (
                    log_content
                    if len(log_content) <= 4000
                    else log_content[:4000] + f"\n... [truncated, total {len(log_content)} chars]"
                )
                lines.append(f"\nLog ({resolved_log_path}):\n{preview}")
            else:
                lines.append(f"\nLog ({resolved_log_path}): (empty or unreadable)")
        if warnings:
            lines.append("\nWarnings:")
            for w in warnings:
                lines.append(f"  - {w}")

        return [TextContent(type="text", text="\n".join(lines))]
