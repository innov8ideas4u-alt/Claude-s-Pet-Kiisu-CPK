# Kiisu / Flipper Zero — Deep Knowledge Base

> **Generated:** 2026-05-15
> **Firmware contexts:** Momentum `mntm-dev`, Momentum `mntm-release-1.4.3` (≈ mntm-012/013 family), Official Flipper Firmware (OFW) `dev`, Unleashed (UN), Xtreme (XFW — merged into Momentum 2024).
> **Scope:** pre-flight reading for `flipperzero-mcp` (Python MCP driving Kiisu V4B over USB-CDC + BLE). Captures the *advanced* gotchas — not basics. Anything pre-mid-2025 is flagged stale.
> **Posture:** primary sources first; every fact has a file:line or URL. Code references > prose. No vibe.

## How to read this file

Three tiers by depth: **TIER 1** (critical / deepest) → **TIER 2** (Path 2 architecture) → **TIER 3** (broad scan). The **Gotcha Index (§15)** is the fastest entry-point — each line cross-references the section that explains it. The **Contradictions section (§16)** calls out where this research conflicts with prior team working-understanding; read it before acting on prior assumptions.

## Table of Contents

- **TIER 1 — Critical for current work**
  - §1 `app_start` / `app_load_file` RPC surface
  - §2 Momentum JS module reference
  - §3 Protobuf RPC — the full surface
  - §4 CLI text-shell quirks
- **TIER 2 — Path 2 architecture relevant**
  - §5 Storage RPC chunked-write protocol
  - §6 USB-CDC transport gotchas
  - §7 BLE quirks beyond Day-1 findings
  - §8 Power and stability
- **TIER 3 — Broad scan**
  - §9 Sub-GHz
  - §10 NFC / RFID
  - §11 BadUSB / BadKB
  - §12 Infrared
  - §13 Ecosystem layer
  - §14 Community knowledge — "wait what" moments
- §15 Index of gotchas (one-liners with section refs)
- §16 **Contradictions Found** (vs prior team understanding)
- §17 Sources (deduplicated, by category)
- §18 Stale-fact flags

---

## TIER 1 — Critical

### 1. `app_start` / `app_load_file` RPC surface

#### 1.1 The protobuf — definitive, all four firmwares share it

**Source:** `flipperdevices/flipperzero-protobuf`, file `application.proto` (dev branch). OFW *is* the canonical proto repo; Momentum/Unleashed/Xtreme pull from it. Verified 2026-05-15.

```protobuf
syntax = "proto3";
package PB_App;

message StartRequest          { string name = 1; string args = 2; }    // = app_start
message AppLoadFileRequest    { string path = 1; }                     // = app_load_file
message AppExitRequest        { }
message AppButtonPressRequest        { string args = 1; int32 index = 2; }
message AppButtonReleaseRequest      { }
message AppButtonPressReleaseRequest { string args = 1; int32 index = 2; }
message AppStateResponse      { AppState state = 1; }   // APP_CLOSED=0, APP_STARTED=1
message GetErrorRequest       { }
message GetErrorResponse      { uint32 code = 1; string text = 2; }
message DataExchangeRequest   { bytes data = 1; }
message LockStatusRequest     { }
message LockStatusResponse    { bool locked = 1; }
```

**Wire envelope (`flipper.proto`, message `Main`):** tag 16 = `app_start_request`, 48 = `app_load_file_request`, 47 = `app_exit_request`, 49 = `app_button_press_request`, 50 = `app_button_release_request`, 75 = `app_button_press_release_request`, 63 = `app_get_error_request`, 64 = `app_get_error_response`, 65 = `app_data_exchange_request`, 58 = `app_state_response`, 17/18 = `app_lock_status_*`.

> Note the *name in the proto message is `StartRequest`* (no `App` prefix). Many wrappers (incl. `flipperzero_protobuf_py`) expose it as `AppStartRequest` at the Python level via the field in `Main`. The wire field-name is `app_start_request`.

#### 1.2 The app-name string — what to put in `StartRequest.name`

| Firmware | appid (FAM) | display name (FAM) | What `loader_start()` actually matches |
|---|---|---|---|
| OFW `dev` | `js_app` | `JS Runner` | EITHER `appid` OR `name` (case-sensitive `strcmp`) |
| Momentum `dev` / `1.4.3` | `js_app` | `JS Runner` | EITHER `appid` OR `name` (case-sensitive `strcmp`) |
| Unleashed `dev` | `js_app` | `JS Runner` | same — Unleashed forks the OFW js_app verbatim |
| Xtreme (deprecated, merged into Momentum 2024) | `js_app` | `JS Runner` | same |

**Sources:**
- OFW `application.fam`: `App(appid="js_app", name="JS Runner", apptype=FlipperAppType.EXTERNAL)` — confirmed from `raw.githubusercontent.com/flipperdevices/flipperzero-firmware/dev/applications/system/js_app/application.fam`.
- Momentum `application.fam`: identical line. `raw.githubusercontent.com/Next-Flip/Momentum-Firmware/dev/applications/system/js_app/application.fam`.
- Loader name matcher: `applications/services/loader/loader.c` — `loader_find_application_by_name()` does `(strcmp(name, list[i].name) == 0) || (strcmp(name, list[i].appid) == 0)`.

> **Practical impact:** Either `"JS Runner"` or `"js_app"` is accepted. `strcmp` is case-sensitive — `"js runner"`, `"JS_RUNNER"`, `"Js Runner"` will all fail with `ERROR_INVALID_PARAMETERS`. The most-cited string in scripts/blogs is `"JS Runner"`.

#### 1.3 `args` contract — what to put in `StartRequest.args` for `js_app`

**Source:** `applications/system/js_app/js_app.c`, the `js_app(void* arg)` entry:

```c
int32_t js_app(void* arg) {
    JsApp* app = js_app_alloc();
    FuriString* script_path = furi_string_alloc_set(EXT_PATH("apps/Scripts"));
    if(arg != NULL && strlen(arg) > 0) {
        furi_string_set(script_path, (const char*)arg);     // arg is treated as a literal path
    } else {
        DialogsFileBrowserOptions browser_options;
        dialog_file_browser_set_basic_options(&browser_options, ".js", &I_js_script_10px);
        // ... user picks file in browser
    }
    // ... js_thread_run(script_path)
}
```

**Confirmed facts:**

- `args` is interpreted as a **filesystem path to the `.js` script**, e.g. `"/ext/apps/Scripts/hello.js"`.
- If `args` is empty or NULL, the device pops a **file-browser dialog on-screen**, defaulting to `/ext/apps/Scripts/`, filtered by `.js`. **The RPC returns OK before the user picks** — the call does not block on user choice.
- There is **no support for path + script-args** in the js_app entry. The argv coming in is a single string used as a path. No JSON, no quoted lists, no script args.
- The path does **not** auto-default to `/ext/apps/Scripts/<arg>` if `arg` is a relative bare name — `furi_string_set(script_path, arg)` overwrites the default, so `args = "hello.js"` becomes a literal path `hello.js` (relative to CWD, which the loader does not set — almost always fails).
- **Always pass an absolute path**: `"/ext/apps/Scripts/<name>.js"`.

#### 1.4 What `app_load_file` *actually* does

**Source:** OFW `applications/services/rpc/rpc_app.c`, handler `rpc_system_app_load_file`:

> "passes the request as an event with the file path to the running application's callback":
> `type = RpcAppEventTypeLoadFile`, `data = string(path)`.
> Returns `ERROR_APP_NOT_RUNNING` if no callback is registered.

**Implication — this is the load-bearing fact for the mcp:**

`app_load_file` requires an app **already started AND with an RPC event callback registered**. The callback is registered via `rpc_app_register_callback()` from inside the running app.

| App | Registers RPC callback? | What happens on `app_load_file`? |
|---|---|---|
| `js_app` (JS Runner) | **NO** (verified — no `rpc_` symbols in `js_app.c`, `js_app_i.h`) | `ERROR_APP_NOT_RUNNING` even if JS Runner is running |
| `Sub-GHz` | YES | Loads a `.sub` file in the receiver UI |
| `Infrared` | YES | Loads an `.ir` remote file |
| `NFC` | YES | Loads a `.nfc` saved card |
| `iButton` | YES | Loads a `.ibtn` key |
| `BadUSB` | YES | Loads a `.txt` Ducky script |
| `U2F`, `Music Player`, `Sub-Brute`, most FAPs | varies — must read each FAP's `app_*_init()` |

> **Conclusion for `flipperzero-mcp`:** Calling `app_load_file("/ext/apps/Scripts/foo.js")` against a running JS Runner will **fail** with `ERROR_APP_NOT_RUNNING` (misleading error name — really means "no callback registered"). To launch a JS script, the only RPC-path is `app_start(name="JS Runner", args="/ext/apps/Scripts/foo.js")` — one shot.

**Enum reference** — `applications/services/rpc/rpc_app.h`:

```c
typedef enum {
    RpcAppEventTypeInvalid,
    RpcAppEventTypeSessionClose,
    RpcAppEventTypeAppExit,
    RpcAppEventTypeLoadFile,
    RpcAppEventTypeButtonPress,
    RpcAppEventTypeButtonRelease,
    RpcAppEventTypeButtonPressRelease,
    RpcAppEventTypeDataExchange,
} RpcAppSystemEventType;
```

#### 1.5 The hidden "RPC context" wart in `args`

**Source:** `rpc_app.c`, handler `rpc_system_app_start_process`:

```c
// If app is being started in RPC mode - pass RPC context via args string
snprintf(app_args_temp, RPC_SYSTEM_APP_TEMP_ARGS_SIZE, "RPC %08lX", (uint32_t)rpc_app);
```

If the caller passes `args == "RPC"` (literal four chars), the firmware **rewrites** it to `"RPC <hex_ptr>"` and that's how the running app discovers it was launched over RPC — by parsing the args for the `"RPC "` prefix.

- **Impact:** Apps that opt-in to RPC mode (Sub-GHz, IR, NFC, etc.) check `if (strncmp(args, "RPC ", 4) == 0)` and switch into a special "remote-controlled" mode where button input comes from `app_button_press` etc.
- **The JS Runner does NOT check for `"RPC "`** — it always treats `args` as a path. So passing `args="RPC /path/to.js"` will be interpreted as the path `"RPC /path/to.js"` literally and fail.

#### 1.6 Edge cases — `app_start`

| Case | Result | Source |
|---|---|---|
| File doesn't exist (`args=/ext/apps/Scripts/nope.js`) | `app_start` returns `OK`, app launches, immediately fails inside JS thread with file-open error; user sees error dialog on device; from RPC side you may see `app_state_response{APP_CLOSED}` shortly after | `js_thread.c` opens file lazily |
| `args` is wrong extension (`.txt` passed to JS Runner) | App launches, JS engine attempts to parse, throws SyntaxError, dies | mJS evaluator — no extension check at launch |
| App already running (`ERROR_APP_SYSTEM_LOCKED`) | `app_start` returns `ERROR_APP_SYSTEM_LOCKED` | `loader.c` — `LoaderStatusErrorAppStarted` → `PB_CommandStatus_ERROR_APP_SYSTEM_LOCKED` |
| Unknown app name | `ERROR_INVALID_PARAMETERS` (NOT a specific "no such app" code) | `LoaderStatusErrorUnknownApp` → `INVALID_PARAMETERS` |
| App starts another app (loader-chain) | Blocked. Only one foreground app at a time. The chain-launching app must `app_exit` first, which is rarely automatic | `loader.c` keeps `app_active` mutex |
| `.fap` extension to `app_start` | Pass full path as `name`: `app_start(name="/ext/apps/Misc/myapp.fap", args="")`. `loader_do_start_by_name()` falls through to `storage_file_exists(storage, name)` then `flipper_application_load()` | `loader.c` |
| `app_load_file` on running Sub-GHz with `.ir` file | App returns its own error via `app_get_error_response` (not the LoadFile RPC) — typically `code != 0, text = "wrong file"` | each app's `_rpc_callback` |

#### 1.7 Authoritative call pattern for launching a JS script via RPC

```text
# WHAT WORKS
app_start(name="JS Runner", args="/ext/apps/Scripts/hello.js")
  → command_status = OK
  → JS Runner launches
  → js_thread loads /ext/apps/Scripts/hello.js
  → script runs to completion or `die()`
  → JS Runner emits app_state_response{APP_CLOSED} when exit

# WHAT DOES NOT WORK (verified from source)
app_load_file("/ext/apps/Scripts/hello.js")
  → ERROR_APP_NOT_RUNNING  (JS Runner doesn't register an RPC callback)

app_start(name="JS Runner", args="hello.js")
  → app starts but `Storage` fails to open relative path

app_start(name="js_app", args="...")
  → ALSO works — loader matches appid too. Either string is fine. Most code uses "JS Runner".
```

#### 1.8 Firmware dating

- mntm-008 (Nov 2023) — overhauled JS modules
- mntm-009 (Jan 2024) — added "send signal once" RPC
- mntm-010 (Apr 2024) — new CLI architecture (autocomplete, kbd shortcuts), BLE 128-bit UUID adv
- mntm-011 (Jul 2024) — added GUI submodules to JS
- mntm-012 (Dec 2024) — **JS SDK 1.0** with breaking changes to `gui/submenu` / `gui/widget`; OFW NFC CLI / buzzer
- mntm-013/014 — (post-Dec 2024, dates not confirmed publicly; `1.4.3` likely maps to mntm-013 era based on user-supplied label)

> Anything published pre-mntm-010 (April 2024) on CLI behavior or BLE adv is **stale**.

---

### 2. Momentum JS module reference — Momentum `mntm-dev` JS SDK 1.x

**Canonical source:** `applications/system/js_app/modules/` directory in `Next-Flip/Momentum-Firmware` at `dev` branch. TypeScript types in `applications/system/js_app/packages/fz-sdk/` (mirrors `@next-flip/fz-sdk-mntm` on npm, currently `1.0.0`, GPL-3.0). The OFW SDK is `@flipperdevices/fz-sdk` — scripts targeting OFW work on Momentum too.

> **Compatibility entry-point:** every script should start with `checkSdkCompatibility(1, 0)` (or whichever) — runtime aborts if the device SDK is too old/new. Signature: `checkSdkCompatibility(expectedMajor, expectedMinor): void | never`.

#### 2.1 Module list — `mntm-dev`, `JS SDK 1.0`

