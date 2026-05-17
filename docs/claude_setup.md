# Configuring Flipper Zero MCP Server for Claude

This guide explains how to run the Flipper Zero MCP server and connect it to Claude Desktop.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration for Claude Desktop](#configuration-for-claude-desktop)
- [Configuration Options](#configuration-options)
- [Verifying the Setup](#verifying-the-setup)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites

Before you begin, ensure you have:

1. **Python 3.10 or higher** installed
   ```bash
   python3 --version  # Should show 3.10 or higher
   ```

2. **Flipper Zero device** connected via one of:
   - USB cable (recommended for first-time setup)
   - WiFi Dev Board (ESP32)
   - Bluetooth

3. **Claude Desktop** installed (for Claude Desktop integration)
   - Download from: [claude.ai/download](https://claude.ai/download)
   - Or use Claude via API/other clients

4. **Basic familiarity** with:
   - Command line/terminal
   - JSON configuration files
   - Your operating system's file system

## Installation

### Step 1: Clone or Download the Repository

```bash
git clone https://github.com/busse/flipperzero-mcp.git
cd flipperzero-mcp
```

### Step 2: Install Dependencies

Install the package and its dependencies:

```bash
# Install in development mode (recommended)
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

### Step 3: Verify Installation

Test that the server can start:

```bash
# This should show the server starting (press Ctrl+C to stop)
python -m flipper_mcp.cli.main
```

You should see output like:
```
============================================================
Flipper Zero MCP Server - Modular Architecture
============================================================

🔌 Initializing USB transport...
   Connecting to Flipper Zero...
✓ Connected to Flipper Zero
...
```

## Configuration for Claude Desktop

Claude Desktop uses a configuration file to manage MCP servers. The location depends on your operating system:

### Configuration File Locations

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Step 1: Locate or Create the Configuration File

1. Open your Claude Desktop configuration file in a text editor
2. If the file doesn't exist, create it with the following structure:

```json
{
  "mcpServers": {}
}
```

### Step 2: Add Flipper Zero MCP Server

Add the Flipper Zero MCP server to the `mcpServers` object. The configuration depends on your Python installation:

#### Option A: Using System Python (Recommended)

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "python3",
      "args": [
        "-m",
        "flipper_mcp.cli.main"
      ],
      "cwd": "/path/to/flipperzero-mcp"
    }
  }
}
```

**Important**: Replace `/path/to/flipperzero-mcp` with the actual path to your cloned repository.

#### Option B: Using Virtual Environment

If you installed the package in a virtual environment:

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "/path/to/venv/bin/python",
      "args": [
        "-m",
        "flipper_mcp.cli.main"
      ],
      "cwd": "/path/to/flipperzero-mcp"
    }
  }
}
```

#### Option C: Using the CLI Command

If you installed with `pip install -e .`, you can use the CLI command directly:

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "flipper-mcp"
    }
  }
}
```

**Note**: When using the CLI command, ensure `flipper-mcp` is in your system PATH.

### Step 3: Complete Example Configuration

Here's a complete example configuration file with the Flipper Zero MCP server:

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "python3",
      "args": [
        "-m",
        "flipper_mcp.cli.main"
      ],
      "cwd": "/Users/yourusername/flipperzero-mcp"
    }
  }
}
```

### Step 4: Restart Claude Desktop

1. **Quit Claude Desktop completely** (don't just close the window)
2. **Reopen Claude Desktop**
3. The MCP server should automatically start when Claude Desktop launches

### Step 5: Verify Connection

1. Open Claude Desktop
2. Start a new conversation
3. Ask Claude: "What tools do you have available?"
4. Claude should list the Flipper Zero MCP tools (e.g., `badusb_list`, `badusb_generate`, etc.)

## Configuration Options

The MCP server supports various configuration options through environment variables or a configuration file.

### Environment variables

The server currently reads configuration from environment variables:

```bash
# Transport selection
# - Default (recommended): auto (USB-first, WiFi fallback if FLIPPER_WIFI_HOST is set)
# - Alternatives: usb, wifi, bluetooth/ble
# export FLIPPER_TRANSPORT=auto

