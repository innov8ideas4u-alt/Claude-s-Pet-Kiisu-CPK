# Claude ↔ Kiisu4b Gap Closure: Hardware Profile and Safety Spec (2026-05-27)

## Why this file exists
This closes the biggest remaining gap: a device-specific Kiisu4b hardware profile with safe electrical and bring-up constraints.

## 1) Hard guardrails (authoritative defaults)

Use these as non-negotiable guardrails until Kiisu4b-specific measurements prove stricter limits:

- Flipper GPIO logic domain is 3.3V.
- Avoid driving 5V into Flipper outputs.
- 5V tolerance only applies when a pin is configured as input.
- Per-pin current budget: up to 20 mA.
- Total GPIO-side power budget limit: 5 W aggregate.
- Pin 9 (+3.3V) and pin 1 (+5V) are each documented with 1.2 A max load in official docs.
- Pin 1 (+5V) may require explicit enable in GPIO settings when not USB-powered.
- Pin 9 (+3.3V) can be interrupted during SD-card related operations/update flows.

## 2) UART/expansion communication defaults

For expansion-mode workflows and smart modules:

- Initial expansion negotiation starts at 9600 baud.
- Keep timeout assumptions around protocol Tto=250 ms and baud switch dead-time Tdt=25 ms when implementing module-side state machines.
- For classic host RPC over USB serial, enforce explicit `start_rpc_session` lifecycle and status checks per command.

## 3) Kiisu4b profile worksheet (fill this first)

Populate this table from bench validation before full automation rollout.

| Field | Value | Status |
|---|---|---|
| Kiisu4b board revision | TBD | open |
| Required supply rail(s) | TBD | open |
| Typical current draw (idle) | TBD | open |
| Peak current draw (active) | TBD | open |
| Accepts 3.3V UART directly | TBD | open |
| RX pin tolerance (max voltage) | TBD | open |
| Required level shifting | TBD | open |
| Boot-time pin behavior constraints | TBD | open |
| Reset pin behavior | TBD | open |
| Safe power-up sequence | TBD | open |
| Safe power-down sequence | TBD | open |

## 4) Canonical pin map contract

Keep one source of truth for your physical wiring. Fill this and keep versioned.

| Function | Kiisu4b Pin | Flipper Pin | Voltage Domain | Direction | Notes |
|---|---|---|---|---|---|
| GND | TBD | GND | - | - | common ground required |
| UART TX (Kiisu->Flipper RX) | TBD | RX (13/14 path as used) | 3.3V/TBD | out->in | verify inversion/baud |
| UART RX (Flipper TX->Kiisu) | TBD | TX (13/14 path as used) | 3.3V/TBD | in<-out | level-shift if needed |
| Enable/Boot strap | TBD | TBD | TBD | TBD | avoid unsafe boot mode |
| Reset | TBD | TBD | TBD | TBD | optional control line |
| Power rail | TBD | Pin 9 or Pin 1 or external | 3.3V/5V | source | prefer external if near limits |

## 5) Bring-up checklist (must pass before automation)

1. Verify wiring continuity and no shorts.
2. Verify common ground.
3. Power with conservative source first (bench supply if available).
4. Confirm idle current is within expected envelope.
5. Confirm UART RX/TX polarity and baud on a terminal.
6. Confirm no unintended boot/strap behavior.
7. Run read-only host checks: ping/version/list only.
8. Run one harmless write/read roundtrip to isolated path.
9. Run one minimal mission with guaranteed cleanup.
10. Record measured values into worksheet and pin map tables above.

## 5b) Strict fill-the-TBDs bench-run card

Use this card exactly during the first hardware characterization pass.

### Run metadata

| Field | Value |
|---|---|
| Run ID | TBD |
| UTC timestamp start | TBD |
| Operator | TBD |
| Device | AmorPoee / Kiisu V4B |
| Firmware channel | mntm-dev |
| Host OS | Windows 11 |
| Transport | USB CDC |

