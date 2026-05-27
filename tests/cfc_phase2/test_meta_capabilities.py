"""META_CAPABILITIES returns the Phase 2 opcode list."""

from flipper_mcp.modules.cfc.module import (
    OP_META_CAPABILITIES,
    OP_PING,
    OP_META_VERSION,
    OP_RESET,
    OP_ERROR,
)


def test_meta_capabilities(cfc_call):
    resp = cfc_call(OP_META_CAPABILITIES, None)
    assert resp.get("status") == "ok"
    opcodes = resp.get("opcodes")
    assert isinstance(opcodes, list)
    for op in (OP_PING, OP_META_CAPABILITIES, OP_META_VERSION, OP_RESET, OP_ERROR):
        assert op in opcodes, f"opcode 0x{op:02x} missing from META_CAPABILITIES"