# Override USB serial device path (only used for FLIPPER_TRANSPORT=usb)
export FLIPPER_PORT=/dev/ttyACM0
```

Notes:

- WiFi host/port (`FLIPPER_WIFI_HOST`, `FLIPPER_WIFI_PORT`) are supported by the default server entry point in `src/flipper_mcp/core/server.py`.
- Additional RPC debugging controls:
  - `FLIPPER_DEBUG`: enable protobuf RPC debug logs (`1`, `true`, `yes`, `on`)
  - `FLIPPER_FORCE_START_RPC_SESSION`: always send `start_rpc_session` on connect (`1`, `true`, `yes`, `on`)

## USB by default, optional WiFi fallback (single MCP config)

You should only need **one** Claude Desktop MCP server entry.

- **Default behavior** (no transport env var set): the server tries **USB first**
- If USB is not available and `FLIPPER_WIFI_HOST` is set, the server automatically tries **WiFi**

Example Claude Desktop config (single server entry):

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "python3",
      "args": ["-m", "flipper_mcp.cli.main"],
      "cwd": "/path/to/flipperzero-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "FLIPPER_WIFI_HOST": "192.168.1.100",
        "FLIPPER_WIFI_PORT": "8080"
      }
    }
  }
}
```

If you don't use WiFi, omit the `FLIPPER_WIFI_HOST`/`FLIPPER_WIFI_PORT` entries and USB will be used.

## Verifying the Setup

### Test 1: Check Server Starts

Run the server manually to verify it starts correctly:

```bash
cd /path/to/flipperzero-mcp
python3 -m flipper_mcp.cli.main
```

Expected output:
```
============================================================
Flipper Zero MCP Server - Modular Architecture
============================================================

🔌 Initializing USB transport...
   Connecting to Flipper Zero...
✓ Connected to Flipper Zero
   Device: Flipper Zero
   Firmware: ...

📦 Discovering modules...
⚡ Loading modules...

✓ 3 module(s) loaded, 8 tool(s) available

📋 Available modules:
   • badusb v1.0.0 - 5 tool(s)
     BadUSB keyboard/mouse emulation with template-based script generation
   • music v1.0.0 - 2 tool(s)
     Play songs on Flipper Zero piezo speaker using FMF format
   • systeminfo v1.0.0 - 1 tool(s)
     Check Flipper Zero connection and retrieve system information

============================================================
🚀 Server ready! Waiting for MCP connections...
============================================================
```

### Test 2: Check Tools in Claude

In Claude Desktop, ask:

```
What tools are available for working with Flipper Zero?
```

Claude should respond with a list of available tools like:
- `systeminfo_get` - Get system and storage information
- `badusb_list` - List all BadUSB scripts
- `badusb_read` - Read a script's contents
- `badusb_generate` - Generate DuckyScript from description
- `badusb_execute` - Execute a script
- `badusb_workflow` - Complete generate→validate→save workflow
- `music_get_format` - Get FMF format specification
- `music_play` - Save and (optionally) play an FMF song

### Test 3: Simple Command

Try a simple command:

```
List all BadUSB scripts on my Flipper Zero
```

Claude should use the `badusb_list` tool and return the list of scripts.

## Troubleshooting

### Problem: Claude Desktop Can't Find the Server

**Symptoms**: Claude doesn't show Flipper Zero tools, or shows an error about the MCP server.

**Solutions**:

1. **Check the configuration file path**:
   - Ensure the path in `claude_desktop_config.json` is correct
   - Use absolute paths, not relative paths
   - On macOS/Linux, paths are case-sensitive

2. **Verify Python path**:
   ```bash
   # Check which Python is being used
   which python3
   
   # Test if the module can be imported
   python3 -m flipper_mcp.cli.main --help
   ```

3. **Check file permissions**:
   - Ensure the configuration file is readable
   - Ensure Python scripts are executable (if needed)

4. **Check Claude Desktop logs**:
   - Look for error messages in Claude Desktop's console/logs
   - On macOS: Check Console.app for Claude Desktop errors

### Problem: "Flipper Zero not connected"

**Symptoms**: Tools return "Flipper Zero not connected" error.

**Solutions**:

1. **Check USB connection**:
   - Ensure Flipper Zero is connected via USB
   - Try a different USB cable
   - Check if the device appears in system (e.g., `/dev/ttyACM0` on Linux)

2. **Check device permissions** (Linux):
   ```bash
   # Add your user to the dialout group
   sudo usermod -a -G dialout $USER
   # Log out and back in for changes to take effect
   ```

