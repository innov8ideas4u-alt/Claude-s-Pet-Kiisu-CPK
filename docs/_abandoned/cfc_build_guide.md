# CFC Build Guide (mntm-dev)

## Scope

This guide defines the practical build, deploy, and validation workflow for the CPK Companion FAP (CFC) on Momentum `mntm-dev` devices.

It is written to support the CFC specs in:

- `docs/cfc_fap_specification.md`
- `docs/cfc_protobuf_schema.md`

## Prerequisites

Host:

- Python 3.11+
- `ufbt` installed
- USB data cable
- qFlipper and browser WebSerial tabs closed during active RPC/build sessions

Device:

- Momentum firmware on target row (`mntm-dev` for initial CFC work)
- SD card mounted and writable

Project context:

- CPK repository checked out
- CFC app source rooted at `cfc/` (target layout for CFC workstream)

## Install and verify uFBT

Install:

```bash
py -m pip install --upgrade ufbt
```

Verify:

```bash
ufbt --version
ufbt -h
```

If `ufbt` is not found after install, open a new terminal session and retry.

## SDK/channel alignment for Momentum

Before first CFC build, ensure your uFBT SDK matches your firmware channel expectations.

Typical command shape:

```bash
ufbt update --channel=dev
```

For explicit index/channel control (when needed):

```bash
ufbt update --index-url=https://up.momentum-fw.dev/firmware/directory.json
```

Use a single update strategy per workspace to avoid mixed SDK state.

## Recommended CFC app layout

Inside repo root, expected CFC app structure:

- `cfc/application.fam`
- `cfc/cfc.c`
- `cfc/include/...`
- `cfc/proto/...` (if generated artifacts are staged locally)
- `cfc/dist/` (build outputs)

`application.fam` must define the CFC app metadata, category, and entrypoint.

## Build workflow

Run build commands from the CFC app root (the directory containing `application.fam`).

### 1) Clean build

```bash
ufbt
```

Expected outcome:

- successful compile/link
- `.fap` artifact generated under `dist/`

### 2) Launch to connected device

```bash
ufbt launch
```

Expected outcome:

- artifact uploaded
- CFC app starts on device

### 3) Optional formatting/lint pass (C source)

```bash
ufbt format
ufbt lint
```

Use this before opening PRs for CFC source changes.

## Manual deploy fallback

If `ufbt launch` is unreliable for your session, deploy manually:

1. Build with `ufbt`
2. Copy generated `.fap` from `cfc/dist/` to device app folder (typically under `/ext/apps/` category path)
3. Start app through RPC or on-device launcher

For RPC start, path-based launch is the safest pattern on `mntm-dev` for external apps.

## Runtime validation workflow (CFC V1 smoke)

After deploy, validate in this exact order:

1. Launch CFC app
2. Call `system.ping`
3. Call `system.version`
4. Call `meta.health`
5. Run one GPIO verb (`gpio.read` or `gpio.pulse`)
6. Run one mission lifecycle (`mission.run_named` then `mission.get_status`)
7. Confirm structured status fields on every response

Minimum pass criteria:

- no generic/opaque failures
- status enums map to expected error classes
- `op_id` and `elapsed_ms` present on every response

## Host-side MCP integration test flow

Once CFC is running, validate host module behavior:

1. Ensure `flipper_mcp/modules/cfc/module.py` is wired and importable
2. Exercise tools in order:
   - `flipper_cfc_ping`
   - `flipper_cfc_version`
   - `flipper_cfc_health`
   - one GPIO tool
   - one mission tool
3. Confirm tool-to-RPC mapping and payload conversion
4. Confirm error propagation is classified, not collapsed

## mntm-dev operational constraints

Carry these constraints into every CFC test run:

- Keep lockscreen requirements from `docs/SETUP_REQUIREMENTS_mntm-dev.md` applied.
- Treat external app launch as path-first when launched through RPC.
- Keep sessions deterministic: single-flight operations and explicit timeouts.

## Suggested iteration loop

For rapid development:

1. Edit CFC source
2. `ufbt`
3. `ufbt launch`
4. Run CFC smoke calls from MCP host
5. Capture failure details (`status`, `message`, timing)
6. Fix and repeat

Keep each loop small and verify one operation family at a time.

## Failure triage checklist

If build fails:

- check `application.fam` keys and app id
- check missing headers/libs
- check SDK/channel mismatch

If launch fails:

- verify USB data link and device visibility
- ensure no competing tools own serial/RPC session
- redeploy artifact and relaunch

If RPC responses fail classification:

- inspect host mapping in `flipper_mcp/modules/cfc/module.py`
- verify enum alignment with `docs/cfc_protobuf_schema.md`
- verify operation timeout and busy-state branches in CFC handlers

## Release-readiness checklist (CFC docs + build)

Before calling CFC V1 build-ready:

- `docs/cfc_fap_specification.md` is current
- `docs/cfc_protobuf_schema.md` is current
- this build guide is current to actual commands used
- clean build + launch succeeds on target `mntm-dev` row
- smoke tests pass for system/meta/gpio/mission paths
- at least one negative-path test per operation family returns classified status

## References

- `docs/cfc_fap_specification.md`
- `docs/cfc_protobuf_schema.md`
- `docs/SETUP_REQUIREMENTS_mntm-dev.md`
- `docs/for_ai_contributors.md`
- `docs/decisions/DAY8_FAP_VISION.md`
- `notebooklm/cfc/medium/ufbt-docs/README.md`
- https://github.com/flipperdevices/flipperzero-ufbt
