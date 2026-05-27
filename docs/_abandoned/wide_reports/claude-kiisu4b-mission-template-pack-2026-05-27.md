# Claude ↔ Kiisu4b Mission Template Pack (2026-05-27)

## Why this file exists
This closes the reusable-template gap by defining standard mission shapes you can quickly implement in JS + host orchestration.

## Template A: GPIO pulse action

### Use case
Trigger a deterministic digital pulse (reset/enable/test pin).

### Inputs
- pin id
- pulse high ms
- pulse low ms
- repeat count

### Expected outputs
- log lines: start, each pulse index, done
- final status token: `MISSION_OK_GPIO_PULSE`

### Host prechecks
- session ready
- pin configured safely
- operation timeout set

## Template B: UART request/response exchange

### Use case
Send command bytes to Kiisu4b and capture response frame.

### Inputs
- baud rate
- command payload
- response timeout ms
- max response bytes

### Expected outputs
- tx hex
- rx hex
- parse status token: `MISSION_OK_UART_EXCHANGE`

### Host prechecks
- known-good baud from matrix
- level compatibility confirmed

## Template C: poll-until-condition loop

### Use case
Poll GPIO/UART state until condition met or timeout.

### Inputs
- poll interval ms
- total timeout ms
- condition expression id

### Expected outputs
- sampled values with timestamps
- terminal token: `MISSION_OK_CONDITION_MET` or `MISSION_TIMEOUT`

## Template D: file-parameterized mission

### Use case
Upload JSON/text parameters via RPC, run generic mission script that reads params from storage.

### Inputs
- params file path
- params payload
- script path

### Expected outputs
- parameter hash
- run status token: `MISSION_OK_PARAM_RUN`

### Host prechecks
- write/read verify params file

## Template E: cleanup-only recovery mission

### Use case
Force UI/app back to neutral state after a failed run.

### Inputs
- cleanup mode (`app_exit`, `back_press`, `both`)
- retries

### Expected outputs
- `MISSION_OK_CLEANUP`

## Standard host orchestration wrapper for all templates

1. `connect`
2. `start_session`
3. `assert_ready`
4. `optional write params`
5. `launch mission`
6. `wait/poll logs`
7. `cleanup`
8. `collect result`
9. `stop_session`

## Standard mission log schema

```json
{
  "mission": "uart_exchange",
  "ts": "2026-05-27T12:00:00Z",
  "step": "rx",
  "ok": true,
  "data": {
    "hex": "AA550102"
  }
}
```

## Result envelope schema

```json
{
  "ok": true,
  "mission": "gpio_pulse",
  "token": "MISSION_OK_GPIO_PULSE",
  "latency_ms": 840,
  "artifacts": {
    "log_path": "/ext/apps_data/mcp_logs/gpio_pulse.log"
  },
  "error": null
}
```

## Minimal implementation backlog

- Implement Template A and D first (fastest value).
- Add Template B once UART profile is confirmed.
- Add Template C for long-running stabilization tests.
- Keep Template E always available as a universal recovery tool.
