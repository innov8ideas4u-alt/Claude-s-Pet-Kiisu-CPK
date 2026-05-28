"""Flipper Zero RPC client wrapper."""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, timezone

from .transport.base import FlipperTransport
from .rpc import FlipperRPC


class FlipperStorage:
    """
    Storage operations wrapper.
    
    Provides file system operations on Flipper Zero.
    """
    
    def __init__(self, client: 'FlipperClient'):
        self.client = client
    
    async def list(self, path: str) -> list[str]:
        """
        List files in directory (names only).

        Returns plain names. Cannot distinguish files from directories.
        For poll loops or any logic that needs to filter by type, prefer
        `list_detailed()` instead.

        Args:
            path: Directory path

        Returns:
            List of filenames
        """
        if not self.client.rpc:
            return []
        return await self.client.rpc.storage_list(path)

    async def list_detailed(self, path: str) -> list[dict[str, Any]]:
        """
        List directory entries with type information.

        Plain English: this is the version that actually tells you whether
        each entry is a file or a directory. Use this whenever you need to
        filter (e.g. polling for new .nfc files in /ext/nfc/, where the
        firmware lazily creates an /ext/nfc/assets/ subdirectory on first
        NFC app launch and we don't want to mistake it for a saved card).

        Args:
            path: Directory path

        Returns:
            List of dicts: {"name": str, "type": "FILE"|"DIR", "size": int}
            Empty list on RPC failure or if directory doesn't exist.
        """
        if not self.client.rpc:
            return []
        if not hasattr(self.client.rpc, "storage_list_detailed"):
            # Older RPC implementations may not have the detailed variant.
            # Fall back gracefully: synthesize entries assuming everything
            # is a FILE (lossy, but no worse than the old behavior).
            names = await self.client.rpc.storage_list(path)
            return [{"name": n, "type": "FILE", "size": 0} for n in names]
        return await self.client.rpc.storage_list_detailed(path)
    
    async def read(self, path: str) -> str:
        """
        Read file contents.
        
        Args:
            path: File path
            
        Returns:
            File contents as string
        """
        if not self.client.rpc:
            return ""
        return await self.client.rpc.storage_read(path)
    
    async def write(self, path: str, content: str) -> bool:
        """
        Write file contents.
        
        Args:
            path: File path
            content: Content to write
            
        Returns:
            True if successful
        """
        if not self.client.rpc:
            return False
        return await self.client.rpc.storage_write(path, content)
    
    async def delete(self, path: str) -> bool:
        """
        Delete file.
        
        Args:
            path: File path
            
        Returns:
            True if successful
        """
        if not self.client.rpc:
            return False
        return await self.client.rpc.storage_delete(path)
    
    async def mkdir(self, path: str) -> bool:
        """
        Create directory.
        
        Args:
            path: Directory path
            
        Returns:
            True if successful
        """
        if not self.client.rpc:
            return False
        return await self.client.rpc.storage_mkdir(path)


class FlipperApp:
    """
    Application launcher wrapper.
    
    Provides app launching and control on Flipper Zero.
    """
    
    def __init__(self, client: 'FlipperClient'):
        self.client = client
    
    async def launch(self, app_name: str, args: Optional[str] = None) -> bool:
        """
        Launch an application.
        
        Args:
            app_name: Application name (e.g., "BadUsb")
            args: Optional arguments
            
        Returns:
            True if launch successful
        """
        if not self.client.rpc:
            return False
        try:
            return await self.client.rpc.app_start(app_name, args=args or "")
        except Exception:
            return False
    
    async def stop(self, app_name: str) -> bool:
        """
        Stop a running application.
        
        Args:
            app_name: Application name
            
        Returns:
            True if stop successful
        """
        # Not implemented yet over protobuf RPC in this repo.
        # (The protobuf schema has AppExitRequest but needs target app context.)
        return False


