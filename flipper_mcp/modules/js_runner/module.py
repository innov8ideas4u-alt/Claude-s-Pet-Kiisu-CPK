"""JS Runner module for Flipper Zero MCP.

Executes JavaScript missions on-device. This is the LLMDR engine:
- push a JS file to SD card (via storage module primitives)
- launch Momentum's js_app.fap with the script path as arg
- poll a log file written by the script for results
- optionally stop the running app

Notes / caveats (honest):
- `app_start` may disrupt USB CDC for certain apps (BadUSB especially).
  js_app.fap does NOT change USB mode, so we are OK.
- JS runtime is mJS + Momentum module bindings. Not all Flipper subsystems
  are exposed equally; NFC/IR bindings are firmware-version-dependent.
- There is no live stdout stream back to us; JS writes to a log file, we
  read the log after the run (or poll during long runs).
"""

import asyncio
import time
from typing import Any, List, Sequence, Optional
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


# Default on-SD paths. Missions live in one folder, logs in another.
MISSION_DIR = "/ext/apps_data/mcp_missions"
LOG_DIR = "/ext/apps_data/mcp_logs"

# Momentum JS runtime app. If this ever moves, we centralize the override here.
JS_APP_NAME = "js_app"


class JsRunnerModule(FlipperModule):
    """Run JS missions on the Flipper, read their logs, stop them."""

    @property
    def name(self) -> str:
        return "js_runner"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Push, run, and collect output from on-device JavaScript missions (LLMDR engine)"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="js_ensure_dirs",
                description=(
                    "Create the MCP mission and log directories on the SD card if missing. "
                    "Call this once per fresh Flipper before pushing missions."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="js_push",
                description=(
                    "Write a JS mission script to the Flipper SD card. "
                    "The script will live at /ext/apps_data/mcp_missions/<name>.js. "
                    "Use js_run after to execute it."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Mission name (no extension, no path). Example: 'rf_survey_433'",
                        },
                        "code": {
                            "type": "string",
                            "description": "Full JS source of the mission.",
                        },
                    },
                    "required": ["name", "code"],
                },
            ),
            Tool(
                name="js_run",
                description=(
                    "Launch a previously-pushed mission. The Flipper's JS app opens the script "
                    "and starts executing. This call returns immediately; use js_read_log to get output. "
                    "Mission should write its output to /ext/apps_data/mcp_logs/<name>.log."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Mission name to run (must have been js_push'd first).",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="js_run_inline",
                description=(
                    "Push a JS mission AND immediately launch it. Convenience wrapper for "
                    "js_push + js_run. Returns after launch, not after mission completes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Mission name."},
                        "code": {"type": "string", "description": "JS source."},
                    },
                    "required": ["name", "code"],
                },
            ),
            Tool(
                name="js_read_log",
                description=(
                    "Read the log file a mission writes to. Call after js_run, or repeatedly "
                    "during long-running missions to poll progress. "
                    "Returns the full text of /ext/apps_data/mcp_logs/<name>.log."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Mission name whose log to read."},
                        "tail_chars": {
                            "type": "integer",
                            "description": "If set, return only the last N chars of the log.",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="js_wait_and_read",
                description=(
                    "Sleep on the host side for N seconds (usually the mission's expected duration + a buffer), "
                    "then read the log file. Use this for fire-and-forget fixed-duration missions like RF surveys. "
                    "For unknown-duration missions use js_run + periodic js_read_log instead."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Mission name."},
                        "wait_seconds": {
                            "type": "number",
                            "description": "How long to wait before reading the log.",
                        },
                    },
                    "required": ["name", "wait_seconds"],
                },
            ),
            Tool(
                name="js_stop",
                description=(
                    "Ask the Flipper to close the currently running app. Useful when an "
                    "interactive mission should end. Does NOT forcefully kill — sends the same "
                    "signal as the user pressing Back."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="js_list_missions",
                description="List JS missions currently pushed to the Flipper's mission directory.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="js_list_logs",
                description="List mission log files on the Flipper.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        args = arguments or {}
        try:
            if tool_name == "js_ensure_dirs":
                return await self._ensure_dirs()
            if tool_name == "js_push":
                return await self._push(args["name"], args["code"])
            if tool_name == "js_run":
                return await self._run(args["name"])
            if tool_name == "js_run_inline":
                return await self._run_inline(args["name"], args["code"])
            if tool_name == "js_read_log":
                return await self._read_log(args["name"], args.get("tail_chars"))
            if tool_name == "js_wait_and_read":
                return await self._wait_and_read(args["name"], float(args["wait_seconds"]))
            if tool_name == "js_stop":
                return await self._stop()
            if tool_name == "js_list_missions":
                return await self._list_missions()
            if tool_name == "js_list_logs":
                return await self._list_logs()
        except KeyError as e:
            return [TextContent(type="text", text=f"Missing required arg: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"js_runner error: {type(e).__name__}: {e}")]

        return [TextContent(type="text", text=f"Unknown js_runner tool '{tool_name}'")]

    # -- internals ------------------------------------------------------

    def _mission_path(self, name: str) -> str:
        safe = self._sanitize(name)
        return f"{MISSION_DIR}/{safe}.js"

    def _log_path(self, name: str) -> str:
        safe = self._sanitize(name)
        return f"{LOG_DIR}/{safe}.log"

    @staticmethod
    def _sanitize(name: str) -> str:
        # Strip anything that would escape the mission dir. Paranoid but cheap.
        bad = set('/\\:*?"<>|')
        out = "".join(c for c in name if c not in bad).strip()
        if not out:
            raise ValueError("mission name cannot be empty after sanitization")
        if out.endswith(".js"):
            out = out[:-3]
        return out

    async def _ensure_dirs(self) -> Sequence[TextContent]:
        # mkdir is idempotent-ish; we just try both and don't care about "already exists"
        await self.flipper.storage.mkdir("/ext/apps_data")
        await self.flipper.storage.mkdir(MISSION_DIR)
        await self.flipper.storage.mkdir(LOG_DIR)
        return [TextContent(
            type="text",
            text=f"Ensured mission dir: {MISSION_DIR}\nEnsured log dir:     {LOG_DIR}",
        )]

    async def _push(self, name: str, code: str) -> Sequence[TextContent]:
        path = self._mission_path(name)
        # Inject a small header so logs always know which mission produced them.
        # We do NOT auto-add any radio/NFC calls — that's the mission author's job.
        header = (
            f"// Mission: {name}\n"
            f"// Pushed via MCP js_runner\n"
            f"// Log path convention: {self._log_path(name)}\n"
        )
        ok = await self.flipper.storage.write(path, header + code)
        if not ok:
            return [TextContent(type="text", text=f"Failed to write mission to {path}")]
        return [TextContent(type="text", text=f"Mission written: {path} ({len(code)} chars)")]

    async def _run(self, name: str) -> Sequence[TextContent]:
        path = self._mission_path(name)
        if self.flipper.rpc is None:
            return [TextContent(type="text", text="RPC not connected; cannot launch app.")]

        # PRIMARY: CLI `js <path>` command. This works on:
        #   - Momentum (mntm-dev and later) — the documented launch path
        #   - Stock OFW with JS support (newer builds) — same CLI command
        # It executes synchronously: the CLI returns when the script finishes,
        # so we get the script's stdout in the captured output if the script
        # uses console.log() or print().
        try:
            cli_out = await self.flipper.rpc.cli_command(f"js {path}", timeout_s=120.0)
            # Heuristic: if the output indicates the command was unknown, fall through.
            if cli_out and "unknown command" not in cli_out.lower() and "command not found" not in cli_out.lower():
                return [TextContent(
                    type="text",
                    text=f"Launched via CLI 'js {path}'.\n\nCLI output:\n{cli_out[:4000]}",
                )]
        except Exception:
            pass  # fall through to app_load_file / app_start strategies

        # FALLBACK 1: app_load_file — on firmwares that route .js by extension.
        try:
            ok = await self.flipper.rpc.app_load_file(path)
            if ok:
                return [TextContent(
                    type="text",
                    text=f"Launched via app_load_file -> {path}",
                )]
        except Exception:
            pass

        # FALLBACK 2: app_start strategies for forks that expose JS as a named app.
        attempts = [
            ("js_app", path),
            ("JS", path),
            (path, ""),
        ]
        cached = getattr(self, "_winning_launch", None)
        if cached is not None:
            attempts = [cached] + [a for a in attempts if a != cached]

        last_err: Optional[Exception] = None
        for app_name, app_arg in attempts:
            try:
                ok = await self.flipper.rpc.app_start(app_name, app_arg)
                if ok:
                    self._winning_launch = (app_name, app_arg)
                    label = f"{app_name!r}" if app_name != path else "<path-as-app>"
                    return [TextContent(
                        type="text",
                        text=f"Launched via app_start({label}) -> {path}",
                    )]
            except Exception as e:
                last_err = e
                continue

        return [TextContent(
            type="text",
            text=(
                f"All launch strategies failed for {path}.\n"
                f"Tried: CLI 'js <path>', app_load_file, app_start variants. "
                f"Last error: {last_err}" if last_err else
                f"All launch strategies failed for {path}."
            ),
        )]

    async def _run_inline(self, name: str, code: str) -> Sequence[TextContent]:
        push_res = await self._push(name, code)
        run_res = await self._run(name)
        return list(push_res) + list(run_res)

    async def _read_log(self, name: str, tail_chars: Optional[int] = None) -> Sequence[TextContent]:
        path = self._log_path(name)
        content = await self.flipper.storage.read(path)
        if content is None or content == "":
            return [TextContent(type="text", text=f"(empty or missing) {path}")]
        if tail_chars and len(content) > tail_chars:
            content = "... [truncated]\n" + content[-tail_chars:]
        return [TextContent(type="text", text=f"Log {path}:\n\n{content}")]

    async def _wait_and_read(self, name: str, wait_seconds: float) -> Sequence[TextContent]:
        wait_seconds = max(0.5, min(wait_seconds, 600.0))  # clamp 0.5s .. 10min
        await asyncio.sleep(wait_seconds)
        return await self._read_log(name)

    async def _stop(self) -> Sequence[TextContent]:
        # No dedicated "stop" in protobuf layer; app_start('') is a no-op.
        # FlipperApp.stop exists but is also a light best-effort wrapper.
        if hasattr(self.flipper, "app") and hasattr(self.flipper.app, "stop"):
            try:
                await self.flipper.app.stop()
                return [TextContent(type="text", text="Sent app stop request.")]
            except Exception as e:
                return [TextContent(type="text", text=f"stop failed: {e}")]
        return [TextContent(type="text", text="No stop primitive available on this client.")]

    async def _list_missions(self) -> Sequence[TextContent]:
        entries = await self.flipper.storage.list(MISSION_DIR)
        if not entries:
            return [TextContent(type="text", text=f"(no missions pushed) {MISSION_DIR}")]
        return [TextContent(type="text", text=f"{MISSION_DIR}:\n  " + "\n  ".join(entries))]

    async def _list_logs(self) -> Sequence[TextContent]:
        entries = await self.flipper.storage.list(LOG_DIR)
        if not entries:
            return [TextContent(type="text", text=f"(no logs yet) {LOG_DIR}")]
        return [TextContent(type="text", text=f"{LOG_DIR}:\n  " + "\n  ".join(entries))]

    # -- lifecycle ------------------------------------------------------

    def get_dependencies(self) -> List[str]:
        # We call self.flipper.storage.* directly (it's on the client), so we don't
        # strictly depend on the "storage" module being loaded — but loading it is
        # strongly recommended so users have the primitive tools too.
        return []

    def requires_sd_card(self) -> bool:
        return True

    def validate_environment(self) -> tuple[bool, str]:
        return True, ""
