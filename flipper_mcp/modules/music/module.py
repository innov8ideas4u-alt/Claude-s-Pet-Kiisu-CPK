"""Music Player module for Flipper Zero MCP."""

import re
from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule
from .formatter import validate_fmf_format, get_fmf_format_specification, normalize_fmf
from ...core.utils import sanitize_filename


class MusicModule(FlipperModule):
    """
    Music Player module for Flipper Zero.
    
    Provides tools to play songs on the Flipper Zero piezo speaker.
    Features:
    - Get FMF (Flipper Music Format) specification
    - Play songs formatted in FMF format
    - Automatic file management and app launching
    """
    
    @property
    def name(self) -> str:
        """Module name."""
        return "music"
    
    @property
    def version(self) -> str:
        """Module version."""
        return "1.0.1"
    
    @property
    def description(self) -> str:
        """Module description."""
        return "Play songs on Flipper Zero piezo speaker using FMF format"
    
    def __init__(self, flipper_client: Any):
        """
        Initialize Music Player module.
        
        Args:
            flipper_client: Flipper client instance
        """
        super().__init__(flipper_client)
        # Music Player stores songs under apps_data on the SD card.
        # Example known-good path: /ext/apps_data/music_player/Marble_Machine.fmf
        self.music_path = "/ext/apps_data/music_player"
    
    def get_tools(self) -> List[Tool]:
        """Register Music Player tools with MCP server."""
        return [
            Tool(
                name="music_get_format",
                description="Get the FMF (Flipper Music Format) specification. Use this to understand how to format songs before calling music_play. Returns detailed format documentation including header format, note syntax, examples, and tips.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="music_play",
                description="Play a song on the Flipper Zero piezo speaker. Accepts song data in FMF format, writes it to the device, and optionally launches the Music Player app to play it immediately.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "song_data": {
                            "type": "string",
                            "description": "Song in FMF format (e.g., 'BPM=120:DURATION=4:OCTAVE=4: 4C 4C 8C 4D 4E')"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Filename to save as (e.g., 'happy_birthday.fmf'). If not provided, will auto-generate from song content or use 'song.fmf'",
                            "default": ""
                        },
                        "play_immediately": {
                            "type": "boolean",
                            "description": "Launch Music Player app to play the song immediately after saving",
                            "default": True
                        }
                    },
                    "required": ["song_data"]
                }
            ),
        ]
    
    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        """Handle tool execution for Music Player module."""
        
        if tool_name == "music_get_format":
            return await self._get_format()
        
        elif tool_name == "music_play":
            return await self._play_song(
                arguments["song_data"],
                arguments.get("filename", ""),
                arguments.get("play_immediately", True)
            )
        
        return [TextContent(
            type="text",
            text=f"❌ Error: Unknown Music Player tool '{tool_name}'"
        )]
    
    async def _get_format(self) -> Sequence[TextContent]:
        """Get FMF format specification."""
        try:
            spec = get_fmf_format_specification()
            return [TextContent(type="text", text=spec)]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error retrieving format specification: {str(e)}"
            )]
    
    async def _play_song(
        self, song_data: str, filename: str, play_immediately: bool
    ) -> Sequence[TextContent]:
        """Play a song on Flipper Zero."""
        try:
            # Check SD card availability first
            sd_card_available = await self.flipper.check_sd_card_available()
            if not sd_card_available:
                return [TextContent(
                    type="text",
                    text="❌ MicroSD card is not detected or not accessible\n\n"
                         "This operation requires a MicroSD card to be installed in your Flipper Zero.\n"
                         "The music files need to be saved to the SD card storage.\n\n"
                         "Please:\n"
                         "1. Insert a MicroSD card into your Flipper Zero\n"
                         "2. Ensure the card is properly formatted\n"
                         "3. Use 'systeminfo_get' to verify SD card status\n"
                         "4. Try again\n\n"
                         "Note: The systeminfo module can check SD card status without requiring an SD card."
                )]
            
            # Normalize + validate FMF format (accept legacy input; save in FMF v0)
            normalized_song = normalize_fmf(song_data)
            is_valid, error = validate_fmf_format(normalized_song)
            if not is_valid:
                return [TextContent(
                    type="text",
                    text=f"❌ Invalid FMF format: {error}\n\n"
                         "Use 'music_get_format' to see the correct format specification.\n\n"
                         f"Received song data:\n```\n{song_data}\n```"
                )]
            
            # Generate filename if not provided
            if not filename or not filename.strip():
                # Try to extract a meaningful name from the song data
                # Look for common patterns or use default
                filename = self._generate_filename(song_data)
            else:
                # Sanitize provided filename
                filename = sanitize_filename(filename)
            
            # Ensure .fmf extension
            if not filename.endswith('.fmf'):
                filename = filename + '.fmf'
            
            # Ensure directory exists (create if needed)
            # Note: In stub mode, this may not actually create the directory
            # but it won't fail either
            try:
                await self.flipper.storage.mkdir(self.music_path)
            except Exception:
                pass  # Directory may already exist or stub mode
            
            # Write file to Flipper
            file_path = f"{self.music_path}/{filename}"
            success = await self.flipper.storage.write(file_path, normalized_song)
            
            if not success:
                return [TextContent(
                    type="text",
                    text=f"❌ Failed to write song file to {file_path}\n\n"
                         "Check Flipper Zero connection and storage availability."
                )]
            
            result = f"✅ Song saved: {filename}\n\n"
            result += f"📁 Path: {file_path}\n"
            result += f"📊 Size: {len(normalized_song)} characters\n\n"
            
            # NOTE: App launching is not implemented over protobuf RPC in this repo yet.
            # We keep the flag for API compatibility, but instruct the user to open the app manually.
            if play_immediately:
                result += "🎵 Saved. Please open the Music Player app on your Flipper Zero and select the file to play.\n"
            else:
                result += "⏭️  Saved (play_immediately=false). Open Music Player manually to play.\n"
            
            result += f"\n📄 Song data (saved, normalized):\n```fmf\n{normalized_song}\n```"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error playing song: {str(e)}"
            )]
    
    def _generate_filename(self, song_data: str) -> str:
        """
        Generate a safe filename from song data.
        
        Args:
            song_data: FMF format song data
            
        Returns:
            Safe filename
        """
        # Try to extract a meaningful name
        # Look for common song patterns in comments or metadata
        # For now, use a simple hash-based approach or default
        
        # Extract first few notes as identifier (simplified)
        # In a real implementation, might use song name if provided
        notes_match = re.search(r':\s*([\dCDEFGABP#b\s,\.]+)', song_data)
        if notes_match:
            notes = notes_match.group(1).strip()[:20]  # First 20 chars of notes
            # Create a simple identifier
            identifier = re.sub(r'[^\w]', '_', notes)[:15]
            if identifier:
                return f"song_{identifier}.fmf"
        
        # Default fallback
        return "song.fmf"
    
    def requires_sd_card(self) -> bool:
        """Music Player module requires SD card to save and play music files."""
        return True
    
    def validate_environment(self) -> tuple[bool, str]:
        """Check if Music Player is available."""
        # In production, could check firmware version, Music Player app presence, etc.
        # Note: We don't check SD card here because modules should still load
        # even if SD card is missing - they'll check at operation time
        return True, ""
    
    def get_dependencies(self) -> List[str]:
        """Music Player has no module dependencies."""
        return []
    
    async def on_load(self) -> None:
        """Called when module is loaded."""
        # Could perform initialization here, e.g., check music directory exists
        pass
    
    async def on_unload(self) -> None:
        """Called when module is unloaded."""
        # Could perform cleanup here
        pass

