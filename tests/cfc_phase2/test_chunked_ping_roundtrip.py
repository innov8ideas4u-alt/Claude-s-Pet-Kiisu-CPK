"""§4.3 — chunked PING roundtrip (Phase 2.5 Item B).

Sends a ~2KB msgpack payload via flipper_cfc_call(OP_PING, ...). The payload
exceeds CFC_MAX_FRAGMENT_PAYLOAD (884), so flipper_cfc_call fragments the
request into multiple frames. The FAP echoes the structure; response must be
byte-identical to the request and may itself be multi-fragment.
"""

from flipper_mcp.modules.cfc.module import OP_PING


def _build_2kb_echo() -> dict:
    # ~2KB of nested-dict echo content; sentinel "echo" key preserves structure
    # so assertion compares against the exact value sent.
    inner = {"k_" + str(i): "v_" + str(i) * 4 for i in range(80)}
    return {"echo": {"nested": inner, "sentinel": "chunked_ping_v1"}}


def test_chunked_ping_roundtrip(cfc_call):
    payload = _build_2kb_echo()
    resp = cfc_call(OP_PING, payload, timeout_s=30.0)
    assert resp.get("status") == "ok"
    assert resp.get("echo") == payload["echo"]