| Module | `require(...)` string | Plugin entry (.fam) | Source file |
|---|---|---|---|
| Globals (no require) | n/a | js_thread | `js_thread.c` (`print`, `delay`, `parseInt`, `require`, `console.{log,warn,error,debug}`, `ffi_address`, `chr`, `die`, `load`, `__dirname`, `__filename`, SDK-compat fns) |
| flipper | `"flipper"` | n/a (compiled into js_app) | `modules/js_flipper.c` |
| event_loop | `"event_loop"` | `js_event_loop` | `modules/js_event_loop/js_event_loop.c` |
| math | `"math"` | `js_math` | `modules/js_math.c` |
| storage | `"storage"` | `js_storage` | `modules/js_storage.c` |
| gui | `"gui"` (+ submodules) | `js_gui` | `modules/js_gui/js_gui.c` + 15 subviews |
| gpio | `"gpio"` | `js_gpio` | `modules/js_gpio.c` |
| notification | `"notification"` | `js_notification` | `modules/js_notification.c` |
| badusb | `"badusb"` | `js_badusb` | `modules/js_badusb.c` |
| serial | `"serial"` | `js_serial` | `modules/js_serial.c` |
| subghz | `"subghz"` | `js_subghz` | `modules/js_subghz/js_subghz.c` |
| infrared | `"infrared"` | `js_infrared` | `modules/js_infrared/js_infrared.c` |
| blebeacon | `"blebeacon"` | `js_blebeacon` | `modules/js_blebeacon.c` |
| usbdisk | `"usbdisk"` | `js_usbdisk` | `modules/js_usbdisk/js_usbdisk.c` |
| vgm (ICM42688P motion) | `"vgm"` | `js_vgm` | `modules/js_vgm/` |
| i2c | `"i2c"` | `js_i2c` | `modules/js_i2c.c` |
| spi | `"spi"` | `js_spi` | `modules/js_spi.c` |
| tests (build-time) | `"tests"` | `js_tests` (debug only) | `modules/js_tests.c` |

GUI submodules (each is `require("gui/<name>")`): `loading`, `empty_screen`, `submenu`, `text_input`, `number_input`, `byte_input`, `button_panel`, `button_menu`, `menu`, `vi_list` (mntm extension), `popup`, `text_box`, `dialog`, `file_picker`, `widget`, `icon`.

#### 2.2 `flipper` — device info globals

**Source:** `modules/js_flipper.c` registration. Exposed on global `flipper` object (one `require` call returns it):

```js
let flipper = require("flipper");
flipper.getModel()        // string device model
flipper.getName()         // string device-name (the BLE name too)
flipper.getBatteryCharge()// number 0-100
flipper.firmwareVendor    // string property — "Flipper Devices Inc.", "Momentum", "Xtreme", etc.
flipper.jsSdkVersion      // array [major, minor]
```

**Gotcha:** `firmwareVendor` is `"Momentum"` on `mntm-*`, `"Flipper Devices Inc."` on OFW. Useful for forking scripts.

#### 2.3 `event_loop` — the async / streaming primitive

**Source:** `modules/js_event_loop/js_event_loop.c`.

```js
let el = require("event_loop");
el.subscribe(contract, callback, ...userArgs) → {cancel(): void}
el.run(): void | never           // blocks until stop() called
el.stop(): void
el.timer("oneshot"|"periodic", intervalMs) → Contract   // emits on tick
el.queue(length) → Queue<T>      // FIFO message queue, .input is a Contract, .send(msg)
```

**Patterns (battle-tested from `examples/apps/Scripts/interactive.js`):**

```js
let eventLoop = require("event_loop");
let gui = require("gui");
let dialog = require("gui/dialog");

let views = { dialog: dialog.makeWith({ header: "Hi" }) };

eventLoop.subscribe(views.dialog.input, function (_sub, button, gui, views) {
    if (button === "left") gui.viewDispatcher.switchTo(views.dialog);
    return [gui, views];     // last value is fed as userArgs on next callback fire
}, gui, views);

eventLoop.run();
```

**Hard gotchas:**

- `eventLoop.run()` blocks the script thread forever until `eventLoop.stop()` is called from inside a callback. There is **no implicit exit**.
- `subscribe`'s callback signature is `(subscription, item, ...userArgs)`. The callback **can return new userArgs** as an array — they replace the previous userArgs in the next firing.
- No `Promise`, no `async/await`. Event-driven only.
- Callbacks run on the JS thread — they must not block more than a few ms.

#### 2.4 `subghz` — Sub-GHz radio

**Source:** `modules/js_subghz/js_subghz.c`. Confirmed methods registered via `mjs_set`:

```js
let s = require("subghz");
s.setup()                        // claim radio
s.end()                          // release
s.setRx() / s.setIdle()
s.getRssi(): number|undefined
s.getState(): "RX"|"TX"|"IDLE"|""
s.getFrequency(): number
s.setFrequency(hz: number): number     // returns clamped freq
s.isExternal(): boolean          // CC1101 module attached?
s.transmitFile(path: string, repeat?: number): true
```

- Frequency clamping is regional — `setFrequency` returns what was actually set.
- `transmitFile` is fire-and-block (synchronous until TX done). Pre-mid-2024 firmwares had no `repeat` arg — flagged stale if you see docs without it.

#### 2.5 `infrared` — IR

**Source:** `modules/js_infrared/js_infrared.c`. Only TWO methods exist:

```js
let ir = require("infrared");
ir.sendSignal(protocol: string, address: string, command: string)
ir.sendRawSignal(timings: number[], frequency: number, duty?: number)
```

No `receive` over JS yet (as of mntm-012). Use `subghz` for receive.

#### 2.6 `badusb` — HID emulation

**Source:** `modules/js_badusb.c`. All methods registered with mjs_set.

```js
let bu = require("badusb");
bu.setup({ vid: 0x046D, pid: 0xC52B, mfrName: "...", prodName: "...", layoutPath: "/ext/badusb/assets/layouts/en-US.kl" })
bu.isConnected(): boolean
bu.quit()
bu.press(...keys)     // KeyCode = "CTRL"|"SHIFT"|"ALT"|"GUI"|MainKey|number
bu.hold(...keys)
bu.release(...keys)
bu.print(s, delay?)
bu.println(s, delay?)
bu.altPrint(s, delay?)   // Windows ALT-numpad only
bu.altPrintln(s, delay?)
```

- `setup({})` is optional. Call `bu.quit()` if you want to switch USB profile after.
- `isConnected()` returns false on Kiisu if USB is in CDC mode and BadUSB profile hasn't claimed the bus.

#### 2.7 `blebeacon` — beacon advertising

**Source:** `modules/js_blebeacon.c`.

```js
let b = require("blebeacon");
b.isActive(): boolean
b.setConfig({ minIntervalMs, maxIntervalMs, channels, power, mac })   // tx params
b.setData(bytes)                  // raw adv payload
b.start()
b.stop()
b.keepAlive()                     // call periodically to prevent stack timeout
```

- **Critical:** while a BLE beacon is active, **the device's regular BLE (incl. RPC over BLE) is stopped**. So calling JS scripts that use `blebeacon` over BLE will get cut off mid-script.

#### 2.8 `storage` — filesystem

**Source:** `modules/js_storage.c`. Mirrors most of `Storage`-RPC plus virtual-mount API.

```js
let st = require("storage");
let f = st.openFile(path, accessMode, openMode)  // returns File or undefined
//   accessMode = "r"|"w"|"rw"
//   openMode = "open_existing"|"open_always"|"open_append"|"create_new"|"create_always"
f.read(): ArrayBuffer       // returns up to N bytes — see file methods
f.write(buf): number
f.seekRelative(n) / seekAbsolute(n) / tell() / size() / truncate() / eof() / close() / isOpen()
f.copyTo(destPath)

st.fileExists(p) / directoryExists(p) / fileOrDirExists(p) / stat(p) / remove(p) / rmrf(p)
st.rename(old, new) / copy(src, dst)
st.makeDirectory(p) / readDirectory(p): FileInfo[]
st.fsInfo(): { totalSpace, freeSpace }
st.nextAvailableFilename(dir, name, ext)
st.arePathsEqual(a, b) / st.isSubpathOf(parent, child)

// virtual-mount (FatFS image as a disk for usbdisk):
st.virtualInit(path)
st.virtualMount()
st.virtualQuit()
```

#### 2.9 `gpio`, `notification`, `serial`, `usbdisk`, `math`

**`gpio`:**
```js
let g = require("gpio").get("PC0")    // or pin index
g.init({ direction: "in"|"out", outMode: "push_pull"|"open_drain",
         inMode: "analog"|"plain_digital"|"interrupt"|"event",
         edge: "rising"|"falling"|"both", pull: "up"|"down" })
g.write(bool) / g.read(): bool / g.readAnalog(): number  // millivolts
g.interrupt(): Contract        // event_loop-compatible
g.isPwmSupported() / g.pwmWrite(freq, duty) / g.isPwmRunning() / g.pwmStop()
```

**`notification`:** `success()`, `error()`, `blink(color, type)` — colors `"red"|"green"|"blue"|"yellow"|"cyan"|"magenta"`, types `"short"|"long"`.

**`serial`:** `setup(port, baud)`, `end()`, `write(buf)`, `read(n, timeout)`, `readln(timeout)`, `readBytes(n, timeout)`, `readAny(timeout)`, `expect(needle, timeout)`. Useful for talking to ESP boards.

**`usbdisk`:** `createImage(path, sizeBytes)`, `start(path)`, `stop()`, `wasEjected()`.

**`math`:** standard library shim because mJS has none. Methods: `isEqual`, `abs`, trig+inverse (`sin/cos/tan/asin/acos/atan/atan2/sinh/asinh/cosh/acosh/tanh/atanh`), `cbrt/sqrt/pow/exp/log`, `ceil/floor/trunc/sign/random/clz32/max/min`. Constants: `PI`, `E`, `EPSILON`.

#### 2.10 mJS limitations — **the load-bearing reality**

**Source:** `cesanta/mjs` README, "Restrictions" section — quoted verbatim:

> "No standard library. No String, Number, RegExp, Date, Function, etc. JSON.parse() and JSON.stringify() are available. No closures, only lexical scoping (i.e. nested functions are allowed). No exceptions. No new. In order to create an object with a custom prototype, use Object.create(), which is available. Strict mode only. No var, only let. No for..of, =>, destructors, generators, proxies, promises. No getters, setters, valueOf, prototypes, classes, template strings. No == or !=, only === and !==. mJS strings are byte strings, not Unicode strings."

**Translated to dev practice on Flipper:**

| Want | Can't have | Workaround |
|---|---|---|
| `try { } catch { }` | no exceptions in mJS | Check return values; call `die(msg)` to abort; for "soft" errors return sentinel like `undefined` or `null` and `if`-check |
| `new Date()` | no Date | Use `flipper.getName()` + system-time via Storage timestamps; no high-resolution time in JS — only `delay(ms)` |
| `async/await`, `Promise` | none | Use `event_loop` with subscribe + queue (sec 2.3) |
| `for (let x of arr)` | no `for..of` | Use `for (let i = 0; i < arr.length; i++)` |
| `() => x` arrow fns | no arrows | Use `function(){ return x; }` |
| `class Foo {}` | no class keyword | Factory: `function makeFoo(){ return { ... }; }` |
| Regex `/foo/g` | no RegExp | Manual string scan via `indexOf` / `slice` |
| Template strings `` `${x}` `` | none | `"a " + x + " b"` |
| `==` / `!=` | none | Always `===` / `!==` |
| `var x` | none | Always `let` |
| Unicode strings | byte strings only | UTF-8 bytes work; multi-byte chars are 2+ chars in `.length` |
| Closures | only "lexical scoping" — capturing **mutable** outer-scope vars in nested fns is broken | Pass needed values explicitly via event_loop userArgs |
| `Number.toFixed()` | no Number methods | Use `math` module or manual string slicing |

> **mJS is a SUBSET of mJS that's a subset of JavaScript.** Per OFW issue #3516 ("There is no language specification for Flipper's subset of MJS"), the **Flipper-flavoured mJS is even more restricted than upstream mJS**, and there is no official spec. Don't trust the mJS README 100% — test on device.

#### 2.11 `@next-flip/fz-sdk-mntm` (npm)

- Version `1.0.0`, last published ≈ Feb 2026, license GPL-3.0, ~95 KB.
- TypeScript `.d.ts` files for IDE type-checking — **Flipper does not run TypeScript**; users transpile to JS, then upload.
- Companion CLI: `@next-flip/create-fz-app-mntm` scaffolds a new project.
- Versioning rule: major.minor matches the firmware's JS SDK version (`flipper.jsSdkVersion`).
- The corresponding OFW package is `@flipperdevices/fz-sdk`; scripts written against it work on Momentum.

---

### 3. Protobuf RPC — the full surface

**Repos:**
- `flipperdevices/flipperzero-protobuf` — proto definitions. Branches: `main` (last release tag), `dev` (current). Versioning lives in `system.proto/ProtobufVersionResponse { major, minor }`.
- `flipperdevices/flipperzero_protobuf_py` — Python client, also reflects the version surface.
- Rust: `flipper-rpc` (crates.io 0.6.x) — autoreg'd up to mid-2025.
- Go: `github.com/flipperdevices/go-flipper`.

#### 3.1 Top-level envelope: `Main` (file: `flipper.proto`)

```protobuf
message Main {
    uint32 command_id = 1;
    CommandStatus command_status = 2;   // OK | ERROR_* enum
    bool has_next = 3;
    oneof content { /* 75 entries — full table below */ }
}
```

| Tag | Field | Service |
|---|---|---|
| 4 | empty | (heartbeat / ack) |
| 5,6 | system_ping_request/response | System |
| 7,8 | storage_list_request/response | Storage |
| 9,10 | storage_read_request/response | Storage |
| 11 | storage_write_request | Storage (streamed) |
| 12 | storage_delete_request | Storage |
| 13 | storage_mkdir_request | Storage |
| 14,15 | storage_md5sum_request/response | Storage |
| 16 | app_start_request | App |
| 17,18 | app_lock_status_request/response | App |
| 19 | stop_session | Session control |
| 20,21,22 | gui_*_screen_stream + screen_frame | GUI |
| 23 | gui_send_input_event_request | GUI |
| 24,25 | storage_stat_request/response | Storage |
| 26,27 | gui_*_virtual_display_request | GUI |
| 28,29 | storage_info_request/response | Storage |
| 30 | storage_rename_request | Storage |
| 31 | system_reboot_request | System (OS/DFU/UPDATE) |
| 32,33 | system_device_info_request/response | System (streamed: many key/value pairs, terminated by `has_next=false`) |
| 34 | system_factory_reset_request | System |
| 35,36 | system_get_datetime_request/response | System |
| 37 | system_set_datetime_request | System |
| 38 | system_play_audiovisual_alert_request | System |
| 39,40 | system_protobuf_version_request/response | System |
| 41,46 | system_update_request/response | System |
| 42 | storage_backup_create_request | Storage |
| 43 | storage_backup_restore_request | Storage |
| 44,45 | system_power_info_request/response | System (streamed kv) |
| 47 | app_exit_request | App |
| 48 | app_load_file_request | App |
| 49,50 | app_button_press/release_request | App |
| 51 | gpio_set_pin_mode | GPIO |
| 52 | gpio_set_input_pull | GPIO |
| 53,54 | gpio_get_pin_mode + response | GPIO |
| 55,56 | gpio_read_pin + response | GPIO |
| 57 | gpio_write_pin | GPIO |
| 58 | app_state_response | App (unsolicited) |
| 59,60 | storage_timestamp_request/response | Storage |
| 61,62 | property_get_request/response | Property |
| 63,64 | app_get_error_request/response | App |
| 65 | app_data_exchange_request | App |
| 66 | desktop_is_locked_request | Desktop |
| 67 | desktop_unlock_request | Desktop |
| 68,69 | desktop_status_subscribe/unsubscribe_request | Desktop |
| 70 | desktop_status | Desktop (notification) |
| 71 | storage_tar_extract_request | Storage |
| 72,73 | gpio_get_otg_mode + response | GPIO |
| 74 | gpio_set_otg_mode | GPIO |
| 75 | app_button_press_release_request | App |

