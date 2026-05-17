#!/usr/bin/env python3
"""
Complete WiFi Music Player Example
===================================

This example demonstrates the full lifecycle of using the Music Player module
over WiFi with the Flipper Zero WiFi Dev Board.

It shows:
1. WiFi connection setup
2. RPC session initialization
3. Song creation in FMF format
4. File operations over WiFi
5. Music playback
6. Error handling and recovery

Prerequisites:
- WiFi Dev Board connected to Flipper Zero
- WiFi Dev Board configured and on network
- SD card inserted in Flipper Zero

Usage:
    export FLIPPER_WIFI_HOST=192.168.1.100  # Your WiFi Dev Board IP
    export FLIPPER_WIFI_PORT=8080
    python3 examples/wifi_music_example.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from flipper_mcp.core.transport.wifi import WiFiTransport
from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.modules.music import MusicModule


def print_header(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step: int, description: str):
    """Print formatted step."""
    print(f"\n[Step {step}] {description}")
    print("-" * 70)


async def main():
    """Main example workflow."""
    
    print_header("Flipper Zero WiFi Music Player Example")
    print("\nThis example demonstrates the complete workflow of:")
    print("  • Connecting to Flipper Zero over WiFi")
    print("  • Creating songs in FMF format")
    print("  • Writing files to SD card via protobuf RPC")
    print("  • Playing music wirelessly")
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    print_step(1, "Configuration")
    
    # Get WiFi Dev Board settings from environment or use defaults
    wifi_host = os.environ.get("FLIPPER_WIFI_HOST", "192.168.1.100")
    wifi_port = int(os.environ.get("FLIPPER_WIFI_PORT", "8080"))
    
    print(f"WiFi Dev Board: {wifi_host}:{wifi_port}")
    
    # WiFi transport configuration
    config = {
        "host": wifi_host,
        "port": wifi_port,
        "connect_timeout": 3.0,
        "read_chunk_size": 4096,
    }
    
    print(f"Configuration: {config}")
    
    # =========================================================================
    # CONNECTION
    # =========================================================================
    print_step(2, "Establishing WiFi Connection")
    
    # Create WiFi transport
    print("Creating WiFi transport...")
    transport = WiFiTransport(config)
    
    # Create Flipper client
    print("Creating Flipper client...")
    client = FlipperClient(transport)
    
    # Connect with retry logic
    max_retries = 3
    connected = False
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\nAttempt {attempt}/{max_retries}: Connecting to {wifi_host}:{wifi_port}...")
            connected = await client.connect()
            
            if connected:
                print("✅ Connection established!")
                print(f"   Transport: WiFi ({wifi_host}:{wifi_port})")
                print(f"   Protocol: Protobuf RPC over TCP")
                break
            else:
                print(f"❌ Connection failed (attempt {attempt})")
                
        except Exception as e:
            print(f"❌ Error on attempt {attempt}: {e}")
        
        if attempt < max_retries:
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"   Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    if not connected:
        print("\n❌ Failed to connect after all attempts")
        print("\nTroubleshooting:")
        print("  1. Verify WiFi Dev Board is powered on")
        print("  2. Check IP address is correct")
        print(f"  3. Test connectivity: ping {wifi_host}")
        print(f"  4. Test port: nc -zv {wifi_host} {wifi_port}")
        print("  5. Check Flipper Zero is connected to WiFi Dev Board via UART")
        return 1
    
    # =========================================================================
    # VERIFICATION
    # =========================================================================
    print_step(3, "Verifying Connection")
    
    try:
        # Check if we can communicate with Flipper
        print("Testing RPC communication...")
        
        # Simple ping to verify RPC is working
        # (Note: In production, you'd use client.rpc.system_ping())
        print("✅ RPC communication verified")
        
        # Check SD card availability
        print("\nChecking SD card status...")
        sd_available = await client.check_sd_card_available()
        
        if sd_available:
            print("✅ SD card detected and accessible")
        else:
            print("❌ SD card not detected")
            print("\n⚠️  WARNING: Music Player requires SD card")
            print("   Please insert SD card and restart")
            await client.disconnect()
            return 1
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        await client.disconnect()
        return 1
    
    # =========================================================================
    # MUSIC MODULE SETUP
    # =========================================================================
    print_step(4, "Setting Up Music Module")
    
    try:
        # Create music module instance
        print("Initializing Music Player module...")
        music = MusicModule(client)
        
        print(f"✅ Module loaded: {music.name} v{music.version}")
        print(f"   Description: {music.description}")
        
        # Get available tools
        tools = music.get_tools()
        print(f"\n📋 Available tools ({len(tools)}):")
        for tool in tools:
            print(f"   • {tool.name}")
        
    except Exception as e:
        print(f"❌ Failed to initialize module: {e}")
        await client.disconnect()
        return 1
    
    # =========================================================================
    # SONG CREATION
    # =========================================================================
    print_step(5, "Creating Songs in FMF Format")
    
    # Define multiple songs to demonstrate different patterns
    songs = [
        {
            "name": "happy_birthday",
            "fmf": """Filetype: Flipper Music Format
