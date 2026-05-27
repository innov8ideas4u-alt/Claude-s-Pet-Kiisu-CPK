# Introduction
Most of the tutorials I have are about making applications, which can be compiled into a FAP file that you install on your firmware.  Some changes however, involve changing the code of the firmware itself -- for example the videos in [Flipper Zero - UX](https://www.youtube.com/playlist?list=PLM1cyTMe-PYJiK1cl3qGMSbd6Ssp3tOg4) playlist for customizing your Flipper's main menu.

# Fork the firmware
* The first step is to make sure you have a [github.com](https://github.com) account.
* The second step is to decide [which firmware](https://github.com/UberGuidoZ/Flipper/tree/main/Firmware_Options) you want to fork.  You can click the "Main" link on UberGuidoZ page to be redirected to the repository for that firmware.
* Next step is to fork the repository into your own GitHub.
  * Near the top of the page, you should see a "Fork" option with a dropdown arrow.  **Click** the drop-down arrow.
  * Click on "+ Create a new fork"
  * You should see "Owner" with your name filled out.
  * You should see "Repository name" with the name of the repository filled out.  You can change this name if you want.
  * If you are okay with latest dev changes, check the "copy the dev branch only" option.  If you need other branches, like release candidates, then uncheck the box.
  * Click the "Create Fork" button.

# Clone the repository
* Load your github.com account.
* Click on Repositories (for example, https://github.com/jamisonderek?tab=repositories)
* Choose the repository you just made.
* Click on the green "Code" button.
* Click on the clipboard icon, under Clone/HTTPS.
* Either: Clone the repository in VS Code
  * Open VSCode.
  * Ctrl+Shift+P
  * type: "Git: Clone (Recursive)"
  * paste the URL from your clipboard and click Enter
  * choose a destination 
* Or: Clone the repository in a command line.  From a command window that is in the parent directory where you want to clone...
  ``git clone --recursive`` _https-url-from-your-clipboard_

# Configure project for VSCode
* In VSCode, open the project you just created.
* Right click on fbt.cmd and choose "Open in Integrated Terminal"
* Type: ``./fbt vscode_dist``
* Once that completes, close Visual Studio Code & reopen it.

# Build the firmware
* In VSCode, CTRL+SHIFT+B
* Choose "[Debug] Build update bundle"
* Once that completes...

# Deploy firmware to Flipper Zero
* Connect your Flipper
* Be sure you close any apps that are connected to the Flipper (like serial port, https://lab.flipper.net/cli, qFlipper, etc.)
* CTRL+SHIFT+B
* Choose "[Debug] Flash (USB, with resources)"
* Another method is to just go to your ``.\dist\f7-D\f7-update-local`` folder and copy those files into a folder on the Flipper Zero (I usually drag-and-drop in qFlipper).  You can then DOWN arrow on the Flipper, RIGHT arrow until you are in 'Browser', DOWN arrow to choose the folder on your Flipper, click OK on the "Update" app, choose Run in app, and then RIGHT to install.

# Make your changes
* Make whatever changes you want (be sure you are in the correct branch if you unselected "copy dev branch only" when you created the fork).
* Follow the "Build the firmware" instructions
* Follow the "Deploy firmware to Flipper Zero" instructions

# Update your fork to have new fixes
* Load your github.com account.
* Click on Repositories (for example, https://github.com/jamisonderek?tab=repositories)
* Choose the repository you made.
* Click on the "Sync fork" button (it should be below the green "Code" button).
* Hopefully it says "This branch is out of date"
  * Click "Compare" if you want to understand the differences.
  * Or click "Update branch" and hopefully it will automatically merge.
* Follow the "Build the firmware" instructions
* Follow the "Deploy firmware to Flipper Zero" instructions

# Resolving conflicts
* If you made changes to files that were also changed, you may have to resolve the conflicts so that the computer knows what to do.  Often it is less confusing to store off your changes somewhere, accept their change, and then add back your changes.  It all depends on how many changes you had & what the conflicts are.