# BLE Probe Results - 2026-04-30 22:42:59

Target: AmorPoee (80:E1:26:EA:3D:5A) - Kiisu V4B / Momentum mntm-dev
Adapter: OnTopDesk built-in MB Bluetooth


========================================================================
Q0 - Does AmorPoee advertise over BLE?
========================================================================
[22:42:59] Scanning for 10 seconds...
[22:43:09] Scan complete. 6 devices total.

Device MAC                | Name                     | RSSI | Notes
----------------------------------------------------------------------------
BE:11:1C:00:11:35 | MELK-OC21   35           |  -69 | 
4C:CF:7C:98:AE:68 | (no name)                |  -69 | 
FB:5E:CD:44:97:09 | Razer Lev3               |  -52 | 
54:77:B5:BC:0B:3B | (no name)                |  -80 | 
80:E1:26:EA:3D:5A | AmorPoee                 |  -72 | ** AMORPOEE ** ** MATCHES TARGET MAC **
71:27:95:DF:93:4A | (no name)                |  -72 | 

Q0 RESULT: PASS - AmorPoee is advertising and discoverable.

========================================================================
Q1 - Can we connect and enumerate GATT services?
========================================================================
[22:43:09] Connecting to 80:E1:26:EA:3D:5A...
[22:43:19] Connected in 10.24s
  is_connected: True
  MTU: 23 bytes (payload = 20)

--- GATT services & characteristics ---

[Service] 00001801-0000-1000-8000-00805f9b34fb  
  handle=1
    [Char] 00002a05-0000-1000-8000-00805f9b34fb  props=[indicate]  handle=2  max_write_no_resp=20  
        [Desc] 00002902-0000-1000-8000-00805f9b34fb  handle=4
[Service] 00001800-0000-1000-8000-00805f9b34fb  
  handle=5
    [Char] 00002a00-0000-1000-8000-00805f9b34fb  props=[read]  handle=6  max_write_no_resp=20  
    [Char] 00002a01-0000-1000-8000-00805f9b34fb  props=[read]  handle=8  max_write_no_resp=20  
    [Char] 00002a04-0000-1000-8000-00805f9b34fb  props=[read]  handle=10  max_write_no_resp=20  
[Service] 0000180a-0000-1000-8000-00805f9b34fb  Device Information Service (standard)
  handle=12
    [Char] 00002a29-0000-1000-8000-00805f9b34fb  props=[read]  handle=13  max_write_no_resp=20  
    [Char] 00002a25-0000-1000-8000-00805f9b34fb  props=[read]  handle=15  max_write_no_resp=20  
    [Char] 00002a26-0000-1000-8000-00805f9b34fb  props=[read]  handle=17  max_write_no_resp=20  
    [Char] 00002a28-0000-1000-8000-00805f9b34fb  props=[read]  handle=19  max_write_no_resp=20  
    [Char] 03f6666d-ae5e-47c8-8e1a-5d873eb5a933  props=[read]  handle=21  max_write_no_resp=20  
[Service] 0000180f-0000-1000-8000-00805f9b34fb  Battery Service (standard)
  handle=23
    [Char] 00002a19-0000-1000-8000-00805f9b34fb  props=[notify,read]  handle=24  max_write_no_resp=20  
        [Desc] 00002902-0000-1000-8000-00805f9b34fb  handle=26
    [Char] 00002a1a-0000-1000-8000-00805f9b34fb  props=[notify,read]  handle=27  max_write_no_resp=20  
        [Desc] 00002902-0000-1000-8000-00805f9b34fb  handle=29
[Service] 8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000  FLIPPER_SERIAL_SERVICE (research)
  handle=31
    [Char] 19ed82ae-ed21-4c9d-4145-228e62fe0000  props=[read,write,write-without-response]  handle=32  max_write_no_resp=20  FLIPPER_TX (Flipper->us notify)
    [Char] 19ed82ae-ed21-4c9d-4145-228e61fe0000  props=[read,indicate]  handle=34  max_write_no_resp=20  FLIPPER_RX (us->Flipper write)
        [Desc] 00002902-0000-1000-8000-00805f9b34fb  handle=36
    [Char] 19ed82ae-ed21-4c9d-4145-228e63fe0000  props=[notify,read]  handle=37  max_write_no_resp=20  FLIPPER_OVERFLOW (backpressure)
        [Desc] 00002902-0000-1000-8000-00805f9b34fb  handle=39
    [Char] 19ed82ae-ed21-4c9d-4145-228e64fe0000  props=[notify,read,write]  handle=40  max_write_no_resp=20  FLIPPER_RPC_STATE
        [Desc] 00002902-0000-1000-8000-00805f9b34fb  handle=42

