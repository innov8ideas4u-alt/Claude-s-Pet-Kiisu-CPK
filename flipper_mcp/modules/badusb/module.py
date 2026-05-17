"""BadUSB module for Flipper Zero MCP."""

from typing import Any, List, Sequence
import difflib
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule
from .generator import DuckyScriptGenerator
from .validator import ScriptValidator


class BadUSBModule(FlipperModule):
    """
    BadUSB module for keyboard/mouse emulation.
    
    Provides natural language → DuckyScript generation and execution.
    This is the Phase 1 reference implementation showing how modules work.
    
    Features:
    - List, read, and manage BadUSB scripts
    - Generate DuckyScript from natural language
    - Validate scripts for safety
    - Execute scripts on target device
    - Complete workflows (generate + validate + execute)
    """
    
    @property
    def name(self) -> str:
        """Module name."""
        return "badusb"
    
    @property
    def version(self) -> str:
        """Module version."""
        return "1.1.0"
    
    @property
    def description(self) -> str:
        """Module description."""
        return "BadUSB keyboard/mouse emulation with AI-powered script generation"
    
    def __init__(self, flipper_client: Any):
        """
        Initialize BadUSB module.
        
        Args:
            flipper_client: Flipper client instance
        """
        super().__init__(flipper_client)
        self.generator = DuckyScriptGenerator()
        self.validator = ScriptValidator()
        self.badusb_path = "/ext/badusb"
    
    def get_tools(self) -> List[Tool]:
        """Register BadUSB tools with MCP server."""
        return [
            Tool(
                name="badusb_list",
                description="List all BadUSB scripts stored on Flipper Zero",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="badusb_read",
                description="Read contents of a BadUSB script",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Script filename (e.g., 'test.txt')"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            Tool(
                name="badusb_generate",
                description="Generate BadUSB DuckyScript from natural language description",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What the script should do"
                        },
                        "target_os": {
                            "type": "string",
                            "enum": ["windows", "macos", "linux"],
                            "description": "Target operating system",
                            "default": "windows"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Script filename to save as",
                            "default": "ai_generated.txt"
                        }
                    },
                    "required": ["description"]
                }
            ),
            Tool(
                name="badusb_validate",
                description="Validate a BadUSB DuckyScript payload for safety (no device changes)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "DuckyScript content to validate"
                        }
                    },
                    "required": ["content"]
                },
            ),
            Tool(
                name="badusb_write",
                description="Write/overwrite a BadUSB script on the Flipper SD card (validated first)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Script filename to write (e.g., 'demo.txt')"
                        },
                        "content": {
                            "type": "string",
                            "description": "DuckyScript content to save"
                        },
                        "confirm_overwrite": {
                            "type": "boolean",
                            "description": "Must be true to overwrite if the file already exists",
                            "default": False
                        }
                    },
                    "required": ["filename", "content"]
                },
            ),
            Tool(
                name="badusb_delete",
                description="Delete a BadUSB script from the Flipper SD card (destructive)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Script filename to delete"
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "Must be true (safety confirmation)",
                            "default": False
                        }
                    },
                    "required": ["filename", "confirm"]
                },
            ),
            Tool(
                name="badusb_diff",
                description="Show a unified diff between an existing script and proposed new content (no device changes)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Existing script filename on the Flipper"
                        },
                        "proposed_content": {
                            "type": "string",
                            "description": "Proposed new DuckyScript content"
                        }
                    },
                    "required": ["filename", "proposed_content"]
                },
            ),
            Tool(
                name="badusb_rename",
                description="Rename a BadUSB script (implemented as read+write+delete; destructive)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "old_filename": {
                            "type": "string",
                            "description": "Existing script filename"
                        },
                        "new_filename": {
                            "type": "string",
                            "description": "New script filename"
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "Must be true (safety confirmation)",
                            "default": False
                        }
                    },
                    "required": ["old_filename", "new_filename", "confirm"]
                },
            ),
            Tool(
                name="badusb_execute",
                description="Execute a BadUSB script on the target device. WARNING: This will run the script immediately!",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Script filename to execute"
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "Must be true (safety confirmation)",
                            "default": False
                        }
                    },
                    "required": ["filename", "confirm"]
                }
            ),
            Tool(
                name="badusb_workflow",
                description="Complete workflow: generate, validate, save, and optionally execute a BadUSB script",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What the script should do"
                        },
                        "target_os": {
                            "type": "string",
                            "enum": ["windows", "macos", "linux"],
                            "description": "Target operating system",
                            "default": "windows"
                        },
                        "execute": {
                            "type": "boolean",
                            "description": "Execute after generation (requires manual confirmation)",
                            "default": False
                        }
                    },
                    "required": ["description"]
                }
            ),
        ]
    
    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        """Handle tool execution for BadUSB module."""
        
        if tool_name == "badusb_list":
            return await self._list_scripts()
        
        elif tool_name == "badusb_read":
            return await self._read_script(arguments["filename"])
        
        elif tool_name == "badusb_generate":
            return await self._generate_script(
                arguments["description"],
                arguments.get("target_os", "windows"),
                arguments.get("filename", "ai_generated.txt")
            )

        elif tool_name == "badusb_validate":
            return await self._validate_script(arguments["content"])

        elif tool_name == "badusb_write":
            return await self._write_script(
                arguments["filename"],
                arguments["content"],
                arguments.get("confirm_overwrite", False),
            )

        elif tool_name == "badusb_delete":
            return await self._delete_script(
                arguments["filename"],
                arguments.get("confirm", False),
            )

        elif tool_name == "badusb_diff":
            return await self._diff_script(
                arguments["filename"],
                arguments["proposed_content"],
            )

        elif tool_name == "badusb_rename":
            return await self._rename_script(
                arguments["old_filename"],
                arguments["new_filename"],
                arguments.get("confirm", False),
            )
        
        elif tool_name == "badusb_execute":
            return await self._execute_script(
                arguments["filename"],
                arguments.get("confirm", False)
            )
        
        elif tool_name == "badusb_workflow":
            return await self._workflow(
                arguments["description"],
                arguments.get("target_os", "windows"),
                arguments.get("execute", False)
            )
        
        return [TextContent(
            type="text",
            text=f"❌ Error: Unknown BadUSB tool '{tool_name}'"
        )]

    def _sanitize_filename(self, filename: str) -> tuple[bool, str]:
        """
        Prevent path traversal / unexpected paths.

        BadUSB scripts live under `/ext/badusb` and should be simple filenames.
        """
        if not filename or not isinstance(filename, str):
            return False, "Filename must be a non-empty string."
        if "/" in filename or "\\" in filename:
            return False, "Filename must not contain path separators."
        if filename.startswith("."):
            return False, "Filename must not start with '.'."
        return True, ""

    async def _ensure_sd_or_explain(self) -> Sequence[TextContent] | None:
        """Shared SD card check with consistent user messaging."""
        sd_card_available = await self.flipper.check_sd_card_available()
        if sd_card_available:
            return None
        return [TextContent(
            type="text",
            text="❌ MicroSD card is not detected or not accessible\n\n"
                 "This operation requires a MicroSD card to be installed in your Flipper Zero.\n"
                 "BadUSB scripts are stored on the SD card.\n\n"
                 "Please:\n"
                 "1. Insert a MicroSD card into your Flipper Zero\n"
                 "2. Ensure the card is properly formatted\n"
                 "3. Use 'systeminfo_get' to verify SD card status\n"
                 "4. Try again\n\n"
                 "Note: The systeminfo module can check SD card status without requiring an SD card."
        )]
    
    async def _list_scripts(self) -> Sequence[TextContent]:
        """List all BadUSB scripts."""
        try:
            sd_msg = await self._ensure_sd_or_explain()
            if sd_msg:
                return sd_msg
            
            files = await self.flipper.storage.list(self.badusb_path)
            
            if not files:
                return [TextContent(
                    type="text",
                    text=f"📁 No BadUSB scripts found in {self.badusb_path}\n\n"
                         "Use 'badusb_generate' to create new scripts."
                )]
            
            result = f"📁 BadUSB Scripts ({len(files)}):\n\n"
            for f in files:
                result += f"  • {f}\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error listing scripts: {str(e)}"
            )]
    
    async def _read_script(self, filename: str) -> Sequence[TextContent]:
        """Read script contents."""
        try:
            ok, err = self._sanitize_filename(filename)
            if not ok:
                return [TextContent(type="text", text=f"❌ Invalid filename: {err}")]

            sd_msg = await self._ensure_sd_or_explain()
            if sd_msg:
                return sd_msg
            
            path = f"{self.badusb_path}/{filename}"
            content = await self.flipper.storage.read(path)
            
            return [TextContent(
                type="text",
                text=f"📄 Contents of {filename}:\n\n```duckyscript\n{content}\n```"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error reading script: {str(e)}"
            )]
    
    async def _generate_script(
        self, description: str, target_os: str, filename: str
    ) -> Sequence[TextContent]:
        """Generate and save BadUSB script."""
        try:
            ok, err = self._sanitize_filename(filename)
            if not ok:
                return [TextContent(type="text", text=f"❌ Invalid filename: {err}")]

            sd_msg = await self._ensure_sd_or_explain()
            if sd_msg:
                return sd_msg
            
            # Generate script
            script = self.generator.generate(description, target_os)
            
            # Validate for safety
            is_valid, error = self.validator.validate(script)
            if not is_valid:
                return [TextContent(
                    type="text",
                    text=f"❌ Script validation failed: {error}\n\n"
                         f"Generated script:\n```duckyscript\n{script}\n```"
                )]
            
            # Save to Flipper
            path = f"{self.badusb_path}/{filename}"
            await self.flipper.storage.write(path, script)
            
            result = f"✅ BadUSB script generated: {filename}\n\n"
            result += f"📝 Description: {description}\n"
            result += f"💻 Target OS: {target_os}\n"
            if error:  # Warnings
                result += f"\n{error}\n"
            result += f"\n📄 Script:\n```duckyscript\n{script}\n```"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error generating script: {str(e)}"
            )]

    async def _validate_script(self, content: str) -> Sequence[TextContent]:
        """Validate script content for safety (no device changes)."""
        try:
            is_valid, msg = self.validator.validate(content)
            if not is_valid:
                return [TextContent(
                    type="text",
                    text=f"❌ Validation failed: {msg}\n\n```duckyscript\n{content}\n```"
                )]
            out = "✅ Validation passed."
            if msg:
                out += f"\n\n{msg}"
            return [TextContent(type="text", text=out)]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error validating script: {str(e)}")]

    async def _write_script(self, filename: str, content: str, confirm_overwrite: bool) -> Sequence[TextContent]:
        """Write (or overwrite) a script after validation."""
        ok, err = self._sanitize_filename(filename)
        if not ok:
            return [TextContent(type="text", text=f"❌ Invalid filename: {err}")]

        sd_msg = await self._ensure_sd_or_explain()
        if sd_msg:
            return sd_msg

        try:
            is_valid, msg = self.validator.validate(content)
            if not is_valid:
                return [TextContent(
                    type="text",
                    text=f"❌ Script validation failed: {msg}\n\n```duckyscript\n{content}\n```"
                )]

            # If file exists, require confirm_overwrite.
            existing = await self.flipper.storage.list(self.badusb_path)
            if filename in (existing or []) and not confirm_overwrite:
                return [TextContent(
                    type="text",
                    text="❌ Refusing to overwrite existing script without confirmation.\n\n"
                         f"File exists: {filename}\n\n"
                         "Re-run with confirm_overwrite=true to overwrite."
                )]

            path = f"{self.badusb_path}/{filename}"
            success = await self.flipper.storage.write(path, content)
            if not success:
                return [TextContent(type="text", text=f"❌ Failed to write {filename} to {self.badusb_path}.")]

            out = f"✅ Wrote BadUSB script: {filename}\n\nPath: {path}\n"
            if msg:
                out += f"\n{msg}\n"
            return [TextContent(type="text", text=out)]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error writing script: {str(e)}")]

    async def _delete_script(self, filename: str, confirm: bool) -> Sequence[TextContent]:
        """Delete a script (destructive)."""
        if not confirm:
            return [TextContent(
                type="text",
                text="❌ Delete blocked: 'confirm' parameter must be true\n\n"
                     "⚠️  WARNING: This will permanently delete the script from the SD card."
            )]

        ok, err = self._sanitize_filename(filename)
        if not ok:
            return [TextContent(type="text", text=f"❌ Invalid filename: {err}")]

        sd_msg = await self._ensure_sd_or_explain()
        if sd_msg:
            return sd_msg

        try:
            path = f"{self.badusb_path}/{filename}"
            success = await self.flipper.storage.delete(path)
            if success:
                return [TextContent(type="text", text=f"✅ Deleted: {filename}\nPath: {path}")]
            return [TextContent(type="text", text=f"❌ Failed to delete: {filename}\nPath: {path}")]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error deleting script: {str(e)}")]

    async def _diff_script(self, filename: str, proposed_content: str) -> Sequence[TextContent]:
        """Show a unified diff between an existing script and proposed content."""
        ok, err = self._sanitize_filename(filename)
        if not ok:
            return [TextContent(type="text", text=f"❌ Invalid filename: {err}")]

        sd_msg = await self._ensure_sd_or_explain()
        if sd_msg:
            return sd_msg

        try:
            path = f"{self.badusb_path}/{filename}"
            existing = await self.flipper.storage.read(path)
            existing_lines = (existing or "").splitlines(keepends=True)
            proposed_lines = (proposed_content or "").splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(
                existing_lines,
                proposed_lines,
                fromfile=f"{filename} (current)",
                tofile=f"{filename} (proposed)",
            ))
            if not diff:
                return [TextContent(type="text", text="✅ No changes (proposed content matches existing).")]
            return [TextContent(type="text", text=f"```diff\n{diff}\n```")]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error diffing script: {str(e)}")]

    async def _rename_script(self, old_filename: str, new_filename: str, confirm: bool) -> Sequence[TextContent]:
        """Rename a script via read+write+delete (destructive)."""
        if not confirm:
            return [TextContent(
                type="text",
                text="❌ Rename blocked: 'confirm' parameter must be true\n\n"
                     "⚠️  WARNING: This performs a write+delete operation on the SD card."
            )]

        ok1, err1 = self._sanitize_filename(old_filename)
        if not ok1:
            return [TextContent(type="text", text=f"❌ Invalid old_filename: {err1}")]
        ok2, err2 = self._sanitize_filename(new_filename)
        if not ok2:
            return [TextContent(type="text", text=f"❌ Invalid new_filename: {err2}")]
        if old_filename == new_filename:
            return [TextContent(type="text", text="❌ old_filename and new_filename are the same.")]

        sd_msg = await self._ensure_sd_or_explain()
        if sd_msg:
            return sd_msg

        try:
            old_path = f"{self.badusb_path}/{old_filename}"
            new_path = f"{self.badusb_path}/{new_filename}"
            content = await self.flipper.storage.read(old_path)
            if content == "":
                return [TextContent(type="text", text=f"❌ Could not read source file: {old_filename}")]

            # Refuse to overwrite destination without explicit overwrite flow.
            existing = await self.flipper.storage.list(self.badusb_path)
            if new_filename in (existing or []):
                return [TextContent(
                    type="text",
                    text=f"❌ Refusing to rename over an existing destination: {new_filename}\n\n"
                         "Delete it first, or use badusb_write with confirm_overwrite=true."
                )]

            wrote = await self.flipper.storage.write(new_path, content)
            if not wrote:
                return [TextContent(type="text", text=f"❌ Failed to write destination file: {new_filename}")]

            deleted = await self.flipper.storage.delete(old_path)
            if not deleted:
                return [TextContent(
                    type="text",
                    text=f"⚠️  Wrote destination but failed to delete source.\n\n"
                         f"Destination: {new_filename}\nSource still exists: {old_filename}"
                )]

            return [TextContent(
                type="text",
                text=f"✅ Renamed script.\n\nFrom: {old_filename}\nTo: {new_filename}"
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error renaming script: {str(e)}")]
    
    async def _execute_script(
        self, filename: str, confirm: bool
    ) -> Sequence[TextContent]:
        """Execute BadUSB script."""
        if not confirm:
            return [TextContent(
                type="text",
                text="❌ Execution blocked: 'confirm' parameter must be true\n\n"
                     "⚠️  WARNING: This will execute the script immediately!\n"
                     "Make sure the target device is ready and you understand what the script does."
            )]
        
        try:
            ok, err = self._sanitize_filename(filename)
            if not ok:
                return [TextContent(type="text", text=f"❌ Invalid filename: {err}")]

            sd_msg = await self._ensure_sd_or_explain()
            if sd_msg:
                return sd_msg
            
            path = f"{self.badusb_path}/{filename}"
            
            # Read script first (for display)
            content = await self.flipper.storage.read(path)
            
            # Execute
            success = await self.flipper.app.launch("BadUsb", path)
            
            result = f"⚡ Executing: {filename}\n\n"
            result += f"📄 Script:\n```duckyscript\n{content}\n```\n\n"
            
            if success:
                result += (
                    "✅ BadUSB app launch request sent.\n\n"
                    "⚠️  Important:\n"
                    "- BadUSB may switch the Flipper’s USB mode to HID, which can disconnect the USB serial/RPC session.\n"
                    "- If you don’t see keystrokes, open **BadUSB** on the Flipper manually and run the script from the device UI.\n"
                )
            else:
                result += (
                    "❌ Could not launch BadUSB app via RPC.\n\n"
                    "Try:\n"
                    "- Ensure the Flipper is connected and unlocked\n"
                    "- Then launch **BadUSB** manually on the device and select the script\n"
                )
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error executing script: {str(e)}"
            )]
    
    async def _workflow(
        self, description: str, target_os: str, execute: bool
    ) -> Sequence[TextContent]:
        """Complete workflow: generate, validate, save, and optionally execute."""
        try:
            sd_msg = await self._ensure_sd_or_explain()
            if sd_msg:
                return sd_msg
            
            result = "🤖 BadUSB Workflow\n"
            result += "=" * 50 + "\n\n"
            
            # Step 1: Generate
            result += "📝 Step 1: Generating script...\n"
            script = self.generator.generate(description, target_os)
            result += f"   ✓ Generated {len(script)} characters\n\n"
            
            # Step 2: Validate
            result += "🔍 Step 2: Validating...\n"
            is_valid, error = self.validator.validate(script)
            
            if not is_valid:
                result += f"   ❌ Validation failed: {error}\n\n"
                result += f"Generated script:\n```duckyscript\n{script}\n```"
                return [TextContent(type="text", text=result)]
            
            result += "   ✅ Valid"
            if error:  # Warnings
                result += f" (with warnings: {error})"
            result += "\n\n"
            
            # Step 3: Save
            result += "💾 Step 3: Saving...\n"
            filename = "ai_workflow.txt"
            path = f"{self.badusb_path}/{filename}"
            await self.flipper.storage.write(path, script)
            result += f"   ✓ Saved as {filename}\n\n"
            
            # Step 4: Execute (optional)
            if execute:
                result += "⚡ Step 4: Executing...\n"
                result += "   ⚠️  NOTE: Execution requires manual confirmation for safety\n"
                result += "   Use 'badusb_execute' with confirm=true to run\n\n"
            else:
                result += "⏭️  Step 4: Execution skipped (execute=false)\n\n"
            
            result += "=" * 50 + "\n"
            result += f"📄 Generated Script:\n```duckyscript\n{script}\n```\n\n"
            result += "💡 Next steps:\n"
            result += f"   • Review the script above\n"
            result += f"   • Use 'badusb_execute' to run: badusb_execute(filename='{filename}', confirm=true)\n"
            result += f"   • Or edit manually on Flipper Zero\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error in workflow: {str(e)}"
            )]
    
    def requires_sd_card(self) -> bool:
        """BadUSB module requires SD card to store and execute scripts."""
        return True
    
    def validate_environment(self) -> tuple[bool, str]:
        """Check if BadUSB is available."""
        # In production, could check firmware version, BadUSB app presence, etc.
        # Note: We don't check SD card here because modules should still load
        # even if SD card is missing - they'll check at operation time
        return True, ""
    
    def get_dependencies(self) -> List[str]:
        """BadUSB has no module dependencies."""
        return []
    
    async def on_load(self) -> None:
        """Called when module is loaded."""
        # Could perform initialization here
        pass
    
    async def on_unload(self) -> None:
        """Called when module is unloaded."""
        # Could perform cleanup here
        pass
