# Overview
uFBT us a cross-platform tool for building application for Flipper Zero. It is a lightweight version of FBT that is installed when you clone the entire firmware repo. uFBT requires you first install Python 3.8 or newer.

# Installation
You can find installation directions on the [official project](https://github.com/flipperdevices/flipperzero-ufbt?tab=readme-ov-file#installation) documentation.

- Linux & macOS: python3 -m pip install --upgrade ufbt
- Windows: py -m pip install --upgrade ufbt

# Building
- Run `ufbt` in the directory where your **application.fam** file is. This will compile the application and create a **dist** folder with the resulting FAP file, which you can copy onto the SD card.
- Run `ufbt launch` in the directory where your **application.fam** file is. Be sure your Flipper Zero is connected with a USB cable that has data capabilities and that qFlipper and lab.flipper.net are NOT running. This will build, install and run the application on the Flipper Zero. If you look at the application.fam file, the `fap_category` will tell you which folder it was installed into.

# Changing channel
`ufbt update --channel=[dev|rc|release]` will change which release channel you are using. If your Flipper is running a different channel than uFBT you may see API compatibility errors.

# Changing branches
`ufbt update -b branchname` will change to the branch name. This is helpful if you want to change to a named branch. For example, `ufbt update -b 1.1.2-rc` will switch to using branch index https://update.flipperzero.one/builds/firmware/1.1.2-rc/ for the SDK definitions.

# Switching target Firmware
## Official firmware
`ufbt update --index-url=https://update.flipperzero.one/firmware/directory.json`

## Unleashed firmware
`ufbt update --index-url=https://up.unleashedflip.com/directory.json`

## Momentum firmware
`ufbt update --index-url=https://up.momentum-fw.dev/firmware/directory.json`

## RogueMaster firmware
- UFBT is not supported. Please contain [RogueMaster](https://www.patreon.com/c/roguemaster/about) to add your application into the firmware.
