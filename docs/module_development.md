# Module Development Guide

This repo implements a small module system that allows new MCP tools to be added without changing the core server.

## How module discovery works

At startup, `flipper_mcp.core.registry.ModuleRegistry` scans the `flipper_mcp.modules` package and looks for subpackages that contain:

- a `module.py` file
- at least one concrete `FlipperModule` subclass in that file

The registry instantiates the module class with a single argument: the `FlipperClient`.

## Create a new module (in this repo)

1. Create a new package:

```bash
mkdir -p src/flipper_mcp/modules/mymodule
touch src/flipper_mcp/modules/mymodule/__init__.py
touch src/flipper_mcp/modules/mymodule/module.py
```

2. Implement `FlipperModule`:

```python
from typing import Any, List, Sequence

from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class MyModule(FlipperModule):
    @property
    def name(self) -> str:
        return "mymodule"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Example module"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="mymodule_echo",
                description="Echo back the provided text",
                inputSchema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ]

    async def handle_tool_call(self, tool_name: str, arguments: Any) -> Sequence[TextContent]:
        if tool_name == "mymodule_echo":
            return [TextContent(type="text", text=arguments["text"])]
        return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
```

3. Export the module from `__init__.py` (optional, but conventional):

```python
from .module import MyModule

__all__ = ["MyModule"]
```

4. Run the server and verify the tool appears in `list_tools`:

```bash
python -m flipper_mcp.cli.main
```

## Tool naming conventions

- Tools should be named `{module}_{action}` to avoid collisions.
- Example: `badusb_generate`, `music_play`, `systeminfo_get`.

## Working with the Flipper

Modules receive a `FlipperClient` via `self.flipper`.

Common APIs:

- `await self.flipper.get_device_info()`
- `await self.flipper.check_sd_card_available()`
- `await self.flipper.storage.list("/ext")`
- `await self.flipper.storage.write("/ext/path/file.txt", "content")`

## SD card requirements

If your module needs to read/write under `/ext/*`, it should:

- implement `requires_sd_card()` and return `True`
- check `await self.flipper.check_sd_card_available()` before operations and return a helpful error if unavailable

## Testing

Unit tests live under `tests/`. See existing tests in:

- `tests/modules/`
- `tests/core/`

Run tests with:

```bash
pytest
```





