"""Bluetooth transport for Flipper Zero."""

from typing import Optional

from .base import FlipperTransport


class BluetoothTransport(FlipperTransport):
    """
    Bluetooth Low Energy transport implementation.
    
    Note: This is a stub implementation. Full BLE support requires
    platform-specific libraries (bleak, etc.)
    """
    
    def __init__(self, config: dict):
        """
        Initialize Bluetooth transport.
        
        Args:
            config: Bluetooth configuration with 'address'
        """
        super().__init__(config)
        self.address = config.get("address")
    
    async def connect(self) -> bool:
        """
        Connect to Flipper Zero via Bluetooth.
        
        Returns:
            True if connection successful
        """
        # Stub implementation
        print("⚠️  Bluetooth transport not yet implemented")
        print("   Install 'bleak' for BLE support: pip install bleak")
        return False
    
    async def disconnect(self) -> None:
        """Close Bluetooth connection."""
        self.connected = False
    
    async def send(self, data: bytes) -> None:
        """
        Send data over Bluetooth.
        
        Args:
            data: Bytes to send
        """
        raise NotImplementedError("Bluetooth transport not yet implemented")
    
    async def receive(self, timeout: Optional[float] = None) -> bytes:
        """
        Receive data from Bluetooth.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Received bytes
        """
        raise NotImplementedError("Bluetooth transport not yet implemented")
    
    async def is_connected(self) -> bool:
        """
        Check if Bluetooth is connected.
        
        Returns:
            True if connected
        """
        return False
