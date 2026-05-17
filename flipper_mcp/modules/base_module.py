"""Base module interface for Flipper MCP modules."""

from abc import ABC, abstractmethod
from typing import Any, List, Sequence
from mcp.types import Tool, TextContent


class FlipperModule(ABC):
    """
    Base class for all Flipper Zero MCP modules.
    
    Modules are self-contained units that:
    1. Register tools with the MCP server
    2. Handle tool execution
    3. Manage their own state
    4. Can depend on core transport layer
    
    Example:
        class MyModule(FlipperModule):
            @property
            def name(self) -> str:
                return "mymodule"
            
            def get_tools(self) -> List[Tool]:
                return [Tool(...)]
            
            async def handle_tool_call(self, tool_name, arguments):
                # Handle the tool call
                pass
    """
    
    def __init__(self, flipper_client: Any):
        """
        Initialize module with Flipper client.
        
        Args:
            flipper_client: Core Flipper RPC client (transport-agnostic)
        """
        self.flipper = flipper_client
        self.enabled = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Module name (e.g., 'badusb', 'subghz').
        
        Returns:
            Module name
        """
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """
        Module version (semver).
        
        Returns:
            Version string
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Short description of module capabilities.
        
        Returns:
            Description string
        """
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Tool]:
        """
        Return list of MCP tools this module provides.
        
        Tools are registered with the MCP server and become
        callable by AI assistants.
        
        Returns:
            List of Tool objects with name, description, and schema
        """
        pass
    
    @abstractmethod
    async def handle_tool_call(self, tool_name: str, arguments: Any) -> Sequence[TextContent]:
        """
        Handle execution of a tool from this module.
        
        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments from AI assistant
            
        Returns:
            List of TextContent responses
        """
        pass
    
    async def on_load(self) -> None:
        """
        Called when module is loaded.
        Use for initialization, validation, etc.
        """
        pass
    
    async def on_unload(self) -> None:
        """
        Called when module is unloaded.
        Use for cleanup.
        """
        pass
    
    def get_dependencies(self) -> List[str]:
        """
        Return list of module names this module depends on.
        
        Returns:
            List of module names (e.g., ['storage', 'system'])
        """
        return []
    
    def validate_environment(self) -> tuple[bool, str]:
        """
        Check if environment is suitable for this module.
        
        Returns:
            (is_valid, error_message)
        """
        return True, ""
    
    def requires_sd_card(self) -> bool:
        """
        Return whether this module requires SD card to function.
        
        Modules that need to write files to /ext/* paths should
        override this to return True. The module system will check
        SD card availability before executing operations that require it.
        
        Returns:
            True if module requires SD card, False otherwise
        """
        return False  # Default: no SD card required