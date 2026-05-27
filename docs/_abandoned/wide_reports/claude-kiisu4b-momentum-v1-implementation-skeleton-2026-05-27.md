# Claude ↔ Kiisu4b Momentum Control: V1 Implementation Skeleton (2026-05-27)

## Goal
Define a concrete V1 host adapter shape for reliable Claude-driven control over a Kiisu4b running Momentum firmware.

## 1) Core module layout

- `adapter/config.py`
- `adapter/errors.py`
- `adapter/transport.py`
- `adapter/session.py`
- `adapter/rpc_ops.py`
- `adapter/js_missions.py`
- `adapter/orchestrator.py`
- `adapter/telemetry.py`
- `adapter/cli.py`

## 2) Runtime state model

`DISCONNECTED -> CONNECTED -> RPC_READY -> BUSY -> RPC_READY -> DISCONNECTED`

- `DISCONNECTED`: no serial handle
- `CONNECTED`: serial opened, prompt drained
- `RPC_READY`: session started, health checks passed
- `BUSY`: operation in flight (single-flight lock)

## 3) Config contract

```python
from dataclasses import dataclass

@dataclass
class AdapterConfig:
    port: str
    baudrate: int = 230400
    rpc_timeout_s: float = 8.0
    op_timeout_s: float = 30.0
    mission_timeout_s: float = 90.0
    retry_count_idempotent: int = 2
    require_unlock: bool = True
    log_jsonl_path: str = "./logs/kiisu_rpc.jsonl"
```

## 4) Error taxonomy

```python
class AdapterError(Exception):
    pass

class TransportError(AdapterError):
    pass

class SessionError(AdapterError):
    pass

class RpcCommandError(AdapterError):
    def __init__(self, command_id: int, status: str, message: str = ""):
        self.command_id = command_id
        self.status = status
        super().__init__(f"command_id={command_id} status={status} {message}".strip())

class DeviceLockedError(AdapterError):
    pass

class MissionTimeoutError(AdapterError):
    pass
```

## 5) Transport interface

```python
class Transport:
    def open(self) -> None: ...
    def close(self) -> None: ...
    def write_raw(self, payload: bytes) -> None: ...
    def read_raw(self, n: int, timeout_s: float) -> bytes: ...
    def drain_prompt(self, marker: bytes = b">: ") -> None: ...
```

## 6) Session manager

```python
class SessionManager:
    def __init__(self, transport: Transport): ...

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...

    def start_rpc_session(self) -> None: ...
    def stop_rpc_session(self) -> None: ...

    def assert_ready(self) -> None: ...
    def assert_unlocked(self) -> None: ...
```

`assert_ready()` minimal checks:
- ping success
- protobuf version returned
- optional lock check

## 7) RPC operation facade

```python
class RpcFacade:
    def ping(self) -> dict: ...
    def protobuf_version(self) -> tuple[int, int]: ...

    def app_start(self, name: str, args: str = "") -> None: ...
    def app_load_file(self, path: str) -> None: ...
    def app_exit(self) -> None: ...

    def gui_send_input(self, key: str, event_type: str = "SHORT") -> None: ...

    def storage_list(self, path: str = "/ext") -> list[dict]: ...
    def storage_read(self, path: str) -> bytes: ...
    def storage_write(self, path: str, data: bytes) -> None: ...

    def lock_status(self) -> bool: ...
```

Execution invariants:
- Every call emits structured telemetry.
- Non-OK status raises `RpcCommandError`.
- `has_next` responses are drained until complete.

## 8) Mission runner contract

```python
class JSMissionRunner:
    def push_script(self, name: str, source: str) -> str: ...
    def run_script(self, script_path: str) -> None: ...
    def wait_for_log(self, log_path: str, timeout_s: float) -> str: ...
    def cleanup_app(self) -> None: ...

    def run(self, script_path: str, log_path: str, timeout_s: float) -> str: ...
```

`run()` flow:
1. Ensure session ready
2. Launch JS app/script
3. Wait/poll log
4. Cleanup (app exit / back)
5. Return log text

## 9) Claude-facing orchestration API

```python
class ClaudeControlAdapter:
    def connect(self) -> dict: ...
    def health(self) -> dict: ...
    def list_files(self, path: str) -> dict: ...
    def write_file(self, path: str, content: str) -> dict: ...
    def run_mission(self, script_path: str, log_path: str, timeout_s: float = 90.0) -> dict: ...
    def send_button(self, key: str, event_type: str = "SHORT") -> dict: ...
    def disconnect(self) -> dict: ...
```

Response shape:
```json
{
  "ok": true,
  "operation": "run_mission",
  "latency_ms": 1320,
  "data": {},
  "error": null
}
```

## 10) Telemetry schema (JSONL)

```json
{
  "ts": "2026-05-27T12:00:00Z",
  "device": "kiisu4b",
  "op": "rpc.app_start",
  "command_id": 42,
  "status": "OK",
  "latency_ms": 88,
  "attempt": 1,
  "idempotent": false
}
```

## 11) Retry policy

- Retry only idempotent operations:
  - ping
  - protobuf_version
  - storage_list
  - storage_read
- No automatic retry for:
  - storage_write
  - app_start
  - gui_send_input
  - mission run

## 12) Minimal V1 acceptance tests

- Connect/disconnect smoke test
- Session lifecycle test
- Ping + protobuf version test
- Storage write/read roundtrip under `/ext/apps_data/...`
- App start + app exit test
- GUI input dispatch test
- JS mission happy path test
- Timeout behavior test
- Locked-device handling test

## 13) Priority next implementation order

1. `transport.py` + `session.py`
2. `rpc_ops.py` health/storage subset
3. `orchestrator.py` single-flight queue
4. `js_missions.py` with cleanup guarantees
5. telemetry + CLI wrapper
