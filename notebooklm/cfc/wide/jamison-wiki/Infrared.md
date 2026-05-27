# Infrared
The Flipper Zero supports sending and receiving infrared signals.  From the main menu on the Flipper Zero, go to ``Infrared`` then choose ``Learn New Remote`` to create an .IR file or ``Saved Remotes`` to playback an .IR file.  If you don't have the original remote, you can also copy [existing .IR files](#resources) to the ``SD Card\infrared`` folder, for use in the Saved Remotes feature. 

## Protocols
The Flipper Zero registers infrared encoder/decoder protocol entries in ``lib\infrared\encoder_decoder\infrared.c``. 

|protocol|preamble|freq|pulse length|maximum address|maximum command|
|-|-|-|-|-|-|
|Samsung32|4500/4500| | | 8-bits (FF 00 00 00)| 8-bits (FF 00 00 00)|
|Kaseikyo|3360/1650 | | |26-bits (FF FF FF 03)|10-bits (FF 03 00 00)|
|NEC|9000/4500      | | | 8-bits (FF 00 00 00)| 8-bits (FF 00 00 00)|
|NECext|9000/4500   | | |16-bits (FF FF 00 00)|16-bits (FF FF 00 00)|
|NEC42|9000/4500    | | |13-bits (FF 1F 00 00)| 8-bits (FF 00 00 00)|
|NEC42ext|9000/4500 | | |26-bits (FF FF FF 03)|16-bits (FF FF 00 00)|
|RC5|none   |36kHz|888uS| 5-bits (1F 00 00 00)| 6-bits (3F 00 00 00)|
|RC5X|none  |36kHz|888uS| 5-bits (1F 00 00 00)| 7-bits (7F 00 00 00)|
|RC6|2666/889       | | | 8-bits (FF 00 00 00)| 8-bits (FF 00 00 00)|
|RCA|4000/4000      | | | 4-bits (0F 00 00 00)| 8-bits (FF 00 00 00)|
|SIRC|2400/600|  40kHz| | 5-bits (1F 00 00 00)| 7-bits (7F 00 00 00)|
|SIRC15|2400/600|40kHz| | 8-bits (FF 00 00 00)| 7-bits (7F 00 00 00)|
|SIRC20|2400/600|40kHz| |13-bits (FF 1F 00 00)| 7-bits (7F 00 00 00)|

## .IR File
You can create a demo.ir file and place it in ``SD Card\infrared`` folder to have it show up as a Saved Remote.  The .ir file can have multiple buttons, with a mix of protocols (and even raw entries).  Below is an example with three buttons:

```c
Filetype: IR signals file
Version: 1
#
# Example remote with 3 buttons.
# Power - Toggles power on TV.
# Mute - Toggles sound on TV.
# Fan_pwr - Toggles power on fan.
#
name: Power
type: parsed
protocol: Samsung32
address: 07 00 00 00
command: 02 00 00 00
# 
name: Mute
type: parsed
protocol: Samsung32
address: 07 00 00 00
command: 0F 00 00 00
#
name: Fan_pwr
type: raw
frequency: 38000
duty_cycle: 0.50000
data: 2100 700 700 700 700 700 700 1400 700 1400 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 1400 700 700 700 89600 2100 700 700 700 700 700 700 1400 700 1400 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 700 1400 700 700 700
```

### Comments 
- Start the line with a ``#`` character for comments.  You should put an empty comment between buttons, so it is easier to read.

### Fields (for type: parsed)
For **type: parsed** entry, the fields are as follows...
- The ``name`` field is the name of the button to show for the remote.  The remote only shows the first part of the name, so keep it small.
- The ``type`` field is ``parsed`` for a known protocol.  (It will be ``raw`` for unknown protocol.)
- The ``protocol`` field is the name of the protocol.
- The ``address`` field is a 4-byte value. The value ranges from ``00 00 00 00`` to whatever maximum is supported by the protocol.
- The ``command`` field is a 4-byte value. The value ranges from ``00 00 00 00`` to whatever maximum is supported by the protocol.

If the ``address`` or ``command`` is larger than the maximum value, an error will be logged and the parser will quit processing the file.

```
1173129 [I][InfraredRemote] load file: '/any/infrared/demo-bad1.ir'
1197599 [E][InfraredSignal] Command is out of range (mask 0x000000FF): 0x54241202
1173129 [I][InfraredRemote] load file: '/any/infrared/demo-bad2.ir'
1197599 [E][InfraredSignal] Address is out of range (mask 0x000000FF): 0x44332207
```

