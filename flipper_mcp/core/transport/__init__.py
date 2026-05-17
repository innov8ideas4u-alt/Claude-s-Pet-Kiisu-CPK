"""Transport layer initialization and factory."""

from typing import Dict, Type
from .base import FlipperTransport
from .auto import AutoTransport
from .usb import USBTransport
from .wifi import WiFiTransport
from .bluetooth import BluetoothTransport

__all__ = [
    "FlipperTransport",
    "AutoTransport",
    "USBTransport", 
    "WiFiTransport",
    "BluetoothTransport",
    "get_transport"
]

# Transport registry
TRANSPORTS: Dict[str, Type[FlipperTransport]] = {
    "auto": AutoTransport,
    "usb": USBTransport,
    "wifi": WiFiTransport,
    "bluetooth": BluetoothTransport,
    "ble": BluetoothTransport,  # Alias
}


def get_transport(transport_type: str, config: dict) -> FlipperTransport:
    """
    Factory function to create transport instances.
    
    Args:
        transport_type: Type of transport ("usb", "wifi", "bluetooth")
        config: Full configuration dict
        
    Returns:
        Transport instance
        
    Raises:
        ValueError: If transport type is unknown
    """
    transport_type = transport_type.lower()
    
    if transport_type not in TRANSPORTS:
        raise ValueError(
            f"Unknown transport type: {transport_type}. "
            f"Available: {', '.join(TRANSPORTS.keys())}"
        )
    
    # Get transport-specific config
    if transport_type == "auto":
        # Auto needs access to both usb/wifi sub-configs.
        transport_config = config.get("transport", {}) or {}
    else:
        transport_config = config.get("transport", {}).get(transport_type, {}) or {}
    
    # Create and return transport
    transport_class = TRANSPORTS[transport_type]
    return transport_class(transport_config)
