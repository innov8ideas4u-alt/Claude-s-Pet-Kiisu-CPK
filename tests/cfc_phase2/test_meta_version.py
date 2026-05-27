"""META_VERSION returns non-empty cfc_version and firmware strings."""

from flipper_mcp.modules.cfc.module import OP_META_VERSION


def test_meta_version(cfc_call):
    resp = cfc_call(OP_META_VERSION, None)
    assert resp.get("status") == "ok"
    assert isinstance(resp.get("cfc_version"), str) and resp["cfc_version"]
    assert isinstance(resp.get("firmware"), str) and resp["firmware"]
    assert isinstance(resp.get("schema_major"), int)
    assert isinstance(resp.get("schema_minor"), int)
