"""PING with a simple echo payload — first empirical validation of Q-IMPL-5."""

from flipper_mcp.modules.cfc.module import OP_PING


def test_ping_roundtrip(cfc_call):
    resp = cfc_call(OP_PING, {"echo": "hello"})
    assert resp.get("status") == "ok"
    assert resp.get("echo") == "hello"
