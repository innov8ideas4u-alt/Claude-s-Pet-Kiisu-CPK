# Overview
Feb 8, 2025 - RogueMaster does not currently have support for **event_loop** & therefore most of the new JavaScript files (**anything written after October 15, 2024 will not run**) on RogueMaster firmware.

Example scripts can be found in the RogueMaster firmware under the [js_app/examples](https://github.com/RogueMaster/flipperzero-firmware-wPlugins/tree/420/applications/system/js_app/examples/apps/Scripts) folder. You can also ask people in the [RogueMaster Discord](https://discord.gg/gF2bBUzAFe) server.

# Capabilities
Feb 8, 2025 - RogueMaster is running the old (Oct 13, 2024) version of JavaScript. **Newer script will not run!**
- BadUSB keyboard support, including different keyboard layouts.
- BLE Beacon support.
- Read and write to files on the Flipper.
- Read and write to serial port (TX/RX or C1/C0 pins).
- Transmit a Sub-GHz file.
- See if a Sub-GHz frequency has strong signal on it.
- Expose a virtual USB drive.
- GPIO for digital input/output.
- GPIO for analog input.
- I2C communication with hardware device.
- Dialog to pick a file.
- Dialog with Left/Right/Center choices.
- Menu with items to pick.
- On-screen keyboard for text or hex input.
- Dynamic textbox (update text contents while app still running).
- Get the pitch, roll and yaw of the Video Game Module (VGM)
- Widget support for rending more complex screens.
- Success/Error notifications.
- Math functions.
- Get the battery level of the Flipper.
- Get the name of the Flipper.
- Conditional logic, Loops, Number to String, String to Number.

# Globals
As of Feb 8, 2025 the supported globals are as follows:

|Feature|Description|
|-|-|
|[console](#globals-console)|Console object for logging|
|[delay](#globals-delay)|Waits num milliseconds|
|[ffi_address](#globals-ffi-address)|Foreign Function Interface (FFI) address|
|[parse_int](#globals-parse-int)|String to number|not implemented|
|[print](#globals-print)|Print message on screen and logs|
|[require](#globals-require)|Import module|
|[to_string](#globals-to-string)|Number to string|
|[to_hex_string](#globals-to-hex-string)|Number to hex string|
|[to_lower_case](#globals-to-lower-case)|Convert string to lowercase|
|[to_upper_case](#globals-to-upper-case)|Convert string to uppercase|
|[__filepath](#globals-filepath)|Path of script|not implemented|
|[__dirpath](#globals-dirpath)|Path of script directory|

## globals-console
The `console` object exposes 4 levels of debugging that will get logged to the serial debugger.  Each parameter passed will be converted to a string and then concatenated with a space being added between displayed values.

```js
console.error("error message", 7.1, 'c', 'f', 12, false); // "[E][JS] error message 7.100000 c f 12 false"
console.warn("warning"); // Warning
console.log("info", 4.2); // Info
console.debug("debug", 1); // Debug only
```

## globals-delay
The `delay` function delays for the specified number of milliseconds before continuing to the next statement.

```js
delay(100); // wait 100 milliseconds
```

## globals-ffi-address
The `ffi_address` function converts a method signature into an address?  No examples use this method directly.

## globals-parse-int
The `parse_int` function converts a string into number.

```js
let str = "42";
let num = parse_int(str); // num will be a number with a value of 42
```

## globals-print
The `print` function displays text on the screen and also in the logs.

The function allows passing multiple parameters of various types.

```js
print("hello");
print(42);
let answer=true;
print("got",answer);
```

## globals-require
The `require` function loads a module.  If the module is unknown it will throw an error.

The parameter is the name of the module.

```js
let badusb = require("badusb");
```

## globals-to-string
The `to_string` function will convert a number into a string.

The parameter is a number.

```js
let num = 42;
let str = to_string(num); // str is the string "42".
```

## globals-to-hex-string
The `to_hex_string` function will convert a number into a hex string.

The parameter is a number.

```js
let num = 1337;
let str = to_hex_string(num); // str is the string "539" (because 1337 decimal is 0x539).
```

## globals-to-lower-case
The `to_lower_case` function converts a string to lowercase.

The parameter is the string to convert.

```js
let str = "Hello World";
print(to_lower_case(str)); // prints: hello world
```

## globals-to-upper-case
The `to_upper_case` function converts a string to uppercase.

The parameter is the string to convert.

```js
let str = "Hello World";
print(to_upper_case(str)); // prints: HELLO WORLD
```

## globals-filepath
The `__filepath` is the path to the JS file that is being run.

```js
print("This JS file is",__filepath);
```

## globals-dirpath
The `__dirpath` is the folder where the JS file is being run from.

```js
let otherFile = __dirpath + "/demo.img"; // path to another file in the same folder as our script.
print(otherFile);
```

# MJS Internals
Here is some example code that demonstrates features that are part of the MJS library...

```
// There is a global called 'global'.
global.abc = 123;
print("global.abc =", global.abc); // prints "global.abc = 123"

// Unsigned and Signed arrays of various sizes:
// Uint8Array, Int8Array, Uint16Array, Int16Array, Uint32Array, Int32Array.
// NOTE: You will get TYPE_ERROR for out of bounds!
let b1 = Uint16Array(6); // 6 elements
b1[0] = 1;
b1[1] = 200;
b1[2] = 2000;
b1[3] = 42000;
b1[4] = 4000;
b1[5] = 1000;
let b2 = Int16Array(b1.buffer); // Create using the ArrayBuffer.
print(b1[1],b2[1]);
print(b1.buffer.byteLength); // 12 bytes
print(b1.length); // 6 elements
let b3 = b1.buffer.slice(2,4); // The buffer is Bytes! [start index, stop index = not inclusive)
let b4 = Uint16Array(b3);
print(b4[0]); // 200
let data = [1,13,45,66];
data[2] = data[2] - 3;
let b5 = Int8Array(data);
data[2] = 55;
data = data.splice(0,2); // elements 0 and 1 only.
print(data.length, b5[2]); // 2 42

print("12345".slice(2,4)); // "34"
print("531234543215415412".indexOf("54", 7)); // 11
let c1 = "123ABC".charCodeAt(3);
let c2 = chr(c1);
print (c1, c2); // 65 A

let x = Object.create({y:42});
x.z = 10;
print (x.y, x.z); // 42 10

let n = 42/0;
print (n);
print (isNaN(n)); // true
let n2 = NaN;
print (isNaN(n2)); // true
print (typeof n); // prints the text: 'number'
// NOTE: (typeof foo) "gives [foo] in not defined error".

function calc(a,b) {
 if (a===b) { // Always use === instead of ==
  return (a*b)+20;
 }
 if (a!==b) { // Always use !== instead of !=
  return (a*b)+10;
 }
}

print (calc(3,3)); // 29
print (calc(2,3)); // 16

// Example of calling native API calls...
// Not great, because we might not call release() if user aborts scripts.
let acquire = ffi("int furi_hal_speaker_acquire(int)");
let start = ffi("void furi_hal_speaker_start(float, float)");
let stop = ffi("void furi_hal_speaker_stop()");
let release = ffi("void furi_hal_speaker_release()");
let speaker = acquire(1000);
if (speaker) {
  start(1000,1.0);
  delay(100);
  stop();
  release();
}

die("Crashing"); // Exits with error message.

// What about: ffi_cb_free, mkstr, getMJS, s2o
```

# Supported Modules
As of Feb 8, 2025 the supported modules are as follows:
|Feature|Description|
|-|-|
|[badusb](#badusb)|Send keystrokes as hid|
|[blebeacon](#blebeacon)|Send BLE events|
|[dialog](#dialog)|Show dialog, select File|
|[flipper](#flipper)|Device info|
|[gpio](#gpio)|Input/Output hardware pins|
|[i2c](#i2)|I2C hardware protocol|
|[keyboard](#keyboard)|Text and Byte input (no support for illegalsymbols)|
|[math](#math)|Math functions|
|[notification](#notification)|LED sequences|
|[serial](#serial)|Serial port|
|[storage](#storage)|Flipper SD Card files|
|[subghz](#subghz)|Sub-GHz Radio|not implemented|
|[submenu](#submenu)|Submenu|
|[textbox](#textbox)|Textbox|
|[usbdisk](#usbdisk)|USB disk images|
|[vgm](#vgm)|Video Game Module sensor|
|[widget](#widget)|UI drawing (no [addIcon](#widget-add-icon))|

## badusb
```js
let badusb = require("badusb");
```

badusb is used to simulate an HID (Human Interface Device), like a USB keyboard, sending various keystrokes to the attached computer.

- [`setup`](#badusb-setup)`({ vid: number, pid: number, mfr_name: string, prod_name: string, layout: string }): undefined | error`
- [`quit`](#badusb-quit)`(): undefined | error`
- [`isConnected`](#badusb-is-connected)`(): bool | error`
- [`press`](#badusb-press)`(...keyAndModifiers: string | number): undefined | error`
- [`hold`](#badusb-hold)`(...keyAndModifiers: string | number): undefined | error`
- [`release`](#badusb-release)`(...keyAndModifiers: string | number | undefined): undefined | error`
- [`print`](#badusb-print)`(text: string, delay: number | undefined): undefined | error`
- [`println`](#badusb-println)`(text: string, delay: number | undefined): undefined | error`
- [`altPrint`](#badusb-alt-print)`(text: string, delay: number | undefined): undefined | error`
- [`altPrintln`](#badusb-alt-println)`(text: string, delay: number | undefined): undefined | error`

### badusb-setup
The `setup` function takes an configuration object with the vendor id (`vid`), the product id (`pid`), the manufacturer name (`mfr_name`) and the product name (`prod_name`).  This function will change the USB port from the typical Flipper port into a device with the specified vid/pid, acting as a USB keyboard.  When you are done using the bad usb, you should call [quit](#badusb-quit).  You cannot call this method a second time without first calling `quit`.  The layout parameter (`layout`) should be a fully qualified path to a `.kl` keyboard layout.

```js
badusb.setup({ vid: 0xAAAA, pid: 0xBBBB, mfr_name: "Flipper", prod_name: "Zero", layout: "/ext/badusb/assets/layouts/en-US.kl" });
```

### badusb-quit
The `quit` function will change the USB port back to the typical Flipper port.  This will also happen when the script exits.

```js
badusb.quit();
```

### badusb-is-connected
The `isConnected` function will return true if the Flipper Zero is connected to a computer.

```js
let connected = badusb.isConnected();
```

### badusb-press
The `press` function will press and release a key combination.  See [badusb keys](#badusb-keys) for the list of additional supported key names.

```js
badusb.press("CTRL", "c");
```

### badusb-hold
The `hold` function will hold down a key combination.  Use [release](#badusb-release) to release the keys.  See [badusb keys](#badusb-keys) for the list of additional supported key names.

```js
badusb.hold("ENTER");
delay(2000);
badusb.release("ENTER");
```

### badusb-release
The `release` function will release a key combination that was pressed with [hold](#badusb-hold).  See [badusb keys](#badusb-keys) for the list of additional supported key names.

```js
badusb.hold("ENTER");
delay(2000);
badusb.release("ENTER");
```

### badusb-print
The `print` function will type the string specified.  It takes an optional 2nd parameter with a delay in milliseconds (up to 60 seconds) to wait before returning to the caller.

```js
badusb.print("Hello", 1000); // Wait 1 second before typing next part...
badusb.print(" world!");
```

### badusb-println
The `println` function will type the string specified and then press Enter.  It takes an optional 2nd parameter with a delay in milliseconds (up to 60 seconds) to wait before returning to the caller.

```js
badusb.println("Hello", 1000); // Wait 1 second before typing next part...
badusb.println("world!");
```

### badusb-alt-print
The `altPrint` function will type the string specified using the numeric keypad.  It takes an optional 2nd parameter with a delay in milliseconds (up to 60 seconds) to wait before returning to the caller.

```js
badusb.altPrint("Hello", 1000); // Wait 1 second before typing next part...
badusb.alpPrint(" world!");
```

### badusb-alt-println
The `altPrintln` function will type the string specified using the numeric keypad and then press Enter.  It takes an optional 2nd parameter with a delay in milliseconds (up to 60 seconds) to wait before returning to the caller.

```js
badusb.altPrintln("Hello", 1000); // Wait 1 second before typing next part...
badusb.altPrintln("world!");
```

#### badusb keys
```js
    {"CTRL", KEY_MOD_LEFT_CTRL},
    {"SHIFT", KEY_MOD_LEFT_SHIFT},
    {"ALT", KEY_MOD_LEFT_ALT},
    {"GUI", KEY_MOD_LEFT_GUI},

    {"DOWN", HID_KEYBOARD_DOWN_ARROW},
    {"LEFT", HID_KEYBOARD_LEFT_ARROW},
    {"RIGHT", HID_KEYBOARD_RIGHT_ARROW},
    {"UP", HID_KEYBOARD_UP_ARROW},

    {"ENTER", HID_KEYBOARD_RETURN},
    {"PAUSE", HID_KEYBOARD_PAUSE},
    {"CAPSLOCK", HID_KEYBOARD_CAPS_LOCK},
    {"DELETE", HID_KEYBOARD_DELETE_FORWARD},
    {"BACKSPACE", HID_KEYBOARD_DELETE},
    {"END", HID_KEYBOARD_END},
    {"ESC", HID_KEYBOARD_ESCAPE},
    {"HOME", HID_KEYBOARD_HOME},
    {"INSERT", HID_KEYBOARD_INSERT},
    {"NUMLOCK", HID_KEYPAD_NUMLOCK},
    {"PAGEUP", HID_KEYBOARD_PAGE_UP},
    {"PAGEDOWN", HID_KEYBOARD_PAGE_DOWN},
    {"PRINTSCREEN", HID_KEYBOARD_PRINT_SCREEN},
    {"SCROLLLOCK", HID_KEYBOARD_SCROLL_LOCK},
    {"SPACE", HID_KEYBOARD_SPACEBAR},
    {"TAB", HID_KEYBOARD_TAB},
    {"MENU", HID_KEYBOARD_APPLICATION},

    {"F1", HID_KEYBOARD_F1},
    {"F2", HID_KEYBOARD_F2},
    {"F3", HID_KEYBOARD_F3},
    {"F4", HID_KEYBOARD_F4},
    {"F5", HID_KEYBOARD_F5},
    {"F6", HID_KEYBOARD_F6},
    {"F7", HID_KEYBOARD_F7},
    {"F8", HID_KEYBOARD_F8},
    {"F9", HID_KEYBOARD_F9},
    {"F10", HID_KEYBOARD_F10},
    {"F11", HID_KEYBOARD_F11},
    {"F12", HID_KEYBOARD_F12},
    {"F13", HID_KEYBOARD_F13},
    {"F14", HID_KEYBOARD_F14},
    {"F15", HID_KEYBOARD_F15},
    {"F16", HID_KEYBOARD_F16},
    {"F17", HID_KEYBOARD_F17},
    {"F18", HID_KEYBOARD_F18},
    {"F19", HID_KEYBOARD_F19},
    {"F20", HID_KEYBOARD_F20},
    {"F21", HID_KEYBOARD_F21},
    {"F22", HID_KEYBOARD_F22},
    {"F23", HID_KEYBOARD_F23},
    {"F24", HID_KEYBOARD_F24},

    {"NUM0", HID_KEYPAD_0}, // Not in OFW as of 3/26/2024
    {"NUM1", HID_KEYPAD_1}, // Not in OFW as of 3/26/2024
    {"NUM2", HID_KEYPAD_2}, // Not in OFW as of 3/26/2024
    {"NUM3", HID_KEYPAD_3}, // Not in OFW as of 3/26/2024
    {"NUM4", HID_KEYPAD_4}, // Not in OFW as of 3/26/2024
    {"NUM5", HID_KEYPAD_5}, // Not in OFW as of 3/26/2024
    {"NUM6", HID_KEYPAD_6}, // Not in OFW as of 3/26/2024
    {"NUM7", HID_KEYPAD_7}, // Not in OFW as of 3/26/2024
    {"NUM8", HID_KEYPAD_8}, // Not in OFW as of 3/26/2024
    {"NUM9", HID_KEYPAD_9}, // Not in OFW as of 3/26/2024
```

## blebeacon
```js
let blebeacon = require("blebeacon");
```

blebeacon is used to send BLE (Bluetooth Low Energy) beacon messages.

- [`isActive`](#blebeacon-is-active)`(): bool | error`
- [`setConfig`](#blebeacon-set-config)`(mac: Uint8Array, power: number | undefined, intvMin: number | undefined, intvMax: number | undefined): undefined | error`
- [`setData`](#blebeacon-set-data)`(data: Uint8Array): undefined | error`
- [`start`](#blebeacon-start)`(): undefined | error`
- [`stop`](#blebeacon-stop)`(): undefined | error`
- [`keepAlive`](#blebeacon-keep-alive)`(keep: boolean): undefined | error`

### blebeacon-is-active
The `isActive` function returns `true` if a BLE beacon is currently running, otherwise it returns `false`.  You can call [stop](#blebeacon-stop) to stop the running beacon.

```js
let bool_active = blebeacon.isActive();
```

### blebeacon-keep-alive
Pass a `true` to the `keepAlive` function if you want the BLE beacon to continue running when your script exits.  The default configuration is `false`, which will stop sending the BLE beacon when the script exits.

```js
blebeacon.keepAlive(false);
```

### blebeacon-set-config
The `setConfig` function sets the mac address for the BLE beacon.  You can optionally specify the power level, min time (milliseconds) and max time (milliseconds) parameters.

```js
let mac = Uint8Array([0x42,0x42,0x42,0x42,0x42,0x42]);
blebeacon.setConfig(mac, 0x1F, 50, 150); // power level: 0x1F, minTime: 50ms, maxTime: 150ms
```

### blebeacon-set-data
The `setData` function sets the data for the BLE beacon.

```js
let packet = [14, 0xFF, 0x75, 0x00, 0x01, 0x00, 0x02, 0x00, 0x01, 0x01, 0xFF, 0x00, 0x00, 0x43, 0x05];
blebeacon.setData(Uint8Array(packet));
```

### blebeacon-start
The `start` function will start sending BLE beacons.  You should call [setConfig](#blebeacon-set-config) and [setData](#blebeacon-set-data) before calling start.

```js
blebeacon.start();
```

### blebeacon-stop
The `stop` function will stop sending a BLE beacon if it is currently running.  If it is already stopped, the function call will be ignored.

```js
blebeacon.stop();
```

## dialog
```js
let dialog = require("dialog");
```

dialog is used to show a message (with Left/Center/Right options) or allow user to select a file.

- [`message`](#dialog-message)`({ header: string, text: string, button_left: string | undefined, button_center: string | undefined, button_right: string | undefined }): string | error`
- [`custom`](#dialog-custom)`(header: string, text: string): boolean | error`
- [`pickFile`](#dialog-pick-file)`(path: string, ext: string): string | error`

### dialog-custom
The `custom` function will display a dialog with header, text, and LCR button choices.  If back is pressed it will return empty string.  You can set a button to `undefined` if you do not want it to be selectable.

```js
let dialog_params = ({
    header: "Test header",
    text: "Test text",
    button_left: "Left",
    button_right: "Right",
    button_center: "OK"
});
let result = dialog.custom(dialog_params);

// Check result
if (result === "") { print("Back pressed."); }
else if (result === dialog_params.button_left) { print("Left pressed."); }
else if (result === dialog_params.button_right) { print("Right pressed."); }
else if (result === dialog_params.button_center) { print("OK pressed."); }
```

### dialog-message
The `message` function will display a dialog with header, text, and OK button.  If back is pressed it will return false, otherwise true.

```js
let result = dialog.message("Dialog header", "Press OK button");
if (result) { print("OK pressed.); } else { print("Back pressed."); }
```

### dialog-pick-file
The `pickFile` function will prompt the user to select a file.  The first parameter is the directory to start in.  The second parameter is the file extension.

```js
let result = dialog.pickFile("/ext/subghz", ".sub"); // Use "*" for second parameter to allow all files.
print("File path:"+result);
```

## flipper
```js
let flipper = require("flipper");
```

flipper is used to access information about the Flipper Zero device.

- [`getModel`](#flipper-get-model)`() : string`
- [`getName`](#flipper-get-name)`() : string`
- [`getBatteryCharge`](#flipper-get-battery-charge)`() : number`
- [`firmwareVendor`](#flipper-firmware-vendor)` : string`

### flipper-get-model
The `getModel` function will return the model of the device (like "flipper Zero")

```js
let result = flipper.getModel();
print("Model:"+result); // prints "Model: flipper Zero"
```

### flipper-get-name
The `getName` function will return the unique name of this Flipper.

```js
let result = flipper.getName();
print("Name:"+result); // prints "Name: Rim"
```

### flipper-get-battery-charge
The `getBatteryCharge` function will return the current battery level of this Flipper.

```js
let result = flipper.getBatteryCharge();
print("Battery:"+result); // prints "Battery: 98"
```

### flipper-firmware-vendor
The `firmwareVendor` property will return the vendor's name ("roguemaster"). This feature was added Feb 7, 2025. The other firmware implementations will return "flipperdevices", "momentum" or "unleashed".

RogueMaster version prior to Feb 7, 2025 will return `undefined`.

```js
let vendor = flipper.firmwareVendor;
print("Vend:", vendor); // prints "Vend: roguemaster"
```

## gpio
```js
let gpio = require("gpio");
```

gpio is used to access the General Purpose Input/Output (GPIO) pins of the Flipper Zero.

- [`init`](#gpio-init)`(pin: string, mode: string, pull: string) : undefined | error`
- [`read`](#gpio-read)`(pin: string) : boolean | error`
- [`write`](#gpio-write)`(pin: string, data: boolean) : undefined | error`
- [`startAnalog`](#gpio-start-analog)`([scale : double])`
- [`stopAnalog`](#gpio-stop-analog)`()`
- [`readAnalog`](#gpio-read-analog)`(pin: string) : double | error`

### gpio-init
The `init` function configures the pin for the specified mode.

The first parameter is the name of the pin:
- "PA7", "PA6", "PA4", "PB3", "PB2", "PC3", "PA14" (pin 10), "PA13" (pin 12), "PB6" (pin 13), "PB7" (pin 14), "PC1", "PC0", "PB14" (pin 17).

The second parameter supports the following:
- "input", "outputPushPull", "outputOpenDrain", "analog", 
it also supports these values (but lacks APIs to leverage the advanced state):
- "altFunctionPushPull", "altFunctionOpenDrain", "interruptRise", "interruptFall", "interruptRiseFall", "eventRise", "eventFall", "eventRiseFall"

The third parameter supports the following:
- "no", "up" (applies an internal pull-up resistor to 3V3), "down" (applies an internal pull-down resistor to GND)

```js
gpio.init("PA7", "outputPushPull", "no"); // Configure pin 2 (Pin A7) as output with no pull-up resistor.
gpio.init("PA6", "outputOpenDrain", "no"); // Configure pin 3 (Pin A6) as output (open-drain) with no pull-up resistor.
gpio.init("PA4", "input", "up"); // Configure pin 4 (Pin A4) as input with a pull-up resistor.
```

### gpio-read
The `read` function reads the status of a pin.  The pin should first be [init](#gpio-init) as "input".

```js
let result = gpio.read("PA4"); // returns false when pin PA4 is low, otherwise true.
print(result); 
```

### gpio-write
The `write` function changes the status of a pin.  The pin should first be [init](#gpio-init) as "outputPushPull" or "outputOpenDrain".

If the pin is "outputPushPull", setting `false` will set the pin to 0 volts and `true` will set the pin to 3.3 volts.
If the pin is "outputOpenDrain", setting `false` will set the pin to 0 volts and `true` will set the pin to floating.

```js
gpio.write("PA7", true); // Set the pin to 3.3 volts
gpio.write("PA6", false); // Set the pin to 0 volts
```

### gpio-start-analog
The `startAnalog` function configures the Flipper Zero for reading analog signals.  You must call this prior to using readAnalog. You must call stopAnalog() prior to calling this function a second time.  You can pass an optional parameter with the reference voltage range to use (either 2048 or 2500).  Analog pins should not exceed this reference voltage.

```js
gpio.startAnalog(2048); // 2.048 volt reference [pins can be 0-2048mV].
```

### gpio-stop-analog
The `stopAnalog` function configures the Flipper Zero to stop reading analog signals.  You must already have called startAnalog prior to calling this function.

```js
gpio.stopAnalog();
gpio.startAnalog(2500); // Switch to a 2.5 Volt reference range.
```
### gpio-read-analog
The `readAnalog` function reads the analog voltage on a GPIO pin.  Only PA7, PA6, PA4, PC3, PC1 and PC0 are supported.  The voltage on the pin should be between 0 volts and the reference voltage that was specified when startAnalog was called.  The measured circuit should have a 10K or less impedance for the value to be accurate.

```js
gpio.init("PA7", "analog", "no");
gpio.startAnalog(2048); // 0 - 2.048 volts on analog pins.
let millivolts = gpio.readAnalog("PA7");
print(to_string(millivolts) + "mV");
```

## i2c
```js
let i2c = require("i2c");
```

i2c is used to interface with hardware connected to GPIO that uses the I2C interface.

- [`isDeviceReady`](#i2c-is-device-ready)`(address: number, timeout: number) : bool | error`
- [`write`](#i2c-write)`(address: number, data:Uint8Array|array of numbers(0x00-0xFF), [timeout: number]) : bool | error`
- [`read`](#i2c-read)`(address: number, length: number, [timeout: number]) : array of numbers(0x00-0xFF) | error`
- [`writeRead`](#i2c-write-read)`(address: number, data:Uint8Array|array of numbers(0x00-0xFF), length: number, [timeout: number]) : array of numbers(0x00-0xFF) | error`

### i2c-is-device-ready
The `isDeviceReady` function return true if a device is found at the address specified.

```js
bool foundDevice = i2c.isDeviceReady(0x42, 5);
```

### i2c-write
The `write` function is used to send data to the device.

```js
i2c.write(addr, [0x00, 0x00, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]);
// or
i2c.write(addr, Uint8Array([0x00, 0x00, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]));
```

### i2c-read
The `read` function is used to read data from the device.

```js
let data_buf = i2c.read(addr, 2);
let data = Uint8Array(data_buf);
print("Read bytes: " + to_string(data.length));
for (let i = 0; i < data.length; i++) {
   print("data[" + to_string(i) + "] = " + to_hex_string(data[i]));
}
```

### i2c-write-read
The `writeRead` function is used to send data to the device, then read a response.

```js
let data_buf = i2c.writeRead(addr, [0x00, 0x01], 3, 100);
let data = Uint8Array(data_buf);
```


## keyboard
```js
let keyboard = require("keyboard");
```

keyboard is used to input text or hex data.

- [`setHeader`](#keyboard-set-header)`(header: string) : undefined | error`
- [`text`](#keyboard-text)`(allocSize: number, defaultText: string, selected: boolean) : string | undefined | error `
- [`byte`](#keyboard-byte)`(numBytes: number, data: Uint8Array) : Uint8Array | undefined | error `

### keyboard-set-header
The `setHeader` function sets the header text that will be displayed by the `byte` and `text` functions.

```js
keyboard.setHeader("Example Input");
```

### keyboard-text
The `text` function prompts the user to enter some text and then returns the inputted text.  If the user presses the back button then `undefined` is returned.

The first parameter is the number of bytes of memory to allocate for the response, which includes a byte for the null-terminator.  So if you want to allow entering up to 8 characters, you would pass a value of 8+1 to the function.

The second parameter is the default text to display.

The third parameter is `true` if the text should be selected otherwise `false`.  Having the text selected allows the user to quickly replace the text with something else.

```js
let result = keyboard.text(8+1, "demo", true);
print("Text is:"+result);
```

### keyboard-byte
The `byte` function prompts the user to enter a hex value and then returns the value.  If the user presses the back button then `undefined` is returned.

The first parameter is the number of bytes for the hex value.

The second parameter is the initial hex value to display.

```js
let result = keyboard.byte(6, Uint8Array([1, 2, 3, 4, 5, 6]));
if (result !== undefined) {
    let data = Uint8Array(result);
    result = "0x";
    for (let i = 0; i < data.byteLength; i++) {
        if (data[i] < 0x10) result += "0";
        result += to_hex_string(data[i]);
    }
}
```

## math
```js
let math = require("math");
```

math is used to perform various math operations on numbers.
- [`abs`](#math-abs)`(x : double) : double | undefined`
- [`acos`](#math-acos)`(x : double) : double | nan`
- [`acosh`](#math-acosh)`(x : double) : double | undefined | error`
- [`asin`](#math-asin)`(x : double) : double | error`
- [`asinh`](#math-asinh)`(x : double) : double | error`
- [`atan`](#math-atan)`(x : double) : double | error`
- [`atan2`](#math-atan2)`(y : double, x : double) : double | error`
- [`atanh`](#math-atanh)`(x : double) : double | error`
- [`cbrt`](#math-cbrt)`(x : double) : double | error`
- [`ceil`](#math-ciel)`(x : double) : double | error`
- [`clz32`](#math-clz32)`(x : double) : double | error`
- [`cos`](#math-cos)`(x : double) : double | error`
- [`exp`](#math-exp)`(x : double) : double | error`
- [`floor`](#math-floor)`(x : double) : double | error`
- [`is_equal`](#math-is-equal)`(x : double, y : double, delta : double) : boolean | error`
- [`log`](#math-log)`(x : double) : double | error`
- [`max`](#math-max)`(x : double, y : double) : double | error`
- [`min`](#math-min)`(x : double, y : double) : double | error`
- [`pow`](#math-pow)`(base : double, exponent : double) : double | error`
- [`random`](#math-random)`() : double | error`
- [`sign`](#math-sign)`(x : double) : double | error`
- [`sin`](#math-sin)`(x : double) : double | error`
- [`sqrt`](#math-sqrt)`(x : double) : double | error`
- [`trunc`](#math-trunc)`(x : double) : double | error`
- [`PI`](#math-pi)` : double`
- [`E`](#math-e)` : double`
- [`EPSILON`](#math-epsilon)` : double`

### math-abs
The `abs` function returns the absolute value of the input parameter.  Negative numbers become positive and positive numbers are unchanged.

```js
print(math.abs(-4)); // 4
```

### math-acos
### math-acosh
### math-asin
### math-asinh
### math-atan
### math-atab2
### math-atanh
### math-cbrt
### math-ciel
### math-clz32
### math-cos
### math-exp
### math-floor
### math-is-equal
The `isEqual` function compares two values for equality (within specified delta).

```js
print(math.isEqual(3.0/9.0, 0.3333, 0.0001)); // true
```

### math-log
### math-max
The `max` function returns the larger of the two parameters.

```js
print(math.max(15,4)); // 15
```

### math-min
The `min` function returns the smaller of the two parameters.

```js
print(math.max(15,4)); // 4
```

### math-pos
### math-random
The `random` function returns a random number between 0 and 2 (exclusive).

```js
print(math.random()); // 1.082337
```

### math-sign
### math-sin
### math-sqrt
### math-trunc
The `trunc` function removes the fractional part of a number.

```js
print(trunc(-3.432)); // -3.0
```

### math-pi
The `PI` constant is a double with value `3.14159265358979323846`.

```js
var pi = math.PI;
```

### math-e
The `E` constant is a double with value `2.7182818284590452354`.

```js
var e = math.E;
```

#math-epsilon
The `EPSILON` constant is a double with a value that represents the smallest positive double value that is greater than zero.

```js
var really_small_positive = math.EPSILON;
```


## notification

```js
let notify = require("notification");
```

notification is used to blink the status LED, play tones, and vibrate the Flipper Zero.

- `success() : undefined`
- `error() : undefined`
- `blink(color: string, type: string) : undefined | error`

### notification-success

The `success` function is called to indicate a successful action to the user.  Status light blinks green, vibrates, plays happy "do-de-da-lat" sound.

```js
notify.success();
```

### notification-error

The `error` function is called to indicate an error to the user.  Status light blinks red, vibrates, plays mad "do-do" sound.

```js
notify.error();
```

### notification-blink

The `blink` function is called to cause the status LED to blink.  Often this is called in a loop with a delay to have the LED blink multiple times.  NOTE: If the USB cable is plugged in the LED is turned to green and the blink may not be seen.

The first parameter is the name of the color.  Supported colors are: "blue", "red", "green", "yellow", "cyan", "magenta".

The second parameter is the type of notification.  Supported types are: "short", "long".

```js
for (let i = 0; i < 10; i++) {
    notify.blink("red", "short");
    delay(500);
}
```

## serial

```js
let serial = require("serial");
```

serial is used for USART (pins 13, 14) and LPUART (pins 15, 16) communication on the Flipper Zero.

- [`setup`](#serial-setup)`(port: string, baudrate: number) : undefined | error`
- [`end`](#serial-end)`() : undefined | error`
- [`write`](#serial-write)`(string | number | Uint8Array | [...number]) : undefined | error`
- [`read`](#serial-read)`(readlen: number [, timeout: number] ) : string | undefined | error`
- [`readln`](#serial-readln)`( [timeout: number] ) : string | undefined | error`
- [`readBytes`](#serial-read-bytes)`(readlen: number [, timeout: number] ) : array | undefined | error`
- [`readAny`](#serial-read-any)`( [timeout: number] ) : string | undefined | error`
- [`expect`](#serial-expect)`(array | string [, timeout: number] ) : number | undefined | error`

### serial-setup

The `setup` function is used to initialize the serial port.  Once it is initialized, it cannot be initialized again until `end` is called.

The first parameter is the port.  The valid values are "usart" (for pins 13 & 14) or "lpuart" (for pins 15 & 16).

The second parameter is the baud rate.

```js
serial.setup("lpuart", 115200);
```

### serial-end

The `end` function is used to deinitialize the serial port.  It should only be called after the `setup` function is called.

```js
serial.end();
```

### serial-write

The `write` function sends data on the serial port.  The port must already be initialized.  The parameter can be a string, number or array.  The numeric values must all be in the range of (0x00..0xFF).

```js
serial.write([0x0a]);
serial.write("uci\n");
```

## storage

```js
let storage = require("storage");
```

storage is used for accessing the SD card in the Flipper Zero.

- [`read`](#storage-read)`(path: string) : string | error`
- [`read v2`](#storage-read)`(path: string, size: number, offset: number) : string | error`
- [`write`](#storage-write)`(path: string, data: string) : boolean | error`
- [`write v2`](#storage-write)`(path: string, data: array | string) : boolean | error`
- [`append`](#storage-append)`(path: string, data: string) : boolean | error`
- [`copy`](#storage-copy)`(sourcePath: string, targetPath: string) : boolean`
- [`move`](#storage-move)`(originalPath: string, newPath: string) : boolean`
- [`exists`](#storage-exists)`(path: string) : boolean | error`
- [`mkdir`](#storage-mkdir)`(path: string) : boolean`
- [`remove`](#storage-remove)`(path: string) : boolean | error`
- [`virtualInit`](#storage-virtual-init)`(path: string) : boolean | error`
- [`virtualMount`](#storage-virtual-mount)`() : undefined | error`
- [`virtualQuit`](#storage-virtual-quit)`() : undefined | error`

### storage-read
The `read` function reads a file up to 128KB in size, starting at the specified offset and returns the contents as a binary array.

The first parameter is the path of the file.
The second parameter is the size to read.
The third parameter is the offset.

```js
function arraybuf_to_string(arraybuf) {
    let string = "";
    let data_view = Uint8Array(arraybuf);
    for (let i = 0; i < data_view.length; i++) {
        string += chr(data_view[i]);
    }
    return string;
}
let data = storage.read("/ext/demo.txt", 4096, 20480); // Read up to 4096 bytes, starting at offset 20480.
print(arraybuf_to_string(data));
```

### storage-write
The `write` function writes a string to a file, returning `true` if successful.  Overwrites existing file.

The first parameter is the path of the file.

The second parameter is the contents to write.

```js
let result = storage.write("/ext/demo.txt", "Hello world");
if (!result) { print("Failed to write file."); }
```

### storage-append
The `append` function appends a string to a file, returning `true` if successful.

The first parameter is the path of the file.

The second parameter is the contents to append.

```js
let result = storage.append("/ext/demo.txt", "Line 2.");
if (!result) { print("Failed to append to file."); }
```

### storage-copy
The `copy` function copies a file from one location to another, returning `undefined` if successful (otherwise returning the error description).

The first parameter is the path of the source file.

The second parameter is the path of the target file.

```js
let result = storage.copy("/ext/demo.txt", "/ext/demo2.txt");
if (result !== undefined) {
  print("Failed to copy file", result);
}
```

### storage-move
The `move` function moves a file from one location to another, returning `undefined` if successful (otherwise returning the error description).

The first parameter is the path of the source file.

The second parameter is the new path.

```js
let result = storage.move("/ext/demo.txt", "/ext/demo2.txt");
if (result !== undefined) {
  print("Failed to move file", result);
}
```

### storage-exists
The `exists` function returns `true` if a file exists at the specified path, otherwise `false`.

The parameter is the path of the file.

```js
let result = storage.exists("/ext/demo.txt");
if (result) { print("File exists"); } else { print("File does not exist"); }
```

### storage-mkdir
The `mkdir` function create a new directory.  It returns `true` if successful, otherwise `false`.

The parameter is the path of the directory.

```js
if (!storage.exists("/ext/demo")) {
  let result = storage.mkdir("/ext/demo");
  if (!result) {
    print("Failed to create directory");
  }
}
```

### storage-remove
The `remove` function deletes a file at the specified path, returning `true` if successful.

The parameter is the path of the file.

```js
let result = storage.remove("/ext/demo.txt");
if (!result) { print("Failed to remove file."); }
```

### storage-virtual-init
The `virtualInit` function maps virtual storage to a file.

The first parameter is the path to the file to mount.  The file should be created with [usbdisk.createImage](#usbdisk-create-image).

```js
let usb = require("usbdisk");
let path = __dirpath + "4MB.img";
usbdisk.createImage(path, 4*1024*1024); // Create the image using usbdisk.createImage.
storage.virtualInit(path);
```

### storage-virtual-mount
The `virtualMount` function attaches virtual storage to the `/mnt/` folder.

```js
let result = storage.virtualMount();
if (result) {
  storage.write("/mnt/demo.txt", "Hello World");
} else {
  print("failed to mount");
}
```

### storage-virtual-quit
The `virtualQuit` function detaches virtual storage from the `/mnt/` folder.

```js
storage.virtualQuit();
```

## subghz
```js
let subghz = require("subghz");
```

subghz is used for accessing the subghz radio (CC1101) on the Flipper Zero.

- [`end`](#subghz-end)`() : undefined`
- [`getFrequency`](#subghz-get-frequency)`() : number`
- [`getRssi`](#subghz-get-rssi)`() : number | error`
- [`getState`](#subghz-get-state)`() : string`
- [`isExternal`](#subghz-is-external)`() : boolean`
- [`setFrequency`](#subghz-set-frequency)`(frequency: number) : number | error`
- [`setIdle`](#subghz-set-idle)`() : undefined`
- [`setRx`](#subghz-set-rx)`() : undefined`
- [`setup`](#subghz-setup)`() : undefined`
- [`transmitFile`](#subghz-transmit-file)`(file: string) : boolean | undefined | error`

### subghz-end

The `end` function allows you to call [`setup`](#subghz-setup) again, checking for an external module.

```
subghz.end();
```

### subghz-get-frequency

The `getFrequency` function returns the current frequency for the received or last sent signal.

```
let rssi = subghz.getRssi();
print("rssi: ", rssi);
```

### subghz-get-rssi

The `getRssi` function returns the current RSSI (Receive Signal Signal Indicator) for the received signal.  The subghz must be in receive mode.

```
let rssi = subghz.getRssi();
print("rssi: ", rssi);
```

### subghz-get-state

The `getState` function returns the current state of the radio.  Valid states are "RX", "TX", "IDLE" and "".

```js
let state = subghz.getState();
print("state: ", state);
```

### subghz-is-external

The `isExternal` function returns `true` if an external CC1101 radio is being used, otherwise it returns `false`.

```js
let result = subghz.isExternal();
if (result) { print("external radio"); } else { print("internal radio"); }
```

### subghz-set-frequency

The `setFrequency` function is used to set the frequency of the radio.  The state must be "IDLE" before setting the frequency.

The first parameter is the frequency in hertz.  The frequency must be a frequency allowed by the firmware.

```js
subghz.setFrequency(433920000);
```

### subghz-set-idle

The `setIdle` function is used to set the state of the radio to "IDLE".

```js
subghz.setIdle();
```

### subghz-set-rx

The `setRx` function is used to set the state of the radio to "RX".

```js
subghz.setRx();
```

### subghz-setup

The `setup` function initializes the subghz radio.  It configures to use the external radio based on firmware settings.  It sets the radio to "IDLE" and changes the default frequency to 433.92MHz.

```js
subghz.setup();
```

### subghz-transmit-file

The `transmitFile` function sets a subghz file.  The '.sub' file can use a supported protocol or it can use `RAW` format.  The file is sent on the frequency specified in the file, and the `getFrequency` value is updated.  If the file is successful sent the function will return `true`.

You can pass a `repeat` count as a second parameter to `transmitFile`.  If set, the signal will be repeated the number of times requested.  (NOTE: This feature is not available on Xtreme FW).

```js
let result = subghz.transmitFile("/ext/subghz/demo.sub");
if (result) { print("sent"); } else { print("failed to send"); }

subghz.transmitFile("/ext/subghz/demo.sub", 3); // Repeat signal 3 times.
```

## submenu

```js
let submenu = require("submenu");
```

submenu is used for creating a scrollable menu of items and returning the selected one.

- [`addItem`](#submenu-add-item)`(label: string, id: number) : undefined | error`
- [`setHeader`](#submenu-set-header)`(label: string) : undefined | error`
- [`show`](#submenu-show)`() : number : undefined`

### submenu-add-item
The `addItem` function adds a new entry to the menu.

The first parameter is the name of the entry.

The second parameter is the id associated with the entry, which will be returned when the user selects the item.

```js
submenu.addItem("Calculate tip", 0);
```

### submenu-set-header
The `setHeader` function updates the header that is displayed at the top of the submenu.

```js
submenu.setHeader("Choose an item");
```

### submenu-show
The `show` function displays the submenu and returns the id of the item selected.  If the user presses the `Back` button, then `undefined` is returned.

```js
let result = submenu.show();
if (result === undefined) {
  print("User pressed back");
} else if (result === 0) {
  print("User selected id 0.");
}
```

## textbox

```js
let textbox = require("textbox");
```

textbox is used for creating a dynamic display of text on the Flipper Zero.  Contents are displayed in a non-blocking way, allowing the script to continue running and update the UI.  The user can scroll the textbox contents, however whenever it is updated, focus is reset.

- [`addText`](#textbox-add-text)`(contents: string) : undefined | error`
- [`close`](#textbox-close)`() : undefined`
- [`clearText`](#textbox-clear-text)`() : undefined`
- [`isOpen`](#textbox-is-open)`() : boolean`
- [`setConfig`](#textbox-set-config)`(focus: string, font: string) : undefined | error`
- [`show`](#textbox-show)`() : undefined`

### textbox-add-text

The `addText` function appends the specified text to the end of the textbox.

The parameter is the contents to append.

```js
textbox.addText("Hello world");
```

### textbox-close

The `close` function closes the textbox.

```js
textbox.close();
```

### textbox-clear-text

The `clearText` function clears the contents of the textbox.  NOTE: On Xtreme firmware, this is still called `emptyText`.

```js
textbox.clearText();
```

### textbox-is-open

The `isOpen` function returns `true` if the textbox is currently visible.  After a `show` command the textbox is visible until it is closed by either calling `close` or by the user pressing the `Back` button.

```js
let result = textbox.isOpen();
if (!result) { print("textbox is closed"); } else { print("textbox is open"); }
```

### textbox-set-config

The `setConfig` function configures the textbox.

The first parameter is where focus should be set when it is updated.  Valid values are "start" (set focus to beginning of text) and "end" (set focus to the end of the text).

The second parameter is the font to use.  Valid values are "text" and "hex".

```js
textbox.setConfig("end", "text");
```

### textbox-show

The `show` function displays the textbox.  It will be visible until it is closed by either calling `close` or by the user pressing the `Back` button.

```js
textbox.show();
```

## usbdisk

```js
let usbdisk = require("usbdisk");
```

usbdisk is used for exposing a special file on the SD Card as a USB thumb drive via the Flipper Zero's USB port.  This is helpful for copying files between the host computer and the Flipper Zero without needing any special software installed.

- [`createImage`](#usbdisk-create-image)`(path: string, capacity: number) : undefined | error`
- [`start`](#usbdisk-start)`(path: string) : undefined | error`
- [`stop`](#usbdisk-stop)`() : undefined | error`
- [`wasEjected`](#usbdisk-was-ejected)`() : boolean | error`

### usbdisk-create-image

The `createImage` function is used to create a special file that can be used as the USB drive.  Note: This file can also be used by [storage.virtualInit](#storage-virtual-init) to read and write files to it.

The first parameter is the path to the file.

The second parameter is the number of bytes to reserve for the image.

```js
usbdisk.createImage("/ext/apps_data/mass_storage/4MB.img", 4*1024*1024);
```

### usbdisk-start

The `start` function will expose the file as a USB drive.

The parameter is the path to the file.

```js
usbdisk.start("/ext/apps_data/mass_storage/4MB.img");
```

### usbdisk-stop

The `stop` function will detach the USB drive.

```js
usbdisk.stop();
``` 

### usbdisk-was-ejected

The `wasEjected` function will return `true` if the USB drive has been ejected from the host computer.

```js
// Wait for the disk to be ejected.
while (usbdisk.wasEjected()) {
  delay(1000);
}
```

## vgm
```js
let vgm = require("vgm");
```

vgm is used to access the sensors of the [Video Game Module](https://blog.flipper.net/introducing-video-game-module-powered-by-raspberry-pi). See [this project](https://github.com/jamisonderek/flipper-zero-tutorials/tree/main/vgm/imu_controller) for more details on pitch, roll and yaw.
<img alt="VGM pitch-roll-yaw" src="https://github.com/jamisonderek/flipper-zero-tutorials/blob/main/vgm/imu_controller/flipper-pitch-roll-yaw.png" width="50%"/>

- [`getPitch`](#vgm-get-pitch)`(): number`
- [`getRoll`](#vgm-get-roll)`(): number`
- [`getYaw`](#vgm-get-yaw)`(): number`
- [`deltaYaw`](#vgm-delta-yaw)`(angle: number [, timeout: number]): number`

#vgm-get-pitch
The `getPitch` function returns the pitch of the VGM in degrees (-90 to 90).

```js
let pitch = vgm.getPitch();
print("Pitch", pitch);
```

#vgm-get-roll
The `getRoll` function returns the roll of the VGM in degrees (-180 to 180).

```js
let roll = vgm.getRoll();
print("Roll", roll);
```

#vgm-get-yaw
The `getYaw` function returns the yaw of the VGM in degrees (-180 to 180).

```js
let yaw = vgm.getYaw();
print("Yaw", yaw);
```

#vgm-delta-yaw
The `delyaYaw` function returns the amount of change in yaw of the VGM in degrees if it exceeds the threshold, otherwise 0.

The first parameter is the threshold of yaw change.

The second parameter is the timeout in milliseconds.

```js
let yaw = vgm.deltaYaw(45, 3000); // Wait for Flipper to be rotated at least 45 degrees in the next 3 seconds.
if (yaw===0) {
  print("Flipper was not rotated.");
} if (yaw>0) {
  print("Flipper was rotated clockwise");
} else {
  print("Flipper was rotated counter-clockwise");
}
```

## widget

```js
let widget = require("widget");
```

widget is used for displaying non-blocking UI elements.

- [`addBox`](#widget-add-box)`(x: number, y: number, w: number, h: number): number`
- [`addCircle`](#widget-add-circle)`(x: number, y: number, r: number): number`
- [`addDisc`](#widget-add-disc)`(x: number, y: number, r: number): number`
- [`addDot`](#widget-add-dot)`(x: number, y: number): number`
- [`addFrame`](#widget-add-frame)`(x: number, y: number, w: number, h: number): number`
- `addIcon` is not supported, use [`addXbm`](#widget-add-xbm)` instead.
- [`addGlyph`](#widget-add-glyph)`(x: number, y: number, ch: number): number`
- [`addLine`](#widget-add-line)`(x1: number, y1: number, x2: number, y2: number): number`
- [`addRbox`](#widget-add-rbox)`(x: number, y: number, w: number, h: number, r: number): number`
- [`addRframe`](#widget-add-rframe)`(x: number, y: number, w: number, h: number, r: number): number`
- [`addText`](#widget-add-text)`(x: number, y: number, font: string, text: string): number`
- [`addXbm`](#widget-add-xbm)`(x: number, y: number, index: number): number`
- [`close`](#widget-close)`(): undefined`
- [`loadImageXbm`](#widget-load-image-xbm)`(path: string): number`
- [`remove`](#widget-remove)`(id: number): boolean`
- [`isOpen`](#widget-is-open)`(): boolean`
- [`show`](#widget-show)`(): undefined`

### widget-add-box
The `addBox` function will add a filled in box at (x,y) with a width of (w,h).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the width.

The fourth parameter is the height.

```js
let x=10; // over
let y=15; // down
let w=20; // 20 pixels wide
let h=10; // 10 pixels high
let id = widget.addBox(x,y,w,h); // You can remove later with: remove(id);
```

### widget-add-circle
The `addCircle` function will add a circle centered at (x,y) with a radius of (r).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the radius.

```js
let x=10; // over
let y=15; // down
let r=5; // 5 pixel radius
let id = widget.addCircle(x,y,r); // You can remove later with: remove(id);
```

### widget-add-disc
The `addCircle` function will add a filled in disc centered at (x,y) with a radius of (r).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the radius.

```js
let x=10; // over
let y=15; // down
let r=5; // 5 pixel radius
let id = widget.addDisc(x,y,r); // You can remove later with: remove(id);
```

### widget-add-dot
The `addDot` function will set the pixel at (x,y).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

```js
let x=10; // over
let y=15; // down
let id = widget.addDot(x,y); // You can remove later with: remove(id);
```

### widget-add-frame
The `addFrame` function will add an outlined rectangle at (x,y) with a width of (w,h).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the width.

The fourth parameter is the height.

```js
let x=10; // over
let y=15; // down
let w=20; // 20 pixels wide
let h=10; // 10 pixels high
let id = widget.addFrame(x,y,w,h); // You can remove later with: remove(id);
```

### widget-add-glyph
The `addGlyph` function will add a glyph at (x,y) using the character specified.

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the code of the glyph.

```js
let x=10; // over
let y=15; // down
let ch=35; // typically ascii code of glyph.
let id = widget.addGlyph(x, y, ch); // You can remove later with: remove(id);
```

### widget-add-line
The `addLine` function will draw a line from (x1,y1) to (x2,y2).

The first parameter is the x coordinate of the first point. 0 is left most. 127 is right most.

The second parameter is the y coordinate of the first point. 0 is top most. 63 is bottom most.

The third parameter is the x coordinate of the second point. 0 is left most. 127 is right most.

The fourth parameter is the y coordinate of the second point. 0 is top most. 63 is bottom most.

```js
let x1=10; // over
let y1=15; // down
let x2=100; // over
let y2=35; // down
let id = widget.addLine(x1, y1, x2, y2); // You can remove later with: remove(id);
```

### widget-add-rbox
The `addRbox` function will add a filled in box at (x,y) with a width of (w,h) with rounded corners of radius (r).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the width.

The fourth parameter is the height.

The firth parameter is the radius.

```js
let x=10; // over
let y=15; // down
let w=20; // 20 pixels wide
let h=10; // 10 pixels high
let r=3; // 3 pixel radius
let id = widget.addBox(x,y,w,h,r); // You can remove later with: remove(id);
```

### widget-add-rframe
The `addRbox` function will add an outlined rectangle at (x,y) with a width of (w,h) with rounded corners of radius (r).

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the width.

The fourth parameter is the height.

The firth parameter is the radius.

```js
let x=10; // over
let y=15; // down
let w=20; // 20 pixels wide
let h=10; // 10 pixels high
let r=3; // 3 pixel radius
let id = widget.addRbox(x,y,w,h,r); // You can remove later with: remove(id);
```

### widget-add-text
The `addText` function will add text at (x,y) with the specified font.

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the font.  Valid values are: "Primary", "Secondary".

The fourth parameter is the height.

The firth parameter is the radius.

```js
let x=10; // over
let y=15; // down
let font="Primary"; // Large font
let text="Hello!";
let id = widget.addText(x,y,font,text); // You can remove later with: remove(id);
```

### widget-add-xbm
The `addXbm` function will render a XBM image at (x,y) with the specified image.

The first parameter is the x coordinate. 0 is left most. 127 is right most.

The second parameter is the y coordinate. 0 is top most. 63 is bottom most.

The third parameter is the image identifier.  Use [`loadImageXbm`](#widget-load-image-xbm) to get the identifier.

```js
let x=10; // over
let y=15; // down
let identifier= widget.loadImageXbm(__dirpath + "/demo.xbm");
let id = widget.addText(x,y,identifier); // You can remove later with: remove(id);
```

### widget-close
The `close` function will stop displaying the widget.

### widget-load-image-xbm
The `loadImageXbm` function is used to load an image.  You can then pass the returned value to [`addXbm`](#widget-add-xbm).

The parameter is the path to the xbm file.

```js
let identifier= widget.loadImageXbm(__dirpath + "/demo.xbm");
```
 
### widget-remove
The `remove` function is used to remove a previously added component.

The parameter is the id that was returned from a previous add... method.

```js
let line = widget.addLine(10, 10, 100, 60);
widget.show();
delay(1000);
widget.remove(line); // Remove the previously added component.
delay(1000);
widget.close();
```

### widget-is-open
The `isOpen` function is used to tell if the widget is being displayed.  When a user presses the `Back` button the widget will be dismissed and this function will return `false`.

```js
widget.show();
while (widget.isOpen()) {
  delay(100);
}
```

### widget-show
The `show` function is used to display the widget.  The widget can be dismissed by pressing the `Back` button or by calling [`close`](#widget-close).

```js
widget.show();
```
