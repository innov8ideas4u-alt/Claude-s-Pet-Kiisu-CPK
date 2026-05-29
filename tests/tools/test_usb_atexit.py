"""Pure-mock tests for the USBTransport atexit port-close net (R7 Deliverable A).

No hardware. serial.Serial is never opened; self.serial is set to a MagicMock
whose .is_open the test controls. atexit.register/unregister are patched so the
test inspects the wiring without leaving real hooks behind.
"""

from __future__ import annotations

from unittest import mock

import pytest

from flipper_mcp.core.transport.usb import USBTransport


def _make_transport():
    """Build a transport with an explicit port (skips auto-detect) and no real hook."""
    with mock.patch("atexit.register"):
        return USBTransport({"port": "COM_TEST"})


# --- (a) atexit.register wired once during __init__ ------------------------- #
def test_init_registers_atexit_hook_once():
    with mock.patch("atexit.register") as reg:
        transport = USBTransport({"port": "COM_TEST"})
    reg.assert_called_once_with(transport._atexit_hook)
    assert callable(transport._atexit_hook)


# --- (b) _sync_close closes an open serial ---------------------------------- #
def test_sync_close_closes_when_open():
    transport = _make_transport()
    fake_serial = mock.MagicMock()
    fake_serial.is_open = True
    transport.serial = fake_serial
    transport._sync_close()
    fake_serial.close.assert_called_once()


# --- (c) _sync_close is a no-op when not open / None ------------------------ #
def test_sync_close_noop_when_closed():
    transport = _make_transport()
    fake_serial = mock.MagicMock()
    fake_serial.is_open = False
    transport.serial = fake_serial
    transport._sync_close()
    fake_serial.close.assert_not_called()


def test_sync_close_noop_when_serial_none():
    transport = _make_transport()
    transport.serial = None
    transport._sync_close()  # must not raise


def test_sync_close_swallows_close_exception():
    transport = _make_transport()
    fake_serial = mock.MagicMock()
    fake_serial.is_open = True
    fake_serial.close.side_effect = Exception("boom")
    transport.serial = fake_serial
    transport._sync_close()  # must not raise
    fake_serial.close.assert_called_once()


# --- (d) disconnect() unregisters the same handle --------------------------- #
async def test_disconnect_unregisters_hook():
    transport = _make_transport()
    transport.serial = None  # skip the close branch
    with mock.patch("atexit.unregister") as unreg:
        await transport.disconnect()
    unreg.assert_called_once_with(transport._atexit_hook)


async def test_disconnect_closes_and_unregisters():
    transport = _make_transport()
    fake_serial = mock.MagicMock()
    fake_serial.is_open = True
    transport.serial = fake_serial
    with mock.patch("atexit.unregister") as unreg:
        await transport.disconnect()
    fake_serial.close.assert_called_once()
    assert transport.connected is False
    unreg.assert_called_once_with(transport._atexit_hook)
