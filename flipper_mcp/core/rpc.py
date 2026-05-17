"""Basic Flipper Zero RPC protocol implementation.

This module implements a simplified RPC protocol for communicating with
Flipper Zero devices. The Flipper Zero uses a protobuf-based RPC protocol,
but for initial testing, we implement a basic CLI-based approach.

The implementation tries to use proper protobuf RPC when possible, falling
back to simplified methods if needed.
"""

import asyncio
import struct
import json
import subprocess
import shutil
from typing import Optional, Dict, Any, List
from .transport.base import FlipperTransport

# Try to import protobuf RPC implementation
try:
    from .protobuf_rpc import ProtobufRPC, AppRpcResult
    PROTOBUF_RPC_AVAILABLE = True
except ImportError:
    PROTOBUF_RPC_AVAILABLE = False
    # Fallback shim so type-hints don't blow up when protobuf layer missing
    class AppRpcResult:  # type: ignore[no-redef]
        def __init__(self, ok: bool = False, status_code: int = -1, status_name: str = "NO_PROTOBUF"):
            self.ok = ok
            self.status_code = status_code
            self.status_name = status_name
        def __bool__(self) -> bool:
            return self.ok


class FlipperRPC:
    """
    Basic RPC client for Flipper Zero.
    
    Implements a simplified RPC protocol for basic operations.
    Note: Full protobuf RPC implementation would be more robust,
    but this provides basic functionality for testing.
    """
    
    def __init__(self, transport: FlipperTransport):
        """
        Initialize RPC client.
        
        Args:
            transport: Transport layer for communication
        """
        self.transport = transport
        self.command_id = 0
        
        # Try to use protobuf RPC if available
        # Note: We initialize it lazily to avoid blocking if protobuf isn't working
        self.protobuf_rpc: Optional[ProtobufRPC] = None
        self._protobuf_rpc_initialized = False
        if PROTOBUF_RPC_AVAILABLE:
            # Don't initialize yet - do it lazily on first use
            pass

    def _ensure_protobuf_rpc(self) -> None:
        """Initialize protobuf RPC client once (best-effort)."""
        if not PROTOBUF_RPC_AVAILABLE or self._protobuf_rpc_initialized:
            return
        try:
            self.protobuf_rpc = ProtobufRPC(self.transport)
        except Exception:
            self.protobuf_rpc = None
        finally:
            self._protobuf_rpc_initialized = True
    
    async def send_command(self, command: str, data: bytes = b"") -> bytes:
        """
        Send a command to Flipper Zero.
        
        Note: This is a simplified implementation. The actual Flipper Zero
        uses a protobuf-based RPC protocol. This method tries to communicate
        using a basic framing protocol that may work with some firmware versions.
        
        Args:
            command: Command string (e.g., "system.get_device_info", "property.get")
            data: Optional command data
            
        Returns:
            Response data (empty if no response or error)
        """
        try:
            # Try multiple command formats to increase compatibility
            
            # Format 1: Simple command format: <command_len><command><data_len><data>
            cmd_bytes = command.encode('utf-8')
            cmd_len = len(cmd_bytes)
            data_len = len(data)
            
            # Build message: [4 bytes: cmd_len][cmd][4 bytes: data_len][data]
            message = struct.pack('>I', cmd_len) + cmd_bytes + struct.pack('>I', data_len) + data
            
            await self.transport.send(message)
            
            # Wait for response with longer timeout for device info queries
            timeout = 5.0 if "device_info" in command or "property" in command else 2.0
            response_len_bytes = await self.transport.receive(timeout=timeout)
            if len(response_len_bytes) < 4:
                return b""
            
            response_len = struct.unpack('>I', response_len_bytes[:4])[0]
            if response_len == 0:
                return b""
            
            # Read the actual response
            response = await self.transport.receive(timeout=timeout)
            
            # If response is shorter than expected, try to read more
            if len(response) < (response_len - 4):
                remaining = response_len - 4 - len(response)
                if remaining > 0:
                    additional = await self.transport.receive(timeout=timeout)
                    response = response + additional
            
            return response[:(response_len - 4)] if len(response) >= (response_len - 4) else response
            
        except Exception:
            # If structured RPC fails, return empty (will fall back to other methods)
            return b""
    
    async def ping(self) -> bool:
        """
        Ping the Flipper Zero to test connection.
        
        Returns:
            True if device responds
        """
        try:
            response = await self.send_command("ping")
            return len(response) > 0
        except Exception:
            return False

    async def protobuf_ping(self, data: bytes = b"mcp_health") -> Optional[bytes]:
        """
        Send a protobuf RPC ping (nanopb-delimited) and return echoed bytes.

        This is the most reliable "is RPC alive?" probe we have in this repo.

        Returns:
            Echoed bytes on success, or None on failure.
        """
        self._ensure_protobuf_rpc()
        if not self.protobuf_rpc:
            return None
        try:
            return await self.protobuf_rpc.ping(data=data)
        except Exception:
            return None
    
    async def get_device_info(self) -> Dict[str, Any]:
        """
        Get device information using Flipper Zero RPC methods.
        
        Tries multiple RPC methods to get device information:
        1. Protobuf RPC (if available) - proper protocol implementation
        2. system.get_device_info (official RPC method)
        3. property.get for individual properties
        4. Fallback to basic info
        
        Returns:
            Device info dictionary with name, hardware, firmware, etc.
        """
        info = {
            "name": "Flipper Zero",
            "hardware": "Flipper Zero",
            "firmware": "Unknown",
            "firmware_version": None,
            "hardware_model": None,
            "hardware_version": None,
            "serial_number": None
        }
        
        # Try protobuf RPC first (proper implementation)
        # Initialize lazily on first use
        self._ensure_protobuf_rpc()
        
        if self.protobuf_rpc:
            try:
                # Use asyncio.wait_for to ensure we don't hang forever
                import asyncio
                protobuf_info = await asyncio.wait_for(
                    self.protobuf_rpc.get_device_info(),
                    timeout=6.0
                )
                if protobuf_info:
                    # Map protobuf response to our info structure using known keys.
                    # NOTE: The device_info map also contains protobuf_version_* keys
                    # which we must NOT treat as firmware version.
                    fw = (
                        protobuf_info.get("firmware_version")
                        or protobuf_info.get("firmware_branch")
                        or protobuf_info.get("firmware_commit")
                    )
                    if fw:
                        info["firmware"] = fw
                        info["firmware_version"] = fw

                    hw = protobuf_info.get("hardware_model") or protobuf_info.get("hardware_ver")
                    if hw:
                        info["hardware"] = hw
                        info["hardware_model"] = hw

                    name = protobuf_info.get("hardware_name") or protobuf_info.get("device_name")
                    if name:
                        info["name"] = name

                    serial = protobuf_info.get("serial_number") or protobuf_info.get("hardware_uid")
                    if serial:
                        info["serial_number"] = serial
                    
                    # If we got useful info, return it
                    if info.get("firmware") != "Unknown" or info.get("firmware_version"):
                        return info
            except (asyncio.TimeoutError, Exception):
                # Protobuf RPC failed or timed out - continue to fallback methods
                pass
        
        # Try system.get_device_info (official RPC method)
        try:
            response = await self.send_command("system.get_device_info")
            if response:
                parsed = self._parse_device_info_response(response)
                if parsed:
                    info.update(parsed)
                    if info.get("firmware") != "Unknown" or info.get("firmware_version"):
                        return info
        except Exception:
            pass
        
        # Try property.get for individual properties
        try:
            # Get firmware version
            fw_version = await self._get_property("firmware_version")
            if fw_version:
                info["firmware"] = fw_version
                info["firmware_version"] = fw_version
            
            # Get hardware model
            hw_model = await self._get_property("hardware_model")
            if hw_model:
                info["hardware"] = hw_model
                info["hardware_model"] = hw_model
            
            # Get hardware version
            hw_version = await self._get_property("hardware_version")
            if hw_version:
                info["hardware_version"] = hw_version
            
            # Get serial number
            serial = await self._get_property("serial_number")
            if serial:
                info["serial_number"] = serial
        except Exception:
            pass
        
        # If we got at least firmware version, return what we have
        if info.get("firmware") != "Unknown" or info.get("firmware_version"):
            return info
        
        # Final fallback
        return await self._get_info_via_cli()
    
    async def _get_property(self, key: str) -> Optional[str]:
        """
        Get a property value using property.get RPC call.
        
        Args:
            key: Property key
            
        Returns:
            Property value or None
        """
        try:
            import json
            payload = json.dumps({"key": key}).encode('utf-8')
            response = await self.send_command(f"property.get", payload)
            if response:
                try:
                    result = json.loads(response.decode('utf-8', errors='ignore'))
                    return result.get("value")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    text = response.decode('utf-8', errors='ignore').strip()
                    if text and text != "":
                        return text
        except Exception:
            pass
        return None
    
    def _parse_device_info_response(self, response: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse device info from RPC response.
        
        Args:
            response: Response bytes from RPC call
            
        Returns:
            Parsed device info dictionary or None
        """
        try:
            # Try JSON first
            import json
            text = response.decode('utf-8', errors='ignore')
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
            
            # Try to parse as text/structured format
            info = {}
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for key:value pairs
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if 'firmware' in key or 'version' in key:
                        info["firmware"] = value
                        info["firmware_version"] = value
                    elif 'hardware' in key or 'model' in key:
                        info["hardware"] = value
                        info["hardware_model"] = value
                    elif 'serial' in key:
                        info["serial_number"] = value
                    elif 'name' in key or 'device' in key:
                        info["name"] = value
            
            return info if info else None
            
        except Exception:
            return None
    
    async def _get_info_via_cli(self) -> Dict[str, Any]:
        """
        Get device info via fallback methods.
        
        Tries:
        1. Flipper Zero CLI tools (if available)
        2. Basic info fallback
        
        Returns:
            Device info dictionary
        """
        # Try to use Flipper CLI tools if available
        info = await self._try_flipper_cli()
        if info:
            return info
        
        # Final fallback
        return {
            "name": "Flipper Zero",
            "hardware": "Flipper Zero",
            "firmware": "Unknown (RPC protocol not fully implemented)",
        }
    
    async def _try_flipper_cli(self) -> Optional[Dict[str, Any]]:
        """
        Try to get device info using Flipper Zero CLI tools.
        
        Checks for common CLI tools like 'flipper' or 'qflipper-cli'.
        
        Returns:
            Device info dict if successful, None otherwise
        """
        # Check for common Flipper CLI tools
        cli_tools = ['flipper', 'qflipper-cli', 'flipperzero-cli']
        cli_tool = None
        
        for tool in cli_tools:
            if shutil.which(tool):
                cli_tool = tool
                break
        
        if not cli_tool:
            return None
        
        try:
            # Try to get device info via CLI
            # Common commands: 'flipper info' or 'qflipper-cli info'
            process = await asyncio.create_subprocess_exec(
                cli_tool, 'info',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
            
            if process.returncode == 0 and stdout:
                # Parse CLI output
                output = stdout.decode('utf-8', errors='ignore')
                return self._parse_cli_output(output)
        except (asyncio.TimeoutError, FileNotFoundError, subprocess.SubprocessError):
            pass
        
        return None
    
    def _parse_cli_output(self, output: str) -> Dict[str, Any]:
        """
        Parse output from Flipper CLI tools.
        
        Args:
            output: CLI tool output text
            
        Returns:
            Parsed device info dictionary
        """
        info = {
            "name": "Flipper Zero",
            "hardware": "Flipper Zero",
            "firmware": "Unknown"
        }
        
        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for common patterns
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if any(term in key for term in ['firmware', 'version', 'fw']):
                    info["firmware"] = value
                    info["firmware_version"] = value
                elif any(term in key for term in ['hardware', 'model', 'hw']):
                    info["hardware"] = value
                    info["hardware_model"] = value
                elif 'serial' in key:
                    info["serial_number"] = value
                elif any(term in key for term in ['name', 'device']):
                    info["name"] = value
        
        return info
    
    async def storage_list(self, path: str) -> List[str]:
        """
        List files in a directory.
        
        Args:
            path: Directory path (e.g., "/ext/badusb")
            
        Returns:
            List of filenames
        """
        self._ensure_protobuf_rpc()
        # Prefer protobuf storage API if available (proper protocol)
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.storage_list(path)
            except Exception:
                pass

        try:
            # Try RPC command first
            path_bytes = path.encode('utf-8')
            response = await self.send_command("storage_list", path_bytes)
            
            if response:
                # Parse response - expect newline-separated filenames
                files_str = response.decode('utf-8', errors='ignore')
                files = [f.strip() for f in files_str.split('\n') if f.strip()]
                return files
        except Exception:
            pass
        
        # Fallback: try CLI approach
        return await self._storage_list_via_cli(path)
    
    async def _storage_list_via_cli(self, path: str) -> List[str]:
        """
        List files via CLI commands (fallback method).
        
        Note: This is a placeholder. The actual Flipper Zero requires
        the protobuf RPC protocol to list files. This method will return
        an empty list, indicating that the RPC protocol needs to be
        fully implemented for file operations.
        """
        # Without the full RPC protocol, we can't actually list files
        # This would require implementing the protobuf message format
        return []
    
    async def storage_read(self, path: str) -> str:
        """
        Read file contents.
        
        Args:
            path: File path (e.g., "/ext/badusb/test.txt")
            
        Returns:
            File contents as string
        """
        self._ensure_protobuf_rpc()
        # Prefer protobuf storage API if available (proper protocol)
        if self.protobuf_rpc:
            try:
                data = await self.protobuf_rpc.storage_read(path)
                if data:
                    return data.decode("utf-8", errors="ignore")
            except Exception:
                pass

        try:
            # Try RPC command first
            path_bytes = path.encode('utf-8')
            response = await self.send_command("storage_read", path_bytes)
            
            if response:
                return response.decode('utf-8', errors='ignore')
        except Exception:
            pass
        
        # Fallback: try CLI approach
        return await self._storage_read_via_cli(path)

    async def storage_info(self, path: str) -> Optional[Dict[str, int]]:
        """
        Query storage info (total/free space) for a given path via protobuf.

        Returns:
            Dict with total_space/free_space or None if unavailable.
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                info = await self.protobuf_rpc.storage_info(path)
                if info:
                    total, free = info
                    return {"total_space": total, "free_space": free}
            except Exception:
                pass
        return None

    async def storage_mkdir(self, path: str) -> bool:
        """Create a directory via protobuf storage API (best-effort)."""
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.storage_mkdir(path)
            except Exception:
                return False
        return False

    async def storage_delete(self, path: str, recursive: bool = False) -> bool:
        """Delete a file/dir via protobuf storage API (best-effort)."""
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.storage_delete(path, recursive=recursive)
            except Exception:
                return False
        return False

    async def storage_write(self, path: str, content: str) -> bool:
        """Write a file via protobuf storage API (best-effort)."""
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.storage_write(path, content.encode("utf-8"))
            except Exception:
                return False
        return False

    async def app_start(self, name: str, args: str = "") -> AppRpcResult:
        """
        Start an application via protobuf RPC.

        Returns AppRpcResult (truthy iff firmware reported OK). On failure
        `.status_name` carries the firmware's CommandStatus name; call
        `app_get_error()` for verbose error text.
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.app_start(name, args=args or "")
            except Exception as e:
                return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")
        return AppRpcResult(False, -1, "NO_PROTOBUF_RPC")

    async def app_load_file(self, path: str) -> AppRpcResult:
        """
        Launch whatever app the firmware associates with this file's type.

        Use this for `.nfc`, `.sub`, `.ir`, `.ibtn`, etc. on stock OFW where
        there's no named "app" to start — the file extension picks the handler.

        WARNING: per Momentum/OFW source (see KIISU_DEEP_KNOWLEDGE §1.4), JS scripts
        (`.js`) do NOT work via app_load_file because the JS Runner app does not
        register an RPC callback. The only RPC path for JS launching is
        `app_start("JS Runner", "/abs/path.js")`.

        Returns AppRpcResult (truthy iff firmware accepted the request).
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.app_load_file(path)
            except Exception as e:
                return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")
        return AppRpcResult(False, -1, "NO_PROTOBUF_RPC")

    async def app_exit(self) -> AppRpcResult:
        """
        Ask the currently-running app to exit cleanly.

        Equivalent to user pressing Back-to-exit. Returns ERROR_APP_NOT_RUNNING
        if nothing is open.
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.app_exit()
            except Exception as e:
                return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")
        return AppRpcResult(False, -1, "NO_PROTOBUF_RPC")

    async def app_get_error(self) -> tuple[int, str]:
        """
        Read the firmware's verbose error from the most recent failed app op.

        Returns (code, text). On clean state both are typically (0, '').
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.app_get_error()
            except Exception as e:
                return (-1, f"exception: {type(e).__name__}: {e}")
        return (-1, "no protobuf rpc")

    async def app_lock_status(self) -> Optional[bool]:
        """
        Query whether the Flipper desktop is currently locked.

        Returns True if locked, False if unlocked, None on transport error.
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.app_lock_status()
            except Exception:
                return None
        return None

    async def gui_send_input_event(self, key: str, event_type: str = "SHORT") -> AppRpcResult:
        """
        Synthesize a single button event at the GUI input layer.

        For the common "tap a button" case, prefer `gui_send_input_full_press` —
        a lone SHORT is silently absorbed by most app scenes. This method is for
        advanced cases (LONG holds, REPEAT events, manual triplet construction).
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.gui_send_input_event(key, event_type)
            except Exception as e:
                return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")
        return AppRpcResult(False, -1, "NO_PROTOBUF_RPC")

    async def gui_send_input_full_press(self, key: str) -> AppRpcResult:
        """
        Emit a full PRESS → SHORT → RELEASE triplet for a key.

        Canonical "tap a button" primitive. Validated against UP, DOWN, LEFT,
        RIGHT, OK, BACK on Momentum mntm-dev (May 2026).
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.gui_send_input_full_press(key)
            except Exception as e:
                return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")
        return AppRpcResult(False, -1, "NO_PROTOBUF_RPC")

    async def desktop_is_locked(self) -> Optional[bool]:
        """
        Query whether the desktop lockscreen is showing.

        Distinct from `app_lock_status`: app_lock_status is the app-loader mutex
        (LOCKED whenever any app is running, lockscreen included). This method
        actually asks the firmware whether the lock scene is the current scene.

        Returns True if locked, False if unlocked, None on transport error.
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.desktop_is_locked()
            except Exception:
                return None
        return None

    async def desktop_unlock(self) -> AppRpcResult:
        """
        Dismiss the desktop lockscreen via direct RPC.

        Canonical alternative to synthesizing a UP keypress. Bypasses the
        unlock-prompt UI entirely. Returns OK even if the device wasn't locked.
        Fails if a PIN is configured (can't supply a PIN over RPC).
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.desktop_unlock()
            except Exception as e:
                return AppRpcResult(False, -1, f"EXCEPTION:{type(e).__name__}")
        return AppRpcResult(False, -1, "NO_PROTOBUF_RPC")

    async def cli_command(self, command: str, timeout_s: float = 5.0) -> str:
        """
        Run a CLI command on the Flipper and return its raw text output.

        Use this when the protocol-level RPC primitives don't expose a feature you
        need — for example, launching JS scripts (CLI: `js <path>`) on firmwares
        that don't expose `js_app` to `app_start`.

        Returns the captured output as a string. Returns an empty string if RPC
        isn't available.

        Note: while this method runs, the device is briefly in CLI mode (not RPC).
        The wrapper transparently restarts the RPC session afterwards. Don't call
        this from concurrent tasks that also use other rpc methods.
        """
        self._ensure_protobuf_rpc()
        if self.protobuf_rpc:
            try:
                return await self.protobuf_rpc.cli_command(command, timeout_s=timeout_s)
            except Exception as e:
                return f"<cli_command failed: {type(e).__name__}: {e}>"
        return ""
    
    async def _storage_read_via_cli(self, path: str) -> str:
        """
        Read file via CLI commands (fallback method).
        
        Note: This is a placeholder. The actual Flipper Zero requires
        the protobuf RPC protocol to read files. This method will return
        an empty string, indicating that the RPC protocol needs to be
        fully implemented for file operations.
        """
        # Without the full RPC protocol, we can't actually read files
        # This would require implementing the protobuf message format
        return ""