#### 3.2 Framing — USB CDC vs BLE

**USB CDC:** standard nanopb length-delimited:

```
[varint(N)] [N bytes of Main protobuf]
```

Varint is little-endian base-128. See `flipperzero_protobuf_py` and `busse/flipperzero-mcp/src/flipper_mcp/core/protobuf_rpc.py`:

```python
self.command_id = (self.command_id + 1) % 0xFFFFFFFF
# encode varint LSB-first, 7 bits at a time, MSB=continuation
```

**BLE:** **same framing**, but split across multiple GATT writes to the RX characteristic. Each write is up to `BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX = 243 bytes` (file: `serial_service.h`). The full delimited message can be larger than 243 — you must split outgoing writes into 243-byte chunks.

#### 3.3 BLE service and characteristic UUIDs

**Source:** `targets/f7/ble_glue/services/serial_service_uuid.inc` — 128-bit UUIDs:

| What | UUID (canonical string form) |
|---|---|
| Service | `8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000` |
| TX (notify, central reads) | `19ed82ae-ed21-4c9d-4145-228e61fe0000` |
| RX (write-without-response) | `19ed82ae-ed21-4c9d-4145-228e62fe0000` |
| Flow Control (notify, "buff_size") | `19ed82ae-ed21-4c9d-4145-228e63fe0000` |
| RPC Status (notify) | `19ed82ae-ed21-4c9d-4145-228e64fe0000` |

> Note the **firmware stores UUIDs byte-reversed in the source array** (`0x00, 0x00, 0xfe, 0x60, ...`). The canonical string form uses the reversed bytes. The 0xFE60-0xFE64 range is the "vendor short prefix".

**Constants:**
```c
#define BLE_SVC_SERIAL_DATA_LEN_MAX       (486)   // internal RX ring buffer
#define BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX (243)   // per-GATT-write max payload
#define RPC_BUFFER_SIZE                   (1024)  // application-level RPC stream buffer (rpc.h)
```

#### 3.4 The "OVERFLOW credit-flow" protocol — definitive

**Source:** `targets/f7/ble_glue/services/serial_service.c`.

**Mechanism:**

