"""Quick BLE reconnect test — no protobuf yet, just connect + GATT enumerate again."""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

MAC = "80:E1:26:EA:3D:5A"

async def main():
    print("Re-scanning to see if AmorPoee still advertises...")
    devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
    found = False
    for addr, (dev, adv) in devices.items():
        if addr.upper() == MAC.upper():
            found = True
            print(f"  FOUND: {addr}  RSSI={adv.rssi}  name={dev.name}")
    if not found:
        print("  NOT FOUND in scan. Possible: connected to another central, screen state, or BT wedged.")
        return

    print("Connecting (timeout=30s)...")
    try:
        async with BleakClient(MAC, timeout=30.0) as client:
            print(f"  Connected. is_connected={client.is_connected}, MTU={client.mtu_size}")
            svc = client.services.get_service("8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000")
            if svc:
                print(f"  Flipper serial service present: {svc.uuid}")
            else:
                print("  Flipper serial service MISSING")
    except Exception as e:
        print(f"  CONNECT ERROR: {type(e).__name__}: {e}")

asyncio.run(main())
