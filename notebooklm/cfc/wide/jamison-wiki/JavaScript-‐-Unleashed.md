# Overview
Unleashed firmware has almost all of the same support for JavaScript as the Momentum firmware.

The differences are Unleashed firmware doesn't support:
- **"gui-textinput-illegalsymbols"** since its keyboard doesn't have symbols. 
- **"widget-addicon"** since asset management is not done the same way (so icon names are unknown). 
- **"storage-virtual"** or **"usbdisk-createimage"**, which means you can't create, mount, or manipulate virtual USB drives. Typically used by BadUSB JavaScripts.

Please see the [JavaScript - Momentum](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/JavaScript-%E2%80%90-Momentum) wiki page for additional details on programming JavaScript.