3. **Try different transport**:
   - If USB doesn't work, try WiFi or Bluetooth
   - Update the transport type in configuration

4. **Verify Flipper Zero is powered on**:
   - Ensure the device is turned on
   - Check battery level

### Problem: "Module not found" or Import Errors

**Symptoms**: Server fails to start with import errors.

**Solutions**:

1. **Reinstall the package**:
   ```bash
   pip install -e . --force-reinstall
   ```

2. **Check Python version**:
   ```bash
   python3 --version  # Must be 3.10+
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Problem: Server Starts but No Tools Available

**Symptoms**: Server starts successfully but Claude shows no tools.

**Solutions**:

1. **Check module discovery**:
   - Look at server startup output
   - Ensure modules are being discovered and loaded
   - Check for any error messages during module loading

2. **Verify module structure**:
   - Ensure modules are in `src/flipper_mcp/modules/`
   - Check that `__init__.py` files exist

3. **Check Flipper connection**:
   - Tools won't be available if Flipper Zero isn't connected
   - Server may run in "stub mode" without a connection

### Problem: Configuration File Not Working

**Symptoms**: Changes to `claude_desktop_config.json` don't take effect.

**Solutions**:

1. **Restart Claude Desktop completely**:
   - Quit the application (not just close the window)
   - Wait a few seconds
   - Reopen Claude Desktop

2. **Check JSON syntax**:
   - Validate your JSON using a JSON validator
   - Ensure all quotes and brackets are properly closed

3. **Check file location**:
   - Ensure you're editing the correct configuration file
   - Check the path matches your operating system

## Advanced Configuration

### Using Multiple MCP Servers

You can configure multiple MCP servers in Claude Desktop:

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "python3",
      "args": ["-m", "flipper_mcp.cli.main"],
      "cwd": "/path/to/flipperzero-mcp"
    },
    "other-server": {
      "command": "other-command",
      "args": ["--arg", "value"]
    }
  }
}
```

### Custom Transport Configuration

For advanced transport configuration, you can modify the server code or use environment variables:

```bash
# USB with specific port
export FLIPPER_TRANSPORT=usb
export FLIPPER_PORT=/dev/ttyUSB0

# WiFi configuration
export FLIPPER_TRANSPORT=wifi
export FLIPPER_WIFI_HOST=192.168.4.1
export FLIPPER_WIFI_PORT=8080

# Bluetooth
export FLIPPER_TRANSPORT=bluetooth
export FLIPPER_BT_ADDRESS=AA:BB:CC:DD:EE:FF
```

For WiFi Dev Board firmware setup and bridge details, see `docs/wifi_dev_board.md` and `firmware/tcp_uart_bridge/README.md`.

### Running in Development Mode

For development, you might want to run the server with additional logging:

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "python3",
      "args": [
        "-m",
        "flipper_mcp.cli.main"
      ],
      "cwd": "/path/to/flipperzero-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Using with Other Claude Clients

If you're using Claude via API or other clients (not Claude Desktop), you'll need to:

1. **Start the MCP server manually**:
   ```bash
   python3 -m flipper_mcp.cli.main
   ```

2. **Connect via stdio**: The server communicates via standard input/output, which is the standard MCP protocol.

3. **Use an MCP client library**: Your client application needs to implement the MCP protocol to communicate with the server.

## Next Steps

Once configured, you can:

1. **Explore available tools**: Ask Claude what tools are available
2. **Generate BadUSB scripts**: Try "Create a BadUSB script that opens calculator on Windows"
3. **List existing scripts**: Ask "What BadUSB scripts do I have?"
4. **Read script contents**: Ask to read a specific script
5. **Create custom modules**: See [Module Development Guide](module_development.md)

## Additional Resources

- [Architecture Overview](architecture.md) - Understand how the server works
- [API Reference](api_reference.md) - Detailed API documentation
- [Module Development Guide](module_development.md) - Create your own modules
- [Main README](../README.md) - Project overview and features

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review Claude Desktop logs for error messages
3. Open an issue on GitHub: `https://github.com/busse/flipperzero-mcp/issues`
4. Check existing issues and discussions

---

If you run into problems, include your OS, Python version, transport type, and the server startup logs in your issue.

