# mJS Quick Reference Card

> For writing JS missions on Flipper / Kiisu running Momentum.
> mJS is a Mongoose JS dialect — small, embedded, with sharp edges. Flipper's fork is *more* restricted than upstream mJS and has no published spec (OFW issue #3516). When in doubt, copy an existing mission in `missions/llmdr/missions/library.py`.

## What you DON'T have

| You'd write…              | Doesn't exist                          | Use instead                                                                       |
|---------------------------|----------------------------------------|-----------------------------------------------------------------------------------|
| `Date.now()`, `new Date()`| no `Date` constructor at all           | Counter loop (`for (let i = 0; i < N; i++)`); host records timestamps             |
| `try { } catch { }`       | no exceptions in mJS                   | Check return values. Missing `finished=true` in log == script aborted             |
| `async / await / Promise` | nothing async                          | `require("event_loop")` for subscribe + queue patterns                            |
| `setTimeout/setInterval`  | not in mJS                             | `delay(ms)` — global, NOT a `require()`                                           |
| `"x=" + 42 + "\n"`        | no implicit number→string coercion     | `"x=" + (42).toString() + "\n"` — explicit every time                             |
| `==` / `!=`               | not allowed                            | Only `===` / `!==`                                                                |
| `var x = 1`               | not allowed                            | Only `let x = 1`                                                                  |
| `for (let x of arr)`      | no `for..of`                           | `for (let i = 0; i < arr.length; i++) { let x = arr[i]; ... }`                    |
| `(x) => x + 1`            | no arrow functions                     | `function(x){ return x + 1; }`                                                    |
| `` `value=${x}` ``        | no template strings                    | `"value=" + x.toString()`                                                         |
| `class Foo {}`            | no class keyword                       | Factory: `function makeFoo(){ return { ... }; }`                                  |
| `/foo/g`                  | no RegExp                              | Manual `indexOf` / `slice`                                                        |
| `n.toFixed(2)`            | no `Number` methods                    | `math` module or manual string slicing                                            |
| Closures over mutables    | broken — captures stale values         | Pass values explicitly through `event_loop` userArgs                              |
| Unicode strings           | byte strings only                      | Multi-byte UTF-8 chars count as 2+ in `.length`. Avoid emoji in log keys          |
| Scripts ~1500+ chars      | reliably crash the JS engine, drop USB | Keep under ~800 chars; split into multiple files invoked back-to-back             |
| `JSON.stringify()`        | upstream mJS has it; Flipper's fork *may not* — unverified | Use line-oriented `key=value\n` logs — partial-parseable on abort, diff-friendly |

## What you DO have

- **Globals (no require):** `print(msg)`, `delay(ms)`, `die(msg)`, `checkSdkFeatures([...])`.
- **`flipper` module:** `flipper.getName()`, `flipper.getModel()`, `flipper.getBatteryCharge()`, `flipper.jsSdkVersion` — see KB §2.2.
- **`storage`:** `openFile(path, mode, create)`, `read/write/close`. **DO NOT** call `storage.fsInfo()` — broken on mntm-dev, see below.
- **`notification`:** `notification.success()`, `notification.error()` — these wake the backlight + play audio. Use one of them at the end of every mission.
- **`subghz`:** `setup()`, `setIdle()`, `setFrequency(hz)`, `setRx()`, `setTx()`, `getRssi()`, `transmitFile(path)`. See KB §2.4.
- **`infrared`:** RX + TX primitives. See KB §2.5. TX is permissioned.
- **`badusb`:** HID keystroke emulation. Sends keystrokes to whichever host the Flipper is plugged into. Requires explicit user permission. See KB §2.6.
- **`gpio`:** `gpio.init(pin, mode, pull)`, `gpio.read(pin)`, `gpio.write(pin, value)`. See KB §2.9.
- **`math`:** standard library shim (mJS has no `Math`). `abs/sqrt/pow/exp/log/sin/cos/...`. Constants `PI`, `E`, `EPSILON`. See KB §2.9.
- **`event_loop`:** the only async primitive. Subscribe + queue pattern; user data threads through explicitly. See KB §2.3.

Full module reference: `docs/KIISU_DEEP_KNOWLEDGE.md` §2.

