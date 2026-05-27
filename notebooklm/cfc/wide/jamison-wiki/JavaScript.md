# Overview
The latest version of firmware now supports running JavaScript applications, using [mjs](https://github.com/cesanta/mjs). This version of JavaScript has many [restrictions](https://github.com/cesanta/mjs?tab=readme-ov-file#restrictions). Scripts are typically saved to the `SD Card/apps/Scripts` folder. You launch JS files by starting at the Main Menu on the Flipper Zero and selecting `Apps`/`Scripts`/_name_.js file.

JavaScript files usually have a `.js` file extension. They are text files that can be edited using a text editor. You can even use the mobile phone application to edit your Flipper Zero scripts on your phone. No special tools are required to write JavaScript, however if you write them using VS Code using the cloned firmware project you will get IntelliSense help. When the script runs, mistakes will often show an error message -- [known issue](https://github.com/flipperdevices/flipperzero-firmware/pull/4075).

# Compatibility
Just like JavaScript in the browser, Flipper JS has different levels of support depending on which firmware you are running on.

Feb 8, 2025 - **Scripts written for RogueMaster will not work in any other firmware. Scripts written for any other firmware will not work in RogueMaster.**

When Official firmware added the GUI (user interface) and GPIO (hardware pins) support, they introduced the concept of an **event loop**. Official firmware also changed the function parameters from what Momentum had originally created. These changes were adopted by both Momentum and Unleashed Firmware. RogueMaster has not yet transitioned, so only "older scripts" will function on the RogueMaster implementation.

- [Momentum JavaScript](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript-%E2%80%90-Momentum) has the most support for the latest implementation of JavaScript.
- [Unleashed JavaScript](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript-%E2%80%90-Unleashed) supports the majority of features. It lacks `usb disk creation` & `virtual storage`. The onscreen keyboard is more limited, so it doesn't have the ability to enter any `illegal symbols`. The asset pack support is different, so icons aren't named (so there is no `widget addIcon`).
- [Official firmware JavaScript](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript-%E2%80%90-Official-Firmware) is missing the same features as Unleashed, but it also lacks `BLE Beacon`, `I2C`, `SPI`, `SubGHz`, `VGM` and `Widget` support.
- [RogueMaster JavaScript](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript-%E2%80%90-RogueMaster) is the **older implementation BEFORE event_loop**. It does support SubGHz, USB Disk, VGM, BadUSB, BLEBeacon, Dialog, GPIO, I2C, Keyboard text input, Keyboard byte input, Serial, SubMenu, TextBox and Widget.

You can use `flipper.firmwareVendor` to get the name of the firmware you are running ("flipperdevices", "momentum", "unleashed", "roguemaster"). This can be helpful to load a different script, such as one written specifically for roguemaster.

You can use `if (doesSdkSupport(["feature-name"])) { ... }` to check if a feature is supported in your firmware. You can use `checkSdkFeatures(["feature1", "feature2"])` near the beginning of your script, which will show a warning to the user that these features are not available in their firmware distribution. (note: these APIs are not supported by RogueMaster firmware.)


# Features
It depends on your firmware, but this is the current list of capabilities that JavaScript supports on Momentum: (as of Feb 8, 2025)
- BadUSB keyboard support, including different keyboard layouts.
- Read and write to files on the Flipper.
- Read and write to serial port (TX/RX or C1/C0 pins).
- GPIO for digital input/output.
- GPIO for analog input.
- "PWM" support (required latest dev or MNTM-010 or greater).
- I2C and SPI support. **"i2c"**, **"spi"**
- Run a function when GPIO pin transitions value.
- Run a function after a specific amount of time.
- File Picker dialog to pick a file.
- Dialog with Left/Right/Center choices.
- Empty & Loading screen.
- Submenu with items to pick.
- On-screen keyboard for text input or byte input.
- Dynamic textbox (update text contents while app still running).
- Get the pitch, roll and yaw of the Video Game Module (VGM) **"vgm"**
- Widget support for rendering more complex screens. **"widget"**
- Success/Error notifications.
- Math functions.
- Get the battery level of the Flipper.
- Get the name of the Flipper.
- Get the name ("flipperdevices", "roguemaster", "momentum", "unleashed") of the firmware.
- Conditional logic, Loops, Number to String, String to Number.
- BLE Beacon support. **"blebeacon"**
- Transmit a Sub-GHz file. **"subghz"**
- See if a Sub-GHz frequency has strong signal on it. **"subghz"**
- Manipulate a virtual USB drive. **"storage-virtual"**, **"usbdisk-createimage"**

# Not supported
Here are some examples of features JavaScript on the Flipper cannot currently do.  In some cases, it may be possible to extend the firmware with additional support or to write an FFI (Foreign Function Interface) code that provides access to the needed APIs.  If you have ideas of features you would like supported, please reach out on Discord server (@CodeAllNight) or file an issue on this GitHub repo.
- d-pad input callbacks
- Play tones or vibrate
- Read/Capture Sub-GHz signal (JavaScript can send Sub-GHz)
- Anything with RFID signals
- Anything NFC signals
- Anything with IR signals
- Anything with iButton signals
- Anything with U2F
- Advanced UI screens
- Precision timer
