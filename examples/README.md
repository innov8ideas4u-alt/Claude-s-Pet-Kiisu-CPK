# Examples

This directory contains example scripts and modules demonstrating various features of the Flipper Zero MCP server.

## Available Examples

### WiFi Music Player Example

**File**: `wifi_music_example.py`

Complete end-to-end example demonstrating wireless control of Flipper Zero using the WiFi Dev Board.

**What it demonstrates:**
- WiFi connection setup and configuration
- Protobuf RPC over WiFi
- FMF (Flipper Music Format) song creation
- File operations over WiFi
- Music Player module usage
- Error handling and retry logic

**Prerequisites:**
- WiFi Dev Board connected to Flipper Zero
- WiFi Dev Board configured and on network
- SD card inserted in Flipper Zero

**Usage:**
```bash
# Set WiFi Dev Board IP
export FLIPPER_WIFI_HOST=192.168.1.100  # Your WiFi Dev Board IP
export FLIPPER_WIFI_PORT=8080

# Run example
python3 examples/wifi_music_example.py
```

**See also:** `docs/wifi_dev_board.md` for complete WiFi setup guide

---

### Minimal Module Example

**Directory**: `minimal_module/`

Template for creating custom modules.

**See:** `docs/module_development.md` for module development guide

---

## Running Examples

### From Repository Root

```bash
# Install dependencies
pip install -e .

# Run an example
python3 examples/wifi_music_example.py
```

### Configuration

Most examples support environment variables for configuration:

```bash
# Transport selection
export FLIPPER_TRANSPORT=wifi  # or 'usb'

# WiFi settings (if using WiFi transport)
export FLIPPER_WIFI_HOST=192.168.1.100
export FLIPPER_WIFI_PORT=8080

# USB settings (if using USB transport)
export FLIPPER_PORT=/dev/ttyACM0  # Optional: specify USB port

# Debug logging
export FLIPPER_DEBUG=1  # Enable verbose logging
```

---

## Creating Your Own Examples

### Basic Template

```python
#!/usr/bin/env python3
"""Your example description."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.wifi import WiFiTransport
# or: from flipper_mcp.core.transport.usb import USBTransport

async def main():
    """Main example logic."""
    # Create transport
    config = {"host": "192.168.1.100", "port": 8080}
    transport = WiFiTransport(config)
    
    # Create client and connect
    client = FlipperClient(transport)
    connected = await client.connect()
    
    if not connected:
        print("Failed to connect")
        return 1
    
    # Your code here
    # ...
    
    # Cleanup
    await client.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## Additional Resources

- **Main Documentation**: `../docs/index.md`
- **WiFi Dev Board Guide**: `../docs/wifi_dev_board.md`
- **Module Development**: `../docs/module_development.md`
- **API Reference**: `../docs/api_reference.md`

---

## Contributing Examples

We welcome new examples! To contribute:

1. Create your example following the template above
2. Add clear documentation in docstrings
3. Include usage instructions
4. Test thoroughly with real hardware
5. Submit a pull request

See `CONTRIBUTING.md` for more details.
