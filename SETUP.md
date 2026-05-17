# SETUP — Your first 15 minutes with CPK

This guide gets you from "I just cloned the repo" to "Claude is driving my Flipper."

## What you need

- **A Flipper Zero or Kiisu V4B clone** running [Momentum firmware](https://momentum-fw.dev/) (any recent build — tested on `mntm-dev` and `mntm-release-1.4.3`)
- **A USB-C cable** (data, not just power)
- **Python 3.11 or higher**
- **Either Claude Desktop or Claude Code** — both work. Claude Desktop is easier for first-time setup.

## Step 1 — Set Momentum's device settings

This is the step that gets skipped and costs people 90 minutes. Don't skip it.

Two settings need to be ON for reliable RPC-driven work. From the Flipper:

1. **`Settings → System → Auto Lock` → set to 30 minutes** (or longer, or OFF). Default is 60 seconds and the lockscreen will fight you constantly.

2. **`MNTM → Interface → Lockscreen → Allow USB RPC while locked` → ON**. Lets non-`app_start` RPCs (storage reads, info queries) work even when locked.

3. **`Settings → Power → Prevent Auto Lock with USB/RPC` → ON**. Stops auto-lock while a USB cable is connected.

See [`docs/SETUP_REQUIREMENTS_mntm-dev.md`](./docs/SETUP_REQUIREMENTS_mntm-dev.md) for why these matter (TL;DR: the lockscreen on Momentum is itself an app, so `app_start` calls get rejected with `ERROR_APP_SYSTEM_LOCKED` if the lockscreen is up).

## Step 2 — Install CPK

```bash
git clone git@github.com:innov8ideas4u-alt/Claude-s-Pet-Kiisu-CPK.git
cd Claude-s-Pet-Kiisu-CPK
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
```

Install:

```bash
pip install -e .
```

This installs the `flipper_mcp` package in editable mode — changes you make to the code are picked up without reinstalling.

## Step 3 — Find your COM port

Plug the Flipper in via USB. Then:

```bash
# Windows (PowerShell)
Get-PnpDevice -Class Ports -PresentOnly | Where-Object { $_.InstanceId -like '*VID_0483*' }

# Linux
ls /dev/ttyACM*

# Mac
ls /dev/cu.usbmodem*
```

You should see one port (e.g. `COM9` on Windows or `/dev/ttyACM0` on Linux). Note it.

If you have **multiple Flippers** plugged in (e.g. a Flipper Zero AND a Kiisu), each gets its own port. **Pin them in Device Manager / udev rules** so they don't shuffle on reconnect.

## Step 4 — Configure your AI agent

### For Claude Desktop

Edit `claude_desktop_config.json` (path varies — on Windows it's `%APPDATA%\Claude\claude_desktop_config.json`).

Add this under `mcpServers`:

```json
{
  "mcpServers": {
    "flipper-mcp": {
      "command": "C:\\path\\to\\Claude-s-Pet-Kiisu-CPK\\.venv\\Scripts\\python.exe",
      "args": ["-X", "utf8", "-m", "flipper_mcp.cli.main"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "FLIPPER_TRANSPORT": "usb",
        "FLIPPER_PORT": "COM9"
      }
    }
  }
}
```

Adjust the `command` path and `FLIPPER_PORT` for your machine. On Linux/Mac use forward slashes (`/`) and your venv path will be `bin/python` instead of `Scripts\python.exe`.

Restart Claude Desktop.

### For Claude Code (cc)

Edit `~/.claude.json` (or `$HOME/.claude.json` on Linux/Mac). Add the same `flipper-mcp` block under `mcpServers`.

For project-scoped setup, you can also put it under `projects → <your_path> → mcpServers`.

Restart your cc session.

## Step 5 — Test it

In Claude (or cc), ask:

> *"What's connected? Run the ping mission."*

Claude should:
1. Call `flipper_connection_health` and report back
2. Write a tiny ping.js to the SD card (or use the bundled one)
3. Launch it via `flipper_app_start("/ext/apps/assets/js_app.fap", "/ext/apps_data/mcp_missions/ping.js")`
4. Read the log
5. Send a synthetic BACK to clean up

You should hear a beep from the Flipper and see the screen wake briefly. That's the `notification.success()` call inside ping.js doing its job — your visual + audio confirmation that Claude actually drove the device.

## Troubleshooting

### "COM port denied" or "Permission denied"
Another process has the port. On Windows, look for stray `python.exe` processes (CPK has had this issue with orphan MCP servers — see `recon/PHASE1_SUMMARY.md` finding R7).

### `ERROR_APP_SYSTEM_LOCKED` on every `app_start`
The lockscreen is showing. Either physically press UP on the device to unlock, or call `flipper_desktop_unlock` from your AI agent.

### Scripts silently fail to launch
Check that you're passing the **full FAP path** for the JS Runner: `/ext/apps/assets/js_app.fap`. The string `"js_app"` does NOT work on `mntm-dev` (firmware-version drift — see decision docs).

### `storage_write` says "Write failed" but the file IS there
Known MCP-server-side bug in the response parser. The write actually succeeded. Verify by reading the file back. This is on the fix list.

### Backlight stays off when Claude does things
Expected — synthetic input bypasses the power-management code. Have your JS missions end with `notification.success()` or `notification.error()` to wake the display.

## Where to go next

- **See it run something real:** ask Claude to run one of the missions in `missions/`.
- **Add your own tool:** see [`docs/module_development.md`](./docs/module_development.md).
- **Understand the architecture:** see [`docs/architecture.md`](./docs/architecture.md).
- **Deep-dive on the firmware quirks:** see [`docs/KIISU_DEEP_KNOWLEDGE.md`](./docs/KIISU_DEEP_KNOWLEDGE.md). It's 1596 lines but every section is independent — jump around.
- **Help an AI extend the project:** point them at [`docs/for_ai_contributors.md`](./docs/for_ai_contributors.md).
