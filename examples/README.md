# Examples

This directory contains example scripts and modules demonstrating various features of the Flipper Zero MCP server.

## Tutorial sequence (start here)

The numbered files are a 30-minute guided tour from first-contact to extending the server. Read them in order:

| # | File                                       | What it covers                                              |
|---|--------------------------------------------|-------------------------------------------------------------|
| 1 | `01_hello_flipper.md`                      | Your first 60 seconds — sanity check that everything works  |
| 2 | `02_first_mission.js`                      | The smallest useful JS mission                              |
| 3 | `03_mission_template.js`                   | Canonical template with `// FILL THIS IN` markers           |
| 4 | `04_using_flipper_js_run.py`               | Host-side mission orchestration without going through Claude|
| 5 | `05_button_navigation.md`                  | Driving menus with synthetic input                          |
| 6 | `06_adding_a_new_tool.md`                  | Extending the MCP server with a new module                  |
| 7 | `07_structured_logs.js`                    | Mission log conventions (key=value, required fields)        |
| 8 | `08_for_your_own_AI.md`                    | Copy-paste prompts for onboarding your AI to CPK            |
| 9 | `09_mjs_cheat_sheet.md`                    | Single-page mJS quick-reference card                        |

## Other examples in this directory

### Minimal Module Example

**Directory**: `minimal_module/`

Template for creating custom modules.

**See:** `docs/module_development.md` for module development guide.

### Transport-specific examples

**Directory**: `transports/`

Examples that exercise alternative transports (WiFi Dev Board, BLE). Likely not your first read — most CPK use goes through USB (the default).

- `transports/wifi_music_example.py` — full end-to-end WiFi Dev Board demo.

---

## Running Examples

### From Repository Root

```bash
# Install dependencies
pip install -e .

# Run an example
python3 examples/transports/wifi_music_example.py
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

# Add repo root to path so `flipper_mcp` resolves (only needed if not pip-installed)
sys.path.insert(0, str(Path(__file__).parent.parent))

from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.usb import USBTransport
# or: from flipper_mcp.core.transport.wifi import WiFiTransport

async def main():
    """Main example logic."""
    # USB auto-detects via VID:PID; pass {"port": "COM9"} to override.
    transport = USBTransport(config={})

    client = FlipperClient(transport)
    if not await client.connect():
        print(f"Failed to connect: {client.last_connection_error}")
        return 1

    # Your code here
    # ...

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
- **AI Contributors Guide**: `../docs/for_ai_contributors.md` — read this if you're an AI agent or you're onboarding one.

---

## Contributing Examples

We welcome new examples! To contribute:

1. Create your example following the template above
2. Add clear documentation in docstrings
3. Include usage instructions
4. Test thoroughly with real hardware
5. Submit a pull request

See `CONTRIBUTING.md` for more details.
