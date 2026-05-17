"""Storage module for Flipper Zero MCP.

Wraps the FlipperStorage primitives from core/flipper_client.py into MCP tools.
Foundation module required for pushing JS scripts, pulling logs, managing SD card.
"""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class StorageModule(FlipperModule):
    """File system operations on Flipper Zero internal flash (/int) and SD card (/ext)."""

    @property
    def name(self) -> str:
        return "storage"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Read, write, list, and manage files on Flipper Zero flash and SD card"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="storage_list",
                description=(
                    "List files and directories at a path on the Flipper. "
                    "Use '/ext' for SD card root, '/int' for internal flash root. "
                    "Common subdirs: /ext/apps, /ext/apps_data, /ext/nfc, /ext/subghz, /ext/infrared, /ext/badusb."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list (e.g., '/ext', '/ext/nfc')",
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_read",
                description=(
                    "Read the contents of a file on the Flipper as text. "
                    "For binary files use storage_read_bytes. Use storage_stat first "
                    "if you are unsure of the file size (large files will be truncated "
                    "by the transport)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full file path (e.g., '/ext/apps_data/log.txt')",
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_write",
                description=(
                    "Write text content to a file on the Flipper. Overwrites if the file "
                    "exists. Parent directory must already exist — use storage_mkdir first. "
                    "For pushing JS scripts, use /ext/apps_data/mcp/<name>.js or similar."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full file path to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            ),
            Tool(
                name="storage_delete",
                description="Delete a file on the Flipper. Use with caution — no undo.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full file path to delete"},
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_mkdir",
                description=(
                    "Create a directory on the Flipper. Fails silently if the directory "
                    "already exists. Parent directories must already exist."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to create"},
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_info",
                description=(
                    "Get Flipper storage volume info (total/free/used space) for /int or /ext. "
                    "Useful before writing large files or when checking SD card health."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Volume path ('/int' for internal, '/ext' for SD)",
                            "default": "/ext",
                        },
                    },
                    "required": [],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        args = arguments or {}
        try:
            if tool_name == "storage_list":
                return await self._list(args.get("path", "/ext"))
            elif tool_name == "storage_read":
                return await self._read(args["path"])
            elif tool_name == "storage_write":
                return await self._write(args["path"], args.get("content", ""))
            elif tool_name == "storage_delete":
                return await self._delete(args["path"])
            elif tool_name == "storage_mkdir":
                return await self._mkdir(args["path"])
            elif tool_name == "storage_info":
                return await self._info(args.get("path", "/ext"))
        except Exception as e:
            return [TextContent(type="text", text=f"Storage error: {type(e).__name__}: {e}")]

        return [TextContent(type="text", text=f"Unknown storage tool '{tool_name}'")]

    async def _list(self, path: str) -> Sequence[TextContent]:
        entries = await self.flipper.storage.list(path)
        if not entries:
            return [TextContent(type="text", text=f"(empty) {path}")]
        lines = [f"Listing {path} ({len(entries)} entries):"]
        for e in entries:
            lines.append(f"  {e}")
        return [TextContent(type="text", text="\n".join(lines))]

    async def _read(self, path: str) -> Sequence[TextContent]:
        content = await self.flipper.storage.read(path)
        if content is None or content == "":
            return [TextContent(type="text", text=f"(empty or unreadable) {path}")]
        preview = content if len(content) < 8000 else content[:8000] + f"\n\n... [truncated, total {len(content)} chars]"
        return [TextContent(type="text", text=f"Contents of {path}:\n\n{preview}")]

    async def _write(self, path: str, content: str) -> Sequence[TextContent]:
        ok = await self.flipper.storage.write(path, content)
        if ok:
            return [TextContent(type="text", text=f"Wrote {len(content)} chars to {path}")]
        return [TextContent(type="text", text=f"Write failed for {path}")]

    async def _delete(self, path: str) -> Sequence[TextContent]:
        ok = await self.flipper.storage.delete(path)
        return [TextContent(
            type="text",
            text=f"Deleted {path}" if ok else f"Delete failed for {path}"
        )]

    async def _mkdir(self, path: str) -> Sequence[TextContent]:
        ok = await self.flipper.storage.mkdir(path)
        return [TextContent(
            type="text",
            text=f"Created {path}" if ok else f"mkdir failed for {path} (may already exist)"
        )]

    async def _info(self, path: str) -> Sequence[TextContent]:
        # Best-effort: not all firmwares expose a storage_info RPC.
        # Fall back to asking the FlipperClient if it exposes a helper.
        try:
            if hasattr(self.flipper, "rpc") and self.flipper.rpc is not None:
                rpc = self.flipper.rpc
                if hasattr(rpc, "storage_info"):
                    info = await rpc.storage_info(path)
                    return [TextContent(type="text", text=f"Storage {path}:\n{info}")]
            return [TextContent(type="text", text=f"storage_info RPC not exposed by this firmware/client. Use storage_list to probe.")]
        except Exception as e:
            return [TextContent(type="text", text=f"storage_info error: {e}")]

    def validate_environment(self) -> tuple[bool, str]:
        return True, ""

    def get_dependencies(self) -> List[str]:
        return []

    def requires_sd_card(self) -> bool:
        # Storage tools can work on /int too, so we don't strictly require SD.
        return False
