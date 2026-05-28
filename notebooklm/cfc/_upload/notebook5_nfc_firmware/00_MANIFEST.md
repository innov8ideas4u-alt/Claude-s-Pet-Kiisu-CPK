# Notebook 5 — NFC Firmware Source (Momentum dev)

**Pulled:** 2026-05-27 from github.com/Next-Flip/Momentum-Firmware branch dev
**Commit:** d3ba597
**Purpose:** Close the Cook 3 NFC-API conflicts that notebook 1 couldn't answer.
Real Momentum NFC source — the files NotebookLM Round 6 asked for by name.

## Files
- 01_nfc_h — base NFC transport API + NfcEvent/NfcCommand
- 02_nfc_poller_h — poller API (callback returns NfcCommand; start vs start_ex)
- 03_nfc_scanner_h — HIGHER-LEVEL scanner (detect-any-card continuous scan; closest to our subscribe use case)
- 04_nfc_generic_event_h — the NfcGenericEvent / NfcGenericEventEx enum values (Round 6 wanted this)
- 05_nfc_device_h — NfcDevice accessors (nfc_device_get_uid etc.)
- 06_nfc_cli_scanner_c_REFERENCE_LOOP — *** THE KEY FILE *** real continuous-scan loop, CLI (no GUI), exactly our use case. Uses NfcScanner.
- 07_nfc_cli_command_scanner_c — the CLI command wrapper around the scanner
- 08_nfc_scene_read_c — standard single-read scene (poller usage reference)
- 09_furi_thread_h — thread API (context/priority for the worker)
- 10_furi_message_queue_h — message queue API (confirm furi_message_queue_put usage/safety)

## Round 7 questions this should now answer
- Exact NfcGenericEvent enum values (file 04)
- The real continuous-scan loop + how NfcCommandContinue is returned (file 06)
- Whether furi_message_queue_put is safe from the scan callback (files 06 + 10 + thread context in 09)
- NfcScanner vs raw NfcPoller — which we should use (files 03 + 06)