### Fields (for type: raw)
For **type: raw** entry, the fields are as follows...
- The ``name`` field is the name of the button to show for the remote.  The remote only shows the first part of the name, so keep it small.
- The ``type`` field is ``raw`` for an unknown protocol.  (It will be ``parsed`` for known protocols.)
- The ``frequency`` field is the frequency that the LED is pulsing when sending a signal.  This is typically 38000, but also 36000 and 40000 are fairly common values.
- The ``duty_cycle`` is the percentage of time (0 = 0%, 1.0 = 100%) the light is on during the pulse.  This is typically 0.33, but 0.25 and 0.4 are common values. 
- The ``data`` is a series of positive microsecond values.  The first number is ON, second is OFF, third is ON, etc.

## Fuzzing
Often a device will use only one address value.  You can try learning a few buttons on the remote, then create an .IR file using the same address but different command values.  Be sure to limit the command values from 0 to the maximum allowed value.  For devices like TVs, you may discover additional IR commands; such as jumping direct to a particular source, powering off the device (without powering on), etc.  Some devices may only react to certain input when you are in a particular mode (for example, CH+ on a TV might not do anything while you are in HDMI1 source instead of watching TV channels).  

Some devices are composite devices, like a TV in a hotel, and may have one set for the TV: Power, Vol, etc. and another set for STB (set-top box): Ch+, Ch-, D-Pad, etc.  In that case, looking at the TV power signal, you might be able to determine the signal to switch the **Input**.

**Warning:** Only perform fuzz testing on devices you have permission to test.  It's possible that some TVs don't default back to the proper input when power cycled.


