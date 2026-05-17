"""LLMDR CLI — boots a flipper-mcp server with LLMDR's mission modules registered.

Run:  llmdr
or:   python -m llmdr.cli
"""

import asyncio

from flipper_mcp.cli.main import main as flipper_main
from flipper_mcp.core.registry import ModuleRegistry

from .missions import MissionLibraryModule


def register_llmdr_modules(registry: ModuleRegistry) -> None:
    """Hook called by the LLMDR launcher to add LLMDR-specific modules."""
    registry.register(MissionLibraryModule)


def main() -> None:
    # For now: piggyback on flipper_mcp's CLI. The mission module gets
    # registered via the entry-point hook in pyproject.toml so flipper_mcp's
    # auto-discovery picks it up. If/when we need a separate boot path,
    # we'll add it here.
    asyncio.run(flipper_main())


if __name__ == "__main__":
    main()
