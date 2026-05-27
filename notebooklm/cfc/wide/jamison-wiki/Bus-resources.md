When you use certain Flipper Zero features, the code will end up calling `furi_hal_bus_enable` passing a bus to reserve.  On debug builds of the firmware there is a `furi_check` that makes sure no other code has already requested that bus.  If the resource is already in use, you will get a "Flipper crashed and was rebooted - furi_check failed" message if you are on a [Release] firmware (on a [Debug] firmware the Flipper may appear frozen - waiting for the debugger to attach - or until you press BACK+LEFT to reboot.)

NOTE: furi_check can happen for MANY reasons, but one reason is that `furi_hal_bus_enable` got called on the same bus twice.  

![furi_crash](https://github.com/user-attachments/assets/d1a19971-1e97-402a-b62e-6b3dd56bb01a)

The best way to tell the cause of the crash, is to attach a debugger and reproduce the crash.  And then click on the second function in the call stack.

![image](https://github.com/user-attachments/assets/330ef6fa-791e-49f4-8bbd-3be6a2d0156d)

The `.\targets\f7\furi_hal\furi_hal_bus.h` file lists the various choices for FuriHalBus.  Below is a table of common resources that use common timers that you may be using in your code.

| Feature | Bus |
| ------- | --- |
| iButton | FuriHalBusTIM1 |
| Infrared (RX) | FuriHalBusTIM2 |
| Infrared (TX) | FuriHalBusTIM1 |
| PWM (pin A7) | FuriHalBusTIM1 |
| PWM (pin A4) | FuriHalBusLPTIM2 |
| LF-RFID (READ) | FuriHalBusTIM1 & FuriHalBusTIM2 |
| LF-RFID (Emulate) | FuriHalBusTIM2 |
| NFC | FuriHalBusTIM1 & FuriHalBusTIM17 |
| SUB-GHZ (RX) | FuriHalBusTIM2 |
| SUB-GHZ (TX) | FuriHalBusTIM2 |

There are many more bus that may be in use, but I found this is a common one.  You should search the implementation files for `furi_hal_bus_enable` to understand which resources it uses. Typically the implementation files that use the bus are in `./targets/f7/furi_hal/furi_hal_<feature-name>.c`.  Sometimes they use a name that is redefined elsewhere in the file (for example `INFRARED_RX_TIMER_BUS` is a #define for `FuriHalBusTIM2`.)

```c
// Relevant #define from Official firmware (Sept 5, 2024)
IBUTTON: #define FURI_HAL_IBUTTON_TIMER_BUS FuriHalBusTIM1

INFRARED (RX): #define INFRARED_RX_TIMER_BUS  FuriHalBusTIM2
INFRARED (TX): #define INFRARED_DMA_TIMER_BUS FuriHalBusTIM1

PWM (PA7) :  furi_hal_bus_enable(FuriHalBusTIM1); 
PWM (PA4): furi_hal_bus_enable(FuriHalBusLPTIM2);

LF-RFID (READ): #define FURI_HAL_RFID_READ_TIMER_BUS FuriHalBusTIM1
                #define RFID_CAPTURE_TIM_BUS FuriHalBusTIM2
LF-RFID (EMULATE): #define FURI_HAL_RFID_EMULATE_TIMER_BUS FuriHalBusTIM2
                #define FURI_HAL_RFID_FIELD_COUNTER_TIMER_BUS FuriHalBusTIM2
LF-RFID (FIELD PRESENCE DETECT): #define FURI_HAL_RFID_FIELD_TIMEOUT_TIMER_BUS FuriHalBusTIM1

NFC: [FuriHalNfcTimerFwt] = {.bus = FuriHalBusTIM1,}
NFC: [FuriHalNfcTimerBlockTx] = {.bus = FuriHalBusTIM17,}

SUB-GHz (RX): furi_hal_bus_enable(FuriHalBusTIM2);
SUB-GHz (TX): furi_hal_bus_enable(FuriHalBusTIM2);
```