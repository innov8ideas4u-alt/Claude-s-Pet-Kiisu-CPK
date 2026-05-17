"""Minimal example module for Flipper MCP."""

from typing import List, Any, Sequence
from mcp.types import Tool, TextContent


# Note: Import path would be different if installed as separate package
# This assumes it's in the main repo
try:
    from flipper_mcp.modules.base_module import FlipperModule
except ImportError:
    # If using as standalone, adjust import
    import sys
    sys.path.insert(0, "../../src")
    from flipper_mcp.modules.base_module import FlipperModule


class MinimalModule(FlipperModule):
    """
    Minimal example module.
    
    Demonstrates the bare minimum needed for a module.
    """
    
    @property
    def name(self) -> str:
        """Module name."""
        return "minimal"
    
    @property
    def version(self) -> str:
        """Module version."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Module description."""
        return "Minimal example module"
    
    def get_tools(self) -> List[Tool]:
        """Define module tools."""
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
        """Handle tool execution."""
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
