"""USB Serial transport for Flipper Zero."""

import asyncio
import sys
from typing import Optional
import serial
import serial.tools.list_ports

from .base import FlipperTransport

# Flipper Zero USB VID:PID
FLIPPER_VID = 0x0483  # STMicroelectronics
FLIPPER_PID = 0x5740  # Virtual COM Port


class USBTransport(FlipperTransport):
    """
    USB Serial transport implementation.
    
    Connects to Flipper Zero via USB serial port.
    """
    
    def __init__(self, config: dict):
        """
        Initialize USB transport.
        
        Args:
            config: USB configuration with 'port' and 'baudrate'
        """
        super().__init__(config)
        # IMPORTANT: dict.get(default=...) eagerly evaluates the default, which would
        # auto-detect even when an explicit port was provided. Keep this lazy.
        configured_port = config.get("port")
        self.port = configured_port if configured_port else self._auto_detect_port()
        self.baudrate = config.get("baudrate", 115200)
        self.timeout = config.get("timeout", 1.0)
        self.serial: Optional[serial.Serial] = None
    
    def _auto_detect_port(self) -> str:
        """
        Auto-detect Flipper Zero USB port.
        
        Supports both macOS (tty.usbmodem*) and Linux (ttyACM*, ttyUSB*).
        
        Returns:
            Port path or default
        """
        import platform
        system = platform.system()
        
        # Look for Flipper Zero USB device
        ports = serial.tools.list_ports.comports()
        detected_ports = []
        
        for port in ports:
            device = port.device
            is_flipper = False
            
            # Flipper Zero VID:PID match (most reliable)
            if port.vid == FLIPPER_VID and port.pid == FLIPPER_PID:
                is_flipper = True
            # Description match
            elif "Flipper" in str(port.description):
                is_flipper = True
            # macOS-specific: check for usbmodem pattern with "flip" in name
            elif system == "Darwin" and "usbmodem" in device.lower() and "flip" in device.lower():
                is_flipper = True
            
            if is_flipper:
                # On macOS, prefer cu.* for initiating outgoing serial connections.
                # (tty.* is typically for incoming/call-in.)
                if system == "Darwin":
                    if device.startswith("/dev/tty."):
                        # Prefer cu.* version if available
                        cu_device = device.replace("/dev/tty.", "/dev/cu.")
                        import os
                        if os.path.exists(cu_device):
                            device = cu_device
                
                detected_ports.append((device, port))
        
        # Return the first detected port
        if detected_ports:
            device, port = detected_ports[0]
            print(f"   Detected Flipper Zero at {device}", file=sys.stderr)
            return device
        
        # Platform-specific fallback
        if system == "Darwin":
            # macOS: try common usbmodem pattern
            fallback = "/dev/tty.usbmodemflip_1"
            print(f"   ⚠️  No Flipper Zero detected, using fallback: {fallback}", file=sys.stderr)
            return fallback
        else:
            # Linux: try common ACM port
            fallback = "/dev/ttyACM0"
            print(f"   ⚠️  No Flipper Zero detected, using fallback: {fallback}", file=sys.stderr)
            return fallback
    
    async def connect(self) -> bool:
        """
        Connect to Flipper Zero via USB.
        
        Returns:
            True if connection successful
        """
        try:
            # Open serial port
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            # Wait for connection to stabilize
            await asyncio.sleep(0.5)
            
            self.connected = True
            return True
            
        except (serial.SerialException, OSError) as e:
            print(f"USB connection failed: {e}", file=sys.stderr)
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Close USB connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.connected = False
    
    async def send(self, data: bytes) -> None:
        """
        Send data over USB.
        
        Args:
            data: Bytes to send
        """
        if not self.serial or not self.serial.is_open:
            raise RuntimeError("USB not connected")
        
        # Run serial write in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.serial.write, data)
    
    async def receive(self, timeout: Optional[float] = None) -> bytes:
        """
        Receive data from USB.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Received bytes
        """
        if not self.serial or not self.serial.is_open:
            raise RuntimeError("USB not connected")
        
        # Use provided timeout or default
        old_timeout = self.serial.timeout
        if timeout is not None:
            self.serial.timeout = timeout
        
        try:
            # Run serial read in executor
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                self.serial.read,
                4096  # Max bytes to read
            )
            return data
        finally:
            self.serial.timeout = old_timeout
    
    async def is_connected(self) -> bool:
        """
        Check if USB is connected.
        
        Returns:
            True if connected
        """
        return self.connected and self.serial is not None and self.serial.is_open
