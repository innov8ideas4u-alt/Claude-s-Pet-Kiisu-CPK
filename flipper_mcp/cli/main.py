"""Command-line interface for Flipper MCP server."""

import asyncio
import sys


def main() -> None:
    """
    Main CLI entry point.
    
    Runs the Flipper MCP server.
    """
    # IMPORTANT: When running under MCP stdio, stdout is reserved for JSON-RPC.
    # Send all human-readable logs to stderr.
    print("Starting Flipper Zero MCP Server...", file=sys.stderr)
    
    try:
        from flipper_mcp.core.server import main as server_main
        asyncio.run(server_main())
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        try:
            print(f"\n❌ Server error: {e}", file=sys.stderr)
        except Exception:
            # Best-effort only (stdio may be closed by client).
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