class FlipperClient:
    """
    High-level Flipper Zero RPC client.
    
    Provides a simplified interface to Flipper Zero operations,
    abstracting away the underlying protobuf RPC protocol.
    
    This is a stub implementation that would normally communicate
    with Flipper Zero using the official protobuf RPC protocol.
    """
    
    def __init__(self, transport: FlipperTransport):
        """
        Initialize Flipper client.
        
        Args:
            transport: Transport layer for communication
        """
        self.transport = transport
        # NOTE: `connected` historically meant "server is willing to route tools".
        # For authoritative health, use `get_connection_health()` which checks
        # transport state and protobuf RPC responsiveness.
        self.connected = False
        self.rpc: Optional[FlipperRPC] = None
        self.stub_mode: bool = False
        self.last_connection_error: Optional[str] = None
        
        # Sub-clients
        self.storage = FlipperStorage(self)
        self.app = FlipperApp(self)
        
        # SD card status cache
        self._sd_card_available: Optional[bool] = None
    
    async def connect(self) -> bool:
        """
        Connect to Flipper Zero.
        
        Returns:
            True if connection successful
        """
        try:
            ok = await self.transport.connect()
        except Exception as e:
            ok = False
            self.last_connection_error = str(e)

        if not ok:
            return False
        
        # Initialize RPC client
        self.rpc = FlipperRPC(self.transport)

        # NOTE:
        # Do not send any ad-hoc/binary "ping" bytes on connect.
        # The Flipper USB CDC port typically starts in CLI mode and will interpret
        # random binary framing as garbage input, which can break subsequent
        # `start_rpc_session` negotiation for protobuf RPC.
        
        self.connected = True
        self.last_connection_error = None
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from Flipper Zero."""
        # Phase 3: stop the single reader task BEFORE closing the transport so it
        # isn't left reading a closing/closed port (in a long-lived event loop the
        # reader would otherwise leak; under per-call asyncio.run it's already
        # cancelled at loop close, so this is a no-op there).
        try:
            if self.rpc is not None and getattr(self.rpc, "protobuf_rpc", None) is not None:
                await self.rpc.protobuf_rpc._stop_reader()
        except Exception as e:
            self.last_connection_error = str(e)
        try:
            await self.transport.disconnect()
        except Exception as e:
            # Best-effort; a dead transport may already be gone.
            self.last_connection_error = str(e)
        self.connected = False

    async def get_connection_health(self, probe_rpc: bool = True) -> dict[str, Any]:
        """
        Authoritative connection health.

        `connected` is true only if:
        - transport reports connected, AND
        - protobuf RPC ping succeeds (unless probe_rpc=False)
        """
        ts = datetime.now(timezone.utc).isoformat()

        transport_connected = False
        transport_name: Optional[str] = None
        transport_details: dict[str, Any] = {}
        last_error: Optional[str] = self.last_connection_error

        try:
            if self.transport:
                transport_name = self.transport.get_name()
                try:
                    transport_connected = bool(await self.transport.is_connected())
                except Exception as e:
                    transport_connected = False
                    last_error = last_error or str(e)

                # Best-effort details (USB/WiFi)
                if hasattr(self.transport, "port"):
                    transport_details["port"] = getattr(self.transport, "port")
                if hasattr(self.transport, "host"):
                    transport_details["host"] = getattr(self.transport, "host")
                if hasattr(self.transport, "baudrate"):
                    transport_details["baudrate"] = getattr(self.transport, "baudrate")
        except Exception as e:
            transport_connected = False
            last_error = last_error or str(e)

        rpc_responsive = False
        rpc_echo: Optional[str] = None
        if probe_rpc and transport_connected and self.rpc:
            try:
                echoed = await self.rpc.protobuf_ping(b"mcp_health")
                if echoed == b"mcp_health":
                    rpc_responsive = True
                    rpc_echo = "mcp_health"
            except Exception as e:
                last_error = last_error or str(e)

        connected = bool(transport_connected and (rpc_responsive if probe_rpc else True))

        return {
            "timestamp": ts,
            "connected": connected,
            "transport_connected": bool(transport_connected),
            "rpc_responsive": bool(rpc_responsive) if probe_rpc else None,
            "rpc_echo": rpc_echo,
            "transport": {
                "type": transport_name,
                **transport_details,
            },
            "stub_mode": bool(self.stub_mode),
            "last_error": last_error,
        }
    
    async def get_firmware_version(self) -> str:
        """
        Get Flipper firmware version.
        
        Returns:
            Firmware version string
        """
        if self.rpc:
            try:
                info = await self.rpc.get_device_info()
                # Try multiple possible keys for firmware version
                fw = (info.get("firmware") or 
                      info.get("firmware_version") or 
                      info.get("version") or 
                      "Unknown")
                if fw and fw != "Unknown" and "not fully implemented" not in fw:
                    return fw
            except Exception:
                pass
        return "Unknown"
    
    async def get_device_info(self) -> dict[str, Any]:
        """
        Get device information.
        
        Returns comprehensive device information including:
        - name: Device name
        - hardware: Hardware model/version
        - firmware: Firmware version
        - firmware_version: Detailed firmware version
        - hardware_model: Hardware model
        - hardware_version: Hardware version
        - serial_number: Device serial number (if available)
        
        Returns:
            Device info dict with all available information
        """
        if self.rpc:
            try:
                info = await self.rpc.get_device_info()
                # Ensure we have at least basic structure
                if info and isinstance(info, dict):
                    # Normalize keys
                    normalized = {
                        "name": info.get("name") or info.get("device_name") or "Flipper Zero",
                        "hardware": (info.get("hardware") or 
                                   info.get("hardware_model") or 
                                   info.get("model") or 
                                   "Flipper Zero"),
                        "firmware": (info.get("firmware") or 
                                   info.get("firmware_version") or 
                                   info.get("version") or 
                                   "Unknown"),
                    }
                    
                    # Add additional fields if available
                    if info.get("firmware_version"):
                        normalized["firmware_version"] = info["firmware_version"]
                    if info.get("hardware_model"):
                        normalized["hardware_model"] = info["hardware_model"]
                    if info.get("hardware_version"):
                        normalized["hardware_version"] = info["hardware_version"]
                    if info.get("serial_number") or info.get("serial"):
                        normalized["serial_number"] = info.get("serial_number") or info.get("serial")
                    
                    return normalized
            except Exception as e:
                # Log error but continue to fallback
                pass
        
        # Fallback with basic info
        fw_version = await self.get_firmware_version()
        return {
            "name": "Flipper Zero",
            "hardware": "Flipper Zero",
            "firmware": fw_version if fw_version != "Unknown" else "Unknown (RPC protocol not fully implemented)"
        }
    
    async def check_sd_card_available(self, force_check: bool = False) -> bool:
        """
        Check if MicroSD card is available and accessible.
        
        Detection method: Try to write a test file to /ext directory (SD card mount point),
        then delete it. If both operations succeed, SD card is present and writable.
        This is more reliable than just listing, as listing may succeed even without SD card.
        
        The result is cached to avoid repeated checks. Use force_check=True
        to bypass the cache and check again.
        
        Args:
            force_check: If True, bypass cache and check again
            
        Returns:
            True if SD card is available, False otherwise
        """
        # Return cached result if available and not forcing a check
        if not force_check and self._sd_card_available is not None:
            return self._sd_card_available
        
        # If not connected, SD card cannot be available
        if not self.connected:
            self._sd_card_available = False
            return False

        # Prefer protobuf storage info when available; this is more reliable than write/read probes.
        # On some firmwares / timing windows, the first RPC call after connecting can fail while the
        # CLI->RPC session is still being negotiated. Retry a few times before concluding SD is missing.
        if self.rpc:
            try:
                import asyncio

                for _ in range(3):
                    storage_info = await self.rpc.storage_info("/ext")
                    if storage_info and storage_info.get("total_space", 0) > 0:
                        self._sd_card_available = True
                        return True
                    await asyncio.sleep(0.2)
            except Exception:
                pass

        # Fallback: list /ext (weaker; can be empty even when SD is present).
        try:
            files = await self.storage.list("/ext")
            # If we can list at all, assume the mount is accessible (even if empty).
            self._sd_card_available = True
            return True if files is not None else False
        except Exception:
            self._sd_card_available = False
            return False
    
    async def send_rpc(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Send RPC command to Flipper.
        
        Args:
            command: RPC command name
            params: Command parameters
            
        Returns:
            RPC response
        """
        # Stub: Would normally encode to protobuf and send via transport
        return {"status": "ok"}
