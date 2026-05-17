"""Module registry for discovering and managing Flipper MCP modules."""

import sys
from typing import Any, Dict, List, Sequence, Type
from importlib import import_module
import inspect
import pkgutil

from mcp.types import Tool, TextContent
from ..modules.base_module import FlipperModule


class ModuleRegistry:
    """
    Central registry for all Flipper MCP modules.
    
    Handles loading, initialization, and lifecycle management.
    Automatically discovers modules in the modules package.
    """
    
    def __init__(self, flipper_client: Any):
        """
        Initialize module registry.
        
        Args:
            flipper_client: Flipper client instance to pass to modules
        """
        self.flipper = flipper_client
        self.modules: Dict[str, FlipperModule] = {}
        self.load_order: List[str] = []
    
    def discover_modules(self, search_paths: List[str] | None = None) -> None:
        """
        Auto-discover modules in specified paths.
        
        By default, searches src/flipper_mcp/modules/ for module packages.
        Each module package should contain a module.py with a FlipperModule subclass.
        
        Args:
            search_paths: Optional list of package paths to search
        """
        if search_paths is None:
            search_paths = ['flipper_mcp.modules']
        
        for path in search_paths:
            try:
                package = import_module(path)
                package_dir = package.__path__
                
                # Iterate through subpackages
                for importer, modname, ispkg in pkgutil.iter_modules(package_dir):
                    if not ispkg or modname.startswith('_'):
                        continue
                    
                    try:
                        # Try to import module.py from the package
                        module_path = f"{path}.{modname}.module"
                        submodule = import_module(module_path)
                        
                        # Find FlipperModule subclasses
                        for name, obj in inspect.getmembers(submodule, inspect.isclass):
                            if (issubclass(obj, FlipperModule) and 
                                obj is not FlipperModule and
                                not inspect.isabstract(obj)):
                                
                                # Found a module class!
                                self.register_module(obj)
                                
                    except (ImportError, AttributeError) as e:
                        print(f"⚠️  Could not load module {modname}: {e}", file=sys.stderr)
                        
            except ImportError as e:
                print(f"⚠️  Could not import package {path}: {e}", file=sys.stderr)

    def discover_entry_point_modules(self, group: str = "flipper_mcp.modules") -> None:
        """
        Discover modules contributed by other installed packages via
        setuptools entry-points.

        This is how external projects (e.g. LLMDR) register their own
        FlipperModule classes without flipper-mcp needing to import them
        explicitly. They declare in pyproject.toml:

            [project.entry-points."flipper_mcp.modules"]
            my_module = "my_pkg.modules:MyModuleClass"

        Args:
            group: Entry-point group name. Defaults to 'flipper_mcp.modules'.
        """
        try:
            from importlib.metadata import entry_points
            try:
                eps = entry_points(group=group)
            except TypeError:
                # Older API: entry_points() returns a dict-like.
                eps = entry_points().get(group, [])
        except ImportError:
            print("⚠️  importlib.metadata not available; skipping entry-point discovery", file=sys.stderr)
            return

        for ep in eps:
            try:
                cls = ep.load()
                if (inspect.isclass(cls)
                    and issubclass(cls, FlipperModule)
                    and cls is not FlipperModule
                    and not inspect.isabstract(cls)):
                    self.register_module(cls)
                else:
                    print(f"⚠️  Entry-point {ep.name!r} did not resolve to a FlipperModule subclass", file=sys.stderr)
            except Exception as e:
                print(f"⚠️  Failed to load entry-point {ep.name!r}: {e}", file=sys.stderr)

    def register_module(self, module_class: Type[FlipperModule]) -> None:
        """
        Register a module class.
        
        Args:
            module_class: FlipperModule subclass to register
        """
        try:
            # Instantiate the module
            module = module_class(self.flipper)
            
            # Validate environment
            is_valid, error = module.validate_environment()
            if not is_valid:
                print(f"⚠️  Module {module.name} not loaded: {error}", file=sys.stderr)
                return
            
            # Check dependencies
            missing_deps = [
                dep for dep in module.get_dependencies() 
                if dep not in self.modules
            ]
            
            if missing_deps:
                print(f"⚠️  Module {module.name} missing dependencies: {missing_deps}", file=sys.stderr)
                return
            
            # Register module
            self.modules[module.name] = module
            self.load_order.append(module.name)
            print(f"✓ Registered module: {module.name} v{module.version}", file=sys.stderr)
            
        except Exception as e:
            print(f"✗ Failed to register module: {e}", file=sys.stderr)
    
    async def load_all(self) -> None:
        """Load all registered modules."""
        for name in self.load_order:
            module = self.modules[name]
            try:
                await module.on_load()
                print(f"✓ Loaded: {name}", file=sys.stderr)
            except Exception as e:
                print(f"✗ Failed to load {name}: {e}", file=sys.stderr)
                module.enabled = False
    
    async def unload_all(self) -> None:
        """Unload all modules."""
        for name in reversed(self.load_order):
            module = self.modules[name]
            try:
                await module.on_unload()
            except Exception as e:
                print(f"⚠️  Error unloading {name}: {e}", file=sys.stderr)
    
    def get_all_tools(self) -> List[Tool]:
        """
        Collect tools from all enabled modules.
        
        Returns:
            List of all tools from enabled modules
        """
        tools = []
        for module in self.modules.values():
            if module.enabled:
                try:
                    tools.extend(module.get_tools())
                except Exception as e:
                    print(f"⚠️  Error getting tools from {module.name}: {e}", file=sys.stderr)
        return tools
    
    async def route_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        """
        Route tool call to appropriate module.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Find which module owns this tool
        for module in self.modules.values():
            if not module.enabled:
                continue
            
            try:
                tool_names = [tool.name for tool in module.get_tools()]
                if tool_name in tool_names:
                    return await module.handle_tool_call(tool_name, arguments)
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"❌ Error in module {module.name}: {str(e)}"
                )]
        
        # Tool not found
        return [TextContent(
            type="text",
            text=f"❌ Error: Tool '{tool_name}' not found in any module"
        )]
    
    def get_module(self, name: str) -> FlipperModule | None:
        """
        Get module by name.
        
        Args:
            name: Module name
            
        Returns:
            Module instance or None
        """
        return self.modules.get(name)
    
    def list_modules(self) -> List[Dict[str, Any]]:
        """
        List all registered modules.
        
        Returns:
            List of module info dicts
        """
        return [
            {
                "name": module.name,
                "version": module.version,
                "description": module.description,
                "enabled": module.enabled,
                "tools": len(module.get_tools()) if module.enabled else 0
            }
            for module in self.modules.values()
        ]