1. Device exposes a `buff_size` value via the **Flow Control characteristic** (uuid `*FE63*`). Initial value = `BLE_SVC_SERIAL_DATA_LEN_MAX` = 486, **stored byte-reversed** (`REVERSE_BYTES_U32(buff_size)` is what's actually written to the GATT value).
2. Central (the MCP) **must subscribe to notifications** on the Flow Control characteristic.
3. Each time the central writes N bytes to RX (`*FE62*`), the device's `bytes_ready_to_receive` decrements by N. **The central is expected to maintain its own copy of this credit counter.**
4. When the device fully consumes the ring buffer, it calls `ble_svc_serial_notify_buffer_is_empty()` which resets `bytes_ready_to_receive = buff_size` and **notifies** the FC characteristic with the new (reversed) value. The central must **add this back** to its credit counter.
5. **If the central writes faster than the device drains**, you'll see the firmware log warning:
   > `Received 240, while was ready to receive 54 bytes. Can lead to buffer overflow!`
   The device then **silently disconnects** with reason 0x08 (supervision timeout) after some seconds. This is forum-reported in `forum.flipper.net/t/how-to-handle-ble-overflow/13348`.

**Practical algorithm for the MCP's BLE transport:**

```python
credits = 486  # initial — but actually read from Flow Control char value at connect

def write_ble(payload: bytes):
    while payload:
        # wait for at least 1 byte of credit
        while credits == 0:
            wait_for_credit_notification()   # FC characteristic notify
        chunk_size = min(len(payload), 243, credits)
        chunk = payload[:chunk_size]
        gatt_write_no_response(RX_UUID, chunk)
        credits -= chunk_size
        payload = payload[chunk_size:]

def on_flow_control_notify(value: bytes):
    # value is reversed uint32 — restore byte order
    new_credit = int.from_bytes(value, "little")
    # this is the FULL replenished size, not a delta
    credits = new_credit
```

> **Subtlety:** the notification value is the *new total*, not a delta. The firmware resets `bytes_ready_to_receive = buff_size` (full reset) when the buffer drains to zero. So treat the notify as "reset credit to N", not "add N".

#### 3.5 RPC Status characteristic (FE64)

`ble_svc_serial_set_rpc_active(active)` writes `1` (Active) or `0` (NotActive) and notifies. Use this to know **the device has actually entered RPC mode** — the central should subscribe and wait for the `Active` notification before sending the first `Main` envelope.

> **Implication:** On BLE, you do NOT send `start_rpc_session\r` like on USB CDC. The device enters RPC mode automatically when a central subscribes to the serial service and the desktop is unlocked. The RPC Status characteristic flips to Active. This is the **biggest BLE-vs-USB difference** for the MCP.

#### 3.6 `has_next`, `command_id`, lifecycle

- `command_id` is a 32-bit rolling counter the **client** assigns. Tag 0 is technically reserved but commonly used for unsolicited server messages (e.g. `app_state_response`, `desktop_status`).
- Responses echo the request's `command_id`.
- `has_next = true` means "more responses with this command_id follow." Used by:
  - `system_device_info_response` (one kv per envelope)
  - `system_power_info_response`
  - `storage_list_response` (each chunk holds a batch of `File` entries)
  - `storage_read_response` (large file reads)
  - `gui_screen_frame` (streaming frames)
- **Client MUST handle has_next for these RPCs** or it will read the first response and miss the rest.
- The busse/flipperzero-mcp's `protobuf_rpc.py` caps `has_next` iteration at 100 to avoid infinite loops on malformed sequences.
- `command_status` is the response's pass/fail enum. **Always check before deserializing the payload.**

#### 3.7 Wire-lock / concurrency model

**Source:** `applications/services/rpc/rpc.c`.

- The firmware allocates **one RPC session** per transport (USB and BLE are two separate sessions). They can in theory run simultaneously **but share most of the same handlers**.
- Each session has its own `furi_mutex_t busy_mutex` (acquired with `FuriWaitForever`) that **serializes RPC handler execution on that session**.
- **Therefore on a single transport, RPCs are strictly serialized.** Even if you fire off two `Main` envelopes with different `command_id`, the second one waits on the busy_mutex.
- The session also has a `callbacks_mutex` protecting the `send_bytes` / `buffer_empty` / `session_closed` callbacks — i.e. the transport-write callback can be hot-swapped safely.
- The `furi_stream_buffer` holding incoming wire bytes is sized `RPC_BUFFER_SIZE = 1024`. Larger envelopes (e.g. big `storage_write_request`) MUST be split client-side into multiple `Main` messages with `has_next=true`.

#### 3.8 Known protobuf-RPC bugs / workarounds

| Issue | FW affected | Workaround |
|---|---|---|
| BLE supervision-timeout disconnect during large reads (`StorageReadResponse`) — FW #3174, opened Oct 2023 | OFW pre-1.0, possibly current | Use credit-flow strictly; subscribe to FC notify; the client must not block on its own buffers either |
| `storage_write_request` is one-shot in proto but firmware EXPECTS chunked with `has_next` | All | Send in ≤512-byte chunks per Main; last chunk has `has_next=false` |
| `system_device_info_response` order is **not guaranteed** | All | Collect into dict, don't assume order |
| `app_load_file` returns `ERROR_APP_NOT_RUNNING` against apps that DID start but didn't register a callback (e.g. JS Runner) | All | Don't use `app_load_file` for JS Runner — use `app_start` |
| FW issue #4317 "System Protobuf Version timeout" — connect-time race | OFW ≥0.99 | Retry `system_protobuf_version_request` up to 3x with 600ms-1.2s timeout (busse-mcp does this) |
| `start_rpc_session\r\n` (CRLF) silently hangs on USB CDC, only `\r` works | All | Always send `start_rpc_session\r` on USB |
| `subghz tx_from_file` not in protobuf (issue #3820) | All | Use `app_start("Sub-GHz", "RPC")` + `app_load_file(<.sub path>)` instead |

#### 3.9 Reliable vs flaky inventory

**Rock-solid (use freely):** `system_ping`, `system_device_info`, `system_protobuf_version`, all `storage_*` (with chunking), `app_start`, `app_exit`, `app_state` notifications, `app_button_*`, `gpio_*`, `gui_send_input_event`, `desktop_is_locked`, `system_get_datetime`.

**Flaky / firmware-sensitive:** `gui_start_screen_stream` (occasional drops on BLE under load), `storage_backup_create/restore` (long-running, can timeout), `system_update_request` (handshake fragile, ESP-only on Kiisu).

**Outright stubbed / not implemented on Kiisu V4B (clone-specific — verify per board):** Some `property_get_*` keys may return `ERROR_INVALID_PARAMETERS` on clones. NFC API may differ in subtle ways.

---

### 4. CLI text-shell — quirks we'll keep hitting

#### 4.1 The prompt

**Source:** Flipper Zero docs (`docs.flipper.net/zero/development/cli`) and PuTTY/screen usage. The CLI prompt is:

```
>:_                   (literal: 0x3E 0x3A 0x20)
```

That's `'>'` + `':'` + `' '` (space). After every command the CLI emits `\r\n>: ` and waits.

**Banner / MOTD on connect** (Momentum `cli_main_shell.c` → `cli_main_motd()`):

```
[ANSI orange escape]
              _.-------.._                    -,
... ASCII flipper ...
Welcome to Flipper Zero Command Line Interface!
Read the manual: https://docs.flipper.net/development/cli
Run `help` or `?` to list available commands

Firmware version: <version>

>:
```

**Line endings:** the firmware emits **CRLF** (`\r\n`) consistently for output. The client **must send CR only** (`\r`) for command submission. Sending `\r\n` is the most common silent-hang failure (see 4.4).

**Detection heuristic** (for the MCP's USB transport):

```python
# Detect "command done" boundary
PROMPT_RE = re.compile(b'\r?\n>: $')
# Strict version that won't false-positive on user output that ends with ">: ":
PROMPT_TAIL = b'\r\n>: '
# After sending command + '\r', read until you see PROMPT_TAIL trailing OR a 1.5s quiet-window
```

#### 4.2 Full CLI command inventory — Momentum `mntm-dev`, `mntm-1.4.3` family

**Source:** registered in `applications/services/cli/cli_main_commands.c` plus loader, plus dispatch to individual app's `_cli_command`.

Core (always present):
- `!` (alias for `device_info`), `device_info`, `info` — device info dump
- `help`, `?` — list commands
- `log [level]` — set log level / live tail (`error`,`warn`,`info`,`debug`,`trace`)
- `free`, `free_blocks` — heap
- `echo`, `sleep`, `clear`, `cls` — utility
- `src` — list source command files (mntm)
- `uptime` — millis
- `date [set …]` — get/set RTC
- `sysctl` — system control (factory_reset, heap_track, debug)
- `top` — task list
- `vibro [on|off]`
- `led <r> <g> <b>` (0-255) and `led bl <0-255>` for backlight
- `gpio` — mode/read/write/i2c-bridge subcommands
- `i2c` — bus scan/talk
- `loader` — `list`, `open <name> [args]`, `info`, `close`, `signal <num> [arg]`
- `power` — `off`, `reboot`, `reboot2dfu`, `info`, `debug`
- `start_rpc_session` — **switches the CLI into protobuf mode for that connection** — no return to text shell short of disconnect
- `storage` — `list`, `read`, `read_chunks`, `write`, `write_chunk`, `remove`, `copy`, `rename`, `mkdir`, `md5`, `stat`, `format_ext`, `info`, `tree`, `backup`, `restore`
- `update` — firmware update CLI tool
- `ps`, `top`, `heap_track`, `service` — diagnostics

Per-app CLI (registered by the running services, all firmwares):
- `nfc` — sub-shell with `field`, `detect`, `apdu`, `read` etc.
- `subghz` — `tx`, `tx_from_file`, `rx`, `decode_raw`, `chat`
- `ir` — `tx`, `rx`, `tx_raw`
- `bt` — `tx_carrier`, `rx_carrier`, `info`, `hci_state`
- `crypto` — `encrypt`, `decrypt`, `keys` (enclave key tooling)
- `music_player <path>` — plays an .fmf file
- `js <path>` — runs a JS script and streams output to the CLI ← **the JS path you're using today**
- `factory_reset`
- `input` — emulate input events
- `onewire` — Dallas/iButton
- `buzzer <freq> <volume> <duration_ms>` — added mntm-012

Momentum-only:
- `neofetch`, `buzzer`, `hello_world`, `subshell_demo` (in `applications/services/cli/commands/`)

#### 4.3 `js <path>` — the current launch path

**Source:** `js_app.c` registers `CLI_COMMAND_INTERFACE(js, js_cli_execute, CliCommandFlagDefault, 1024, CLI_APPID)`.

```
>: js /ext/apps/Scripts/hello.js
[script output streamed to CLI as `print()` lines]
>:
```

- **USB only** — the CLI text-shell is NOT exposed over BLE (the BLE serial service jumps straight to RPC). This is the confirmed day-1 BLE finding.
- The `js` CLI command runs the script on the CLI's task — so `eventLoop.run()` inside the script will block the CLI until you `Ctrl-C` (which sends ETX = 0x03 → kills the script).
- Streamed output: every `print()` / `console.log()` is sent to the CLI synchronously, **interleaved with the prompt's input echo**. If you're scripting this, lock terminal echo off.
- Errors print a stack trace via `js_app_compact_trace` (keeps only first line, strips full paths).

#### 4.4 Hang-prone commands / CR vs CRLF / output swallowing

| Command / pattern | Quirk | Fix |
|---|---|---|
| `start_rpc_session\r\n` | Hangs forever. The CLI consumes `\r`, then sees `\n` as a second blank line, then tries to switch into RPC mode but the `\n` is already in the protobuf stream-buffer and corrupts the first read | Always send `\r` only (NO `\n`) |
| `log`, `log debug`, `log trace` | Streams log lines continuously. No prompt returns until Ctrl-C (0x03) | Send `\x03` to break; or open a second session if you need to keep logging |
| `subghz chat` / `nfc apdu` | Enter a sub-shell with its own prompt (some still print `>: `, some print `nfc>: `) | Detect prompt change; send `exit` or Ctrl-C to leave |
| `storage write <path>` | Reads stdin until Ctrl-C — does NOT terminate on newline | Send file bytes followed by `\x03` |
| `factory_reset` | Confirms with a y/N — if you pipe `factory_reset\r` it hangs waiting for input | Send `factory_reset\ry\r` (or just don't) |
| `ir rx`, `subghz rx` | Streams until Ctrl-C | Same as `log` |
| `loader open <Name>` | Returns prompt immediately on success — the app launches in foreground but CLI is still alive. Subsequent CLI commands continue to work (CLI service is independent) | Track app state via the unsolicited `app_state_response` over RPC if you switch transports |
| `update <manifest>` | Long-running, no output until done, can take minutes | Use long quiet-window heuristic (60s+) |
| Empty line / `\r` alone | Re-emits prompt — harmless | Use as "ping" |
| Backspace `\x08` | Edits the in-progress line — be careful if pipes are involved | Strip backspaces from automated input |
| `mntm-010+` autocomplete on TAB | TAB character interpreted as completion. Sending TAB in scripted input is usually a bug | Strip `\t` |

#### 4.5 CLI ↔ `app_start` interaction

- `app_start` (over RPC) and `loader open` (over CLI) ultimately call the same `loader_start()` C function.
- The mutex is **per-loader** (not per-transport). So:
  - If a CLI user runs `loader open Sub-GHz`, then your RPC tries `app_start("JS Runner", "...")`, the second call returns `ERROR_APP_SYSTEM_LOCKED`.
  - Conversely, RPC `app_start` blocks CLI `loader open` until the app exits.
- However the **CLI service itself** continues to accept commands even while an app is running — you can still `log`, `storage list`, etc. while a foreground app is up. The lock is only on starting *another* foreground app.
- **There is no separate "CLI lockout".** Running a CLI command does not lock out `app_start` via RPC. Both can issue commands concurrently to the kernel.

#### 4.6 Quiet-window heuristics — calibration

From the `busse/flipperzero-mcp` core (`protobuf_rpc.py`):
- USB probe: 0.4-1.2s
- BLE probe: longer due to handshake latency
- RPC start retry: 3× with 600ms-1.2s timeout
- For text CLI: **read until `\r\n>: ` OR 1500ms quiet**, whichever first. This is empirical, not from the spec.

For streaming commands (`log`, `ir rx`, `subghz rx`):
- **Don't quiet-wait**, instead match on `\r\n>: ` only when expected (after Ctrl-C).

For `storage read <large file>`:
- Disable quiet-window entirely; the CLI emits chunks with their own pacing; only stop on prompt.

#### 4.7 Build / firmware fingerprinting via CLI

```
>: !          # alias for device_info — fast, ~200 bytes output
hardware_model: Flipper Zero
hardware_target: f7
firmware.branch: dev
firmware.branch_num: ...
firmware.commit: <sha>
firmware.version: 1.4.3 / mntm-dev / Momentum
firmware.build_date: 2025-xx-xx
...
```

The `firmware.version` line is the most-reliable fingerprint. `firmware.branch` distinguishes OFW (`dev`, `release`) from Momentum (`dev`, `release`), Unleashed, Xtreme.

For RPC-side: `system_device_info_request` returns the **same data** as kv pairs streamed with `has_next` — collect into dict, check `firmware.version`.

---

## TIER 2 — Path 2 architecture relevant

### 5. Storage RPC chunked-write protocol

#### 5.1 Chunk size — verified, but not what BLE imposes

Primary source: `applications/services/rpc/rpc_storage.c` in `flipperdevices/flipperzero-firmware` (dev branch).

```c
static const size_t MAX_DATA_SIZE = 512;
```

- 512 bytes is the **protocol-level cap on the `File.data` payload per `StorageWriteRequest` / `StorageReadResponse`** — i.e. inside the protobuf `PB_Main` envelope. It is a firmware-defined constant, not a transport constant. (OFW dev as of late-2025; MTM and UN inherit it because they rebase on upstream RPC code.) Source: rpc_storage.c quoted above.
- **The 512 figure applies equally over USB-CDC and BLE.** It is *not* a "BLE imposes 512" rule — BLE imposes much smaller limits at the ATT layer (see 5.2, 7.2). The operator's mental model "we believe 512 over BLE" is correct *for the protobuf payload chunk*, wrong if it implies BLE characteristic writes carry 512-byte writes natively.
- The Python reference client `flipperzero_protobuf_py/flipperzero_protobuf/flipper_storage.py` uses `chunk_size = 512` and slices the user buffer into 512-byte protobuf chunks with `has_next=True` for all but the last. Source: confirmed via fetch of upstream `flipper_storage.py`.

#### 5.2 The ACK pattern — and why the operator's Q3 theory is probably wrong

The chunked-write ACK semantics in `rpc_storage.c`:

```c
// inside rpc_system_storage_write_process()
send_response = !request->has_next;
```

Translation:
- **The Flipper sends ZERO responses for intermediate chunks.** It only emits one `PB_Main` (`CommandStatus = OK` or an error) **after the final chunk with `has_next=false` arrives.**
- The Python client (`flipper_storage.py`) mirrors this — fires all chunks back-to-back with `has_next=True`, only calls `_rpc_read_answer()` once after the final chunk.
- There is **no per-chunk ACK to lose.** If the operator's Q3 BLE bug is "some chunks lost ACK", that diagnosis is structurally impossible with the upstream protocol. The likely real bugs (in order of probability):
  1. **OVERFLOW credit underrun.** BLE RX characteristic (UUID `…fe62…`, see 7.1) has a finite `bytes_ready_to_receive` window. If the client pushes 512B of protobuf-framed chunk faster than the Flipper drains it, the firmware logs `"Received N, while was ready to receive M bytes. Can lead to buffer overflow!"` and **silently drops the excess** (see 7.3). The chunk isn't lost in transit — it's truncated by the peripheral.
  2. **GATT write-without-response coalescing** at the host BLE stack: writes appear "sent" from the client API but never make it across because the host stack queues+drops on flow-control assertion.
  3. **Protobuf framing break.** Because there is no per-chunk ACK, a single dropped/truncated chunk causes the *next* chunk's varint length prefix to land mid-frame; firmware then waits forever for the message it can no longer parse, and the client's final `_rpc_read_answer()` times out.
- Recommended re-frame: stop hunting an ACK protocol bug; instrument the OVERFLOW characteristic on each write and verify `bytes_ready_to_receive` is non-zero before each chunked send. (See 7.3 for the credit replenishment rule.)

Source: rpc_storage.c (linked above), `flipper_storage.py`, forum.flipper.net thread "How to handle BLE overflow?" (#13348), and serial_service.c overflow check.

#### 5.3 Concurrent storage operations — single-session lock

```c
typedef enum {
    RpcStorageStateIdle = 0,
    RpcStorageStateWriting,
} RpcStorageState;
```

- The RPC subsystem holds one `RpcStorageState` per session. While `RpcStorageStateWriting` is set (between the first `has_next=True` chunk and the final `has_next=False`), **other storage RPCs from the same session will conflict.** Source: rpc_storage.c.
- The transport (USB-CDC or BLE serial service) is a single-channel half-duplex pipe at the protobuf framing layer — there is **no multiplexing of RPC commands on one session**. You cannot stat one file while a write to another file is in progress on the same session.
- The Flipper supports a session abstraction (`rpc_session_*`) but qFlipper, the Python client, and (as of inspection) flipperzero-mcp all use a single session. Concurrency requires multiple parallel sessions, which is *not* supported over a single BLE link (one serial service instance) and not realistic over CDC either.
- **Race-condition surface:** if the GUI app on the Flipper opens a file while RPC is writing it, behavior is **filesystem-defined**, not RPC-defined — see 5.5.

#### 5.4 `/int` vs `/ext` differences

- Both paths route through the same `Storage` service in `applications/services/storage/`. The RPC layer is path-agnostic.
- `/int` is LittleFS on internal STM32WB flash (~1 MB device, ~256 KB user-available). `/ext` is FAT on SD. (OFW + MTM + UN + XFW all share this split.)
- Practical differences observable from RPC:
  - `/int` writes are dramatically slower under sustained load (flash erase cycles on LittleFS GC); a 200KB write to `/int` can stall multi-second.
  - `/int` has no concept of "card not present"; `/ext` returns `ERROR_STORAGE_NO_FS` if no SD inserted.
  - `MD5sumRequest` works on both but is slower on `/ext` (FAT seek penalty).
  - No filename-length difference at the RPC layer; the firmware allocator uses `MAX_NAME_LENGTH = 255` for both. Source: rpc_storage.c.
- **Storage info quirk:** the `flipperzero-mcp` storage module (`D:\Dev\Projects\flipperzero-mcp\src\flipper_mcp\modules\storage\module.py` L192–203) hedges with "not all firmwares expose a storage_info RPC". This is overly cautious — `StorageInfoRequest` has been in storage.proto since at least the 2023 protobuf cut, and is supported by OFW + MTM + UN + XFW. The hedge can be tightened.

#### 5.5 File-locking semantics — there is no lock

- The Flipper firmware does **not** implement per-file mutexes. Two concurrent openers (RPC + GUI app) can both `storage_file_open` the same path.
- For `/int` (LittleFS): two writers will produce **interleaved / truncated** content; LittleFS has no exclusive-write semantic.
- For `/ext` (FAT): the underlying FATFS driver enforces a single writer per file in its default Flipper config (`_FS_LOCK > 0`), but the higher-level Storage service does not advertise this — an RPC write can silently fail with `ERROR_STORAGE_ALREADY_OPEN` if a GUI app has the file open. **Important:** the GUI app does not always *release* the file when its view leaves the screen (depends on app implementation), so a stale handle from a previously-launched app can persist across screen changes.
- **Practical implication for the MCP server:** before writing to `/ext/apps/foo.fap` or similar, the safe pattern is `storage_stat` → `storage_delete` → `storage_write`. The intermediate delete forces a release of the FAT entry; if the GUI is holding the file, the delete fails fast instead of the write succeeding partway and corrupting.
- Source: behavior inferred from `applications/services/storage/storage.c` semantics + observed `ERROR_STORAGE_ALREADY_OPEN` enum in storage.proto error codes; OFW, MTM, UN all behave the same here.

---

### 6. USB-CDC transport gotchas

#### 6.1 VID/PID pinning — and why "wrong PID" happens

Primary source: `targets/f7/furi_hal/furi_hal_usb_cdc.c`:

```c
.idVendor = 0x0483,
.idProduct = 0x5740,
```

- **Normal mode (RPC + CLI):** `0483:5740`. STMicroelectronics VID, generic Virtual COM Port PID. (OFW + MTM + UN + XFW all use 0483:5740 unless explicitly customized — see below.)
- **DFU bootloader mode** (hold LEFT during cold boot): `0483:DF11` — STMicro DFU class device, NOT a COM port at all. qFlipper recognizes this. This is the most common "wrong PID" cause.
- **BadUSB mode:** by default Flipper emits a HID-class descriptor with the **same `0483:5740`**, but reconfigured as HID Keyboard. Apple's "Identify Your Keyboard" wizard exposes this. (Issue #1018 in flipperzero-firmware requests configurable PID for BadUSB; closed as not planned in OFW. Some forks like XFW expose a "USB ID" submenu; **MTM has this exposed under USB → BadUSB → Settings as of 2025.**)
- **USB Mass Storage mode** (Mass Storage app): switches descriptor to MSC class. Windows assigns a drive letter, not a COM port — looks like "wrong PID" from a serial-only enumerator's perspective but is actually class-switched. (OFW + MTM + UN.)
- **CDC + virtual UART bridge** (GPIO → USB serial bridge app): exposes a second CDC interface; on Windows this shows as **two COM ports**, which has confused many automation scripts that grab the first match.

Source: furi_hal_usb_cdc.c (quoted above), forum.flipper.net troubleshooting docs, GitHub issue flipperzero-firmware#1018.

#### 6.2 Baud rate — informational, not enforced

- USB CDC-ACM baud rate is purely a **descriptor field set by the host** via `USB_CDC_SET_LINE_CODING`. The Flipper firmware accepts the value and stashes it but **does not throttle data based on it**. Throughput is bound by USB 2.0 Full-Speed (12 Mb/s nominal) and STM32WB IRQ servicing.
- Source: furi_hal_usb_cdc.c — line coding goes to `config_callback` which the RPC handler simply ignores for rate-limiting purposes.
- Practical: **set 115200 by convention** (qFlipper does), but any value works. Setting 921600 does not make transfers faster. Setting 9600 does not make them slower. This is a frequent retraining for new automation authors.

#### 6.3 DTR/RTS — Flipper does care, but probably not how you think

```c
cdc_ctrl_line_state[if_num] = req->wValue;
if(callbacks[if_num]->ctrl_line_callback != NULL) {
    callbacks[if_num]->ctrl_line_callback(...);
}
```

- The Flipper **stores** DTR/RTS state and **invokes a per-interface callback** when it changes. For the primary CDC interface used by RPC, the callback is set by the RPC USB transport and used to **detect host disconnection**: if DTR goes low, the firmware tears down the RPC session.
- **Implication for Python clients:** PySerial's default behavior is to assert DTR on open and de-assert on close. If your client reconnects rapidly (open → write → close → open), the Flipper may interpret each close as session-end and discard buffered state. **Set `dtr=True` and keep the port open** for the lifetime of the connection. Some Linux pyserial defaults toggle DTR on open which has caused mysterious "Flipper reboots when I connect" reports — DTR is interpreted as a session reset, not a hardware reset, but if it happens during a write it cancels the in-flight RPC.
- Source: furi_hal_usb_cdc.c (line state callback wiring); user reports across forum.flipper.net.
- Note (possibly stale, 2023): community feature request to ignore DTR was closed not-planned.

#### 6.4 Windows COM port assignment

- Windows assigns COM port based on (VID, PID, **serial number**). Flipper exposes its serial number string in the USB descriptor (the device name, e.g. `Furi`). **Therefore the same physical Flipper should keep the same COM port across reboots on Windows** — and in practice it does.
- COM port reassignment ("now it's COM7 instead of COM4") happens when:
  1. Different physical USB port — Windows tracks per-port-per-device, and a different port gets a fresh assignment.
  2. Firmware switch (OFW → MTM, or major version bump) that changes the USB serial-number string — Windows treats it as a new device.
  3. DFU mode (`0483:DF11`) is a different device entirely; Windows assigns nothing visible because it's not a COM-class device.
  4. **Composite device collision:** if BadUSB or Mass Storage was last-mode, then user reboots back to RPC, Windows can take 3-5 seconds to unbind the old class driver and rebind usbser. During that window, COM port enumeration can race and produce a transiently-different number until the next replug.
- Source: Microsoft Q&A "USB Serial Adapter COM Port Assignment Changes on Windows 10 Reboot" + Windows usbser.sys documented behavior + flipperzero docs.flipper.net Windows debug page.

#### 6.5 Buffer sizes and the 2024 hang regression

- USB CDC RX/TX use bulk endpoints with **64-byte packet size** (USB Full-Speed limit; non-negotiable). Multi-byte protobuf chunks are fragmented at the USB layer transparently.
- **2024 regression (issue #3452):** qFlipper hangs writing large files (e.g. resources.tar during firmware update). Root cause was traced to PR #3358 which switched the USB-CDC class from "2x unidirectional endpoints" to "1x bidirectional endpoint" (single OUT/IN pair), causing race conditions under sustained simultaneous read+write. **Fixed in late-2024 OFW; MTM rebased the fix; UN/XFW unclear (verify per-fork).** Pre-fix firmware: USB chunked write of files >~100KB hangs intermittently around byte 80–200KB.
- Source: github.com/flipperdevices/flipperzero-firmware/issues/3452 + PR #3358.
- Aux note: GPIO UART bridge mode loses data at baud rates >115200 (issue #2304). Not directly relevant to USB-CDC RPC but a flag if anyone uses Flipper as a USB-to-UART bridge in tooling — possibly stale, dated 2023.

---

### 7. BLE quirks beyond Day-1 findings

#### 7.1 The full UUID truth table

Primary source: `targets/f7/ble_glue/services/serial_service_uuid.inc` (verbatim byte arrays):

| Role | 128-bit UUID (LE byte array) | Standard hex (BE) |
|---|---|---|
| Service | `00 00 fe 60 cc 7a 48 2a 98 4a 7f 2e d5 b3 e5 8f` | `8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000` |
| TX (FROM_FLIPPER) | `00 00 fe 61 8e 22 45 41 9d 4c 21 ed ae 82 ed 19` | `19ed82ae-ed21-4c9d-4145-228e61fe0000` |
| RX (TO_FLIPPER) | `00 00 fe 62 …` (same suffix) | `19ed82ae-ed21-4c9d-4145-228e62fe0000` |
| Flow Control (OVERFLOW) | `00 00 fe 63 …` | `19ed82ae-ed21-4c9d-4145-228e63fe0000` |
| RPC Status | `00 00 fe 64 …` | `19ed82ae-ed21-4c9d-4145-228e64fe0000` |

Properties (from `serial_service.c`):

| Char | Properties |
|---|---|
| RX (TO_FLIPPER) | `WRITE \| WRITE_WITHOUT_RESP \| READ` |
| TX (FROM_FLIPPER) | `READ \| INDICATE` |
| Flow Control | `READ \| NOTIFY` |
| RPC Status | `READ \| WRITE \| NOTIFY` |

Sources: `serial_service_uuid.inc` and `serial_service.c` lines 28–66 (verified by fetch).

#### 7.2 Why FROM_FLIPPER is INDICATE not NOTIFY

- **Indicate requires the central to send an ATT confirmation per packet**, serializing the throughput at the BLE link layer to 1 packet per connection event. Notify is fire-and-forget.
- This is **deliberate and conservative**: the Flipper firmware author chose flow-control-at-ATT-layer for the outbound path because the host's BLE stack may not drain notifications fast enough; an indicate confirmation gives backpressure.
- **Performance cost:** at a 45ms connection interval (observed in issue #3174), the maximum theoretical FROM_FLIPPER throughput is roughly `(243 bytes payload) × (1 packet per conn event) / 0.045s ≈ 5.4 KB/s`. Real-world is often lower (≈3 KB/s sustained). This is **why reading a 50KB file over BLE takes ~15 seconds** even on a healthy link.
- The inbound path (TO_FLIPPER, write) uses WRITE_WITHOUT_RESP and has its own credit-flow scheme via the Flow Control characteristic (7.3) — that path is faster because it batches.
- Source: serial_service.c properties block + issue #3174 connection params.

#### 7.3 OVERFLOW (Flow Control) — the credit-flow handshake

From `serial_service.c`:

```c
struct BleServiceSerial {
    uint16_t bytes_ready_to_receive;
    uint32_t buff_size;
    FuriMutex* buff_size_mtx;
};

if(attribute_modified->Attr_Data_Length > serial_svc->bytes_ready_to_receive) {
    FURI_LOG_W(TAG, "Received %d, while was ready to receive %d bytes. Can lead to buffer overflow!", ...);
}
serial_svc->bytes_ready_to_receive -= MIN(...);
```

Protocol contract:
1. On connect/MTU-exchange, firmware sets `bytes_ready_to_receive = buff_size` (typically `BLE_SVC_SERIAL_DATA_LEN_MAX = 486`) and pushes that number as a `uint32_t` (big-endian via `REVERSE_BYTES_U32`) on the Flow Control NOTIFY characteristic.
2. Each RX (TO_FLIPPER) write **decrements** `bytes_ready_to_receive` by the packet size.
3. When the buffer empties (RPC has drained it), firmware re-notifies Flow Control with the **next available credit** (usually `buff_size` again).
4. **Client contract:** sum your unacked writes; never let the total exceed the last-notified credit. If you do, the firmware will *log a warning and accept the data anyway up to its actual buffer remaining*, then **drop** any further excess. This is the most likely source of the operator's "lost chunk" Q3 bug.

Behavior under stress (large chunked writes):
- A 50KB chunked write fires ~25 protobuf chunks of 512B each, but each protobuf chunk is fragmented into multiple ATT writes of `BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX = 243` bytes max.
- If the client doesn't watch Flow Control notifications, it will overrun the 486-byte window within the first 2–3 ATT writes. The firmware logs `"Received 240, while was ready to receive 54 bytes"` (real log from forum.flipper.net #13348) and the excess is **silently truncated**, breaking subsequent protobuf parsing (5.2).
- Source: serial_service.c + forum #13348 + observed log evidence.

#### 7.4 Re-advertise rate-limit — the actual numbers

From `targets/f7/ble_glue/gap.c`:

```c
#define FAST_ADV_TIMEOUT    30000   // ms (30s)
#define INITIAL_ADV_TIMEOUT 60000   // ms (60s)
```

- **Fast advertising** (interval `0x80` to `0xa0` = 80ms–100ms) runs for 30s after each connect/disconnect event.
- **Initial advertising** (after boot, before first connect) runs for 60s on fast params, then transitions to low-power advertising (`0x0640`–`0x0fa0` = 1s–2.5s intervals) indefinitely.
- The operator's observation of "30–90s" is consistent: 30s fast-adv post-disconnect, plus up to 60s if the disconnect happened during the initial post-boot window. **The hard maximum before falling to low-power advertising is 60s post-boot, 30s post-reconnect.**
- After low-power advertising kicks in, discovery still works but **connection establishment latency goes from <500ms to 2–5s** because the central must catch one of the slow ADV packets.
- Source: gap.c + gap.h constants (OFW dev; MTM keeps the same values as of v0.12 line).

#### 7.5 MTU negotiation — what it really does

From `gap.c` ATT MTU exchange handler:

```c
max_packet_size = pr->Server_RX_MTU - 3;   // 3-byte ATT header
```

- The Flipper's BLE controller (STM32WB55's ST BLE stack with the `stm32wb5x_BLE_Stack_full_fw.bin` coprocessor binary) defaults to a **Server_RX_MTU of 247** (a common ST default; the exact value depends on the radio firmware version — flagged "possibly stale, verify per radio.bin").
- After exchange, **effective payload per ATT write = MTU – 3 = 244** bytes. This matches `BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX = 243` (the firmware-side cap; rounded conservatively down by 1).
- **The Flipper does not initiate MTU exchange.** It accepts whatever the central requests via `ACI_ATT_EXCHANGE_MTU_RESP_VSEVT_CODE`. If the central does not request an MTU exchange, the default LE ATT MTU of **23 bytes** is used — that's only 20 bytes payload — which would make BLE RPC nearly unusable (a single protobuf chunk = ~26 round trips). All proper clients (qFlipper iOS/Android, Gadgetbridge) request MTU upfront.
- **Implication for the Python BLE client:** call `client.exchange_mtu(247)` immediately after connect, before any RPC traffic. Bleak supports this on Linux/macOS; Windows WinRT backend negotiates automatically with the system default of 517 (capped down by the Flipper to ~247).
- Source: gap.c ATT MTU handler + ST BLE stack defaults + serial_service.h constants.

#### 7.6 Pairing vs bonding — passkey-display bonding, persistent

- From gap.c pairing flags:
  - `MITM_PROTECTION_REQUIRED` / `NOT_REQUIRED` — Flipper uses **NOT_REQUIRED** by default (no man-in-the-middle protection).
  - `USE_FIXED_PIN_FOR_PAIRING_FORBIDDEN` — Flipper does not use fixed PIN.
  - Methods: `GapPairingNone`, `GapPairingPinCodeShow`, `GapPairingPinCodeVerifyYesNo` — the active method depends on whether the host requests bonding with display-yes-no IO capability.
- **Default flow:** When you first connect from a phone/PC, the Flipper screen shows a 6-digit PIN and "verify yes/no" — this is the LE Secure Connections passkey-display variant (NOT JustWorks; the operator's question said pairing-vs-bonding, the answer is BOTH).
- **Bonding (LTK persistence):** the resulting LTK is **persisted to flash** in the Flipper's internal storage (`/int/.bt.keys.settings` or equivalent in the bt service). Across reboots, the pair persists. The "Forget All Paired Devices" menu deletes this store.
- **Reset on firmware swap:** OFW → MTM (and vice versa) often invalidates the bond because the bt service uses a slightly different storage path or key format per firmware family. Symptom: phone says "connected" but no GATT services discovered, or "pairing failed" loop. Fix: forget on both sides, re-pair.
- Source: gap.c + Momentum FAQ ("if you previously paired with Official firmware, you will need to forget and reconnect").

#### 7.7 The 2023 BLE RPC disconnect bug (#3174) — possibly stale but informative

- User reported supervision-timeout disconnects mid-`StorageReadRequest` over BLE despite continuous data flow. Connection params: interval 36 (45ms), slave latency 0, supervision timeout 42 (420ms), RX MTU 414.
- Issue closed "not planned" without root-cause publication. **Theory consistent with 7.2/7.3 above:** the indicate-confirmation latency from the central exceeded the supervision timeout under load, and Flipper's link supervisor treated it as link loss.
- **Mitigation if seen today:** request a longer supervision timeout (200 = 2000ms) at connect, and a slightly slower connection interval (40 = 50ms) to give the central headroom.
- Source: issue #3174.

---

### 8. Power and stability

#### 8.1 USB-power vs battery-power differences for RF

- Sub-GHz CC1101 TX peak current is ~30mA. BLE TX bursts at ~25mA. Both well within the BQ25896 charger + battery envelope when battery is healthy.
- **USB-powered with discharged or absent battery:** the USB-C port supplies 5V → BQ25896 regulates to 3.3V system rail, but the **rail is supply-current-limited** to whatever the host USB allows (typically 500mA on USB 2.0, 900mA on USB 3.0). Under a *very* dirty host (low-quality hub) or USB 2.0 port already under load, sustained Sub-GHz TX + screen + CPU can briefly exceed available current → rail sags → BOR (brown-out reset) trips → Flipper **reboots into bootloader-recovery mode**.
- This is the textbook "Flipper reboots when I try Sub-GHz over USB" community complaint. Fix: insert a healthy charged battery (acts as buffer cap), or use a known-good powered USB hub.
- Source: STM32WB55 datasheet BOR thresholds + Flipper hardware tech specs page + multiple forum.flipper.net reports.

#### 8.2 Brown-out scenarios — concrete triggers

- **<3.0V battery + RF burst:** BOR threshold on STM32WB55 is configurable; Flipper firmware ships with **BOR Level 3 (~2.7V)** as factory default. Battery at 3.0V + CC1101 TX dip + BLE TX dip + display refresh = transient sag below 2.7V → reset. Practical: **stop using RF features below 20% battery.** Source: Flipper power docs.
- **Concurrent USB Mass Storage + Sub-GHz:** USB MSC reads/writes hit the SD card; if the SD draws ≥100mA peak (low-quality cards do) while CC1101 is in TX, rail sags. Anecdotal but widely reported.
- **NFC HF field activation during USB enumeration:** the HF reader (ST25R3916) pulls a 100mA+ pulse to energize a tag field. If this fires the same millisecond as USB descriptor enumeration, some Win10 hosts mark the device as "failed to start" (Code 10) until replug. (Possibly stale, 2022-2023.)

#### 8.3 Sub-GHz prolonged TX — no firmware throttle, but hardware limits

- CC1101 has **no built-in thermal protection** (it's a small radio chip, ambient air does the cooling). It can transmit continuously at +10dBm.
- The Flipper firmware **does not implement a TX-duration throttle**. It will keep transmitting until you stop it or it runs out of battery.
- **What does fail under prolonged TX:** the antenna match degrades slightly with PCB temperature (negligible <1 minute, observable at multi-minute scale). No reports of permanent damage from sustained TX exist in the issue tracker.
- The 2022 issue #1047 ("Sub-GHz transceiver crippled, RX enabled, TX disabled") was a **region-lock firmware issue**, not a thermal one — it added per-region TX allowlists. (Pre-mid-2025; stale for current firmware which has region overrides in all major forks.)
- Source: CC1101 datasheet (TI) + flipperzero-firmware issue #1047.

#### 8.4 "Flipper reboots when I try X" — community catalog

| Trigger | Cause | Firmware |
|---|---|---|
| Sub-GHz TX over USB with no battery | Rail brown-out (8.1) | All |
| Mass Storage app crash on disk-image select | Bug in `flipperzero-good-faps` Mass Storage; SD image not validated | OFW, fixed mid-2024; MTM patched |
| BadUSB stops mid-payload after SD remove | SD-resident scripts; obvious but reported often | All |
| Reboot during BLE pair on iOS 17.x | Old "Apple BLE spam" mitigation in iOS triggered Flipper-side disconnect-storm bug | Fixed in OFW post-Dec 2023; MTM/UN patched. Stale. |
| Reboot when running JS app via mJS | mJS stack overflow on deeply-nested object; not a power issue | MTM, UN (JS_Runner module) |
| Reboot on plugging into Mac M-series charging brick (140W) | USB-PD negotiation race; ~5% of M-series bricks. Fix: USB-A adapter | All |
| Random reboot at idle on default sleep mode | Documented in Flipper power docs: "you may experience device crashes while using this mode" | OFW; not a bug, expected by design |

Sources: Flipper power doc, awesome-flipper FAQ, flipperzero-firmware issues #1047 / #2206 / #2664, forum.flipper.net.

---

## TIER 3 — Broad scan

Scope note: Kiisu V4B is a Flipper-clone; firmware semantics here apply to Momentum `mntm-dev` and `mntm-release-1.4.3` running on Flipper hardware. Where a behavior is OFW-only, Unleashed-only, or Momentum-only it is tagged inline.

### 9. Sub-GHz

**Frequency / region lock**
- OFW gates TX to the region read from the secure element (`R0` band, see docs.flipper.net). Momentum & Unleashed expose an **Extend Freq Bands** toggle in `SubGHz settings` that requires first flipping **Bypass region** — and even then the **CC1101 hardware bands** (300–348, 387–464, 779–928 MHz) are physically immovable. "Outside supported range" errors mean hardware, not policy. (Momentum FAQ; docs.flipper.net/zero/sub-ghz/frequencies; Issue #3245.)
- Extended bands include legally-grey ranges (315 MHz US garage band is fine; 433.92 ISM band overlap with EU SRD 433.05–434.79 is fine; 868 EU SRD has duty-cycle rules the firmware does NOT enforce — you can transmit illegally). Pre-2025 advisory still current.

**Protocol completeness (Momentum-fw.dev/wiki/Protocols/SubGHz; awesome-flipper.com)**
- Well-supported: Princeton, CAME, Nice FLO/Flor-S, Holtek, Linear, Hörmann (HCS-200/300 family), Chamberlain Security+ 1.0, BinRAW, the bulk of `lib/subghz/protocols`.
- Flaky / partial: full **KeeLoq** rolling-code decode-and-replay only works in Momentum/Unleashed and requires you supply a *device key* ("Normal decrypt" / "Secure decrypt"); the "Simple decrypt" path is the only one that just works. Security+ 2.0 emulation and modern Subaru / Honda / late-model GM are **NOT** clonable — the firmware can capture but capture is single-use (synchronization counter on the car desyncs your real fob if you replay). (forum.flipper.net/t/exploring-rolling-codes/6059; baudskidninja medium post.)

**Capture file format quirks (.sub)**
- Two payload shapes: `Protocol: <name>` with parsed `Key:`/`Bit:` fields, **or** `Protocol: RAW` with `RAW_Data:` (microsecond timing list, max 1024 elements per chunk — multi-line RAW splits across `RAW_Data:` entries). `Preset:` is mandatory; custom presets need full `Custom_preset_module:` + `Custom_preset_data:`. (developer.flipper.net subghz_file_format.)
- BinRAW is a third encoding used when the decoder recognized timing structure but not a full protocol. Imported third-party `.sub` files frequently break when `Preset:` is missing — silent fail, button does nothing.

**Rolling-code state persistence**
- KeeLoq learned device-key state lives in `/ext/subghz/assets/keeloq_mfcodes` (or `_user`) on SD. Wiping the SD wipes your decrypt keys; reflashing firmware does NOT. (Momentum wiki.)
- Captured rolling-code `.sub` files are stamped one-shot — Momentum 007+ shows a "Used" tag once transmitted. The counter increment is not stored back, so re-tx is desynced-by-design.

**External CC1101 modules**
- Quen0n's open-hardware design uses pins 2/3/4/5 (SPI) + 6/7 (CSN/IRQ) — these are the same pins the **NRF24** mod and most ESP32 dev-boards use. Stacking is a no-go without a switching hat. (github.com/quen0n/flipperzero-ext-cc1101.)
- KRIDA boosted (+20 dBm) and Tindie "boosted" modules add a PA — be aware these violate FCC §15.231 power limits even on legal frequencies. Reported ~3-4× range on 433 MHz (electronikz review).
- Some dual-band hats (NRF24 + CC1101 on same board) require firmware-level switching of pin 4/7 ownership — Momentum supports this via the "External Module" setting; Unleashed historically had bugs around auto-detect.

---

### 10. NFC / RFID

**ST25R3916 vs PN532 (Flipper uses ST25R3916, docs.flipper.net/zero/development/hardware/tech-specs)**
- ST25R3916 is dramatically more capable: 13.56 MHz multi-protocol (ISO 14443A/B, 15693/NFC-V, FeliCa, ISO 18092), longer range (~11 cm vs ~4 cm for PN532), and supports listen-mode load modulation. PN532 is the "Arduino-friendly easy" chip; ST25R3916 is the "actually a reader IC" chip.
- **Critical gotcha**: ST25R3916 has no native passive-target emulation for **ISO 15693** — Flipper does NFC-V *reads* fine, but NFC-V card *emulation* is firmware-faked via pass-through load modulation and is unreliable on some readers. (g3gg0.de NFC-V writeup, 2023; still current.)

**MIFARE Classic — recent advances**
- **Static Encrypted Nested** (FUDAN FM11RF08S / S70-clones, 2024 eprint paper 2024/1275) is now cracked on-device by FlipperNested or MFKey32 with auto-attack selection. RogueMaster changelog (Dec 2025) reports 10× speedup. (lab.flipper.net/apps/mifare_nested; gist noproto/MifareClassic.md.)
- Static-Nested-with-NACK-leak still fastest; the **constant-distance nonce** trick works on cards that try to look static.
- Hardnested for the post-2020 RF08S "FM1208" generation is feasible offline only (`FlipperNestedRecovery` on PC) — Flipper itself has neither RAM nor CPU.

**DESFire / Plus / Ultralight C**
- DESFire EV1/EV2: read app structure & free memory; cannot crack 3DES/AES keys. Seader plugin (bettse) reads HID iClass SE, iClass, DESFire EV1/EV2, **and SEOS** credentials — but only the credential is exfilled, not the underlying card master keys. v3.2 last updated 2024-06.
- MIFARE Plus SL3 (AES) and Ultralight-C 3DES — read only, no key recovery.

**Card emulation gotchas**
- 4-byte UID emulation: solid. **7-byte UID emulation: known broken for many readers** because Flipper writes the UID into the emulated SAK/UID slot but does not always synthesize a valid block 0 (the system's reader rechecks the in-block UID and rejects). Issue #1598; gist rickdoesburg "Cloning Mifare 1k 7-byte". **8-byte UIDs: read only, no emulation at all.**
- Saved-vs-live emulation drift: re-emulating a previously-saved card sometimes differs from emulating immediately-after-read because some non-block-0 metadata is not persisted. (Issue #2577.)

**Rabbit holes — community status as of 2025-2026**
- **Saflok (Unsaflok, Dormakaba hotel locks)**: parser landed in Momentum 007 (Sept 2024). Read-only on Flipper — the actual key derivation requires a property-master card you already have. The "Unsaflok" exploit (Carroll/Wouters DEFCON 2024) is **not** packaged on-device; demo code is researcher-controlled.
- **Picopass / iClass legacy**: bettse Picopass plugin (v1.17, 2024-06) does read/write/emulate, loclass dictionary attacks, key changes. Mature.
- **Seader**: bridges iClass SE / SEOS via Omnikey 5022 over UART. Working but requires an external reader.
- **HID SEOS / iClass SR (Elite key)**: unbroken. Flipper sees them but can't decrypt.

---

### 11. BadUSB / BadKB

**DuckyScript dialect (developer.flipper.net/.../badusb_file_format; gist methanoliver)**
- Flipper implements DuckyScript 1.0 + extensions. **Missing from DS3.0**: `VAR`/assignment, `IF`/`WHILE`, `FUNCTION`, jitter, `RANDOM_*`, attack-mode polymorphism. Momentum's Bad-Keyboard app adds some control flow but it is NOT upstream DS3.
- **Flipper-specific extras**: `ID <vid>:<pid> <manufacturer>:<product>` (preload only — must be line 1), `ALTSTRING`/`ALTCODE` for Alt+numpad Unicode, `WAIT_FOR_BUTTON_PRESS`, `SYSRQ`, `HOLD` / `RELEASE`. Comments are `REM`.
- **Layout files** live at `/ext/badusb/assets/layouts/*.kl`. Wrong layout = scrambled output (the most common "it doesn't work" cause on Reddit).

**Mode-switch collateral**
- Entering BadUSB tears down whatever USB profile was up (CDC console, mass storage, MTP). qFlipper / `flipperzero-protobuf` sessions drop. The MCP server should resubscribe after running a BadKB payload.
- On Windows specifically: a fast script + rapid disconnect-reconnect of HID can leave the OS marking the device as "not responding" — restart fixes it (forum.flipper.net thread; awesome-flipper FAQ).

**Bluetooth BadKB / BadBT (Momentum/Xtreme — renamed "BadKB" in v41)**
- Two BLE modes: classic HID-over-BR/EDR-emulation and **BadBLE**. MAC randomization supported per session; layouts work the same.
- Targets must accept HID-over-BLE without pairing prompt (Windows 10+ does; iOS prompts; macOS prompts; many smart TVs accept silently — that's the interesting attack surface).
- Speed cap: BLE HID is rate-limited; long payloads run ~30-40% slower than USB. No `DEFAULT_DELAY` adjustment fully compensates.

---

### 12. Infrared

**Protocol coverage (developer.flipper.net infrared_file_format)**
- Parsed protocols: **NEC, NECext, NEC42, NEC42ext, Samsung32, RC5, RC5X, RC6, Sony SIRC (12/15/20-bit), Kaseikyo, RCA, Pioneer**. Anything else falls through to RAW.
- Big gaps: **no native Sharp**, **no Mitsubishi-specific decoders**, **no Panasonic-AC long-frame** (AC remotes with state — temperature, fan — are RAW-only and you have to capture each button state).

**Raw vs parsed .ir**
- Parsed: `protocol`, `address`, `command` (hex, little-endian). Replays cleanly across devices.
- RAW: alternating pulse/gap microseconds, `frequency:` field (typically 38000, sometimes 36000/40000), `duty_cycle:` (default 0.33). **Max 1024 timings per signal** — long signals (AC frames at 200+ edges + multi-frame) need RAW with multiple `data:` chunks.

**Universal remote DB on Momentum**
- Stock universal TV is mostly **POWER + VOL only**. Full button coverage requires replacing `/ext/infrared/assets/tv.ir` with a community DB (Lucaslhm/Flipper-IRDB is the canonical fork — search.flippertools.net is the searchable index, ~50k entries as of late 2025).
- AC universal is power-only by design (state-machine ACs can't be brute-forced sanely).
- Bruteforce universal mode is slow because it iterates dictionaries serially — large `tv.ir` makes power-cycling take 60+ seconds.

---

### 13. Ecosystem layer

**Official WiFi Dev Board (ESP32-S2)**
- Hardware is fixed (ESP32-S2 + USB-C + Black Magic Probe headers). Three common firmwares: **Marauder** (justcallmekoko), **Bruce** (pr3y/Bruce), **Black Magic** (debugger). All flash via web-updater or `esptool`.
- UART contract: **115200 8N1** between Flipper UART (GPIO 13 TX / 14 RX) and ESP32. Flipper companion plugins drive Marauder over this link via line-oriented ASCII commands (`scanap`, `attack -t deauth`, `stopscan`, etc.). Bruce has its own command set, NOT Marauder-compatible.
- Power gotcha: the dev board pulls ~250-400 mA in WiFi scan modes — Flipper's onboard regulator can deliver but battery drain is ~3× normal.

**Bruce (companion firmware)**
- Different scope from Marauder: Bruce is a *full standalone hacking firmware* for ESP32/ESP32-S3 with its own UI on attached display modules (CYD, M5StickC, etc.). When run on the Flipper WiFi board (no display) it exposes a serial menu but loses most UX. Marauder is the right pick for Flipper-tethered use.

**ESP32 Marauder Double Barrel / 5G (Apex 5, 2025-2026)**
- Newer multi-radio boards: Double Barrel adds RTL8720DN for 5 GHz deauth; Apex 5 adds ESP32-C5 + dual sub-GHz + nRF24 + GPS. These work as Flipper expansion modules but require Marauder Companion app and a per-board firmware build. (cnx-software, 2025-09 and 2026-02.)

**Video Game Module**
- Internally an RP2040 + ST7789 240×320 LCD. **GPIO 8, 15, 18, 19, 20** are reserved for module internals — not available for breakout. (docs.flipper.net/zero/video-game-module/gpio.)
- Color format: **RGB565** (5R/6G/5B); `COLOR_BG` / `COLOR_FG` in `app/frame.c` for theming.
- Latency: input lag is reportedly negligible for arcade-style games; SPI to the LCD runs fast enough not to be the bottleneck. (Tom's Hardware review.)

**External hat conflicts (general pattern)**
- SPI hats (CC1101, NRF24, SD readers) all want pins 2/3/4/5. Only one SPI peripheral can be active at a time; firmware doesn't multiplex.
- UART hats (ESP32 board, GPS, LoRa) all want pins 13/14. Same story.
- I2C is dual-purpose (5V tolerant pins 15/16) — fewer conflicts but used by NFC and the screen internally.

---

### 14. Community knowledge — the "wait what" moments

The recurring forum/Reddit/GitHub-issue tripwires, each tagged with subsection ref:

1. **[§9] "Captured rolling code won't replay"** — by design. Rolling codes desync once. Real fob now ahead of car; user assumes Flipper broke. (baudskidninja medium; forum.flipper.net/t/6059.)
2. **[§9] "Outside supported range" on 868 MHz** — CC1101 hardware can't tune there in EU mode without region bypass *and* extend-bands. Two toggles, both buried. (Momentum FAQ; Issue #3245.)
3. **[§10] 7-byte UID emulation fails on some readers** — UID-vs-block-0 mismatch. Magic card (Gen1a, Gen2 CUID, Gen3, FUID, UFUID) needed to rewrite block 0 cleanly. (gist rickdoesburg.)
4. **[§10] Saved-vs-live emulation differs** — Flipper persists card data but not all state; saved emulation behaves subtly different from immediate-emulation-after-read. (Issue #2577.)
5. **[§10] Custom firmware breaks Bluetooth pairing** — different BLE config means OFW mobile app, phone Bluetooth, *and* Flipper all need pairings cleared. Most common "Momentum doesn't work" support ticket. (Momentum FAQ.)
6. **[§11] BadUSB fails on Linux/Mac due to keyboard layout** — Flipper defaults to US-QWERTY. Layout file at `/ext/badusb/assets/layouts/` is mandatory for non-US targets. (awesome-flipper FAQ.)
7. **[§11] BadKB Bluetooth gets "stuck" mid-run on Windows** — rapid HID connect/disconnect makes Windows mark device unresponsive; PC reboot fixes. (forum.flipper.net BadBT thread.)
8. **[§12] AC remote replay only sends one state** — Panasonic-AC-style stateful remotes need per-button RAW captures; cannot be parsed. (developer.flipper.net infrared_file_format.)
9. **[§14 / general] "Flipper froze in Sub-GHz menu"** — Firmware 0.86.x had a known Sub-GHz hang; current Momentum 1.4.x clean. If still happening: hold BACK 30s for hard reset, then BACK+LEFT 3s for normal reboot. (forum.flipper.net/t/18099, /t/18103.)
10. **[§14 / general] Bricked Flipper recovery** — Hold OK+BACK ~30s with USB unplugged → DFU mode. qFlipper repairs via DFU. If DFU not enumerating: data-capable USB-C cable required (charge-only fails silently). Last resort: SWD via TP1/TP2 with Black Magic Probe / J-Link. (docs.flipper.net firmware-recovery; forum.flipper.net/t/6259.)
11. **[§14 / general] SD card "Card Full" with space free** — FAT corruption from improper eject. Fix: format on PC (FAT32, exFAT also OK for ≤64 GB), restore SD asset structure via qFlipper "Repair". Cards >64 GB officially unsupported but often work with manual FAT32 format. (forum.flipper.net/t/4945; docs.flipper.net storage-repair.)
12. **[§14 / general] Battery drain in standby >30 mA** — Settings → Power → Battery Info. >30 mA standby = something stuck (often a rogue user app, sometimes BLE pairing loop). Reboot, then if persistent factory-reset. (support.flipper.net battery KB.)
13. **[§13] Stacking CC1101 + ESP32 dev board** — pin conflict on UART vs SPI; firmware cannot multiplex. Need a switching hat or pick one. (quen0n repo; community recurring question.)
14. **[§9 / §10] Region lock and NFC do not interact** — operators sometimes disable region lock thinking it unlocks more NFC features. It doesn't; NFC and LFRFID are not region-gated, only Sub-GHz is.

*Tier-3 gaps (couldn't cleanly close):* (a) detailed Bruce-vs-Marauder feature matrix specifically for the Flipper WiFi Dev Board ESP32-S2 — most Bruce coverage assumes ESP32-S3 + display; (b) authoritative "complete" parsed-protocol list for Sub-GHz — docs show examples not enumeration, would need to read `lib/subghz/protocols/` source directly; (c) Apex 5 / 2026-02 ESP32-C5 board — limited independent testing yet, mostly vendor + CNX-Software coverage; (d) controlled benchmarks on external CC1101 pin-contention scenarios — anecdotal range numbers exist (~3-4× on KRIDA boosted) but no rigorous comparison.

---

## §15 Index of gotchas

One-liners with section references. Read this section first when debugging.

### app_start / app_load_file (TIER 1, §1)

- **§1.2** — App name match is case-sensitive `strcmp`; `"JS Runner"` and `"js_app"` both work, `"js runner"` does NOT.
- **§1.3** — `args` to JS Runner is a literal path only — no JSON, no script-args, no relative-path fallback to `/ext/apps/Scripts/`. Pass absolute.
- **§1.3** — Empty `args` pops a file-browser dialog on the device; RPC returns OK before user picks.
- **§1.4** — `app_load_file` against running JS Runner returns `ERROR_APP_NOT_RUNNING` because `js_app.c` does NOT register an RPC callback (confirmed from source). **This is the most important single fact in the file.**
- **§1.5** — Passing literal `args="RPC"` gets rewritten to `"RPC <hex_ptr>"`; JS Runner ignores this prefix and treats the whole thing as a path → fail.
- **§1.6** — Bad-path `app_start` returns OK then fails async — must subscribe to `app_state_response{APP_CLOSED}` to know it died.
- **§1.6** — Unknown-app returns generic `ERROR_INVALID_PARAMETERS`, not a "no such app" code.

### Momentum JS (TIER 1, §2)

- **§2.7** — Starting a `blebeacon` JS module kills the device's regular BLE — RPC-over-BLE will disconnect mid-script.
- **§2.10** — mJS has NO try/catch, NO Date, NO Promise, NO `==`, NO `var`, NO arrows, NO template strings, NO `for..of`. Workarounds in table.
- **§2.10** — Flipper's mJS is *even more restricted* than upstream mJS (issue #3516) — no public spec exists; test on device.

### Protobuf RPC (TIER 1, §3)

- **§3.3 / §3.4** — BLE per-write chunk max = 243 bytes (`BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX`); device buffer = 486; client MUST implement credit-flow on the FC characteristic (UUID `*FE63*`).
- **§3.4** — Flow-control notify value is the *new total* credit, not a delta — full-reset semantics. Treat as "set credit to N", not "add N".
- **§3.5** — On BLE you do NOT send `start_rpc_session`; the device auto-enters RPC. Subscribe to RPC-Status char (UUID `*FE64*`) to confirm Active.
- **§3.7** — RPC handlers are mutex-serialized per session; firing two `Main` envelopes in parallel doesn't help — second blocks on `busy_mutex`.
- **§3.8** — `start_rpc_session\r\n` (CRLF) silently hangs USB CDC; only `\r` works.
- **§3.8** — `storage_write_request` is one-shot in the proto but firmware EXPECTS `has_next` chunking; send ≤512-byte chunks.

### CLI text-shell (TIER 1, §4)

- **§4.1** — Prompt is literally `">: "` (greater-than, colon, space); device emits CRLF, client sends CR only.
- **§4.4** — `factory_reset\r` hangs waiting for `y/N` — pipe `y\r` after, or avoid.
- **§4.4** — `log`, `ir rx`, `subghz rx`, `storage write` are streaming — only Ctrl-C (0x03) returns prompt.
- **§4.5** — RPC `app_start` and CLI `loader open` share the same `loader_start()` mutex — second returns `ERROR_APP_SYSTEM_LOCKED`.

### Storage (TIER 2, §5)

- **§5.1** — `MAX_DATA_SIZE = 512` is the *protobuf* `File.data` cap, NOT a BLE transport size — equally applies over USB-CDC.
- **§5.2** — There is **no per-chunk ACK** in storage writes; Flipper sends ONE response after the final `has_next=false`. **The operator's Q3 "ACK pattern bug" diagnosis is structurally impossible.** See §16.
- **§5.2** — Real Q3 culprit is almost certainly OVERFLOW credit underrun (firmware silently truncates excess on RX buffer overrun, breaking subsequent protobuf framing).
- **§5.3** — Single-session RPC has zero command multiplexing — you can't stat one file while writing another on the same session.
- **§5.5** — No file lock between RPC and GUI; on FAT/`/ext`, RPC write fails with `ERROR_STORAGE_ALREADY_OPEN` if the GUI is holding the file. Safe pattern: `stat → delete → write`.

### USB-CDC (TIER 2, §6)

- **§6.1** — Normal PID `0483:5740`, DFU `0483:DF11`, BadUSB reuses `0483:5740`. PR #1018 to change BadUSB PID closed not-planned in OFW; MTM exposes it.
- **§6.2** — USB-CDC baud rate is informational — 115200 vs 921600 changes nothing; protocol layer doesn't care.
- **§6.3** — PySerial's default DTR-toggle-on-open can cancel in-flight RPC writes — keep the port open for the connection lifetime.
- **§6.5** — 2024 hang regression (#3452): single-bidirectional-endpoint switch (PR #3358) caused large-write deadlocks. Fixed late-2024 in OFW; verify per fork.

### BLE (TIER 2, §7)

- **§7.2** — FROM_FLIPPER is INDICATE deliberately — ATT confirmation gives backpressure; costs ≈3 KB/s sustained throughput max over BLE.
- **§7.3** — Buffer credit is `BLE_SVC_SERIAL_DATA_LEN_MAX = 486` bytes; ATT max value `CHAR_VALUE_LEN_MAX = 243`. Overrun is logged-and-silently-truncated.
- **§7.4** — Re-advertise: 30s fast-adv post-disconnect, 60s initial post-boot, then 1–2.5s low-power adv indefinitely. Matches operator's "30–90s" observation.
- **§7.5** — Flipper does NOT initiate MTU exchange — central must request it or you're stuck at 23-byte ATT MTU (20-byte payload). All proper clients request upfront.
- **§7.6** — OFW↔MTM firmware swap invalidates the BLE bond — always forget on both sides during firmware migration.

### Power (TIER 2, §8)

- **§8.1** — Sub-GHz TX over USB without a healthy battery = rail brown-out reset; battery acts as buffer cap.
- **§8.3** — No firmware-side Sub-GHz TX throttle. CC1101 has no thermal protection but no firmware-level duration limit either.

### Sub-GHz, NFC, BadUSB, IR, ecosystem (TIER 3)

- **§9** — Captured rolling codes desync the real fob — by design, replay is one-shot.
- **§9** — "Outside supported range" needs two hidden toggles (region bypass + extend bands), and even then CC1101 hardware bands are physically immovable.
- **§10** — 7-byte UID emulation fails on many readers due to UID-vs-block-0 mismatch — magic card needed.
- **§10** — Saved-emulation behaves differently from emulation-immediately-after-read (Flipper doesn't persist all metadata).
- **§10** — Switching to Momentum requires clearing pairings in 3 places (Flipper / phone Bluetooth / mobile app) — #1 support ticket.
- **§11** — Wrong keyboard layout silently scrambles BadUSB output — `/ext/badusb/assets/layouts/*.kl` is mandatory for non-US targets.
- **§11** — Rapid HID connect/disconnect on Windows leaves the OS marking BadKB device unresponsive; PC reboot fixes.
- **§12** — Stateful AC remotes (Panasonic-AC etc.) cannot be parsed — RAW-only per button state, no universal coverage.
- **§13** — Stacking CC1101 + ESP32 dev board contends on SPI vs UART pins — firmware cannot multiplex.
- **§14** — Bricked Flipper recovery needs a data-capable USB-C cable; charge-only cables fail DFU silently.
- **§14** — "SD Card Full" with space free = FAT corruption from improper eject — qFlipper Repair restores asset tree.
- **§14** — Standby battery drain >30 mA means rogue app or BLE pair loop (Battery Info screen surfaces it).

---

## §16 Contradictions Found

Findings from this research that conflict with prior team working-understanding. Read once; do not silently overwrite.

### C1 — `app_load_file` does NOT launch JS scripts (load-bearing)

**Prior assumption:** `flipper_app_load_file` was added as a direct RPC primitive expected to be able to launch JS scripts (the user prompt described it as a candidate for replacing `cli_command("js …")`).

**Finding:** `app_load_file` requires the target app to call `rpc_app_register_callback()` from within itself. **`js_app.c` does NOT do this** — confirmed by source inspection (no `rpc_` symbols in `js_app.c` or `js_app_i.h`). Against a running JS Runner, `app_load_file` returns `ERROR_APP_NOT_RUNNING` — a misleading error name that actually means "no RPC callback registered".

**The only RPC path to launch a JS script is:** `app_start(name="JS Runner", args="/ext/apps/Scripts/foo.js")`. One shot, no `app_load_file` involved. (See §1.4 and §1.7 for the full call pattern.) This applies on all firmwares: OFW, Momentum, Unleashed, Xtreme.

**Sub-finding:** `app_start` returning `OK` does NOT mean the script ran successfully. It means the app launched. Bad path / SyntaxError fail async — subscribe to `app_state_response{APP_CLOSED}` to know whether it actually died.

### C2 — Q3 BLE chunked-write bug is NOT an ACK-pattern bug

**Prior assumption:** the Q3 BLE chunked-write bug "lives in the ACK pattern" — chunks were thought to be losing their per-chunk ACKs.

**Finding:** the upstream protocol has **no per-chunk ACK to lose.** `rpc_storage.c` line: `send_response = !request->has_next;` — the Flipper emits exactly one `PB_Main` response, after the final chunk with `has_next=false`. The Python reference client (`flipper_storage.py`) mirrors this — fires all chunks back-to-back, reads one answer.

**Almost certainly the real bug:** OVERFLOW credit-flow tracking. The client pushes ATT writes faster than the Flipper drains its 486-byte RX buffer; firmware logs `"Received N, while was ready to receive M bytes"` and silently truncates the excess; subsequent protobuf framing breaks because the next chunk's varint length prefix lands mid-frame; the client's `_rpc_read_answer()` times out — looking superficially like "a chunk's ACK got lost" when no ACK ever existed. (See §5.2 + §7.3.)

**Recommended action:** instrument the Flow Control NOTIFY characteristic (UUID `*FE63*`) and gate each ATT write on remaining credit, using the algorithm in §3.4. Verify `bytes_ready_to_receive` is non-zero before each chunked send.

### C3 — "512 over BLE" wording is precise but easy to misread

**Prior wording:** "we believe 512 over BLE."

**Finding:** accurate as the protobuf `File.data` chunk size (firmware constant `MAX_DATA_SIZE = 512`, applies equally over USB-CDC and BLE). **Misleading** if it suggests BLE writes carry 512B natively. Actual BLE ATT writes are ≤243B (`BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX`), fragmented by the BLE stack — a 512B protobuf chunk fires as ~3 ATT writes. Keep both numbers in mind: 512 protobuf-chunk, 243 ATT-write. (See §5.1 + §7.3.)

### What was confirmed

For completeness, these prior beliefs are **confirmed correct** by this research:

- CLI text-shell is NOT exposed over BLE. The BLE serial service jumps straight to RPC; there is no `start_rpc_session\r` equivalent on BLE. Confirmed by both `serial_service.c` behavior and §3.5 RPC Status char semantics.
- JS missions currently launch via `cli_command("js <path>")` on USB only. The new RPC-side replacement is `app_start("JS Runner", "<absolute path>")`, NOT `app_load_file`.

---

## §17 Sources

Deduplicated across all three tiers, grouped by category.

### Official Flipper repos & docs

- https://github.com/flipperdevices/flipperzero-firmware
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/applications/services/rpc/rpc.c
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/applications/services/rpc/rpc.h
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/applications/services/rpc/rpc_app.c
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/applications/services/rpc/rpc_app.h
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/applications/services/rpc/rpc_storage.c
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/services/serial_service.c
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/services/serial_service.h
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/services/serial_service_uuid.inc
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/gap.c
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/gap.h
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/furi_hal/furi_hal_usb_cdc.c
- https://github.com/flipperdevices/flipperzero-firmware/tree/dev/applications/system/js_app
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/applications/system/js_app/application.fam
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/documentation/file_formats/SubGhzFileFormats.md
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/documentation/file_formats/InfraredFileFormats.md
- https://github.com/flipperdevices/flipperzero-firmware/blob/dev/documentation/file_formats/BadUsbScriptFormat.md
- https://github.com/flipperdevices/flipperzero-protobuf
- https://github.com/flipperdevices/flipperzero-protobuf/blob/dev/flipper.proto
- https://github.com/flipperdevices/flipperzero-protobuf/blob/dev/application.proto
- https://github.com/flipperdevices/flipperzero-protobuf/blob/dev/system.proto
- https://github.com/flipperdevices/flipperzero-protobuf/blob/dev/storage.proto
- https://github.com/flipperdevices/flipperzero_protobuf_py
- https://github.com/flipperdevices/flipperzero_protobuf_py/blob/main/doc.md
- https://flipperdevices.github.io/flipperzero-firmware/rpc__i_8h_source.html

### Flipper documentation sites

- https://docs.flipper.net/zero/development/cli
- https://docs.flipper.net/zero/development/hardware/tech-specs
- https://docs.flipper.net/zero/sub-ghz
- https://docs.flipper.net/zero/sub-ghz/frequencies
- https://docs.flipper.net/zero/sub-ghz/supported-vendors
- https://docs.flipper.net/zero/nfc
- https://docs.flipper.net/zero/nfc/read
- https://docs.flipper.net/zero/nfc/magic-cards
- https://docs.flipper.net/zero/nfc/mfkey32
- https://docs.flipper.net/zero/bad-usb
- https://docs.flipper.net/zero/infrared
- https://docs.flipper.net/zero/infrared/read
- https://docs.flipper.net/zero/infrared/universal-remotes
- https://docs.flipper.net/zero/video-game-module
- https://docs.flipper.net/zero/video-game-module/gpio
- https://docs.flipper.net/zero/gpio-and-modules
- https://docs.flipper.net/zero/basics/power
- https://docs.flipper.net/zero/basics/firmware-update/firmware-recovery
- https://docs.flipper.net/zero/basics/firmware-update/storage-repair
- https://docs.flipper.net/zero/qflipper/windows-debug
- https://developer.flipper.net/flipperzero/doxygen/js.html
- https://developer.flipper.net/flipperzero/doxygen/js_builtin.html
- https://developer.flipper.net/flipperzero/doxygen/js_developing_apps_using_js_sdk.html
- https://developer.flipper.net/flipperzero/doxygen/js_engine.html
- https://developer.flipper.net/flipperzero/doxygen/serial__service_8h_source.html
- https://developer.flipper.net/flipperzero/doxygen/storage_8h.html
- https://developer.flipper.net/flipperzero/doxygen/subghz_file_format.html
- https://developer.flipper.net/flipperzero/doxygen/infrared_file_format.html
- https://developer.flipper.net/flipperzero/doxygen/badusb_file_format.html

### Flipper firmware issues / PRs

- https://github.com/flipperdevices/flipperzero-firmware/issues/1018 (BadUSB PID config request — closed not-planned)
- https://github.com/flipperdevices/flipperzero-firmware/issues/1047 (region-lock TX disabled)
- https://github.com/flipperdevices/flipperzero-firmware/issues/1598 (7-byte UID emulation)
- https://github.com/flipperdevices/flipperzero-firmware/issues/2206 (SD reinsertion)
- https://github.com/flipperdevices/flipperzero-firmware/issues/2304 (UART bridge high-baud loss)
- https://github.com/flipperdevices/flipperzero-firmware/issues/2577 (saved-vs-live NFC emulation drift)
- https://github.com/flipperdevices/flipperzero-firmware/issues/2664 (BLE forget-pair)
- https://github.com/flipperdevices/flipperzero-firmware/issues/2983
- https://github.com/flipperdevices/flipperzero-firmware/issues/3174 (BLE RPC supervision timeout)
- https://github.com/flipperdevices/flipperzero-firmware/issues/3227 (BLE CLI feature request, not-planned)
- https://github.com/flipperdevices/flipperzero-firmware/issues/3245 (region/band)
- https://github.com/flipperdevices/flipperzero-firmware/issues/3452 (USB large-file hang)
- https://github.com/flipperdevices/flipperzero-firmware/issues/3516 (mJS subset spec missing)
- https://github.com/flipperdevices/flipperzero-firmware/issues/3820 (subghz tx_from_file not in protobuf)
- https://github.com/flipperdevices/flipperzero-firmware/issues/4194
- https://github.com/flipperdevices/flipperzero-firmware/issues/4317 (System Protobuf Version timeout)
- https://github.com/flipperdevices/flipperzero-firmware/pull/3358 (USB endpoint refactor — regression source)
- https://github.com/flipperdevices/flipperzero-firmware/pull/4142 (UART flow control PR)

### Momentum firmware

- https://github.com/Next-Flip/Momentum-Firmware
- https://github.com/Next-Flip/Momentum-Firmware/wiki
- https://github.com/Next-Flip/Momentum-Firmware/wiki/SubGHz
- https://github.com/Next-Flip/Momentum-Firmware/tree/dev/applications/system/js_app
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/application.fam
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/js_app.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/js_thread.c
- https://github.com/Next-Flip/Momentum-Firmware/tree/dev/applications/system/js_app/modules
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_subghz/js_subghz.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_event_loop/js_event_loop.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_badusb.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_infrared/js_infrared.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_storage.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_gpio.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_blebeacon.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_notification.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_usbdisk/js_usbdisk.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_serial.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_math.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/modules/js_flipper.c
- https://github.com/Next-Flip/Momentum-Firmware/tree/dev/applications/system/js_app/packages/fz-sdk
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/system/js_app/packages/fz-sdk/global.d.ts
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/services/loader/loader.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/services/loader/loader_cli.c
- https://github.com/Next-Flip/Momentum-Firmware/tree/dev/applications/services/cli
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/services/cli/cli_main_shell.c
- https://github.com/Next-Flip/Momentum-Firmware/blob/dev/applications/services/cli/cli_main_commands.c
- https://github.com/Next-Flip/Momentum-Firmware/tree/dev/applications/services/cli/commands
- https://github.com/Next-Flip/Momentum-Firmware/releases
- https://github.com/Next-Flip/Momentum-Firmware/releases/tag/mntm-008
- https://github.com/Next-Flip/Momentum-Firmware/releases/tag/mntm-009
- https://github.com/Next-Flip/Momentum-Firmware/releases/tag/mntm-010
- https://github.com/Next-Flip/Momentum-Firmware/releases/tag/mntm-011
- https://github.com/Next-Flip/Momentum-Firmware/releases/tag/mntm-012
- https://github.com/Next-Flip/Momentum-Firmware/issues/151
- https://github.com/Next-Flip/Momentum-Firmware/issues/328
- https://momentum-fw.dev/
- https://momentum-fw.dev/wiki
- https://momentum-fw.dev/wiki/FAQ
- https://momentum-fw.dev/wiki/Protocols
- https://momentum-fw.dev/wiki/Protocols/SubGHz

### Xtreme firmware (deprecated, merged into Momentum 2024)

- https://github.com/Flipper-XFW/Xtreme-Firmware/wiki/SubGhz
- https://github.com/Flipper-XFW/Xtreme-Firmware/wiki/Infrared
- https://github.com/Flipper-XFW/Xtreme-Firmware/wiki/Key-Combos
- https://github.com/Flipper-XFW/Xtreme-Firmware/wiki/Generic-Guides

### Flipper forum & support

- https://forum.flipper.net/t/cli-command-line-interface-examples/1874
- https://forum.flipper.net/t/how-to-handle-ble-overflow/13348
- https://forum.flipper.net/t/trying-to-send-some-bytes-via-ble-to-an-app-on-the-flipper/15746
- https://forum.flipper.net/t/exploring-rolling-codes-with-flipper/6059
- https://forum.flipper.net/t/rolling-code-remote/23569
- https://forum.flipper.net/t/flipperzero-freezes/18103
- https://forum.flipper.net/t/firmware-0-86-1-sub-ghz-freezes-flipper-zero/18099
- https://forum.flipper.net/t/flipper-stuck-in-dfu-mode/5501
- https://forum.flipper.net/t/flipper-bricked-at-update-or-can-t-recover-with-dfu-mode-solved/6259
- https://forum.flipper.net/t/sd-card-formatting-internal-error/10716
- https://forum.flipper.net/t/cannot-format-sd-card-cannot-detect-sd-card/4945
- https://forum.flipper.net/t/battery-issues/12922
- https://forum.flipper.net/t/nfc-mifare-card-emulation/2987
- https://forum.flipper.net/t/nfc-chipset/1016
- https://forum.flipper.net/c/troubleshooting/34
- https://support.flipper.net/hc/en-us/articles/17915915964445-The-device-has-a-short-battery-life
- https://support.flipper.net/hc/en-us/articles/14114283967005-Troubleshooting

### Flipper Lab / Tools

- https://lab.flipper.net/apps/mifare_nested
- https://lab.flipper.net/apps/picopass
- https://lab.flipper.net/apps/esp32_wifi_marauder
- https://search.flippertools.net/
- https://picopass.ericbetts.dev/

### Community plugins / third-party repos

- https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript
- https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript-%E2%80%90-Momentum
- https://github.com/quen0n/flipperzero-ext-cc1101
- https://github.com/AloneLiberty/FlipperNested
- https://github.com/AloneLiberty/FlipperNested/wiki/Usage-guide
- https://github.com/AloneLiberty/FlipperNested/wiki/FAQ
- https://github.com/Lucaslhm/Flipper-IRDB
- https://github.com/justcallmekoko/ESP32Marauder/wiki/flipper-zero
- https://github.com/justcallmekoko/ESP32Marauder/wiki/update-firmware
- https://github.com/justcallmekoko/ESP32Marauder/wiki/BFFB
- https://github.com/justcallmekoko/ESP32Marauder/wiki/Marauder-Dev-Board-Pro
- https://github.com/AGO061/BadBT
- https://github.com/RogueMaster/flipperzero-firmware-wPlugins
- https://github.com/nvx/flipperzero-firmware/tree/picopass_emulation
- https://github.com/HoneyHoneyTeam/ESP32-Marauder-Double-Barrel

### MCP / RPC clients

- https://github.com/busse/flipperzero-mcp
- https://github.com/busse/flipperzero-mcp/blob/main/src/flipper_mcp/core/protobuf_rpc.py
- https://github.com/roostercoopllc/flipper-mcp
- https://github.com/elijah629/flipper-rpc
- https://docs.rs/crate/flipper-rpc/0.4.1
- https://github.com/flipperdevices/go-flipper
- https://github.com/maybe-hello-world/fbs

### npm packages

- https://www.npmjs.com/package/@next-flip/fz-sdk-mntm
- https://www.npmjs.com/package/@next-flip/create-fz-app-mntm
- https://www.npmjs.com/package/@flipperdevices/fz-sdk

### Misc / research / community

- https://github.com/cesanta/mjs
- https://gist.github.com/noproto/63f5dea3f77cae4393a4aa90fc8ef427
- https://gist.github.com/noproto/7f0481ac1588a4d0cd7bdea06b63dfb6
- https://gist.github.com/rickdoesburg/344a21b72623d5b47059ae6bdcff2122
- https://gist.github.com/methanoliver/efebfe8f4008e167417d4ab96e5e3cac
- https://eprint.iacr.org/2024/1275.pdf
- https://baudskidninja.medium.com/reverse-engineering-of-fixed-code-remotes-flipper-zero-edition-b4f318bb337e
- https://www.g3gg0.de/reversing/flipper-zero-got-iso15693-nfc-v-support/
- https://secburg.com/posts/flipper-momentum-007-released/
- https://hackmag.com/security/flipper-zero-firmwarez
- https://www.spartanssec.com/post/flipper-zero-choosing-the-best-firmware-for-pentesting
- https://awesome-flipper.com/firmware/
- https://awesome-flipper.com/firmware/momentum/
- https://awesome-flipper.com/firmware/unleashed/
- https://awesome-flipper.com/faq/
- https://awesome-flipper.com/faq/infrared/
- https://awesome-flipper.com/application/lab.flipper.net/nfc/
- https://awesome-flipper.com/application/lab.flipper.net/nfc/picopass/
- https://flipper.wiki/troubleshooting/
- https://devicehunt.com/view/type/usb/vendor/0483/device/5740
- https://www.cnx-software.com/2025/09/22/esp32-marauder-double-barrel-5g-adds-5ghz-deauthentication-with-rtl8720dn-module/
- https://www.cnx-software.com/2026/02/11/esp32-marauder-5g-apex-5-module-for-flipper-zero-combines-esp32-c5-two-sub-ghz-radios-nrf24-and-gps/
- https://www.cnx-software.com/2025/01/16/flipmods-combo-is-a-3-in-1-flipper-zero-expansion-module-with-esp32-gps-and-cc1101-modules/
- https://www.tomshardware.com/raspberry-pi/raspberry-pi-pico/video-game-module-for-flipper-zero-review-gaming-comes-to-hacker-device

---

## §18 Stale-fact flags

Anything below should be cross-checked on a current device if it's load-bearing for a mission:

- BLE chunk size 243 (`BLE_SVC_SERIAL_CHAR_VALUE_LEN_MAX`) — stable since at least 2022, but verify on Kiisu V4B's MCU variant if it differs from F7.
- mJS upstream README (cesanta/mjs) — last meaningful update 2022. Flipper's mJS fork has further restrictions not in the README (see issue #3516).
- Older forum posts (pre-2024) about "RX MTU 414" — that was true with an older BLE stack; current is 243 per write.
- `forum.flipper.net/t/how-to-handle-ble-overflow/13348` (Feb 2023) — diagnosis still correct, but the credit-flow API has been formalized since.
- `flipperzero-firmware` issue #3174 (Oct 2023, "not planned") — still relevant, no fix landed; the workaround is strict credit-flow.
- `MTU default = 247` in §7.5 — based on common ST default; the exact value depends on the radio coprocessor binary (`stm32wb5x_BLE_Stack_full_fw.bin`). Verify per radio.bin version.
- BadUSB region-PID toggle (§6.1) — MTM exposes a USB ID submenu "as of 2025"; verify on current firmware.
- 2024 USB-CDC hang regression fix (§6.5) — confirmed in OFW, MTM rebased; UN/XFW unclear, verify per fork.
- mntm-013/014 release notes — Momentum tags 013/014 returned 404 during research; `mntm-release-1.4.3` label likely maps to ~mntm-013 era but could not verify from public release pages.

### Gaps not closed by this research (dig manually if needed)

- Exact mJS-subset spec for Flipper (community-acknowledged gap, issue #3516).
- Whether Kiisu V4B's MCU differs from the F7 enough to change BLE constants (clone-specific — assumed identical, untested).
- Whether `gui_screen_frame` streaming over BLE is reliable at full FPS — anecdotal "flaky under load" only.
- Exact `_FS_LOCK` value in current Flipper FATFS config — claimed `>0` based on observed `ERROR_STORAGE_ALREADY_OPEN`, didn't verify ffconf.h.
- Per-fork status of the PR #3358 USB endpoint fix in Unleashed and Xtreme.
- MTM vs OFW divergence in BLE bond storage path — asserted bonds invalidated on swap from Momentum FAQ wording, didn't find exact source delta.
- Issue #4317 ("System Protobuf Version timeout") may have additional BLE/USB protocol detail; not fully fetched.
- Bruce-vs-Marauder feature matrix specifically on the ESP32-S2 WiFi Dev Board.
- Authoritative enumeration of parsed Sub-GHz protocols (requires reading `lib/subghz/protocols/` directly).
- Apex 5 / 2026-02 ESP32-C5 Marauder board — limited independent testing yet.
- Controlled benchmarks on external CC1101 pin-contention scenarios.

---

*End of document.*
