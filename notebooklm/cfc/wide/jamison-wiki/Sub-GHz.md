<img src="https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/8dd7ea0e-b75c-4f2f-9f93-a162813078c2" height="200px"/>

# Table of Contents

Introduction:
* [Introduction](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#introduction) to Sub-GHz radio & YouTube link.
* [Key concepts & terms](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#sub-ghz-concepts), like frequency, modulation, deviation, etc.

Flipper Zero Applications:
* ["Sub-GHz" application](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#flipper-sub-ghz-app) for the Flipper Zero.
* **COMING SOON**: CLI application for Flipper Zero (Phone/PC uses Flipper Zero).

Basic topics:
* [Distances](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#distance) for send/receive on the Flipper Zero.
* [Modulation](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#modulations) learn the differences between "AM650" and "FM238".
* [Static and Dynamic codes](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#static-and-dynamic-codes).  "Rolling code"

Advanced topics:
* [Create custom settings](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#custom-settings) to tune your Flipper Zero Sub-GHz radio!
* [File formats](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#sub-file-format) to understand how to read the .SUB files supported by the Flipper Zero.
* [Protocols](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#protocols) to understand how signals are decoded/encoded.

Programming:
* [Radios](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#radios)
* [Send Asynchronous](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#send-asynchronous-transfer) like .SUB file
* [Send Synchronous](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#send-synchronous-transfer) like Sub-GHz CLI Chat app

# Introduction
My [YouTube playlist on SubGHz](https://www.youtube.com/playlist?list=PLM1cyTMe-PYKeMm52J8Y_4SKqdm6Utl__) has a variety of videos about Sub-GHz radio.

Flipper Zero can receive and transmit radio frequencies in the range of 300-348, 387-464, 779-928 MHz with its built-in CC1101 module.  The frequencies you are allowed to transmit on varies by region.  Most firmware allow connecting an [external CC1101 module](https://github.com/quen0n/flipperzero-ext-cc1101), which can end up adding extended range (but typically cannot handle higher data rates).  Sub-GHz feature can read, save, and emulate remote controls that operate in the 300-928MHz range (below 1000MHz or 1GHz). These controls are used for interaction with gates, barriers, radio locks, remote control switches, wireless doorbells, smart lights, and more. This feature will not work for remote controls that use Infrared or for remote controls that use Bluetooth, BLE, 2.4GHz, etc.  Flipper Zero can help you to learn if your security is compromised and susceptible to replay attacks.

Flipper Zero official firmware will not Save/Replay a rolling code.  It does support [adding a remote](https://docs.flipperzero.one/sub-ghz/add-new-remote) which you may be able to pair to your existing system.  When you do this, the SUB file will be updated each time you send a signal using the Flipper Zero.  If you edit the SUB file to match another remote you own, you risk desyncing your remote.

Most devices are registered with the FCC, so it may be helpful to go to [fccid.io](https://fccid.io) and search for the device FCC id to learn additional information about the device you are trying to test.  Often times this will list the frequency, modulation, internal pictures, etc. of the remote or receiver that you are testing.

# Read and capture signal
To capture a signal, you can run `Sub-GHz` then `Frequency analyzer`.  Then press a button on the remote.  Hopefully the frequency will be displayed.
I think people guess the modulation, at least that is what I do.  Lots of things use on-off keying (OOK), so AM650 and AM270 works for them.  The different numbers just reduce the interference and change the sensitivity.  When sending the signal back, you are just using AM (or really OOK).  Some things use 2 frequency shift keying (2FSK), so we use FM238 and FM476 to try to pick those up.  The number is basically how far apart the two tones are from each other, 2.38kHz or 47.607kHz.  Signals could have different deviations (like Honda is 15.869kHz and many restaurant pagers are 5.157kHz) so it's possible you would have to make custom setting to decode what you want.  Also, the center frequency you need might be slightly different than what is shown, so you may need to add a custom frequency to read it.  Reading signals is typically more forgiving than sending.

If using the frequency analyzer the -T and +T indicates you are running some custom firmware.  🙂  It changes the RSSI threshold needed for the signal to be considered valid.  Pressing left/right you will see a little cursor move at the bottom of the screen to indicate the sensitivity.

Since you are running custom firmware, you can use arrow down to select one of the detected frequencies and long press on OK to automatically run the Sub-GHz read feature!  You still may need to adjust the modulation, but the frequency should get automatically selected for you.  If you don't have custom firmware, use `Sub-GHz` then `Read` then left arrow to configure the frequency and modulation.


# Sub-GHz concepts
## Frequency
Different devices broadcast their signal on different frequencies.  Similar to how you may listen to 101.5MHz FM on the radio for one station and 102.3MHz FM for a different station.  The frequency that you set in the Flipper Zero is the carrier frequency.  The lowest supported frequency is 300MHz and the highest is 928MHz.  The Sub-GHz application uses the CC1101 radio module where it is tuned to a specific frequency and modulation.  This is different than an SDR (software defined radio) where you are able to pick up a range of frequency spectrum at the same time (the Flipper can quickly hop between a small set of frequencies or range of spectrum, but it's typically milliseconds per frequency before the change).  Many devices in the US operate at a frequency of 433.92 MHz.

Most devices you find in the United States will be FCC certified and will display the FCC identifier on the device.  You can go to [fccid.io](https://fccid.io) to lookup the device and typically will find the frequency information.  The Flipper Zero also has a [Frequency Analyzer](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#frequency-analyzer---subghz) that can help identify the frequency.

## TX/RX
TX stands for transmitting a signal.  The Flipper Zero needs to be updated with latest database so that it knows what region you are in and then it will enable transmit for frequencies that are valid in your region.

RX stands for receiving a signal.  The Flipper Zero is able to receive signals on a variety of frequencies.  There are some default frequencies which it can receive on, but you can [modify](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Sub-GHz#custom-settings) your configuration to enable more frequencies if needed.


## Hopping
Hopping is the act of bouncing between a small set of frequencies looking for a signal instead of just listening to one frequency.  The larger the list, the more chance there is that you miss part of a signal while listening on a different frequency.

## Modulation
The CC1101 supports OOK, ASK, 2FSK, GFSK, 4FSK & MSK.  The Flipper Zero Sub-GHz application uses the CC1101 in async mode which only OOK, ASK, 2FSK and GFSK.  OOK and ASK are called "AM" where the amplitude of the carrier frequency is altered.  OOK (On-Off-Keying) the signal is either present or not. ASK (Amplitude Shift Keying) the signal is either low amplitude or large amplitude.  2FSK and GFSK are called "FM" where the signal is either lower than the carrier frequency or higher than the carrier frequency.  In GFSK, instead of the signal instantly jumping from one frequency to another, it quickly slides over to the other frequency.

The video [Jeeves teaches RF modulation](https://youtu.be/tzLmMl9HlTY) explains all of the modulations in detail.

NOTE: In the Flipper Zero the "Modulation" setting is actually picking a CC1101 preset configuration, which includes attributes like modulation, deviation, bandwidth, data rate, ASK decision boundary, AGC settings, etc. 

## Deviation
For FM signals, like 2FSK, the signal is not sent on the carrier frequency, but instead is some distance above/below that frequency.  For 2FSK, this distance is the deviation.  Having the proper deviation is almost as important as getting the correct frequency for an FM device, especially when trying to retransmit the signal (as the receiver may be finely tuned to the two frequencies it expects the transmitter to use).  

NOTE: For other modulations used by the CC1101, like 4FSK, the signal may be +-1/3 of the deviation as well.

## Bandwidth
Bandwidth concept in Sub-GHz refers to receiving (RX) a signal.  This applies a filter on the signal that the CC1101 can receive.  For example, a 650KHz bandwidth will have a range of 650KHz (650KHz/2 = 325KHz), where it will only pick up signals +- 325KHz of the carrier frequency.  For AM, all signals within the bandwidth will be considered as part of the OOK/ASK -- a wider range can help if you are unsure of the frequency (but it also means other devices have a better chance of causing interference).  For FM you need to make sure the bandwidth is large enough so that the frequencies on the deviation are in range.

## Data rate
The Flipper Zero Sub-GHz communicates with the CC1101 using asynchronous serial mode.  In this mode, a GPIO pin is used to represent the current state of the received signal.  This GPIO pin is updated at 8x the configured data rate.  For example, if your data rate is 4000 then the data will be updated 32,000 times a second or every 31.25 microseconds.  The higher the data rate, the more accurate the Flipper Zero will time the length of the pulses.  Internal CC1101 seems to be find running at a data rate of 115K (which is within 2 microsecond accuracy) however external CC1101 have been reported to only support rates around 15-20K.  When trying to clone a remote with short pulses, you may need to use higher data rates, so your pulses are properly timed.

## ASK/OOK decision boundary
The CC1101 supports 4 dB, 8 dB, 12 dB and 16 dB decision boundary.  This boundary is the strength of the signal relative to the off signal, for the signal to be considered the on signal.  A bigger dB number indicates that the signal needs to be larger to be considered part of the on signal, this allow for more noise in the signal but also requires you be closer to the transmitter.  Typically, 8 dB is a good compromise, which is what "AM650" on the Flipper Zero uses.

## RSSI
The RSSI value is an estimate of the signal power level.  The rate at which the RSSI value is updated is based on the bandwidth and the filter length.  You can use RSSI to help the Flipper Zero only start recording data when the signal is at least a certain average strength.  This can be helpful if there are other devices far away broadcasting on the same frequency range as the device you are trying to record.

RSSI Threshold of "-----" will result in any signal being considered valid. A value of "-85" will still pick up far away signals, while a value of "-65" will only pick up closer signals.  You will see the dotted line (floor) increase in the Read RAW screen as the value approaches -40 (at which point only really close signals will get detected). Typically the remote you are recording is nearby and you want to ignore interference from other devices that may be transmitting farther away, I find `-65` or `-60` to be a reasonable value when the remote is in the same room as the Flipper Zero (a few meters away at 433MHz using the internal antenna).  If you want to capture Walkie-talkie audio to play it back, then I threshold of `-----` is helpful, even though there may be some interference from other devices.

## AGC
The CC1101 supports many settings for automatic gain control (AGC).  The primary registers used are [AGCCTRL2](https://www.ti.com/lit/ds/symlink/cc1101.pdf?#page=85), AGCCTRL1 and AGCCTRL0.  These values impact RSSI, Carrier Sense and other aspects.  

# Flipper Sub-GHz app
## Region Information - SubGHz
Official firmware has a "Region Information" menu option.  This will display your region (like "US") and the transmit frequency bands that are supported.  See the list of [frequencies](https://docs.flipperzero.one/sub-ghz/frequencies) based on your region.  Your flipper can still do receive in frequencies outside of this list, for example, in the US one of the receive frequencies is 868.35MHz (even though you can't transmit).

If you try to transmit on an unsupported frequency, you will get the "Transmission is blocked" error message.

## Frequency Analyzer - SubGHz
The Frequency Analyzer is helpful to determine what frequency a device is broadcasting on.  If you press the right button on the Flipper Zero you can then use the OK button to toggle how to sort the information.  When looking at this extended view, there is a box showing the max RSSI for the value (if it exceeds a certain limit) each pixel represents 3dB (in groups of 4 pixels or 12dB groups).

| Label | Description |
|-------|-------------|
| Seq D | Order in which frequency was first received (newest to oldest) |
| Seq A | Order in which frequency was first received (oldest to newest) |
| Count D | Ordered by occurrences of the frequency (most to least) |
| Count A | Ordered by occurrences of the frequency (least to most) |
| RSSI D | Ordered by RSSI [signal strength] of strongest signal for frequency (strong to weak) |
| RSSI A | Ordered by RSSI [signal strength] of strongest signal for frequency (weak to strong) |
| Freq D | Ordered by frequency (high to low) |
| Freq A | Ordered by frequency (low to high) |

## Read RAW - SubGHz
Read RAW is used to read a signal without interpreting it, just store the RAW data (duration in microseconds of HIGH/LOW signal from CC1101 chip).  You can press the left button to go into a Config menu.  You can set the Frequency in MHz.  You can set the Modulation (which is really the preset information).  You can set Sound ON/OFF - which will click the speaker each time the data switches from HIGH to LOW.  You can set the RSSI Threshold, which is the minimum signal strength needed for capturing data.

| Modulation | Description |
|------------|-------------|
| AM270      | AM (OOK/ASK). 270 kHz bandwidth.  4 dB decision boundary. 3794 data rate. |
| AM650      | AM (OOK/ASK). 650 kHz bandwidth.  8 dB decision boundary. 3794 data rate. |
| FM238      | FM (2FSK). 2.380 kHz deviation. 270 kHz bandwidth. 4798 data rate. 16 chan filter w/carrier-sense |
| FM476      | FM (2FSK). 47.607 kHz deviation. 270 kHz bandwidth. 4798 data rate. 16 chan filter w/carrier-sense |
| FM95 *     | POCSAG - FM (2FSK). 9.521 kHz deviation. 270 kHz bandwidth. 4798 data rate. 16 chan filter w/carrier-sense |
| FM15k *    | FM (2FSK). 15.869 kHz deviation. 135 kHz bandwidth. 3794 data rate. PATable Ramp. 32 chan filter w/carrier-sense |
| Pagers *   | FM (2FSK). 5.157 kHz deviation. 270 kHz bandwidth. 625 data rate. 16 chan filter w/carrier-sense |
| HND_1 *    | Honda_1 - FM (2FSK). 15.869 kHz deviation. 270 kHz bandwidth. 15373 data rate. 16 chan filter w/carrier-sense |
| HND_2 *    | Honda_2 - FM (2FSK). 15.869 kHz deviation. 67 kHz bandwidth. 15373 data rate. 32 chan filter w/carrier-sense |

NOTE: The items above marked with * are not part of the official firmware settings.

Press OK button to start recording the data, then press it again to stop recording.  Once you have a recorded signal, you can:
- press Left button to erase your recording & arm for recording.
- press OK button to send the signal (if the frequency is allowed in your region)
- press Right button to save the file, for analysis or playback later. One you save it, the right button will allow you to rename or delete the file.

The saved data is a text file that contains the frequency, the modulation and mostly the raw data.  The positive numbers are the duration in microseconds where there was tone, and the negative numbers are the microseconds where there was silence.

## Read - SubGHz
Read is used to read a signal and try to match it to an existing known protocol.  You can press the left button to go into a Config menu.  You can set the Frequency in MHz.  You can enable Hopping to hop between a small set of frequencies to be monitored (instead of choosing the frequency). You can set the Modulation (which is really the preset information).  You can set Sound ON/OFF - which will click the speaker each time the data switches from HIGH to LOW.  You can enable "Bin_RAW" (I still need to learn more about this feature).  You can choose to lock the keyboard, which will require you to press Back button three times to reenable the keyboard.  Some firmware has options to Ignore certain protocols (for example to ignore a signal from car alarms).

If a signal matches a protocol, the protocol and id will be displayed.  You can use the Up and Down buttons on the Flipper Zero to choose a signal (the oldest signal is at the top of the list).  Pressing the Ok button will display details about the signal.  You can then use the Ok button again to send the signal (if the frequency is allowed in your region) or you can press the Right button to save the signal.

When you send the signal, the protocol code will use the data to create a transmit timing.  The encoder is interpreting the data from the decoded signal, so it may be slightly different than the received signal.  For example, the encoder could choose to transmit 300 microseconds of tone and 200 microseconds of silence, even though the received signal was 270 microseconds of tone and 230 microseconds of silence.  Typically, the encoder will play a more "ideal to the spec" signal vs. what is captured during a RAW capture.

The saved data is a text file, that contains the details the protocol code needs to be able to recreate the signal.

### TODO - Bin_RAW details
How does it bucketize?  Does anything above some RSSI match?

## Add Manually - SubGhz
Add Manually feature will create a random saved signal, without needing to receive the signal.  This uses subghz_scene_set_type which will generate a random number and use that for the key and then feed that to the protocol for saving the signal to the Flipper Zero.  Choose [the protocol](https://docs.flipperzero.one/sub-ghz/add-new-remote) you would like to create and then enter a name for the saved file.

The saved data is a text file, that contains the details the protocol code needs to be able to recreate the signal (exactly the same as a file that was saved using the Read feature).

## Saved - SubGHz
Saved feature will allow you to load a saved file.  (These are just text files, so you can edit these files to represent different data than what was originally saved.)

- If the signal is a RAW file, you will go to the RAW menu as if you had just saved a Read RAW signal.
- If the signal is a known protocol, you will go to a menu with Emulate, Rename, Delete options.  Choosing Emulate will display the technical details of the signal and the Ok button will send the signal (similar UI to clicking on a Read signal, but without the Save option).  If the code is a Dynamic code, the SUB file will be updated once the signal is sent.

## Test - SubGHz
Test feature has three options - Carrier, Packet, Static.

### Carrier
In Carrier mode, the application displays the RSSI.  Use the Left and Right buttons to change the frequency the Flipper Zero is listening on.  Up and Down buttons change the path (isolate, 315 MHz, 433Mhz, 868 Mhz).  The Flipper has [second stage components](https://docs.flipperzero.one/development/hardware/schematic#t7n8l) which are picked.

### Packet
In Packet mode, the application displays the RSSI and number of packets detected.  Use the Left and Right buttons to change the frequency the Flipper Zero is listening on.  Up and Down buttons change the path (isolate, 315 MHz, 433Mhz, 868 Mhz).  The Flipper has [second stage components](https://docs.flipperzero.one/development/hardware/schematic#t7n8l) which are picked.  Press the Ok button to switch between receiving Priceton packets and transmitting them.

### Static
In Static model, the application will broadcast 1 of 4 static Princeton codes.  Use the Left and Right buttons to change the frequency the Flipper Zero will transmit on.  Up and Down buttons change the static key used.  Ok button transmits the code.

## Radio Settings - (Some firmware)
These settings are not enabled in official firmware, however some firmware expose additional options for SubGHz.  

### Module
You can choose between Internal and External radio.  You must connect a CC1101 to the SPI pins to enable the External Radio, otherwise you will get an error.

### External Radio 5v
You can enable the +5 volt GPIO pin.  Typically +5 volts is only supplied when the Flipper is connected to USB-C cable, but this option will provide 5 volts without needing the cable.

### Time in names
Enable this setting will make your save files have a timestamp by default.

### Counter increment
Usually its settings for rolling codes - value for increment next rolling code key.

### Debug pin
Enable a pin to mirror the CC1101 raw data.  Note: This pin will have the signal data even when the signal has not met the RSSI threshold value.

# CLI (Command Line Interface)
Coming soon - I will be adding information about the Flipper Zero's CLI (command line interface).  This allows devices such as a phone or computer to communicate with the Flipper Zero using the serial port.

# Distance
A lot of factors can impact the distance the Flipper Zero and send and receive signals.  I did some testing using two Flipper Zeros with AM650 modulation sending a DoorHan signal at different frequencies.  I used an external [CC1101 w/433 antenna](https://www.amazon.com/gp/product/B01DS1WUEQ) and [915MHz antenna](https://www.amazon.com/gp/product/B086ZG5WBR) and [315MHz antenna](https://www.amazon.com/gp/product/B09TW8SPPV).  I used the Sub-GHz Read function on official firmware.  For sending I modified the Saved .SUB files to contain the frequencies I wanted to test and updated official firmware to resend a signal every 10 seconds after the first signal was sent.  I was in an open parking lot for testing and made sure I could receive a repeat signal within a 30-second window from the same location.  Your distance may vary if you use AM270 (should be slightly farther) or FM.

|Freq|TX|RX|Approx distance (feet)|
|-|-|-|-|
|315MHz|int|int|140 ft|
|315MHz|int|ext|225 ft|
|315MHz|ext|int|90 ft|
|315MHz|ext|ext|160 ft|
|433MHz|int|int|50 ft|
|433MHz|int|ext|120 ft|
|433MHz|ext|int|110 ft|
|433MHz|ext|ext|Max (290 ft+)|
|915MHz|int|int|115 ft|
|915MHz|int|ext|10 ft|
|915MHz|ext|int|26 ft|
|915MHz|ext|ext|4 ft|


# Modulations
There are a variety of modulations, depending on the firmware you have.

| Modulation | Description |
|------------|-------------|
| AM270      | AM (OOK/ASK). 270 kHz bandwidth.  4 dB decision boundary. 3794 data rate. |
| AM650      | AM (OOK/ASK). 650 kHz bandwidth.  8 dB decision boundary. 3794 data rate. |
| FM238      | FM (2FSK). 2.380 kHz deviation. 270 kHz bandwidth. 4798 data rate. 16 chan filter w/carrier-sense |
| FM476      | FM (2FSK). 47.607 kHz deviation. 270 kHz bandwidth. 4798 data rate. 16 chan filter w/carrier-sense |
| FM95 *     | POCSAG - FM (2FSK). 9.521 kHz deviation. 270 kHz bandwidth. 4798 data rate. 16 chan filter w/carrier-sense |
| FM15k *    | FM (2FSK). 15.869 kHz deviation. 135 kHz bandwidth. 3794 data rate. 32 chan filter w/carrier-sense |
| Pagers *   | FM (2FSK). 5.157 kHz deviation. 270 kHz bandwidth. 625 data rate. 16 chan filter w/carrier-sense |
| HND_1 *    | Honda_1 - FM (2FSK). 15.869 kHz deviation. 270 kHz bandwidth. 15373 data rate. 16 chan filter w/carrier-sense |
| HND_2 *    | Honda_2 - FM (2FSK). 15.869 kHz deviation. 67 kHz bandwidth. 15373 data rate. 32 chan filter w/carrier-sense |

NOTE: The items above marked with * are not part of the official firmware settings.


# Static and Dynamic Codes
Static codes are codes that are broadcast the same time each time the remote is pressed.  The Flipper Zero official firmware supports saving codes that are registered as Static.  

Dynamic codes are codes that change based on some algorithm each time the remote is pressed.  An internal counter is updated and the SUB (SubGHz file) is updated with the new information.  Replaying a dynamic (also known as rolling code) has a high probability of getting out of sync with the remote.  If you replay the old signal, the receiving device may detect this condition.  If you play a newer signal, then the original remote will have an old count (and so it will be sending old signals that will not work).  It is difficult to keep multiple remotes in sync.  The Flipper Zero official firmware does not support saving dynamic codes.  

The Flipper Zero official firmware does allow you to use the [Add Manually](#add-manually---subghz) to create a new SUB file, which you can then associate with the receiver.  This is a better solution, since you do not risk getting the original remote out of sync and having to resync the device.  Every time you send a code, the SUB file is updated with new information, so the next code will be later in the sequence.

## Sync with another Flipper
As mentioned above, it is better to [Add Manually](#add-manually---subghz) and just create a new device that you pair with.  If you look at the SUB file and the detailed data presented by the Flipper, and then press Ok to generate a new code, looking at the data & look at the SUB file... eventually you will realize how to modify the SUB file on a second Flipper to match a transmission by your first Flipper.  The data has to be in the SUB file, otherwise the Flipper couldn't keep sending an incrementing code.  You will likely be able to edit a SUB file originally created with [Add Manually](#add-manually---subghz) using a text editor.  If you figure all of the bytes of data you receive, when you emulate your hand-edited SUB file, it should be able to match the signal that your other Flipper will send in the future.  Depending on your firmware, the counters might not increment at the same rate, so it is still possible to get out of sync with the other device (like having to press the button twice as often on one Flipper with one firmware vs another) so it is highly recommended to use Add Manually a new code and register that with the receiver.



# Custom Settings
In the firmware, the applications\main\subghz\helpers\subghz_txrx.c file loads a "subghz/assets/setting_user" file to further configure the SubGHz application.  In some firmware, this file may be renamed, like "setting_user.txt".  Some firmware use this file for their own configuration, while other firmware set their own configuration in code.  An example of the "setting_user" file may be found in "setting_user.example", where you can rename the file to "setting_user" (or "setting_user.txt") and copy it to your SD CARD/subghz/assets folder to make it apply.  If you have debug logging enabled (Settings, System, LogLevel Debug) then messages should be logged if the file fails to load.

## Comments
The "setting_user" file is a text file.  If the line starts with a "#" character, the line will be treated as a comment and the Flipper Zero will ignore the contents of that line.  Remove the "#" to uncomment the line.

## Add Standard Frequencies
If you uncomment the line and set the value to "Add_standard_frequencies: true" then the Flipper will populate the list of standard frequencies for Read and Read RAW.  It will also populate the list of hopper frequencies.

If you uncomment the line and set the value to "Add_standard_frequencies: false" then the Flipper will not populate the frequencies or hopper frequencies.  You must provide at least one uncommented "Frequency" and one uncommented "Hopper_frequency" for your settings file to be valid.

## Default frequency
If you uncomment the line "Default_frequency: 433920000" then that value will be the default frequency to use when Read or Read RAW is selected.

## Frequency
If you uncomment the line "Frequency: 300000000" then that frequency will be used for Read, Read RAW and Frequency Analyzer.  You can change the frequency to any valid frequency that the Flipper Zero supports.  The list of frequencies are not in order (so your frequency may be at the beginning or end of the configuration selection when doing Read or Read RAW).  The Flipper Zero does not need to be able to transmit on the frequency for you to add it to this list.  If you set "Add_standard_frequencies: false" then you must provide at least one of these entries.

## Hopper_frequency
If you uncomment the line "Hopper_frequency: 300000000" then that frequency will be added to the list of hopper frequencies to use when frequency hopping is enabled.  If you set "Add_standard_frequencies: false" then you must provide at least one of these entries.

## Custom preset
Set the "Custom_preset_name" to a name you would like to show up in Modulation.  Set "Custom_preset_module: CC1101" to specify the module.  Set "Custom_preset_data" to the data for your preset.

AM650 is the following preset data:
"02 0D 03 07 08 32 0B 06 14 00 13 00 12 30 11 32 10 17 18 18 19 18 1D 91 1C 00 1B 07 20 FB 22 11 21 B6 00 00 00 C0 00 00 00 00 00 00"

### Preset data
The data is a hexadecimal register number of the CC1101 followed by the hexadecimal value to set for the register.  For example, in AM650 register 0x02 is set to a value of 0x0D and then register 0x03 is set to a value of 0x07.  The pattern continues until "00 00" which signals the end of the register list.  The 8 bytes following that are the PATable, which is the signal strength for transmitting. In the AM650 example, the PATable is "00 C0 00 00 00 00 00 00" (the first byte means the OFF signal will be "00" strength, and the second byte means the ON signal will be "C0" strength, or about 10 dBm).

#### Custom preset
##### AM650
```
02 0D 03 07 08 32 0B 06 14 00 13 00 12 30 11 32 10 17 18 18 19 18 1D 91 1C 00 1B 07 20 FB 22 11 21 B6 00 00 00 C0 00 00 00 00 00 00

Modulation: "12 30" 6:4 MOD_FORMAT[2:0] => OOK
Bandwidth:  "10 17" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 650kHz
Data rate: "10 17" 3:0 DRATE_E[3:0] & "11 32" 7:0 DRATE_M[7:0] => 3,794
Decision boundary: "1D 91" 1:0 FILTER_LENGTH[1:0] => 8 dB
Sync: "12 30" 2:0 SYNC_MODE[2:0] => no preamble/sync
PATABLE: 00 C0 00 00 00 00 00 00 => OOK, max power [no ramp]
```

##### AM270
```  
02 0D 03 47 08 32 0B 06 14 00 13 00 12 30 11 32 10 67 18 18 19 18 1D 40 1C 00 1B 03 20 FB 22 11 21 B6 00 00 00 C0 00 00 00 00 00 00

Modulation: "12 30" 6:4 MOD_FORMAT[2:0] => OOK
Bandwidth:  "10 67" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 270.833kHz
Data rate: "10 67" 3:0 DRATE_E[3:0] & "11 32" 7:0 DRATE_M[7:0] => 3,794
Decision boundary: "1D 40" 1:0 FILTER_LENGTH[1:0] => 4 dB
Sync: "12 30" 2:0 SYNC_MODE[2:0] => no preamble/sync
PATABLE: 00 C0 00 00 00 00 00 00 => OOK, max power [no ramp]
```

##### FM238
```
02 0D 0B 06 08 32 07 04 14 00 13 02 12 04 11 83 10 67 15 04 18 18 19 16 1D 91 1C 00 1B 07 20 FB 22 10 21 56 00 00 C0 00 00 00 00 00 00 00

Modulation: "12 04" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 04" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 2.380kHz
Bandwidth:  "10 67" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 270.833kHz
Data rate: "10 67" 3:0 DRATE_E[3:0] & "11 83" 7:0 DRATE_M[7:0] => 4,798
Channel filter samples: "1D 91" 1:0 FILTER_LENGTH[1:0] => 16
Sync: "12 04" 2:0 SYNC_MODE[2:0] => no preamble/sync, carrier-sense above threshold
PATABLE: C0 00 00 00 00 00 00 00 => 2FSK, max power [no ramp]
```

##### FM476
```
02 0D 0B 06 08 32 07 04 14 00 13 02 12 04 11 83 10 67 15 47 18 18 19 16 1D 91 1C 00 1B 07 20 FB 22 10 21 56 00 00 C0 00 00 00 00 00 00 00

Modulation: "12 04" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 47" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 47.607kHz
Bandwidth:  "10 67" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 270.833kHz
Data rate: "10 67" 3:0 DRATE_E[3:0] & "11 83" 7:0 DRATE_M[7:0] => 4,798
Channel filter samples: "1D 91" 1:0 FILTER_LENGTH[1:0] => 16
Sync: "12 04" 2:0 SYNC_MODE[2:0] => no preamble/sync, carrier-sense above threshold
PATABLE: C0 00 00 00 00 00 00 00 => 2FSK, max power [no ramp]
```

##### FM95 "POCSAG settings"
```
02 0D 0B 06 08 32 07 04 14 00 13 02 12 04 11 83 10 67 15 24 18 18 19 16 1D 91 1C 00 1B 07 20 FB 22 10 21 56 00 00 C0 00 00 00 00 00 00 00

Modulation: "12 04" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 24" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 9.521kHz
Bandwidth:  "10 67" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 270.833kHz
Data rate: "10 67" 3:0 DRATE_E[3:0] & "11 83" 7:0 DRATE_M[7:0] => 4,798
Channel filter samples: "1D 91" 1:0 FILTER_LENGTH[1:0] => 16
Sync: "12 04" 2:0 SYNC_MODE[2:0] => no preamble/sync, carrier-sense above threshold
PATABLE: C0 00 00 00 00 00 00 00 => 2FSK, max power [no ramp]
```

##### FM15k
```
02 0D 03 47 08 32 0B 06 15 32 14 00 13 00 12 00 11 32 10 A7 18 18 19 1D 1D 92 1C 00 1B 04 20 FB 22 17 21 B6 00 00 00 12 0E 34 60 C5 C1 C0

Modulation: "12 00" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 32" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 15.869kHz
Bandwidth:  "10 A7" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 135.417kHz
Data rate: "10 A7" 3:0 DRATE_E[3:0] & "11 32" 7:0 DRATE_M[7:0] => 3,794
Channel filter samples: "1D 92" 1:0 FILTER_LENGTH[1:0] => 32
Sync: "12 00" 2:0 SYNC_MODE[2:0] => no preamble/sync
PATABLE: 00 12 0E 34 60 C5 C1 C0 + "22 17" 2:0 PA_POWER[2:0] => Ramp to full power
```

##### Pagers
```
02 0D 07 04 08 32 0B 06 10 64 11 93 12 0C 13 02 14 00 15 15 18 18 19 16 1B 07 1C 00 1D 91 20 FB 21 56 22 10 00 00 C0 00 00 00 00 00 00 00

Modulation: "12 0C" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 15" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 5.157kHz
Bandwidth:  "10 64" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 270.833kHz
Data rate: "10 64" 3:0 DRATE_E[3:0] & "11 93" 7:0 DRATE_M[7:0] => 625
Channel filter samples: "1D 91" 1:0 FILTER_LENGTH[1:0] => 16
Sync: "12 0C" 2:0 SYNC_MODE[2:0] => no preamble/sync, carrier-sense above threshold
Manchester_en: "12 0C" 3 MANCHESTER_EN => Enabled (but "async" disabled per 27.1)
Maybe treated as "12 04"?
PATABLE:  C0 00 00 00 00 00 00 00 => 2FSK, max power [no ramp]
```

##### HND_1 "Honda1"
```
02 0D 0B 06 08 32 07 04 14 00 13 02 12 04 11 36 10 69 15 32 18 18 19 16 1D 91 1C 00 1B 07 20 FB 22 10 21 56 00 00 C0 00 00 00 00 00 00 00

Modulation: "12 04" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 32" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 15.869kHz
Bandwidth:  "10 69" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 270.833kHz
Data rate: "10 69" 3:0 DRATE_E[3:0] & "11 36" 7:0 DRATE_M[7:0] => 15,373
Channel filter samples: "1D 91" 1:0 FILTER_LENGTH[1:0] => 16
Sync: "12 04" 2:0 SYNC_MODE[2:0] => no preamble/sync, carrier-sense above threshold
PATABLE: C0 00 00 00 00 00 00 00 => 2FSK, max power [no ramp]
```

##### HND_2 "Honda2"
```
02 0D 0B 06 08 32 07 04 14 00 13 02 12 07 11 36 10 E9 15 32 18 18 19 16 1D 92 1C 40 1B 03 20 FB 22 10 21 56 00 00 C0 00 00 00 00 00 00 00

Modulation: "12 07" 6:4 MOD_FORMAT[2:0] => 2FSK
Deviation: "15 32" 6:4 DEVIATION_E[2:0] & 2:0 DEVIATION_M[2:0] => 15.869kHz
Bandwidth:  "10 E9" 7:6 CHANBW_E[1:0] & 5:4 CHANBW_M[1:0] => 67.708kHz
Data rate: "10 E9" 3:0 DRATE_E[3:0] & "11 36" 7:0 DRATE_M[7:0] => 15,373
Channel filter samples: "1D 92" 1:0 FILTER_LENGTH[1:0] => 32
Sync: "12 07" 2:0 SYNC_MODE[2:0] => 30/32 + carrier-sense (but "30/32" disabled per 27.1)
Maybe treated as "12 04"?
PATABLE: C0 00 00 00 00 00 00 00 => 2FSK, max power [no ramp]
```


#### CC1101 Registers
The [CC1101 datasheet](https://www.ti.com/lit/ds/symlink/cc1101.pdf) contains detailed information about the various registers.

| Register (in hex) | Description |
|-------------------|-------------|
| 12 | Modulation: 2FSK or ASK/OOK |
| 10-11 | Bandwidth & Data rate |
| 15 | Deviation (for 2FSK) |
| 22 + PATABLE (last 8 bytes) | broadcast power & ramp |
| 1B-1D | RX: AGC, ASK decision boundaries |
| | |
| 21 | Front-end RX config. 0xB6 is Flipper recommendation, 0x56 is CC1101 default. |
| 02 + 08 | "02 0D 08 32" - GDO0 output pin is async data w/infinite packet length. |
| 07 | "07 04" - CRC_AutoFlush (used in most 2FSK profiles, but not relevant for async?) |
| 0B | "0B 06" = 152,343Hz Intermediate frequency.  Perhaps the CC1101 in the Flipper is tuned to work best at this frequency?  The default is 381kHz. |
| 18 | "18 18" = Calibrate 150us, idle to Rx/TX. |
| 19* | "19 18" = OOK must have lowest two bits off. |
| 19* | "19 16" = 3K, K/2, Bwchan/4 -- Freq offset (Rx vs Tx diff). |
| 19* | "19 1D" = 4K, K/2, BWchan/8 -- Freq offset (Rx vs Tx diff). |
| 20 | "20 FB" = Wake on Radio  (WOR @ hours) |
| 03 | "03 47" is same as "03 07". Same as defaults. Sets the unused FIFO buffers & can be ignored for async? |
| 14 + 13 | "14 00 13 02" = 101,562Hz - Channel Spacing (2FSK) |
| 14 + 13 | "14 00 13 00" = 25,390Hz - Channel Spacing (OOK) |
| 0A | "0A 00" = (default value) Channel number |

##### Details
| Register (in hex) | Details |
|--|--|
| 12 | "12 #x" - The first digit (Most Significant) is: 0 = 2-FSK. 3 = ASK/OOK. 1 = GFSK. 7 = MSK (>26kBaud) |
| 12 | "12 x#" - The second digit (Least Significant) is: 0 = No preamble/sync. 4 = No preamble/sync, carrier-sense above threshold. C = Manchester, 15/16, carrier-sense above threshold (not valid for async). 7 = 30/32, carrier-sense above threshold (not valid for async). |
| 22* | "22 11" = PA1 [OOK]. |
| 22* | "22 10" = PA0 [2FSK, NO RAMP]. |
| 22* | "22 17" = PA0 [2FSK, WITH RAMP (7 values)]. |
| | |

##### Bandwidth and Data rate
Register 0x10 and 0x11 set the bandwidth and data rate.

Bandwidth is the set using the highest 4-bits of register 0x10. For a bandwidth of 650KHz set register 0x10 to 10-1F.  For a bandwidth of 270KHz set register 0x10 to 60-6F.  The max bandwidth is 812KHz (set register 0x10 to 00-0F).  The min bandwidth is 58KHz (set register 0x10 to F0-FF).

Higher data rates will make the RAW value timings more accurate, as shown in this [YouTube video](https://youtu.be/VxMDdYuRITE).  External CC1101 seems unstable at rates above the 15K-20K range using some firmware.

Data rate is set using the lowest 4-bits of register 0x10 for the Exponent (scale) and all 8-bits of register 0x11 for the Mantissa.  
For a data rate of 4798 baud, set register 0x10 to [0-F]7 and Register 0x11 to 0x83.  For a data rate of 3794 baud, set register 0x10 to [0-F]7 and Register 0x11 to 0x32.  For a data rate of 15373, set register 0x10 to [0-F]9 and Register 0x11 to 0x36.  For a data rate of 19985 baud, set register 0x10 to [0-F]9 and Register 0x11 to 0x93.  For a data rate of 115051 baud, set register 0x10 to [0-F]C and Register 0x11 to 0x22.  

##### Deviation
For FSK (FM modulated) signals, deviation is the frequency away from the carrier frequency.  Register 0x15 stores the deviation; with the exponent in the high bits and the mantissa in the low bits.  For a deviation of 2380Hz set Register 0x15 to 0x04.  For a deviation of 47607Hz set Register 0x15 to 0x47. For a deviation of 15869Hz set Register 0x15 to 0x32.

|Hz|0|1|2|3|4|5|6|7|E (high nibble)|
|-|-|-|-|-|-|-|-|-|-|
0|  1,587 |  3,174 |    6,348 |  12,695 |  25,391 |  50,781 |  101,563 |  203,125 ||
1|  1,785 |  3,571 |    7,141 |  14,282 |  28,564 |  57,129 |  114,258 |  228,516 ||
2|  1,984 |  3,967 |    7,935 |  15,869 |  31,738 |  63,477 |  126,953 |  253,906 ||
3|  2,182 |  4,364 |    8,728 |  17,456 |  34,912 |  69,824 |  139,648 |  279,297 ||
4|  2,380 |  4,761 |    9,521 |  19,043 |  38,086 |  76,172 |  152,344 |  304,688 ||
5|  2,579 |  5,157 |  10,315 |  20,630 |  41,260 |  82,520 |  165,039 |  330,078 ||
6|  2,777 |  5,554 |  11,108 |  22,217 |  44,434 |  88,867 |  177,734 |  355,469 ||
7|  2,975 |  5,951 |  11,902 |  23,804 |  47,607 |  95,215 |  190,430 |  380,859 ||
M (low nibble)||||||||||

##### Decision Boundary
The lowest 2-bits of register 0x1D set the decision boundary. For ASK (AM modulation) this is the difference between an ON/OFF signal in dB.  For FSK (FM modulation) this is the channel filter samples.

|Lowest two bits of Register 0x1D|Description (FSK)|Description (ASK)|
|-|-|-|
|00|8 samples|4dB|
|01|16 samples|8dB|
|10|32 samples|12dB|
|11|64 samples|16dB|

#### PATable
The value to use in PATable is somewhat complex. This [PATable document](https://www.ti.com/lit/an/swra151a/swra151a.pdf) explains the values.  You should avoid using 0x61 to 0x6F for the CC1101, even though the values are listed in the table.
The two most common values use are "00" and "C0".  For most frequencies, a value of "C0" represents about 10 dBm (or 10 mW) of power.  A value of "00" represents little-to-no power.

For calculating a ramp of power, it is typically recommended to use [SmartRF Studio 7](https://www.ti.com/tool/SMARTRFTM-STUDIO) from Texas Instruments, with the CC1101 chip configured for your frequency, modulation, bandwidth, etc. rather than try to manually create a ramp.

The table in the [document](https://www.ti.com/lit/an/swra151a/swra151a.pdf) uses dBm, which is a log scale.  To convert to mW the formula is 10^(dBm/10).  Here is a table of common dBm values...

| dBm | mW |
|---|---|
| 10 dBm | 10 mW |
| 7 dBm  | 5.0mW |
| 5 dBm  | 3.2 mW |
| 0 dBm | 1.0 mW |
| -5 dBm | 0.316 mW |
| -10 dBm | 0.100 mW (100 μW) |
| -15 dBm | 0.032 mW (32 μW) |
| -20 dBm | 0.01 mW (10 μW) |
| -30 dBm | 0.001 mW (1 μW) |

# SUB File Format
The [Flipper Zero Documentation](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/documentation/file_formats/SubGhzFileFormats.md#transceiver-configuration-data) does a good job describing the file formats in detail.

One of my subscribers wrote a script to convert a SUB file into a CSV file.
- [SUB to CSV](https://github.com/jamisonderek/flipper-zero-tutorials/tree/main/subghz/scripts/SUB2CSV#readme) script

## Protocol Princeton
Here is a Princeton encoded file:
```
Filetype: Flipper SubGhz Key File
Version: 1
Frequency: 433920000
Preset: FuriHalSubGhzPresetOok650Async
Protocol: Princeton
Bit: 24
Key: 00 00 00 00 00 52 81 1C
TE: 154
```

The Key 52811C can be written out as binary ``010100101000000100011100``.  This is a demodulated signal.

## Protocol RAW
Here is the same remote, but using Read RAW:
```
Filetype: Flipper SubGhz RAW File
Version: 1
Frequency: 433920000
Preset: FuriHalSubGhzPresetOok650Async
Protocol: RAW
RAW_Data: 133 -4806 163 -468 453 -166 123 -500 437 -200 145 -470 129 -472 439 -198 145 -474 441 -176 139 -456 173 -468 133 -490 131 -466 139 -500 129 -472 475 -166 145 -474 127 -472 165 -450 469 -168 459 -174 427 -168 177 -436 161 -472 131 -4816 131 -486 471 -168 145 -476 417 -210 137 -450 173 -466 439 -178 139 -458 473 -168 139 -490 129 -476 141 -476 133 -490 129 -478 133 -494 455 -176 143 -490 135 -452 173 -446 445 -210 429 -168 453 -162 153 -470 131 -482 155 -4802 
```

The positive numbers are tones, and the negative numbers are silence.  Starting with the data after the big silence (-4806)...
|Tone|Silence|Value (0=mostly silence, 1=mostly tone)|Signal|
|-|-|-|-|
|163|-468|0|0|
|453|-166|1|01|
|123|-500|0|010|
|437|-200|1|0101|
|145|-470|0|01010|
|129|-472|0|010100|
|439|-198|1|0101001|
|145|-474|0|01010010|
|441|-176|1|010100101|
|139|-456|0|0101001010|
|173|-468|0|01010010100|
|133|-490|0|010100101000|
|131|-466|0|0101001010000|
|139|-500|0|01010010100000|
|129|-472|0|010100101000000|
|475|-166|1|0101001010000001|
|145|-474|0|01010010100000010|
|127|-472|0|010100101000000100|
|165|-450|0|0101001010000001000| 
|469|-168|1|01010010100000010001| 
|459|-174|1|010100101000000100011| 
|427|-168|1|0101001010000001000111| 
|177|-436|0|01010010100000010001110| 
|161|-472|0|010100101000000100011100| 
|131|-4816|x|

``010100101000000100011100`` matches the Key 52811C from the other SUB file.

## Protocol BinRAW
In Read there is an option for "Bin_RAW".  Here is what the SUB file would look like (assuming Princeton wasn't registered in protocol_items.c):
```
Filetype: Flipper SubGhz Key File
Version: 1
Frequency: 433920000
Preset: FuriHalSubGhzPresetOok650Async
Protocol: BinRAW
Bit: 130
TE: 145
Bit_RAW: 130
Data_RAW: 00 00 00 00 01 1D 1D 11 D1 D1 11 11 1D 11 1D DD 11
```

If you write DATA_RAW out in binary, we get:
```
                         0000 0001   0001 1101   0001 1101   
 0001 0001   1101 0001   1101 0001   0001 0001   0001 0001
 0001 1101   0001 0001   0001 1101   1101 1101   0001 0001
```

If we ignore the last bit and then regroup we get:
```
1000 1110 1000 1110 1000 1000 1110 1000 
1110 1000 1000 1000 1000 1000 1000 1110 
1000 1000 1000 1110 1110 1110 1000 1000 1
```

The 1 represents a tone and the 0 represents silence.  So short tone followed by long silence is ``1000`` (which we can encode as a 0) and long tone followed by short silence is ``1110`` (which we can encode as a 1).  That gives us ``010100101000000100011100``, which matches the previous files.

## Summary
Princeton uses "Short tone+Long silence" for 0 and "Long tone+Short silence for 1".  Other protocols may use a fixed length tone or a fixed length silence, or even something more complex.  Hopefully this helps you understand the relationship between ReadRAW (tone/silence timings), ReadBin (tone/silence represented by series of 1 or 0, with TE being the microsecond duration), and Princeton (or another encoding) where the bits are combined to represent data.

# Protocols
The Flipper Zero has built-in support for decoding and encoding many protocols.  The TE is the microsecond duration that a signal is transmitted (or not transmitted).  Bit is the minimum number of bits expected (in many protocols it much exactly the count).  Some protocols have a header signal that is transmitted before the actual data.  The notation I am using is positive values are signal and negative values are silence, with the "/" being a delimiter.  The data itself typically transmits different patterns to represent each 0/1 bit.  Some protocols have stop bits as well.  Often these signals will repeat many (like 10) times.  Here is my YouTube video on [Protocol encoders/decoders](https://youtu.be/O4bEuYwytv0) including a walkthru.

## Supported Protocols
The protocol encoders/decoders are stored in [lib/subghz/protocols](https://github.com/flipperdevices/flipperzero-firmware/tree/dev/lib/subghz/protocols) in the firmware.

|Protocol Name|Type|te|upload data|
|-|-|-|-|
|ansonic|static|te=555/1111,bit=12|header=-35s/+s; 1=-s/L,0=-L/s|
|bett|static|te=340/2000,bit=18|1=L/-s,0=s/-L; last1=L/-(s+7L),last0=s/-(L+7L)|
|came(12)|static|te=320/640,bit=12(hte=47)|header=-s*hte/s; 1:-L/s,0:-s/L|
|came(18)|static|te=320/640,bit=18(hte=47)|header=-s*hte/s; 1:-L/s,0:-s/L|
|came(24)|static|te=320/640,bit=24(hte=76)|header=-s*hte/s; 1:-L/s,0:-s/L|
|came(25)|static|te=320/640,bit=25(hte=36)|header=-s*hte/s; 1:-L/s,0:-s/L|
|came_twee|static|te=500/1000,bit=54|xor magic,manchester encoding|
|chamberlain_code|static|te=1000,bit=10|1:-2s/2s,0:-s/3s; [case7-9?]|
|clemsa|static|te=385/2695,bit=18|1:L/-s,0:s/-L; last1=L/s(s+7L),last0=s/-(L+7L)|
|doitrand|static|te=400/1100,bit=37|header=-62s/[2s-100]; 1:-L/s,0:-s/L|
|dooya|static|te=366/733,bit=40|header=[bit0=1:-(12L+L)/13s/2L,bit0=0:-(12L+s)/13s/2L]; 1:L/-s,0:s/-L|
|gate_tx|static|te=350/700,bit=24|header=-49s/L; 1:-L/s,0:-s/L|
|holtek|static|te=430/870,bit=40|header=-36s/s; 1:-L/s,0:-s/L|
|holtek_ht12x|static|te=320/640,bit=12|header=-36s/s; 1:-L/s,0:-s/L|
|honeywell_wdb|static|te=160/320,bit=48|header=-3s; 1:L/-s, 0:s/-L; stop=3s|
|hormann|static|te=500/1000,bit=44|header=24s/-s; 1:L/-s,0:s/-L; stop=-24s|
|intertechno_v3|static|te=275/1375,bit=32/36|header=s/-38s/s/-10s; 1:s/-L/s/-s,0:s/-s/s/-L, 36bit_i=9:s/-s/s/s|
|linear|static|static|te=500/1500,bit=10|1:=L/-s,0:s/-L; last1=L/-42s,last0=s/-44s|
|linear_delta3|static|te=500/2000,bit=8|1:s/-7s,0=L/-L; last1=s/-73s,last0=L/-70s|
|magellan|static|te=200/400,bit=32|header=4s/-s/{s/-s}x12/s/-L/3L/-L; 1:s/-L,0:L/-s; stop=-s/100L|
|marantec|static|te=1000/2000,bit=49|Manchester encoded (MSB to LSB)|
|megacode|static|te=1000,bit=24|header=[bit0=1:-11s,bit0=0:-14s]; backwards? 1:000001, 0:001000|
|nero_radio(56)|static|te=200/400,bit=56|header={s/-s}x49/830/-s; 1:L/-s,0:s/L; last1=L/-23s, last0=s/-23s|
|nero_radio(57)|static|te=200/400,bit=57|header={s/-s}x49/830/-s; 1:L/-s,0:s/L; last1=L/-1300, last0=s/-1300|
|nero_sketch|static|te=330/660,bit=40|header={s/-s}x47/4s/-s; 1:L/-s, 0:s/L; stop=3s/-s|
|nice_flo|static|te=700/1400,bit=12|header=-36s/s; 1:-L/s,0:-s/L|
|phoenix_v2|static|te=427/853,bit=52|header=-60s/6s; 1:-L/s,0:-s/L|
|power_smart|static|te=225/450,bit=64|Manchester encoding, stop=-1111L|
|princeton|static|te=390/1170,bit=24|1:L/-s,0:s/-L; stop=s/-30s|
|smc5326|static|te=300/900,bit=25|1:L/-s,0:s/-L; stop=s/25s|
|alutech_at_4n|dynamic|te=400/800,bit=72||
|came_atomo|dynamic|te=600/1200,bit=62||
|faac_slh|dynamic|te=255/595,bit=64||
|ido|dynamic|te=450/1450,bit=48||
|keeloq|dynamic|te=400/800,bit=64||
|kia|dynamic|te=250/500,bit=61||
|kinggates_stylo_4k|dynamic|te=400/1100,bit=89||
|nice_flor_s|dynamic|te=500/1000,bit=52||
|scher_khan|dynamic|te=750/1100,bit=35||
|secplus_v1|dynamic|te=500/1500,bit=21||
|secplus_v2|dynamic|te=250/500,bit=62||
|somfy_keytis|dynamic|te=640/1280,bit=80||
|somfy_telis|dynamic|te=640/1280,bit=56||
|star_line|dynamic|te=250/500,bit=64||

## Unit Tests
The Flipper Zero firmware has a bunch of .SUB files in [assets/unit_tests/subghz](https://github.com/flipperdevices/flipperzero-firmware/tree/dev/assets/unit_tests/subghz) that are helpful in testing that a protocol decoder works.  When you are just starting out and only have one Flipper Zero, I recommend copying one of these _raw signals to your ``SD Card/subghz`` folder and then following the CLI debugging process in the [decoder](#decoder) section. The non-_raw signals are useful too, to see how the data gets serialized.  For rolling codes, if you keep copying back a previous unit test .SUB file, the counter will start back at the original value.  I used this technique to walk through the same Security+2.0 signal multiple times (the algorithm changes depending on the count).

## Firmware code
- There are things called "Rainbow" tables that you will sometimes see in the encoders/decoders.  They typically are "magic data" that is encoded and then those entries are referenced in a lookup table.  For example, the algorithm might be if the 4th bit of data is set, then take the existing data and XOR it with the contents from rainbow_data[1].  These values are typically not intended to be shared; if you look at the code that is messing with the iv I think it says it best... ``Sharing them will bring some discomfort to legal owners and potential legal action against you. While you reading this code think about your own personal responsibility.``
- A good understanding of binary, hexadecimal, and C language bit operations, logical operations, unary operators, printf format specifiers, conditionals, ternary operator, loops, arrays, negatives for unsigned integers, is helpful.  These concepts are not Flipper Zero specific, so many resources already exist on the internet.
  - search for "introduction to binary and hexadecimal"
  - https://en.wikipedia.org/wiki/Bitwise_operation
  - https://www.tutorialspoint.com/cprogramming/c_operators.htm
  - uint8_t is an unsigned integer 8-bits (0..255), uint16_t is 16-bits, uint32_t is 32-bits, uint64_t is 64-bits, size_t is 32-bits.
- A few examples of patterns you are likely to see:
  - "%08lX" is "0" filled, 8-digits wide, l=long type (uint32_t), X=hex in CAPS [0-9A-F].
  - (i & 0x00000000FFFFFFFF) will truncate the top 32-bits of a number.
  - (i & FFFFFF0) will truncate the bottom 4-bits of a number.
  - (i >> 4) shifts the value 4-bits to the left (e.g. divides by 16, drops 1 hex digit)
  - "for (uint8_t i=0; i<bit_count; i++) {...}" initializes i to 0, compares with bit_count, runs code in {...}, increments i, compares with bit_count, runs code in {...}.   This may also be written as "uint8_t i=0; while (i<bit_count) {... i++;}"

## Decoder
Understanding how the decoder works can be valuable when you are trying to troubleshoot why a signal isn't getting decoded by the Flipper Zero.  You can also use the CLI (Command-Line Interface) (https://lab.flipper.net/cli)[https://lab.flipper.net/cli] to decode a RAW .sub file, allowing you to set breakpoints in the feed(...) method to understand why it is not processing. ``subghz decode_raw /ext/subghz/myfile.sub``

When an application registers for subghz, it calls subghz_environment_set_protocol_registry (or the worker's alloc method calls it), passing it a list of protocols.  The most common thing for it to pass is &subghz_protocol_registry, which is all of the protocols listed in "protocol_items.c" (in the same folder as the protocols).  You can also try commenting out a protocol and redeploying firmware if the wrong decoders is getting the signal (for example came vs holtek_ht12x decoding, or if you want a Bin_RAW signal for a known protocol).  Be sure to redeploy with the protocol back when you are done!  Some firmware may have an option to disable certain protocols without requiring you to change the code.

<img src="https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/6d0cc921-3f8a-48b2-bf3a-94844b10950d" height="400px"/>

|method|purpose|
|-|-|
|alloc|typically called at beginning of app, allocates resources needed by the decoder.|
|free|typically called when app exits, releases resources.|
|feed|called for processing each LevelDuration (on/off signal & duration).  This is typically implemented as a state machine, decoding each bit (or resetting to initial state when signal was unexpected). Once a signal is fully decoded it sets Generic's .data_count_bit and .data field and then typically invokes a callback.|
|reset|resets the state machine used by feed.|
|deserialize|reads a .SUB file format object and sets Generic's .data_count_bit and .data field.|
|get_hash_data|returns an 8-bit number that represents the .data_count_bit and .data field.  This is used to determine if a signal was already added to the subghz history. 8-bits are small, so collisions are possible.|
|serialize|creates a .SUB file based on Generic's .data_count_bit and .data fields.  It also writes out the Protocol, Preset & Frequency information.|
|get_string|populates a FuriString* with the contents to display on the screen or CLI (Command-Line interface).  This data is typically generated by decoding the .data_count_bit and .data fields.|

## Encoder
Understanding how the encoder works is mostly helpful when you are trying to make your own encoder.  The encoder is what takes a .SUB file and is able to create the Encoder upload data to be able to broadcast the signal.

Often the official firmware (OFW) will not have an encoder if the protocol is a rolling code; which helps prevent people from accidently getting their remote out of sync.  Other firmware will implement the encoders, however there are often additional helper code that they use, so copying files is a fairly complex process.  If you understand what the code is doing, you may find it easier to just implement the one encoder you need & it will make maintaining your own fork of OFW much easier.

<img src="https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/7cf27f88-9b53-4d87-83aa-0e53dff4f0f4" height="400px"/>

|method|purpose|
|-|-|
|alloc|typically called at beginning of app, allocates resources needed by the encoder.|
|free|typically called when app exits, releases resources.|
|deserialize|reads a .SUB file format object and sets Generic's .data_count_bit and .data field.  It also set's the Encoder's .upload, .size_upload, .repeat value and sets the encoder into the running state (Encoder's .is_running field).  For rolling codes, it typically increments to the next code before setting the Encoder's data.|
|yield|returns the next LevelDuration (on/off, duration) that the radio should send.  It determines this by making sure Encoder's .repeat is not 0.  Then it uses the .upload data at the .front index to get the LevelDuration to return.  It typically increments .front, and if .front is at the end (equals .size_upload) it decrements the .repeat counter.|
|stop|typically sets the .is_running of the Encoder to false.  In rare cases where deserialize started additional threads, it would also terminate those threads.|

# APIs

## Radios
The Flipper Zero has an internal CC1101 Sub-GHz radio.  The firmware now also supports attaching an external CC1101 radio to the SPI pins.  NOTE: Many of the external radios are tunes to a specific band, such as 433MHz. They will likely perform better than the Flipper Zero at that band, but worse than the Flipper Zero at the other bands.

Include these header files:
```c
   #include <lib/subghz/devices/devices.h>
   #include <lib/subghz/devices/cc1101_int/cc1101_int_interconnect.h>
   #include <applications/drivers/subghz/cc1101_ext/cc1101_ext_interconnect.h>
```

To select the internal radio device, use the following:
```c
    // Populate the CC101 device list.
    subghz_devices_init();

    // Get the internal radio device.
    const SubGhzDevice* device = subghz_devices_get_by_name(SUBGHZ_DEVICE_CC1101_INT_NAME);
```

**TODO:** I will add information about the external radio later.  But the basic steps are: To select the external radio device, you would use SUBGHZ_DEVICE_CC1101_EXT_NAME instead.  You would then want to enable +5 pin (if the external device is using a voltage regulator to convert 5-volts to 3.3-volts).  You would also want to add detection to ensure the device is connected.  Any when your application exits, it should disable the 5-volt pin.

## Send Asynchronous transfer
The CC1101 supports asynchronous transfer mode, which uses a GPIO pin for transmitting data asynchronously.  The Sub-GHz tool uses the method to transfer .SUB files.

Include these header files:
```c
#include <devices/cc1101_int/cc1101_int_interconnect.h>
#include <devices/devices.h>
#include <flipper_format_i.h>
#include <lib/subghz/transmitter.h>
#include <subghz_protocol_registry.h>
```

Determine the name of the protocol you want to use for transmitting.  You can find it by opening [./lib/subghz/protocols/protocol_items.c](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/lib/subghz/protocols/protocol_items.c) in your firmware.  Go to the definition of the entry you want, for example ``subghz_protocol_princeton``.  There you will see a .name field getting set, for example ``.name = SUBGHZ_PROTOCOL_PRINCETON_NAME,``.  Go to the definition of the name, for example ``#define SUBGHZ_PROTOCOL_PRINCETON_NAME "Princeton"``.


Get the ``SubGhzTransmitter`` for the protocol we want to transmit:
```c
// TODO: I think we could use subghz_protocol_princeton.name instead of "Priceton"?
char* protocol = "Princeton";
SubGhzEnvironment* environment = subghz_environment_alloc();
subghz_environment_set_protocol_registry(environment, (void*)&subghz_protocol_registry);
SubGhzTransmitter* transmitter = subghz_transmitter_alloc_init(environment, protocol);
```

Next, you need to determine all of the properties that the deserialize will access.  It is often helpful to look at a .SUB file to understand the fields to set. You can also look at the protocols ``deserialize`` method, which may contain additional fields typically not present in the .SUB file; such as ``Repeat``.  For example, [subghz_protocol_encoder_princeton_deserialize](https://github.com/flipperdevices/flipperzero-firmware/blob/4ade0fc76d541ddeffb17f732383e3b8438c0949/lib/subghz/protocols/princeton.c#L145)

Load the data into the ``FlipperFormat``:
```c
FlipperFormat* flipper_format = flipper_format_string_alloc();
uint32_t bits = 24;
uint32_t te = 390;
uint32_t guard_time = 31;
uint32_t repeat = 5;
uint32_t key = 0x967AB4;
uint8_t data[8] = {0};
data[5] = (uint8_t)((key >> 16) & 0xFFU);
data[6] = (uint8_t)((key >> 8) & 0xFFU);
data[7] = (uint8_t)(key & 0xFFU);
flipper_format_insert_or_update_string_cstr(flipper_format, "Protocol", "Princeton");
flipper_format_insert_or_update_uint32(flipper_format, "Bit", &bits, 1);
flipper_format_insert_or_update_hex(flipper_format, "Key", data, COUNT_OF(data));
flipper_format_insert_or_update_uint32(flipper_format, "TE", &te, 1);
flipper_format_insert_or_update_uint32(flipper_format, "Guard_time", &guard_time, 1);
flipper_format_insert_or_update_uint32(flipper_format, "Repeat", &repeat, 1);
flipper_format_rewind(flipper_format);
```

Deserialize the FlipperFormat into your ``SubGhzTransmitter``.  For example, for Princeton this will fill out the SubGHzTransmitter's  ``SubGhzProtocolDecoderPrinceton`` (which includes ``SubGhzBlockGeneric`` data) based on parsing the FlipperFormat.  It will also populate ``initance->encoder.upload[]`` with duration and level information (You can think of this as the RAW data timings).
```c
    SubGhzProtocolStatus status = subghz_transmitter_deserialize(transmitter, flipper_format);
    furi_assert(status == SubGhzProtocolStatusOk);
```

Next do some initialization:
```c
    subghz_devices_init();
    const SubGhzDevice* device = subghz_devices_get_by_name(SUBGHZ_DEVICE_CC1101_INT_NAME);
    subghz_devices_begin(device);
    subghz_devices_reset(device);
```

Then load the CC1101 preset that you wish to use. Use one of the presets in [./lib/subghz/devices/preset.h](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/lib/subghz/devices/preset.h).  If the first argument is ``FuriHalSubGhzPresetCustom``, then the second argument is a custom register table (Reg, value, Reg, value, ...,0, 0, PATable [0..7] entries).
```c
    subghz_devices_load_preset(device, FuriHalSubGhzPresetOok650Async, NULL);
```

Set the frequency you want to transmit on:
```c
    uint32_t frequency = 433920000;
    // Set the frequency, RF switch path (band), calibrates the oscillator on the CC1101.
    frequency = subghz_devices_set_frequency(device, frequency);
```

Stop charging the battery while transmitting:
```c
    furi_hal_power_suppress_charge_enter();
```

Transmit the data:
```c
    // Start transmitting (keeps the DMA buffer filled with the encoder.upload[] data)
    if(subghz_devices_start_async_tx(device, subghz_transmitter_yield, transmitter)) {
        // Wait for the transmission to complete.
        while(!(subghz_devices_is_async_complete_tx(device))) {
            furi_delay_ms(100);
        }

        // Stop transmitting, debug log (tag="FuriHalSubGhz") the duty cycle information.
        subghz_devices_stop_async_tx(device);
    }
```

Shutdown the device:
```c
    subghz_devices_sleep(device);
    subghz_devices_end(device);
```

Remove the devices from the registry:
```c
    subghz_devices_deinit();
```

Allow the battery to charge again:
```c
    furi_hal_power_suppress_charge_exit();
```

Free resources we allocated:
```c
    flipper_format_free(flipper_format);
    subghz_transmitter_free(transmitter);
    subghz_environment_free(environment);
```

## Send Synchronous transfer 
The CC1101 supports synchronous transfer mode, where the data is sent to the CC1101 and the protocol is processed on the chip.  The Sub-GHz CLI chat application uses the method to transfer text messages to nearby Flipper Zeros.

Include this header file:
```c
#include <lib/subghz/subghz_tx_rx_worker.h>
```

Allocate the worker: 
```c
    subghz_txrx = subghz_tx_rx_worker_alloc();
```

Start the worker thread:
```c
    uint32_t frequency = 433920000;
    subghz_devices_init();
    const SubGhzDevice* device = subghz_devices_get_by_name(SUBGHZ_DEVICE_CC1101_INT_NAME);
    if(subghz_tx_rx_worker_start(subghz_txrx, device, frequency)) {
        subghz_tx_rx_worker_set_callback_have_read(
            demo_context->subghz_txrx, subghz_demo_worker_update_rx_event_callback, demo_context);
    }
```

Stop charging the battery while transmitting:
```c
    furi_hal_power_suppress_charge_enter();
```

Convert message to byte stream:
```c
    FuriString* furi_message = furi_string_alloc();
    furi_string_printf(furi_message, "Hello Sub-GHz CLI Chat!");
    uint8_t* message = (uint8_t*)furi_string_get_cstr(furi_message);
    size_t length = strlen((char*)message);
    furi_assert(length < 60);
```

Send the message:
```c
    while(!subghz_tx_rx_worker_write(subghz_txrx, message, length)) {
        // Wait a few milliseconds on failure before trying to send again.
        furi_delay_ms(20);
    }
```

Stop and free the worker thread:
```c
    if(subghz_tx_rx_worker_is_running(demo_context->subghz_txrx)) {
        subghz_tx_rx_worker_stop(demo_context->subghz_txrx);
    }
    subghz_tx_rx_worker_free(demo_context->subghz_txrx);
```

Remove the devices from the registry:
```c
    subghz_devices_deinit();
```

Allow the battery to charge again:
```c
    furi_hal_power_suppress_charge_exit();
```

Free resources we allocated:
```c
   furi_string_free(furi_message);
```
