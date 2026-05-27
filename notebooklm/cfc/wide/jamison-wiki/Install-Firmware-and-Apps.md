# Overview
This page is mostly about how you can build & deploy applications to your Flipper Zero.  In this document, we will use the following steps:
- Install prerequisites 
- Clone firmware and deploy to Flipper
- Find the app
- Copy the app into our firmware's **applications_user** folder
- Build and deploy the app

About 80% of the applications work across all of the different firmware.  Some minor (or major) changes may be needed for the application to work on a different firmware than the one it was designed for.  If you encounter errors building the application for your firmware, you can [ask for help](https://discord.com/invite/NsjCvqwPAd) in my Discord server.

Flipper applications are `FAP` files, which stands for `Flipper Application Package`. When a FAP file is created, it has a required API version.  This version should match the firmware version you are running on your Flipper (older or newer version may not work).  You can read more about FAP files in the [official documentation](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/documentation/AppsOnSDCard.md).

#### CFW
If you just want to install custom firmware (and not custom applications), a web Chrome based installer is the easiest method:
  - [Official](https://lab.flipper.net/) choose "Install"
  - [RogueMaster](https://github.com/RogueMaster/flipperzero-firmware-wPlugins/releases) choose "WEB INSTALLER"
  - [Unleashed](https://github.com/DarkFlippers/unleashed-firmware/releases) choose "Version with Extra apps - Install via Web Updater"
  - [Momentum](https://momentum-fw.dev/update) choose "Install"
  - [Xtreme - no longer under development](https://flipper-xtre.me/update/) choose "Flash"

You can also install applications from the Official apps hub. Open a Chrome based browser, connect your Flipper to your computer and load [https://lab.flipper.net/apps](https://lab.flipper.net/apps).  Click the `Install` button to install an app.  If you are on custom firmware, the application may not work (but following the directions below and building it yourself may work).


# Techniques
There are many techniques to accomplish the various tasks.  At the beginning of this document we will focus on using a command-line interface, but you can also accomplish these tasks using Visual Studio Code (which allows you to pick commands to run from a nice user interface, instead of memorizing command-line parameters).  There are also multiple tools, such as [uFBT](https://github.com/flipperdevices/flipperzero-ufbt) and [FBT](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/documentation/fbt.md).  At the beginning of this document, we will use the **FBT** instead of **uFBT** tool.

# Prerequisites (Required apps)
- **Required**: We use the Git command (and the Git tools with VS Code).  This is pre-installed in Kali.  If it is not already installed for your OS, you can download from [Git tools download](https://git-scm.com/downloads)
- _Required for uFBT only_: Python 3.8 or newer is needed for installing uFBT. You can install from [Python download](https://www.python.org/downloads/)
- _Optional_: Visual Studio Code is nice editor.  You can install from [VS Code download](https://code.visualstudio.com/Download)

# Clone & Deploy firmware
We need the SDK API version to match what we are running on our Flipper Zero. The easiest way to accomplish this is to recursively clone the firmware we are running on the Flipper.  Many people choose to run a custom firmware instead of the official firmware.  This will also update our Flipper firmware, so you can follow this step to switch to a different firmware.

## Step 1: Open a command terminal.  
  - In Kali/Ubuntu, this is called `Terminal Emulator` 
  - In Windows, this is called `Command Prompt`.
## Step 2: Change into whatever directory you want to put the files.
  - In Kali/Ubuntu:
    - First time: `mkdir repo` to make a **repo** folder. 
    - Every time: `cd repo`
  - In Windows:
    - First time: `mkdir c:\repo` to make a **repo** folder.
    - Every time: `cd c:\repo`
## Step 3: Recursively clone the firmware you want to use.

  Be sure that you installed `git tools` listed in the [prerequisites](#prerequisites-required-apps).  Adding a `--jobs 8` switch may make it run faster.
  - Official firmware:
    - `git clone --recursive https://github.com/flipperdevices/flipperzero-firmware.git`
    - `cd flipperzero-firmware`
  - Momentum firmware:
    - `git clone --recursive https://github.com/Next-Flip/Momentum-Firmware momentum-firmware`
    - `cd momentum`
  - RogueMaster firmware:
    - `git clone --recursive https://github.com/RogueMaster/flipperzero-firmware-wPlugins.git roguemaster-firmware`
    - `cd roguemaster-firmware`
  - Unleashed firmware:
    - `git clone --recursive https://github.com/DarkFlippers/unleashed-firmware.git`
    - `cd unleashed-firmware`
  - Xtreme firmware: (no longer under development)
    - `git clone --recursive https://github.com/Flipper-XFW/Xtreme-Firmware.git xtreme-firmware`
    - `cd xtreme-firmware`
  - SquachWare firmware: (no longer under development)
    - `git clone --recursive https://github.com/skizzophrenic/SquachWare-CFW.git squach-firmware`
    - `cd squach-firmware`
## Step 4: Choose the branch
  - Official:
    - Release branch: (Stable release)
      - `git checkout release`
    - Release candidate branch: (Release being tested)
      - `git checkout release-candidate`
    - Dev branch: (Latest version, may be unstable)
      - `git checkout dev`
  - Momentum
    - Dev branch: (Latest, may be unstable)
      - `git checkout dev`
    - Release: (see tags and choose highest version)
  - RogueMaster: 420 (Latest version)
    - `git checkout 420`
  - Unleashed:
    - Release branch: (Stable release)
      - `git checkout release`
    - Dev branch: (Latest, may be unstable)
      - `git checkout dev`
  - Xtreme
    - Main branch: (Stable release)
      - `git checkout main`
    - Dev branch: (Latest, may be unstable)
      - `git checkout dev`
## Step 5 (Optional): Install VS Code support

  The following command will update the `.vscode` folder so that it has all of the required files for VS Code.  If you have VS Code installed on your computer, I recommend doing this step, so that later if you choose to use VS Code you will already have the Flipper support files.
  - Kali/Ubuntu: `./fbt vscode_dist`
  - Windows: `fbt vscode_dist`

## Step 6: Backup your files

  It's always possible that you could lose data, so be sure to backup any files from the SD card that you care about (like captured subghz files, nfc files, etc.)  Some people do `Settings/Storage/Unmount SD Card` before ejecting the SD card, then they put it computer to copy the files.  Once they are done, they put the SD card back into the Flipper Zero.  NOTE: You can also use the mobile app to backup files or the qFlipper app to backup files, you can install from this Flipper Zero [download page](https://flipperzero.one/downloads).

## Step 7: Build and deploy firmware

Make sure your Flipper Zero is not running any applications (press Back putting until you are at the desktop).  Make sure your Flipper Zero is connected to your computer.  Make sure qFlipper and the CLI is not connected.

- Kali/Ubuntu: `./fbt COMPACT=1 DEBUG=0 FORCE=1 flash_usb_full`
- Windows: `fbt COMPACT=1 DEBUG=0 FORCE=1 flash_usb_full`

Congratulations -- your Flipper is now running new firmware that you built!

# Installing Applications

Some people have pre-built FAP files that you can install on your Flipper.  The problem is often the SDK API version of the FAP does not match what you are running so the application will not work correctly.  I recommend instead that you download the source code and build your own FAP files, which you know will match the firmware on your Flipper Zero.

## Step 1: Find the app

Many people use flipc.org but in Jan/Feb of 2024 it seems to be `Under maintenance`.  We need to use a different way to discover apps.  Perhaps Google search for Flipper applications, or maybe someone posted a link to a project on a social network.  I find that RogueMaster firmware has a large majority of the applications, so I use them as a resource (even when I'm running a different firmware).  RogueMaster [Readme](https://github.com/RogueMaster/flipperzero-firmware-wPlugins/blob/420/ReadMe.md#games) file has links for many of the Games and Plugins.  Those links will take you to the projects, but you may need to hunt around until you find the actual project.  Xtreme firmware also has many applications, but they typically have fewer applications than RogueMaster.  

The project folder you are looking for will have a text file named `application.fam`. If you look in that file, you will see a `name=` entry with the name of the application and a `fap_category=` with the name of the category where the application will be installed.

About 80% of the applications will run on any firmware, but it's possible that some applications will call custom APIs (or newer serial APIs) that are only available on one or more custom firmware.  Some applications are not getting updated by their owner, but often RogueMaster will keep updating the application so that it still works.  For example, the `appid` entry in the `application.fam` file must be lowercase letters, numbers and underscores (and RogueMaster will fix the old application.fam file so that it works).  For this reason, I recommend looking at [RogueMaster/applications/external](https://github.com/RogueMaster/flipperzero-firmware-wPlugins/tree/420/applications/external) since these files have the modifications.  Some changes may be optimized for RogueMaster and not run on other firmwrae.  If the application doesn't work, I see if it is [available in Xtreme](https://github.com/Flipper-XFW/Xtreme-Apps) and try that version with my firmware.

In this tutorial, we will use the **Flipper Zero Caesar Cipher application**, but you can use __any application__ you choose:

- Google search for `Caesar cipher flipper zero` returned [https://github.com/panki27/caesar-cipher](https://github.com/panki27/caesar-cipher) as top hit.
- We can find the app at [https://lab.flipper.net/apps](https://lab.flipper.net/apps) and it lists the Repository as [https://github.com/xMasterX/all-the-plugins/tree/dev/apps_source_code/caesarcipher](https://github.com/xMasterX/all-the-plugins/tree/dev/apps_source_code/caesarcipher)
- RogueMaster README lists it as [Ceasar Cipher v1.1 (By panki27)](https://github.com/panki27/caesar-cipher)
- RogueMaster has a copy at [https://github.com/RogueMaster/flipperzero-firmware-wPlugins/tree/420/applications/external/caesarcipher](https://github.com/RogueMaster/flipperzero-firmware-wPlugins/tree/420/applications/external/caesarcipher)
- Xtreme has a copy at [https://github.com/Flipper-XFW/Xtreme-Apps/tree/dev/caesarcipher](https://github.com/Flipper-XFW/Xtreme-Apps/tree/dev/caesarcipher)

## Step 2: Copy the app

**NOTE**: If your firmware already has a copy of the application you want in applications\external, it is highly recommended you use that version instead of creating a duplicate project.  In that case, it is already installed on your Flipper & you are done.  The application.fam file will detail where to find it (see the next step for directions on how to read the application.fam file).

- Copy the project's main folder (the folder you found in the previous step that contains the `application.fam` file) into a folder directly under the `applications_user` folder in your firmware.  You can name this folder whatever you want, in our case we will use `caesarcipher` as the name.  You will be using the folder name in the next step.

In this case you should now have the following files in your firmware:
- /flipperzero-firmware/applications_user/caesarcipher/application.fam
- /flipperzero-firmware/applications_user/caesarcipher/caesar_cipher.c
- /flipperzero-firmware/applications_user/caesarcipher/caesar_cipher_icon.png
- /flipperzero-firmware/applications_user/caesarcipher/img/1.png
- /flipperzero-firmware/applications_user/caesarcipher/img/2.png
- /flipperzero-firmware/applications_user/caesarcipher/LICENSE
- /flipperzero-firmware/applications_user/caesarcipher/README.md

## Step 3: Deploy the app

Make sure your Flipper Zero is not running any applications (press Back putting until you are at the desktop).  Make sure your Flipper Zero is connected to your computer.  Make sure qFlipper and the CLI is not connected.

Your command terminal should be in the main firmware folder (the folder where the `fbt` file is).  In this next step we deploy and launch the application at the specified path.  In this example, `applications_user/caesarcipher` is where our application.fam file is located.  If you put your project in a different folder under applications_user, edit the command as needed.

- Kali/Ubuntu: `./fbt COMPACT=1 DEBUG=0 launch APPSRC=applications_user/caesarcipher`
- Windows: `fbt COMPACT=1 DEBUG=0 launch APPSRC=applications_user/caesarcipher`

Congratulations -- your Flipper should now be running the application!  If you look at the `application.fam` file, you will see the `fap_category="Tools"` so it was installed on your Flipper under `Apps`, `Tools`.  The `name="Caesar Cipher"` so the displayed name is `Caesar Cipher`.

## Step 4: Debugging deployment issues

If Step 3 failed, there are a few different reasons that are possible.

### Failed to find 

```c
[ERROR] Failed to find connected Flipper
[ERROR] Failed to guess which port to use
```

This error typically happens because the Flipper Zero is not connected, or qFlipper or a serial monitor is running.  Close qFlipper, close any browsers that are communicating with Flipper, close any CLI that are communicating with Flipper.  Try the command again.

### Loader is locked

`[ERROR] Unexpected response: Loader is locked, please close the "Sub-GHz" first`

This error typically happens because the Flipper Zero is running another application.  Be sure to press back button to get at the Desktop.  You can also try holding Left+Back to reboot the Flipper to ensure nothing is running.  Try the command again.

### Invalid appid

`fbt: warning: Failed parsing manifest 'application.fam' : Invalid appid 'Caesar_Cipher'. Must match regex 're.compile('^[a-z0-9_]+$')'`

This error indicates the `appid=` in the `application.fam` file contains invalid characters (older versions of Flipper apps were allowed other characters like uppercase).  Edit the appid in the application.fam file to be all lowercase letters, numbers and underscores (you can choose any unique name) and then try the fbt command again.

### Failed to resolve application

`scons: *** Failed to resolve application for given APPSRC=applications_user/democipher`

First, make sure you don't have any warnings above, like Invalid appid.  This error may indicate that the path you specified does not have an application.fam file (or it is invalid).  Be sure that you spelled the path correctly and that you copied the folder containing the application.fam file.

### Multiple definition / first defined here

`bin/ld: build/f7-firmware-C/.extapps/caesar_cipher/caesar_cipher.o: in function 'caesar_cipher_app':
/home/kali/repo/flipperzero-firmware/applications_user/caesarcipher/caesar_cipher.c:101: multiple definition of 'caesar_cipher_app'; build/f7-firmware-C/.extapps/caesar_cipher/caesarcipher/caesar_cipher.o:/home/kali/repo/flipperzero-firmware/applications_user/caesarcipher/caesarcipher/caesar_cipher.c:101: first defined here`

If you get an error similar to the above, it likely means you have two copied of the application.  

Find the path in front of the line number, like:
- `/home/kali/repo/flipperzero-firmware/applications_user/caesarcipher/caesar_cipher.c:101`

And then the other path:
- `/home/kali/repo/flipperzero-firmware/applications_user/caesarcipher/caesarcipher/caesar_cipher.c:101`

You can see these two paths are different, in this case we accidentally have a `/applications_user/caesarcipher/caesarcipher` that is a duplicate folder.  Probably deleting the folder under `applications_user` and copying it from the original source is probably be best option to fix the issue.  It's also possible that the duplicate was because the application was already present in a folder under `/applications/external`.

### No such file or directory

`applications_user/clibridge/cli_control.c:6:10: fatal error: furi/core/thread_i.h: No such file or directory`

An error with `No such file or directory` likely indicates that the firmware does not have the necessary files.  Make sure you copied all subdirectories of the project.  If you have, then it's possible that it's a file only available in newer/older firmware or in some custom firmware.  You can try to find a different copy of the files, and perhaps they will work with your firmware.

### Implicit declaration of function

`applications_user/ble_spam/scenes/config.c:44:5: error: implicit declaration of function 'variable_item_list_set_header'; did you mean 'variable_item_list_get_view'? [-Werror=implicit-function-declaration]`

An error with `implicit declaration of function` likely indicates that the firmware does not have the necessary code.  Make sure you copied all subdirectories of the project.  If you have, then it's possible that it's a file only available in newer/older firmware or in some custom firmware. You can try to find a different copy of the files, and perhaps they will work with your firmware.

### Undeclared here (not in a function)

`applications_user/bad_kb/helpers/ducky_script.h:106:25: error: 'FURI_HAL_BT_ADV_NAME_LENGTH' undeclared here (not in a function); did you mean 'FURI_HAL_VERSION_NAME_LENGTH'?`

An error with `undeclared here` likely indicates that the firmware does not have the necessary code.  Make sure you copied all subdirectories of the project.  If you have, then it's possible that it's a file only available in newer/older firmware or in some custom firmware. You can try to find a different copy of the files, and perhaps they will work with your firmware.

### Wrong Entry_point

`arm-none-eabi/bin/ld: --gc-sections requires a defined symbol root specified by -e or -u`

This error indicates that the `entry_point=` specified in the application.fam file does not match the name of a method in any of your `*.c` files.  Make sure your .c files are also in the same folder as your application.fam file and that the code matches what is specified in the application.fam file.

# Advanced Topics

## Refresh firmware

If it has been a while since you last did a [Clone and Deploy firmware](#clone--deploy-firmware), you can grab the latest version of the firmware.  

### Step 1: Open a command terminal.  

  - In Kali/Ubuntu, this is called `Terminal Emulator` 
  - In Windows, this is called `Command Prompt`.

### Step 2: Change into whatever directory you want to put the files (this is the folder you created before).

  - In Kali/Ubuntu:
    - `cd repo`
  - In Windows:
    - `cd c:\repo`

### Step 3: Change into your firmware directory

    - Official: `cd flipperzero-firmware`
    - RogueMaster: `cd roguemaster-firmware`
    - Unleashed: `cd unleashed-firmware`
    - Xtreme: `cd xtreme-firmware`

### Step 4: Pull the latest

  - `git pull`

### Step 5: Choose the branch

  - Official:
    - Release branch: (Stable release)
      - `git checkout release`
    - Release candidate branch: (Release being tested)
      - `git checkout release-candidate`
    - Dev branch: (Latest version, may be unstable)
      - `git checkout dev`
  - RogueMaster: 420 (Latest version)
    - `git checkout 420`
  - Unleashed:
    - Release branch: (Stable release)
      - `git checkout release`
    - Dev branch: (Latest, may be unstable)
      - `git checkout dev`
  - Xtreme
    - Main branch: (Stable release)
      - `git checkout main`
    - Dev branch: (Latest, may be unstable)
      - `git checkout dev`

### Step 6: Backup your files

  It's always possible that you could lose data, so be sure to backup any files from the SD card that you care about (like captured subghz files, nfc files, etc.)  Some people do `Settings/Storage/Unmount SD Card` before ejecting the SD card, then they put it computer to copy the files.  Once they are done, they put the SD card back into the Flipper Zero.  NOTE: You can also use the mobile app to backup files or the qFlipper app to backup files, you can install from this Flipper Zero [download page](https://flipperzero.one/downloads).

### Step 7: Build and deploy firmware

Make sure your Flipper Zero is not running any applications (press Back putting until you are at the desktop).  Make sure your Flipper Zero is connected to your computer.  Make sure qFlipper and the CLI is not connected.

- Kali/Ubuntu: `./fbt COMPACT=1 DEBUG=0 FORCE=1 flash_usb_full`
- Windows: `fbt COMPACT=1 DEBUG=0 FORCE=1 flash_usb_full`

Congratulations -- your Flipper is now running new firmware that you built!

## VS Code

You can use Visual Studio Code for Flipper Zero development.

### Cloning firmware

You can use Visual Studio Code to clone the github repo, instead of the command-line.

- Step 1: Make sure you installed Git Tools, as described in [Prerequisites](#prerequisites-required-apps).
- Step 2: In VSCode press Ctrl+Shift+P to bring up the command palette.
- Step 3: Type the following `Git: Clone (Recursive)` then press enter.  Be sure it is *recursive*.
- Step 4: Paste in the URL of the firmware that you want to clone, for example Xtreme is `https://github.com/Flipper-XFW/Xtreme-Firmware.git`.
- Step 5: Choose a location to clone the files to.

### Install VSCode tools

- Step 1: In VSCode open your firmware project.
- Step 2: If asked if you trust the authors, choose Yes.
- Step 3: Right click on `fbt` and choose `Open in Integrated Terminal`.  A new command terminal should appear at the bottom right of the screen.
- Step 4: Type `./fbt vscode_dist` in the Integrated Terminal and press enter.
- Step 5: Close Visual Studio Code.

### Setup Firmware

Be sure you already ran the `./fbt vscode_dist` command after you cloned the firmware.  Reopen the firmware folder using Visual Studio Code.
- Step 1: If prompted if you would like to install the recommended extensions, choose `Install`.
- Step 2: Be sure the extensions `CMAKE` and `CMAKE TOOLS` are disabled for the workspace, otherwise Ctrl+Shift+B may not show the build options (and instead show things about `cmake`)!
- Step 3: Click on the `Extensions` icon on the left side of the screen.
- Step 4: Type `cmake` in the search box.
- Step 5: Click on the `CMAKE` extension.
- Step 6: If it has an `Install` button you are done.
- Step 7: If it has a `Disable` button, click on the `Disable` button.

### Choose branch

- Step 1: Ctrl+Shift+P
- Step 2: Type: `Git: Checkout to...`
- Step 3: Choose the `firmware`
- Step 4: Choose the `branch`, such as `/origin/dev`

A faster way to change branches, is to click the branch name in the bottom left of the VS Code window.

### Synchronize changes

If it has been a while, this will get you the latest version of the code.

- Step 1: Ctrl+Shift+P
- Step 2: Type: `Git: Sync`
- Step 3: Choose the `firmware`

### Build and deploy firmware

Make sure your Flipper Zero is not running any applications (press Back putting until you are at the desktop).  Make sure your Flipper Zero is connected to your computer.  Make sure qFlipper and the CLI is not connected.

- Step 1: Connect your Flipper to the computer.
- Step 2: Press `Ctrl+Shift+B` to bring up the build options.
- Step 3: Choose `[Release] Flash (USB, with resources)`.
- Step 4: The firmware and FAPs should get built.
- Step 5: The firmware should get installed on the Flipper Zero.

### Copy any applications into applications_user folder

You can copy any programs you want to build into the applications_user folder but be sure they are not already part of your firmware (for example, many applications may already be in `applications/external`.)

- Step 1: If the source is another Github repo, Ctrl+Shift+P, type `Git: Clone`, enter the URL of the repo, choose a folder to clone the project to.
- Step 2: Copy the project (the folder containing the application.fam folder and it's subfolders) into your applications_user folder.

NOTE: Instead of copy-and-paste files, you may want to make a junction; so that edits you make are also reflected in the project you pulled from.  This is only needed if you plan on contributing your changes back to the original application, or want to keep your changes under source control.  You can do an internet search (or ask chatgpt) how to make a junction for your operating system.

  - In Windows from Admin command prompt in the applications_user folder I run a command similar to `mklink /D gpio_blink_pwm c:\repo\flipper-zero-tutorial\gpio\gpio_blink_pwm`

### Build and deploy an application

- Step 1: Connect your Flipper to the computer.
- Step 2: In VSCode, make sure the Explorer window is open (`View`/`Explorer`).
- Step 3: Open the file `./applications_user/caesarcipher/caesar_cipher.c` (or whichever application you want to build)
- Step 4: Press `Ctrl+Shift+B` to bring up the build options.
- Step 5: Choose `[Release] Launch App on Flipper`.
- Step 6: The application should get built, the FAP installed on the Flipper Zero, and then the application should get launched.