Totals: 5 services, 15 characteristics

Critical-UUID checklist (against research from last chat):
  FLIPPER_SERIAL_SERVICE present: True
  TX char present:                True
  RX char present:                True
  OVERFLOW char present:          True
  RPC_STATE char present:         True

Q1 RESULT: PASS - Flipper serial GATT service present with TX+RX. Day 1 can proceed to Q2-Q6.

Day 1 status after Q0+Q1: Q0=PASS  Q1=PASS


## Q2 run @ 2026-04-30 22:58:20


========================================================================
Q2 USB BASELINE - Same ping over COM9
========================================================================
  Connecting to AmorPoee on COM9...
  USB BASELINE FAIL: connect() returned False

WARNING: USB baseline did not pass. BLE result interpretation will be ambiguous.
Proceeding with BLE probe anyway.

========================================================================
Q2 - Can we send protobuf ping over BLE and get PONG?
========================================================================
[22:58:20] Connecting to AmorPoee BLE...
Q2 RESULT: ERROR - TimeoutError: 

Day 1 Q2 summary: USB baseline=FAIL, BLE ping=FAIL


## Q2 run @ 2026-04-30 23:04:05


========================================================================
Q2 USB BASELINE - Same ping over COM9
========================================================================
  Connecting to AmorPoee on COM9...
  USB BASELINE FAIL: connect() returned False

WARNING: USB baseline did not pass. BLE result interpretation will be ambiguous.
Proceeding with BLE probe anyway.

========================================================================
Q2 - Can we send protobuf ping over BLE and get PONG?
========================================================================
[23:04:05] Connecting to AmorPoee BLE...
  Connected in 0.80s. MTU=23
  Subscribing to FROM_FLIPPER (228e61fe0000)...
  Subscription active.
  Built ping: 17B protobuf, 18B framed
  Framed bytes (hex): 1108012a0d0a0b424c452d50494e472d5132
  Writing to TO_FLIPPER (228e62fe0000) (response=False)...
  Write completed in 2ms
  Waiting up to 5s for indicate response...
  [indicate] +18B  total buffer: 18B  raw: 110801320d0a0b424c452d50494e472d5132
  Decoded varint length: 17, consumed: 1
  Payload (17B): 0801320d0a0b424c452d50494e472d5132
  Parsed response: command_id=1, status=0
  PingResponse data (hex): 424c452d50494e472d5132
  PingResponse data (str): b'BLE-PING-Q2'
Q2 RESULT: PASS - PONG received with matching payload echo!
  *** BLE channel speaks Flipper protobuf RPC. ***

Day 1 Q2 summary: USB baseline=FAIL, BLE ping=PASS


## Q3 run @ 2026-04-30 23:05:55


========================================================================
Q3 - storage write + read over BLE (1KB payload)
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes (deterministic pattern)
  Fragments:  ~52 BLE writes at 20B MTU

[23:05:55] Connecting BLE...
  Connected in 11.21s. MTU=23
  Notify subscription active.
  ProtobufRPC adapter wrapped around BLE transport.

[23:06:06] storage_write_file START
  storage_write_file returned: False
  Wall time: 3.18s (322 B/s)
Q3 RESULT: FAIL - storage_write_file returned False
  Likely cause: OVERFLOW backpressure not honored; some chunks dropped

Day 1 Q3 status: FAIL


## Q3v2 run @ 2026-04-30 23:07:33


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:07:33] Connecting BLE...
  Connected in 16.77s. MTU=23
  [overflow] initial read: 262144 bytes credit
  Notify + OVERFLOW subscriptions active. Initial credit: 262144

[23:07:49] storage_write START
  returned: False
  wall: 3.13s (327 B/s)
  overflow notifications received: 1
  overflow log first 10: [262144]
Q3v2 RESULT: FAIL on write

Day 1 Q3v2 status: FAIL


## Q3v2 run @ 2026-04-30 23:09:51


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:09:51] Connecting BLE...
  Connected in 1.06s. MTU=414
Q3v2 RESULT: ERROR — OSError: [WinError -2147467260] Operation aborted

Day 1 Q3v2 status: FAIL


