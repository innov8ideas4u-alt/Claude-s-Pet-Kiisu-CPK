# Abandoned Day 9 drafts

These docs were drafted by Abacus on 2026-05-27 during a corpus rebuild but
overshot the brief: they were supposed to be Phase 1 research planning, not
implementation specs.

Audit by Claude Desktop on Day 9 found:
- cfc_fap_specification.md: invents new top-level RPC service (cpk.cfc.v1.CfcService)
  which the firmware cannot route. Contradicts Recon Finding A.
- cfc_protobuf_schema.md: same structural error - assumes registerable service,
  ignores AppDataExchange (Finding B), no chunking spec (Finding H), no .fal path
  (Finding C).
- cfc_build_guide.md: generic ufbt tutorial, doesn't reference the actual CFC
  architecture or Decision #002 (full-path app_start on mntm-dev).
- wide/claude-kiisu4b-*.md (6 files): generic Claude-driving-Flipper host adapter
  recommendations, NOT recon-informed CFC research. None answer the 4 open
  Phase 1 questions from RECON_LOG.md.

The real Phase 1 spec will be written from the recon (Findings A-I) anchored in
RECON_LOG.md, not polished from these.

Kept for history. Do not use as reference.