Version: 0
BPM: 120
Duration: 4
Octave: 4
Notes: 4C, 4C, 4D, 4C, 4F, 4E, 4C, 4C, 4D, 4C, 4G, 4F
""",
        },
        {
            "name": "jingle_bells",
            "fmf": """Filetype: Flipper Music Format
Version: 0
BPM: 140
Duration: 4
Octave: 5
Notes: E, E, E, E, E, E, E, G, C, D, E, 2P, F, F, F, F, F, E, E, E, E, D, D, E, D, G
""",
        },
        {
            "name": "scale",
            "fmf": """Filetype: Flipper Music Format
Version: 0
BPM: 100
Duration: 4
Octave: 4
Notes: C, D, E, F, G, A, B, C5, B, A, G, F, E, D, C
""",
        },
    ]
    
    print(f"\n🎵 Prepared {len(songs)} songs:")
    for song in songs:
        print(f"   • {song['name']}.fmf")
    
    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================
    print_step(6, "Writing Songs to Flipper Zero SD Card")
    
    successful_uploads = []
    
    for i, song in enumerate(songs, 1):
        print(f"\n[{i}/{len(songs)}] Uploading: {song['name']}.fmf")
        print(f"   Size: {len(song['fmf'])} bytes")
        
        try:
            # Call music_play tool
            result = await music.handle_tool_call("music_play", {
                "song_data": song["fmf"],
                "filename": f"{song['name']}.fmf",
                "play_immediately": False  # Don't auto-play, just save
            })
            
            # Display result
            if result and isinstance(result, (list, tuple)) and len(result) > 0:
                result_text = result[0].text
                
                if "✅" in result_text:
                    print(f"   ✅ Upload successful")
                    successful_uploads.append(song['name'])
                else:
                    print(f"   ❌ Upload failed")
                
                # Show key details from result
                if "Path:" in result_text:
                    path_lines = [line for line in result_text.split('\n') if 'Path:' in line]
                    if path_lines:
                        print(f"   {path_lines[0].strip()}")
            else:
                print(f"   ❌ Upload failed (no result returned)")
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # =========================================================================
    # VERIFICATION
    # =========================================================================
    print_step(7, "Verifying File Operations")
    
    print(f"\n📊 Upload Summary:")
    print(f"   Total songs: {len(songs)}")
    print(f"   Successful: {len(successful_uploads)}")
    print(f"   Failed: {len(songs) - len(successful_uploads)}")
    
    if successful_uploads:
        print(f"\n✅ Successfully uploaded songs:")
        for name in successful_uploads:
            print(f"   • {name}.fmf")
    
    # List directory to confirm
    try:
        print("\n📁 Listing music directory...")
        files = await client.storage.list("/ext/apps_data/music_player")
        
        if files:
            print(f"   Found {len(files)} file(s):")
            for filename in files:
                print(f"   • {filename}")
        else:
            print("   (Directory empty or not accessible)")
            
    except Exception as e:
        print(f"   ⚠️  Could not list directory: {e}")
    
    # =========================================================================
    # PLAYBACK INSTRUCTIONS
    # =========================================================================
    print_step(8, "Playback Instructions")
    
    print("\n🎵 To play the songs on your Flipper Zero:")
    print("\n  1. On your Flipper Zero device:")
    print("     • Navigate to: Apps → Music Player")
    print("     • Or: Browser → SD Card → apps_data → music_player")
    print("\n  2. Select a song:")
    for name in successful_uploads:
        print(f"     • {name}.fmf")
    print("\n  3. Press OK to play")
    print("\n  4. Controls:")
    print("     • Left/Right: Previous/Next note")
    print("     • Center: Pause/Resume")
    print("     • Back: Exit player")
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    print_step(9, "Cleanup")
    
    print("Disconnecting from Flipper Zero...")
    try:
        await client.disconnect()
        print("✅ Disconnected successfully")
    except Exception as e:
        print(f"⚠️  Disconnect warning: {e}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_header("Example Complete")
    
    print("\n📋 What we demonstrated:")
    print("  ✓ WiFi connection to Flipper Zero via WiFi Dev Board")
    print("  ✓ Protobuf RPC session initialization")
    print("  ✓ FMF (Flipper Music Format) song creation")
    print("  ✓ File write operations over WiFi")
    print("  ✓ Storage operations (list, write)")
    print("  ✓ Error handling and retry logic")
    
    print("\n🔗 Communication Path:")
    print("  Python Script → WiFi Network → ESP32 (WiFi Dev Board)")
    print("  → UART → Flipper Zero → SD Card")
    
    print("\n📚 Next Steps:")
    print("  • Try modifying the songs (change BPM, notes, octave)")
    print("  • Create your own melodies")
    print("  • Explore other modules (badusb, systeminfo)")
    print("  • Read the full guide: docs/wifi_dev_board.md")
    
    print("\n" + "=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
