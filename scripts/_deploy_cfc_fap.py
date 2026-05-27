"""One-off deploy: push cfc/dist/cfc.fap to /ext/apps/Tools/cfc.fap.
Runs against COM9 directly via FlipperClient — no MCP server needed."""

import asyncio
import sys
from pathlib import Path

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.usb import USBTransport

FAP_LOCAL = Path(__file__).resolve().parent.parent / "cfc" / "dist" / "cfc.fap"
FAP_REMOTE = "/ext/apps/Tools/cfc.fap"


async def main() -> int:
    if not FAP_LOCAL.exists():
        print(f"ERR: local FAP not found at {FAP_LOCAL}", file=sys.stderr)
        return 2
    data = FAP_LOCAL.read_bytes()
    print(f"local cfc.fap size: {len(data)} bytes")

    transport = USBTransport({"baudrate": 115200})
    client = FlipperClient(transport)
    if not await client.connect():
        print(f"ERR: connect failed: {client.last_connection_error}", file=sys.stderr)
        return 2

    try:
        client.rpc._ensure_protobuf_rpc()
        rpc = client.rpc.protobuf_rpc
        if rpc is None:
            print("ERR: protobuf_rpc unavailable", file=sys.stderr)
            return 2

        # Best-effort: exit any running CFC instance so the file is not in use.
        try:
            from flipper_mcp.core.protobuf_gen import flipper_pb2, application_pb2
            async with rpc._wire_lock:
                main_exit = flipper_pb2.Main()
                main_exit.command_id = rpc._get_next_command_id()
                main_exit.has_next = False
                main_exit.app_exit_request.CopyFrom(application_pb2.AppExitRequest())
                await rpc._send_rpc_message(main_exit)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"warn: best-effort app_exit raised {type(e).__name__}: {e}")

        ok = await rpc.storage_write(FAP_REMOTE, data)
        if not ok:
            print(f"ERR: storage_write returned False", file=sys.stderr)
            return 3
        print(f"OK: wrote {len(data)} bytes to {FAP_REMOTE}")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