## Q3v2 run @ 2026-04-30 23:10:37


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:10:37] Connecting BLE...
  Connected in 0.65s. MTU=23
  [overflow] initial read: 262144 bytes credit
  Notify + OVERFLOW subscriptions active. Initial credit: 262144

[23:10:38] storage_write START
  returned: False
  wall: 3.13s (328 B/s)
  overflow notifications received: 1
  overflow log first 10: [262144]
Q3v2 RESULT: FAIL on write

Day 1 Q3v2 status: FAIL


## Q3v2 run @ 2026-04-30 23:14:51


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:14:51] Connecting BLE...
Q3v2 RESULT: ERROR — BleakDeviceNotFoundError: Device with address 80:E1:26:EA:3D:5A was not found.

Day 1 Q3v2 status: FAIL


## Q3v2 run @ 2026-04-30 23:17:52


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:17:52] Connecting BLE...
  Connected in 29.12s. MTU=23
  [overflow] initial read: 262144 bytes credit
  Notify + OVERFLOW subscriptions active. Initial credit: 262144

[23:18:21] preflight ping...
  ping returned: b'preflight'

[23:18:22] storage_write START
  returned: False
  wall: 2.53s (404 B/s)
  overflow notifications received: 1
  overflow log first 10: [262144]
Q3v2 RESULT: FAIL on write

Day 1 Q3v2 status: FAIL


## Q3v2 run @ 2026-04-30 23:26:09


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:26:09] Connecting BLE...
Q3v2 RESULT: ERROR — TimeoutError: 

Day 1 Q3v2 status: FAIL


## Q3v2 run @ 2026-04-30 23:29:04


========================================================================
Q3 v2 - storage round-trip WITH OVERFLOW backpressure
========================================================================
  Test path:  /ext/apps_data/ble_probe_q3.bin
  Payload:    1024 bytes
  Fragments:  ~52 BLE writes at 20B MTU

[23:29:04] Connecting BLE...
Q3v2 RESULT: ERROR — TimeoutError: 

Day 1 Q3v2 status: FAIL


## Q4 run @ 2026-04-30 23:37:00


========================================================================
Q4 - Can we reach the CLI prompt over BLE?
========================================================================
  Strategy: send stop_session RPC, drain raw bytes for 1.5s, look for prompt

[23:37:00] Connecting BLE...
Q4 RESULT: ERROR - TimeoutError: 

Day 1 Q4 status: FAIL — RPC-only over BLE


## Q4 run @ 2026-04-30 23:38:29


========================================================================
Q4 - Can we reach the CLI prompt over BLE?
========================================================================
  Strategy: send stop_session RPC, drain raw bytes for 1.5s, look for prompt

[23:38:29] Connecting BLE...
Q4 RESULT: ERROR - TimeoutError: 

Day 1 Q4 status: FAIL — RPC-only over BLE


## Q4 run @ 2026-04-30 23:40:45


========================================================================
Q4 - Can we reach the CLI prompt over BLE?
========================================================================
  Strategy: send stop_session RPC, drain raw bytes for 1.5s, look for prompt

[23:40:45] Connecting BLE...
  Connected in 14.40s. MTU=23
  Notify subscription active.

[23:40:59] Phase A: ping to confirm RPC mode
  ping response: 13B  hex: 0c086332080a0671342d707265
  RPC mode confirmed.

[23:41:00] Phase B: send stop_session RPC
  stop_session framed: 0508649a0100 (6B)
  stop_session sent at 23:41:00.197612

[23:41:00] Phase C: draining for 1.5s, looking for CLI text
  +5B  hex: 0408642200
           ascii: '..d".'

[23:41:01] Phase D: send raw CR, look for prompt
  after CR: +0B
           hex:   
           ascii: ''

[23:41:02] Phase E: send 'help\r', look for command listing
  after 'help': +0B
           hex first 200:   
           ascii first 400: ''

Full rx after all phases: 5 bytes
Full ASCII view: '..d".'

CLI prompt '>: ' seen:    False
Banner/Welcome seen:      False
Help-listing text seen:   False
Any printable ASCII (>8): False

Q4 RESULT: FAIL - No CLI prompt or banner detected over BLE
  *** ARCHITECTURE PIVOT REQUIRED for JS missions ***
  Implication: Flipper's BLE serial-RPC characteristic is RPC-only.
  Options: split-mode (USB for JS, BLE for RPC), pure-RPC mission rewrite,
           or build a custom Flipper app that exposes JS launching via RPC.

Day 1 Q4 status: FAIL — RPC-only over BLE
