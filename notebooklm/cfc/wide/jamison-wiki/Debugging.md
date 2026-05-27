# Video
I have a [YouTube video](https://youtu.be/CLsLZO15S44) for debugging FURI_ASSERT failures on the Flipper Zero using ESP32.  This wiki page goes into even more detail on debugging.

# Easy way (buy the wifi-devboard)
You can purchase a [wifi-devboard](https://shop.flipperzero.one/collections/flipper-zero-accessories/products/wifi-devboard) from shop.flipperzero.one for $29 USD.  The devboard comes preinstalled with the BlackMagic firmware, which exposes the devboard as a WIFI access point and also a pair of serial ports for debugging the Flipper Zero.  Plug the board into the top of your Flipper and you are ready to go!

# DIY (bring your own ESP32-S2)
## Flash the software
If you already have an ESP32-S2, you can use [FZ Marauder Flasher](https://github.com/SkeletonMan03/FZEasyMarauderFlash) to flash the Blackmagic firmware.  For Windows users there is a [second technique](https://github.com/UberGuidoZ/Flipper/tree/main/Wifi_DevBoard/FZ_Marauder_Flasher) available as well.

If you are wanting something custom, you can [build your own firmware](https://github.com/flipperdevices/blackmagic-esp32-s2) and use idf.py to flash your ESP32.  The project seems fairly complex, but I haven't looked into it in detail yet.

I haven't looked into other devices besides the ESP32-S2 for running [Blackmagic](https://black-magic.org/) to debug the Flipper Zero.


## Connect the wires
For Blackmagic to debug the Flipper Zero, there are 4 pins that are used.  Pin 9 (3V3) on the Flipper goes to 3v3 on the ESP32-S2 (this is optional if you are going to be plugging the board into your USB port, since it will get power from there).  Pin 10 (SWC) on the Flipper goes to GPIO1 on the ESP32-S2 (on my board this is marked "1").  Pin 11 (GND) on the Flipper goes to GND on the ESP32-S2 (on my board this is marked "G").  Pin 12 (SIO) on the Flipper goes to GPIO2 on the ESP32-S2 (on my board this is marked "2").

# Connect dev box to the Flipper
## WIFI
If you are using Blackmagic WIFI, then it will expose an access point with an SSID named "blackmagic" and a password of "iamwitcher".  You can connect to the access point and then "blackmagic.local" should show up (at address [192.168.4.1](http://192.168.4.1)).  The debugger is running on port 2345.  Port 80 is a management UI where you can change your SSID/password and also switch from an AP to an STA.

NOTE: Once you switch to an STA, I'm not clear how you would switch back to an AP, if the device failed to connect to the STA?

## USB/Serial
If you are using Blackmagic USB, then plug the USB cable into your computer and two serial ports should appear.  The first port is used for debugging.  (I think the second port may be for logging, but I haven't tried yet.)

# Attaching a debugger
## Confirm you can detect Blackmagic probe
From the root of your Flipper firmware project (e.g. where you ```git clone --recursive https://github.com/flipperdevices/flipperzero-firmware```) you should have the **fbt** command.

Run the following command to detect your blackmagic probe:
```
fbt get_blackmagic
```

## Enable Debugging on Flipper
![Debug-on](https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/a0ccdc48-6ccd-4023-9f6a-d8659309e25f)

On your Flipper, go to Settings, then System, then make sure "Debug" is set to ON.


## Debugging with gdb (from command prompt)
If you want to debug with GDB you can use fbt to launch the blackmagic probe:
```
fbt blackmagic
```

## Debugging with Visual Studio Code
### VS Code Prerequisites
You should have already setup your environment for Visual Studio Code by running the command:
```
fbt vscode_dist
```
You only need to run the command once.

### Edit launch.json file
I make a few tweaks to the launch.json file that is found in the ".vscode" folder.  In the inputs[] section I add the following BLACKMAGIC-menu entry (above the existing BLACKMAGIC entry that is there):
```
        {
            "id": "BLACKMAGIC-menu",
            "type": "pickString",
            "default": "tcp:192.168.4.1:2345",
            "description": "Blackmagic GDB server address",
            "options": [
                "tcp:192.168.4.1:2345",
                "\\\\.\\COM3",
                "/dev/cu.usbmodemblackmagic1"
            ]
        },
```
The advantage of the BLACKMAGIC-menu is you are able to debug quicker since you don't have to go through the auto-detect process.  To use the menu, change the line: ```"gdbTarget": "${input:BLACKMAGIC}",``` to ```"gdbTarget"gdbTarget": "${input:BLACKMAGIC-menu}",```.

**NOTE:** In the "BLACKMAGIC" section I also change the line ```"FBT_QUIET": 1``` to ```// "FBT_QUIET": 1``` or else for some reason my computer doesn't seem to attach to the debugger?  (Let me know if it fixes it for you too.)

### Launch the debugger
On the left side of Visual Studio you should have a Run and Debug icon (bug with an arrow) -- my key bindings this is CTRL+SHIFT+D.  In the attach dropdown choose "Attach FW (Blackmagic)".  Then click the green arrow (my key bindings this is F5) to start debugging.  If all goes well, the debugger should launch and you should be paused in the debugger (and the Flipper Zero should be frozen).  Also switch your View / Debug Console -- my key bindings this is CTRL+SHIFT+Y.

# Debug a furi_assert failure
Developers add ```furi_assert(_condition_);``` statements to help identify coding errors.  For example, a callback might do ```    furi_assert(context);``` to ensure that the context object is not null.  In debug builds, if the assertion is false then ```furi_crash(__FURI_ASSERT_MESSAGE_FLAG);``` will be invoked.  furi_assert is a #define so the code is not on the callstack, but the __furi_crash will be on the callstack (and the caller will be the code doing the assert).  In release builds, the furi_assert still evaluates the expression but the result is cast to a (void) -- it's not clear if the compiler optimizes away some of the checks?

## VSCode
To debug an application that is crashing with 'furi_assert', attach the debugger and then press the Continue button -- my key bindings this is F5.  The Flipper will be running and you should be able to reproduce the issue.  Once the assertion fails, the debugger should be at a breakpoint in the __furi_crash method.

The call stack window should show the method that called furi_assert.  Clicking on that method should show the code and you should be able to inspect variables.

## GDB
To debug an application that is crashing with 'furi_assert', attach the debugger and then type "c" (for 'continue' and press enter).  The Flipper will be running and you should be able to reproduce the issue.  Once the assertion fails, the debugger should be at a breakpoint in the __furi_crash method.

Type "bt" (for 'backtrace' and press enter).  You should then see all of the callstack.  Type "up" (for 'up to previous caller' and press enter).  Type "info locals" (to see the local variables and press enter).  Type "list" (to see the code and press enter).

## Logging

### MacOS

1. connect Flipper Zero to your Mac via USB
2. open a terminal window
3. type in `ls /dev/cu.usbmodemflip*`  
now your device with its unique name should show up `/dev/cu.usbmodemflip_UNIQUENAME`
4. connect to your device with `screen /dev/cu.usbmodemflip_UNIQUENAME`
5. now you should see the Flipper CLI welcome message
6. with `help` you get a list of commands you can use
7. use `log` to view the logs in real time, `Cltr+C` to get out of the logs
8. to end your session, hit `Cltr+A`, release and then `k`. Confirm with `y`  
(don't use `Cltr+C` to end the session, it will get you back to your terminal, but the screen session will still be open and you cannot use the connection anymore)
9. to see a log statement from your own FAP, use `FURI_LOG_D("my_app_name", "My first log statment, nice!");` in your code. (include `furi.h`)

### Windows

TODO