## The standard mission script template

```javascript
let storage = require("storage");
let notification = require("notification");

let MISSION_NAME = "your_mission";
let LOG_PATH = "/ext/apps_data/mcp_logs/" + MISSION_NAME + ".log";

let f = storage.openFile(LOG_PATH, "w", "create_always");
f.write("mission=" + MISSION_NAME + "\n");
f.write("step=loaded\n");

// === mission body ===
// remember .toString() on every number; no try/catch; no Date

f.write("finished=true\n");
f.close();
notification.success();   // wakes screen + plays chime
```

Five-part shape: require → open log → step markers → close + `finished=true` → notification. Skipping the last line means the human watching the device sees nothing happen.

## Right-vs-wrong: the three you'll trip on most

```javascript
// ❌ WRONG — no implicit coercion. mJS will abort here.
f.write("rssi=" + rssi + "\n");

// ✅ RIGHT
f.write("rssi=" + rssi.toString() + "\n");
```

```javascript
// ❌ WRONG — no Date in mJS.
let started = Date.now();
// ... work ...
f.write("elapsed_ms=" + (Date.now() - started) + "\n");

// ✅ RIGHT — let the host measure elapsed time around the call.
// In JS, write phase markers; the host can timestamp around them.
f.write("step=work_started\n");
// ... work ...
f.write("step=work_done\n");
```

```javascript
// ❌ WRONG — no try/catch. A throw here aborts the script silently.
try {
    let rssi = subghz.getRssi();
    f.write("rssi=" + rssi.toString() + "\n");
} catch (e) {
    f.write("error=" + e + "\n");
}

// ✅ RIGHT — check return values, use die() for hard-stops.
checkSdkFeatures(["subghz"]);     // dies cleanly if subghz not bound
let rssi = subghz.getRssi();      // if this throws, script aborts;
                                  // missing finished=true is your signal.
f.write("rssi=" + rssi.toString() + "\n");
```

## Don't use `storage.fsInfo()` from JS

It's a JS binding that looks right but **silently aborts** the calling script on Momentum mntm-dev. Use the host-side `storage_info` MCP tool instead — same data (`total/free` for `/int` and `/ext`), reachable from Python or Claude. Long-form discussion: `docs/for_ai_contributors.md` → "Don't use `storage.fsInfo()` from JS". Reference impl: `missions/llmdr/missions/storage_health_check.py`.

## Module-by-module quick reference

| Module          | High-traffic methods                                     | Gotchas                                                                              |
|-----------------|----------------------------------------------------------|--------------------------------------------------------------------------------------|
| `storage`       | `openFile`, file `read/write/close`                      | `fsInfo()` is broken — use host `storage_info` instead                               |
| `notification`  | `success()`, `error()`                                   | Only these reliably wake the backlight. `gui_send_input` from host does NOT          |
| `subghz`        | `setup`, `setFrequency`, `setRx`, `getRssi`              | CC1101 only tunes in 3 ISM bands (300–348, 387–464, 779–928 MHz). See library.py    |
| `gpio`          | `init`, `read`, `write`                                  | Pullup vs pulldown matters for "what is connected" semantics. Document your choice. |
| `infrared`      | RX primitives; TX is permissioned                        | Mission convention: capture/learn only. TX missions need explicit user permission   |
| `badusb`        | HID emulation                                            | Hits the HOST PC the Flipper is plugged into. NEVER run speculatively                |
| `event_loop`    | `subscribe`, `tick`, queue patterns                      | The only async primitive. Closures over mutables are broken — pass via `userArgs`   |
| `math`          | `abs/sqrt/pow/sin/...`, `PI`, `E`                        | Standalone shim — mJS has no global `Math` object                                   |

## Further reading

- `docs/for_ai_contributors.md` → "mJS Quirks — Read Before Writing JS Missions" — long-form, with the *why*.
- `docs/KIISU_DEEP_KNOWLEDGE.md` §2 — full module reference, every binding, every gotcha sourced.
- `missions/llmdr/missions/library.py` — every existing mission is a copy-pasteable working example.
- `examples/02_first_mission.js`, `03_mission_template.js`, `07_structured_logs.js` — copy-friendly skeletons.
