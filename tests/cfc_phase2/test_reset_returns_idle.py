"""RESET in IDLE returns ok; subsequent PING succeeds."""

from flipper_mcp.modules.cfc.module import OP_PING, OP_RESET


def test_reset_then_ping(cfc_call):
    resp = cfc_call(OP_RESET, None)
    assert resp.get("status") == "ok"
    resp2 = cfc_call(OP_PING, {"echo": "after_reset"})
    assert resp2.get("status") == "ok"
    assert resp2.get("echo") == "after_reset"
