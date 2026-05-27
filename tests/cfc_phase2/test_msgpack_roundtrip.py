"""PING with nested structured payload — FAP must echo byte-identical structure."""

from flipper_mcp.modules.cfc.module import OP_PING


def test_msgpack_roundtrip(cfc_call):
    val = {"nested": [1, 2.5, "string", True, None]}
    resp = cfc_call(OP_PING, {"echo": val})
    assert resp.get("status") == "ok"
    assert resp.get("echo") == val
