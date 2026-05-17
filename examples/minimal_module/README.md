# Minimal Module Example

This is the simplest possible Flipper MCP module.

## Files

```
minimal_module/
├── __init__.py
└── module.py
```

## Implementation

### module.py

```python
from typing import List, Any, Sequence
from mcp.types import Tool, TextContent
from flipper_mcp.modules.base_module import FlipperModule

class MinimalModule(FlipperModule):
    """
    Minimal example module.
    
    Demonstrates the bare minimum needed for a module.
    """
    
    @property
    def name(self) -> str:
        return "minimal"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Minimal example module"
    
    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="minimal_hello",
                description="Say hello",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Your name",
                            "default": "World"
                        }
                    }
                }
            )
        ]
    
    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        if tool_name == "minimal_hello":
            name = arguments.get("name", "World")
            return [TextContent(
                type="text",
                text=f"Hello, {name}! 👋"
            )]
        
        return [TextContent(
            type="text",
            text=f"Unknown tool: {tool_name}"
        )]
```

### __init__.py

```python
from .module import MinimalModule

__all__ = ['MinimalModule']
```

## Usage

1. Copy to `src/flipper_mcp/modules/minimal/`
2. Restart server
3. Module is auto-discovered!

Test with:
```
minimal_hello(name="Alice")
→ "Hello, Alice! 👋"
```

## What This Shows

- **Minimal implementation** - Only required methods
- **No Flipper interaction** - Doesn't use self.flipper
- **Simple tool** - One parameter, one response
- **Auto-discovery** - Just restart to load

## Next Steps

Use this as a starting point for building a new module package under `src/flipper_mcp/modules/`.
