# Overview
Momentum has the most complete support for JavaScript files. The JavaScript model changed on Oct 15, 2024 - so scripts written before this date will need to be migrated to the latest API. This is non-trivial, as you have to rewrite the script to use **event_loop** for the messaging. I created a video about the new features at https://youtu.be/WCIIimWm1qg which may be helpful for migration.

Example scripts can be found in the Momentum firmware under the [js_app/examples](https://github.com/Next-Flip/Momentum-Firmware/tree/dev/applications/system/js_app/examples/apps/Scripts) folder. You can also ask people in the [Momentum Discord](https://discord.gg/momentum) server. The Discord server has a "Coding/javascript" folder for discussion & a "Coding/script-sharing" for people to share scripts.

Flipper Zero uses [mjs](https://github.com/cesanta/mjs). This version of JavaScript has many [restrictions](https://github.com/cesanta/mjs?tab=readme-ov-file#restrictions). Scripts are typically saved to the `SD Card/apps/Scripts` folder. You launch JS files by starting at the Main Menu on the Flipper Zero and selecting `Apps`/`Scripts`/_name_.js file.

# Capabilities
Feb 8, 2025 - Momentum runs the latest Flipper Zero JavaScript. **Scripts made before Oct 15, 2024 will not run!**
- CLI support (from a CLI window run the "js" command).
- BadUSB keyboard support, including different keyboard layouts.
- Read and write to files on the Flipper.
- Read and write to serial port (TX/RX or C1/C0 pins).
- GPIO for digital input/output.
- GPIO for analog input.
- Run a function when GPIO pin transitions value.
- Run a function after a specific amount of time.
- File Picker dialog to pick a file.
- Dialog with Left/Right/Center choices.
- Empty & Loading screen.
- Submenu with items to pick.
- On-screen keyboard for text input or byte input.
- Dynamic textbox (update text contents while app still running).
- Success/Error notifications.
- Math functions.
- Get the battery level of the Flipper.
- Get the name of the Flipper.
- Conditional logic, Loops, Number to String, String to Number.
- I2C and SPI support. **"i2c"**, **"spi"**
- Get the pitch, roll and yaw of the Video Game Module (VGM) **"vgm"**
- Widget support for rending more complex screens. **"widget"**
- BLE Beacon support. **"blebeacon"**
- Transmit a Sub-GHz file. **"subghz"**
- See if a Sub-GHz frequency has strong signal on it. **"subghz"**
- Manipulate a virtual USB drive. **"usbdisk"**

## Vs Official firmware
As of Feb 8, 2025, the following features are only in Momentum:
- CLI support (from a CLI window run the "js" command).
- I2C support. **"i2c"**
- SPI support. **"spi"**
- Get the pitch, roll and yaw of the Video Game Module (VGM). **"vgm"**
- Widget support for rendering more complex screens. **"widget"**
- BLE Beacon support. **"blebeacon"**
- Transmit a Sub-GHz file. **"subghz"**
- See if a Sub-GHz frequency has strong signal on it. **"subghz"**
- Manipulate a virtual USB drive. **"usbdisk"**
- TextInput supports show/hide "illegal symbols" (keyboard lacks symbols). **"gui-textinput-illegalsymbols"**

## Vs Unleashed firmware
As of Feb 8, 2025, the following features are only in Momentum:
- Manipulate a virtual USB drive. **"usbdisk"**
- TextInput supports show/hide "illegal symbols" (keyboard lacks symbols). **"gui-textinput-illegalsymbols"**

# Best Practice
Feb 8, 2025 - Scripts written for RogueMaster will not work in Momentum. Scripts written for Momentum will not work in RogueMaster.

Scripts made for Official Flipper Zero JavaScript will work on Momentum Firmware too. If you use extra features provided by Momentum, you are encouraged to use syntax like `if (doesSdkSupport(["feature-name"])) { ... }` so that your JS app can work on Official Firmware too. If some of those extra features are essential to the functionality of your app, you can use `checkSdkFeatures(["feature1", "feature2"])` near the beginning of your script, which will show a warning to the user that these features are not available in their firmware distribution.

Features supported by `doesSdkSupport` and `checkSdkFeatures` are: 
- **Modules**: "blebeacon", "i2c", "spi", "subghz", "usbdisk", "vgm", "widget".
- **Functions**: "gui-textinput-illegalsymbols", "storage-virtual", "usbdisk-createimage", "widget-addicon".



# Common Script Usage
The most common JavaScript pattern that I've seen used in Momentum firmware was for advanced BadUSB scripts. Momentum supports **"storage-virtual"** and **"usbdisk-createimage"** making it possible to copy payloads from the Flipper Zero onto the host computer and to also exfil payloads back onto the Flipper Zero, instead of needed to send to a webhook.

- Use badusb to connect the keyboard to computer
- Press `Windows`+`R` and type powershell
- Runs the following badusb script (which starts executing after the entire script is entered): 
  - tell user to close window when window closes
  - sleep 10 seconds
  - find "Flipper Mass Storage" drive
  - run commands (sometimes from USB drive, sometimes locally)
  - copy output to USB drive
  - delete MRU and history
  - close window
- Attach USB drive
- Wait for USB drive to be ejected
- Stop USB drive

# Concepts
Flipper Zero uses [mjs](https://github.com/cesanta/mjs). This version of JavaScript has many [restrictions](https://github.com/cesanta/mjs?tab=readme-ov-file#restrictions). The JavaScript scripts are text files with a `.js` file extension stored in the `SD Card/apps/Scripts` folder. You launch JS files by starting at the Main Menu on the Flipper Zero and selecting `Apps`/`Scripts`/_name_.js file. You can use any text editor, including the mobile phone app, to edit the files.

## Let keyword
Variables are defined using the `let` keyword. You should always use the `let` keyword (instead of `var` or other techniques).

```js
let msg = "Hello"; // defines a variable named msg.
print(msg.toUpperCase());
```

## Validate support
The top of your script should use the `checkSdkFeatures` to validate the required APIs exist. See the [Best Practice](#best-practice) section above.
If the feature is optional but not available on all firmware, you should use `doesSdkSupport` to test for the feature.

```js
// This script mounts a 1MB image. 
// If the image doesn't exist, it will be created.
checkSdkFeatures(["storage-virtual");
let storage = require("storage");
let usbdisk = require("usbdisk");
let imagePath = "/ext/apps_data/mass_storage/1MB.img";
let imageSize = 1 * 1024 * 1024;

if (doesSdkSupport(["usbdisk-createimage"])) {
    print("Creating disk image...");
    usbdisk.createImage(imagePath, imageSize);
}

// should be do a storage.fileExists(image) to confirm the file exists?

storage.virtualInit(imagePath);
storage.virtualMount();
```

## Import modules
You import modules using the `require` function. This is typically done at the top of the file.

**NOTE:** Before you import the `gui` module or the `gpio` module, you must first `let eventLoop = require("event_loop");`. If the event_loop is not already loaded, the script will fail.

```js
// import modules
let eventLoop = require("event_loop"); // you MUST require this before "gui" or "gpio".
let gui = require("gui"); // you MUST require this before any "gui/{module}".
let submenuView = require("gui/submenu");
let textInputView = require("gui/text_input");
let dialogView = require("gui/dialog");
let flipper = require("flipper");
let gpio = require("gpio");
```

## Comparison
In Flipper JavaScript you must use `===` to test for equality and `!==` to test for not equal.

```js
if (index === 1) {
   print("Hello");
} if (index !== 2) {
   die("Invalid index: "+index.toString());
} else {
   print("World!");
}
```