## Resources
A good resource with a lot of Flipper Zero IR files is [Flipper-IRDB](https://github.com/UberGuidoZ/Flipper-IRDB)

## Generate files

### Known protocol
You can generate an IR file in Python using the following script.  Be sure to replace the protocol, address, cmd_min and cmd_max with your values.  The values in the file are LSB instead of MSB, so a value of "FF 03 00 00" is written as 0x3FF and a value of "21 43 00 00" is written as 0x4321.  It is recommended that the total number of buttons loaded be 256 or less.

```py
with open('demo.ir', 'w') as f:
    protocol = "NECext"
    address = "05 00 00 00"
    cmd_min = 0x4000
    cmd_max = 0x40FF

    f.write("Filetype: IR signals file\nVersion: 1\n")
    for i in range(cmd_min, cmd_max+1):
        cmd_hex_1 = hex(i % 256)[2:].zfill(2).upper()
        cmd_hex_2 = hex((i>>8) % 256)[2:].zfill(2).upper()
        cmd_hex_3 = hex((i>>16) % 256)[2:].zfill(2).upper()
        cmd_hex_4 = hex((i>>24) % 256)[2:].zfill(2).upper()
        cmd_str = f"#\nname: Cmd {cmd_hex_1} {cmd_hex_2} {cmd_hex_3} {cmd_hex_4}\n" \
                  "type: parsed\n" \
                  f"protocol: {protocol}\n" \
                  f"address: {address}\n" \
                  f"command: {cmd_hex_1} {cmd_hex_2} {cmd_hex_3} {cmd_hex_4}\n"
        f.write(cmd_str)
```

### Laser Tag files (RAW files)
The python script below generates signals for a [Winyea Tag Laser Tag Set](https://amzn.to/3ZwdYgE).  It generates entries with the last 4 bits trying all possible combinations, so you can discover the correct checksum value.  Try to change the gun_id, team or weapons to values not listed in the code!  For example, you can make a peaceful weapon that has "400 400 400 400" and won't take away any points but will still make the target vibrate.

```py
with open('gun.ir', 'w') as f:
    one_zero_pattern = "800 400 800 400 800 400 800 400" # 10101010
    zeros            = "400 400 400 400"                 # 0000  (space between properties)
    gun_id           = "400 800 800 400 400 400 400 400" # 01100000 (My first recorded gun ID, probably anything works?)
    team_blue        = "400 400 400 800"                 # Blue  (0001)
    team_red         = "400 400 800 400"                 # Red   (0010)
    team_green       = "400 400 800 800"                 # Green (0011)
    team_white       = "400 800 400 400"                 # White (0100)
    weapon_single    = "400 400 400 800"                 # Single shot (0001) 1 points
    weapon_laser     = "400 400 800 400"                 # Laser       (0010) 2 points
    weapon_plasma    = "400 400 800 800"                 # Plasma      (0011) 3 points
    weapon_tnt       = "800 400 400 800"                 # TNT         (1001) 9 points

    # Set the values for testing...
    team = team_red
    weapon = weapon_tnt

    cmd_min = 0   # 0000 checksum starts here
    cmd_max = 15  # 1111 checksum ends here
    f.write("Filetype: IR signals file\nVersion: 1\n")
    for i in range(cmd_min, cmd_max+1):
        cmd = hex(i)[2:].zfill(2).upper()
        checksum = ""
        checksum = checksum + "800 " if i & 0x8 else checksum + "400 "
        checksum = checksum + "800 " if i & 0x4 else checksum + "400 "
        checksum = checksum + "800 " if i & 0x2 else checksum + "400 "
        checksum = checksum + "800 " if i & 0x1 else checksum + "400 "
        cmd_str = f"#\nname: {cmd}\n" \
                "type: raw\n" \
                "frequency: 38000\n" \
                "duty_cycle: 0.330000\n" \
                f"data: 1600 {gun_id} {one_zero_pattern} {zeros} {team} {zeros} {weapon} {zeros} {checksum}\n"
        f.write(cmd_str)
```

## Flipper APIs

The Flipper Zero has APIs to send both known protocols (such as NEC or Samsung32) or RAW signal timings.

### Sending a known protocol

Include these header files:

```c
#include <infrared.h>
#include <infrared/infrared_signal.h>
```

Determine the protocol you want to use for transmitting. In this example, we will be using a "Samsung32" with an address of 0x07 and a command of 0x0F (which is the Mute button). Replace `Samsung32` with your protocol. Replace the `0x07` and `0x0F` to match your address and command. The easiest way to determine the value is `Infrared`, `Learn New Remote`, then press the button on the remote.

```c
    InfraredMessage message;
    message.protocol = infrared_get_protocol_by_name("Samsung32");
    message.address = 0x07;
    message.command = 0x0F;
    message.repeat = false;
    InfraredSignal* signal = infrared_signal_alloc();
    infrared_signal_set_message(signal, &message);
    if(infrared_signal_is_valid(signal)) {
        infrared_signal_transmit(signal);
    }
    infrared_signal_free(signal);
```

### Sending a RAW signal

Include these header files:

```c
#include <infrared.h>
#include <infrared/infrared_signal.h>
```

Determine the raw timing. The easiest way to determine the value is `Infrared`, `Learn New Remote`, then press the button on the remote. You should see `# samples` then click the right button to Save, name the button (for example, **RAW_power**) and click Save. Click Edit, then choose `Rename Remote`, type in a name for the remote and click Save. In qFlipper open the File Manager tab, then navigate to `SD Card/infrared`. Right click on the IR file matching the name of the remote you created, and choose `Download`. Open the file in a text editor.

```
Filetype: IR signals file
Version: 1
#
name: Raw_power
type: raw
frequency: 38000
duty_cycle: 0.330000
data: 2193 750 729 1421 777 1454 754 715 753 1478 751 719 728 715 753 716 773 1510 729 1501 728 1477 752 1505 755 1475 754 1477 721 749 751 772 696 102110 2246 748 720 1455 774 1430 747 723 746 1484 724 745 723 720 748 721 779 1477 752 1478 751 1480 749 1508 752 1478 751 1479 729 741 748 748 721 50743 2195 747 721 1454 775
```

Update the `frequency`, `duty_cycle` and the `data` below with the information from your file. Note: remember to add commas between data values!

```c
    InfraredSignal* signal = infrared_signal_alloc();
    uint32_t frequency = 38000;
    float duty_cycle = 0.33f;
    uint32_t timings[] = {2193, 750, 729, 1421, 777, 1454, 754, 715, 753, 1478, 751, 719, 728, 715, 753, 716, 773, 1510, 729, 1501, 728, 1477, 752, 1505, 755, 1475, 754, 1477, 721, 749, 751, 772, 696, 102110, 2246, 748, 720, 1455, 774, 1430, 747, 723, 746, 1484, 724, 745, 723, 720, 748, 721, 779, 1477, 752, 1478, 751, 1480, 749, 1508, 752, 1478, 751, 1479, 729, 741, 748, 748, 721, 50743, 2195, 747, 721, 1454, 775};
    size_t timings_size = COUNT_OF(timings);
    infrared_signal_set_raw_signal(signal, timings, timings_size, frequency, duty_cycle);
    if(infrared_signal_is_valid(signal)) {
        infrared_signal_transmit(signal);
    }
    infrared_signal_free(signal);
```