### Required instruments

- DMM for continuity and rail voltage checks
- Inline current meter or bench supply current readout
- Known-good USB cable

### Gate sequence

| Gate | Requirement | Evidence to record | Pass/Fail |
|---|---|---|---|
| G1 | No shorts on power rail and signal lines | Continuity notes | TBD |
| G2 | Common ground present | GND-to-GND continuity | TBD |
| G3 | Idle current measured at target rail | mA value + rail voltage | TBD |
| G4 | Peak current measured during active action | peak mA value | TBD |
| G5 | UART direction and baud validated | terminal capture summary | TBD |
| G6 | No unsafe boot strap side effect | boot observation note | TBD |
| G7 | RPC read-only checks pass | ping/version/list outputs | TBD |
| G8 | Storage write/read verify passes | byte length + readback match | TBD |
| G9 | One minimal mission passes with cleanup | mission token + log tail | TBD |
| G10 | Worksheet and pin map completed | no remaining TBD cells | TBD |

### Measurement capture block

| Measurement | Value |
|---|---|
| Rail used for Kiisu4b power | TBD |
| Rail voltage under load | TBD |
| Idle current (mA) | TBD |
| Peak current (mA) | TBD |
| UART baud | TBD |
| UART voltage high level | TBD |
| Level shifter used | TBD |

### Completion rule

- Do not mark hardware gap closed until G1-G10 are all PASS and measurement capture block has no TBD values.

### Bench session report template (copy/paste)

```json
{
  "run_id": "HW-YYYYMMDD-001",
  "timestamp_utc_start": "2026-05-27T00:00:00Z",
  "operator": "TBD",
  "device": "AmorPoee / Kiisu V4B",
  "firmware_channel": "mntm-dev",
  "host_os": "Windows 11",
  "transport": "USB CDC",
  "gates": {
    "G1_no_shorts": {"status": "TBD", "evidence": ""},
    "G2_common_ground": {"status": "TBD", "evidence": ""},
    "G3_idle_current": {"status": "TBD", "evidence": ""},
    "G4_peak_current": {"status": "TBD", "evidence": ""},
    "G5_uart_validation": {"status": "TBD", "evidence": ""},
    "G6_bootstrap_safety": {"status": "TBD", "evidence": ""},
    "G7_rpc_read_only": {"status": "TBD", "evidence": ""},
    "G8_storage_roundtrip": {"status": "TBD", "evidence": ""},
    "G9_minimal_mission_cleanup": {"status": "TBD", "evidence": ""},
    "G10_tables_completed": {"status": "TBD", "evidence": ""}
  },
  "measurements": {
    "power_rail": "TBD",
    "rail_voltage_under_load_v": "TBD",
    "idle_current_ma": "TBD",
    "peak_current_ma": "TBD",
    "uart_baud": "TBD",
    "uart_high_level_v": "TBD",
    "level_shifter": "TBD"
  },
  "result": "TBD",
  "notes": []
}
```

## 6) Electrical risk controls

- If Kiisu4b peak current is unknown, do not power from Flipper rails initially.
- Use level shifters if any Kiisu4b signal is above 3.3V domain.
- Never assume DFU/boot states preserve output behavior.
- Avoid connecting large capacitive loads hot while running SD operations.

## 7) Definition of done for hardware gap

Hardware gap is closed only when all are true:

- Completed Kiisu4b worksheet with measured values.
- Completed canonical pin map table and checked-in version tag.
- Bring-up checklist executed and archived with timestamped logs.
- No unexplained resets, brownouts, or corrupted storage events in 3 consecutive full test runs.

## Sources

- https://docs.flipper.net/zero/gpio-and-modules
- https://developer.flipper.net/flipperzero/doxygen/expansion_protocol.html
- https://developer.flipper.net/flipperzero/doxygen/expansion.html
- https://github.com/flipperdevices/flipperzero-protobuf
- https://github.com/elijah629/flipper-rpc
