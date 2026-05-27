# Video Game Module

## Overview
This wiki page is about the Video Game Module (VGM) for the Flipper Zero.

The [official blog entry](https://blog.flipper.net/introducing-video-game-module-powered-by-raspberry-pi/) for the Video Game Module contains links to many helpful resources, such as technical specs, getting started guide and list of apps at launch.  You can buy the Video Game Module for Flipper Zero at the [official store](https://shop.flipperzero.one/products/video-game-module-for-flipper-zero).

Feel free to drop into my [Discord server](https://discord.com/invite/NsjCvqwPAd) for discussions.  I have a v0.1 FAP of **Air Labyrinth** game available for download & I have [submitted it](https://github.com/flipperdevices/flipper-application-catalog/pull/285) to the App Store as well. It is pre-installed on RogueMaster firmware in the `GPIO/VGM` folder.

<img width="592" alt="image" src="https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/589bb7f2-9a81-4754-afce-2343d67ab651">

My [YouTube channel](https://youtube.com/@MrDerekJamison) has videos on VGM, and I will continue to add more videos over the next couple of months.  Let me know the topics you would like me to cover.  

Here is the [YouTube video playlist](https://www.youtube.com/playlist?list=PLM1cyTMe-PYI_-cpOjYmmJY1_xx0rXchm) which links directly to the videos about the Video Game Module.

## Applications

- [Video Game Module Tool](https://lab.flipper.net/apps/video_game_module_tool) : Install firmware on your Video Game Module.
- [Air Arkanoid](https://lab.flipper.net/apps/air_arkanoid) : Tilt left/right to move.
- [Air Mouse](https://lab.flipper.net/apps/vgm_air_mouse) : Tilt left/right/up/down to manipulate your computer's mouse.
- [Air Labyrinth](https://github.com/flipperdevices/flipper-application-catalog/pull/285) : Tilt left/right/up/down to move within a maze.

## Custom firmware

You can build your own custom firmware, to control various aspects of the VGM.  

For example, you can change the HDMI output colors, change the bitmaps, add new "CLI" commands, etc.

### Prerequisite commands
I've only tried building the firmware on Kali Linux.  On my Windows computer, I use VirtualBox to run Kali.  The following commands will install all of the tools needed to build the firmware.

- `sudo apt update`
- `sudo apt upgrade -y`
- `code`
- `cmake`
- `sudo apt install protobuf-compiler`
- `sudo apt install qflipper`
- `sudo apt install libstdc++-arm-none-eabi-newlib`

### Building firmware
- `mkdir repo`
- `cd repo`
- `git clone --recursive https://github.com/flipperdevices/video-game-module.git vgm`
- `cd vgm`
- `git switch release`  (or `git switch main`)
- `git pull`
- `cd build`
- `cmake ..`
- `make`

The source code is in the `./repo/vgm/app` folder.  After running the `make` command the custom firmware will be available at `./repo/vgm/build/app/vgm-fw-0.1.0.u2f`.  Use the qFlipper application to copy the file to your Flipper Zero SD Card.  I copy it to a folder I created named `vgm`, but you can use any folder you prefer.

### Deploying firmware
- Make sure the Video Game Module is attached to your Flipper Zero.
- Run the `Video Game Module Tool` program located under `Apps`/`Tools` (NOTE: some firmware use `Apps`/`GPIO`/`VGM` folder instead.)
- If you want the official firmware, select `Install Official Firmware`.  Otherwise select `Install Firmware from File` and then choose the u2f file that you copied to your Flipper Zero.

### Custom colors
- The easiest way is to edit [COLOR_BG](https://github.com/flipperdevices/video-game-module/blob/fb4fb20e2fa6dbfcbc5ac19a9b5076429af2b0fe/app/frame.c#L16) in app/frame.c   This will change to use the background color you specify.  The color is RGB565 format (5-bits Red, 6-bits Green, 5-bits Blue).  [https://rgbcolorpicker.com/565](https://rgbcolorpicker.com/565) is a color picker that can help figure out the hex value.
- You can also edit the [COLOR_FG](https://github.com/flipperdevices/video-game-module/blob/fb4fb20e2fa6dbfcbc5ac19a9b5076429af2b0fe/app/frame.c#L17) which is the color of writing.
- If you want to customize the LEFT BAND, edit [framebuf[i] = color_bg;](https://github.com/flipperdevices/video-game-module/blob/fb4fb20e2fa6dbfcbc5ac19a9b5076429af2b0fe/app/frame.c#L119) replacing color_bg with your HEX value, like `framebuf[i] = 0x8086;`.
- If you want to customize the RIGHT BAND, edit [framebuf[FRAME_WIDTH - i] = color_bg;](https://github.com/flipperdevices/video-game-module/blob/fb4fb20e2fa6dbfcbc5ac19a9b5076429af2b0fe/app/frame.c#L120) replacing color_bg with your HEX value, like `framebuf[FRAME_WIDTH - i] = 0x8086;`.
- If you want to customize the TOP/BOTTOM BAND, add [else statement](https://github.com/flipperdevices/video-game-module/blob/fb4fb20e2fa6dbfcbc5ac19a9b5076429af2b0fe/app/frame.c#L77)
```c
        if(frame_y >= 0 && frame_y < 64) {
            if(is_pixel_set(&current.frame, frame_x, frame_y)) {
                color = color_fg;
            }
        } else if (frame_y<0) {
            // TOP BAND
            color = 0x8086;
        } else {
            // BOTTOM BAND
            color = 0xFF00;
        }
``` 