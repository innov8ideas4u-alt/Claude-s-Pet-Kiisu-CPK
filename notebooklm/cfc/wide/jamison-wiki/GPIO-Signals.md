# General Purpose Input/Output

This page is focused on how you can send different signals on the GPIO pins of the Flipper Zero.  The timing of the signal you need to send will depend on the hardware attached.  For example, a LED can obtain a specific brightness using pulse-width modulation (PWM) at a certain frequency - basically blink it really quickly [high frequency] and then change the percentage of the time the LED is on [duty cycle].  You may have more advanced devices, where you are trying to simulate some wire protocol (like controlling a WS2812B device).  This page walks through multiple approaches for sending the signal.  In general, try to do the simplest one that works so that other people will be able to understand your code & you can maintain the code.

Pin A7 is tied to TIM1 CH1N signal, and the TIM1 timer has lots of advanced features.  The disadvantage is TIM1 may be in use if you are doing things like IR or SUB-GHZ communication.  In those cases, it may make sense to use a different timer.  Also, if your circuit isn't connected to pin A7 but instead is connected to a different GPIO pin, then you may want to use the timer associate with that pin.  You could use Direct Memory Access (DMA) to write directly to the `BSRR` register of a different pin at the end of the timer event (this works for Toggle but not for PWM).

In the examples here, we typically take the 64 MHz clock from the Flipper Zero and divide it by 64000; so timings are in ms.  If you are dealing with quicker signals, you can use a different value instead of 64000-1.  For Prescaler & Autoreload don't forget that the counting starts at 0 so you typically want to subtract 1 from the value.  For example, if you want something that happens every 16 times, use a value of 16-1 (so it will count 0..15).

If you are new to timers, I recommend watching my [YouTube timer concepts](https://youtu.be/BvslnSeU1F4) video.

## Signals

### Bit-Banging and GPIO write
One approach is to use `furi_hal_gpio_write` to set the logic level of a pin.  You can then delay using `furi_delay_ms` or `furi_delay_us` for the appropriate time until you transition the logic level again.  One challenge with this approach is to remember that the instructions also take some amount of time, so delays in the us may not be accurate.  Also, your process could get interrupted, so you may want to request the scheduler to not switch away from your process using `furi_kernel_lock`. 

In this example, we use configure pin A7 as OutputPushPull. calling gpio_write with `true` will cause the pin to be 3.3 volts; while writing a `false` will cause the pin to be 0.0 volts.  We create 20 pulses, and we wait 150ms between each toggle. 150+150 = 300ms, which is a frequency of 3.333 Hz with a duty cycle of 50%.

```c
#include <furi_hal.h>

void bit_bang_with_gpio_write() {
  furi_hal_gpio_write(&gpio_ext_pa7, true);
  furi_hal_gpio_init(&gpio_ext_pa7, GpioModeOutputPushPull, GpioPullNo, GpioSpeedVeryHigh);
  for(int i = 0; i < 20; i++) {
    furi_hal_gpio_write(&gpio_ext_pa7, true);
    furi_delay_ms(150);
    furi_hal_gpio_write(&gpio_ext_pa7, false);
    furi_delay_ms(150);
  }

  // Uninit GPIO
  furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);
}
```

- `furi_hal_gpio_init(&gpio_ext_pa7, GpioModeOutputPushPull, GpioPullNo, GpioSpeedVeryHigh);` configures pin A7 (`&gpio_ext_pa7`).  `GpioModeOutputPushPull` means that a true will be 3.3 volts and a false will be 0 volts.  `GpioPullNo` means no internal resistor will be connected to 3V3 or GND.
- The initial `furi_hal_gpio_write(&gpio_ext_pa7, true);` before the init call helps prevent the signal from going to low when we initialize it.
- `furi_hal_gpio_write(&gpio_ext_pa7, true);` sets pin A7 (`&gpio_ext_pa7`) to true; or 3.3 volts.
- `furi_hal_gpio_write(&gpio_ext_pa7, false);` sets pin A7 (`&gpio_ext_pa7`) to false; or 0 volts.
- `furi_delay_ms(150);` delays 150 milliseconds (or 0.15 seconds), but in practice this call will takes around 151ms.  You can use `furi_delay_us` instead and specify a delay using microseconds which will be closer.  You can also measure with a logic analyzer and then subtract off the error to get an even more accurate timing.
- `furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);` causes pin A7 (`&gpio_ext_pa7`) to be an Analog input (`GpioModeAnalog`) which has the effect of making the pin float (mostly open circuit) instead of trying to force a voltage of 0 or 3.3 volts.

### Bit-Banging and Register write
Another approach is to use write the port's `BSRR` register to set the logic level of a pin.  This is similar to the previous example; except we use a register to set (`GPIO_BSRR_BS0_Pos`) or reset (`GPIO_BSRR_BR0_Pos`) the logic level.  In general, it's recommended what you use `furi_hal_gpio_write` instead of directly manipulating registers.  Later when we learn about DMA, knowing that there is a memory address `&gpio_ext_pa7.port->BSRR` that you can write values to (`gpio_ext_pa7.pin << GPIO_BSRR_BS0_Pos`, `gpio_ext_pa7.pin << GPIO_BSRR_BR0_Pos`) can be helpful.

```c
#include <furi_hal.h>

void bit_bang_with_register_write() {
  furi_hal_gpio_write(&gpio_ext_pa7, true);
  furi_hal_gpio_init(&gpio_ext_pa7, GpioModeOutputPushPull, GpioPullNo, GpioSpeedVeryHigh);
  for(int i = 0; i < 20; i++) {
    gpio_ext_pa7.port->BSRR = gpio_ext_pa7.pin << GPIO_BSRR_BS0_Pos;
    furi_delay_ms(150);
    gpio_ext_pa7.port->BSRR = gpio_ext_pa7.pin << GPIO_BSRR_BR0_Pos;
    furi_delay_ms(150);
  }

  // Uninit GPIO
  furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);
}
```

### FURI HAL PWM
There is a nice library if you want to output a pulse-width modulation (PWM) signal at a given frequency (in Hertz) and duty cycle.  This API is easy to use, and it automatically initializes the GPIO pin A7 for output.  Internally this uses `TIM1` to generate the signal on `CH1N` using `GpioAltFn1TIM1`.  This API allows you to start a PWM signal on pin A7 and then your code can do other things without having to worry about the pin.  The disadvantage of this API is the frequency is an uint32_t, so you can only set integer amounts (like 3Hz or 4Hz) instead of some fractional speed like 3.333 Hz.

```c
#include <furi.h>
#include <furi_hal_pwm.h>

void furi_hal_pwm() {
  furi_hal_pwm_start(FuriHalPwmOutputIdTim1PA7, 4, 50); // Pin A7, 4 Hz, 50% duty cycle
  furi_delay_ms(5000); // Wait 5 seconds
  furi_hal_pwm_stop(FuriHalPwmOutputIdTim1PA7); // Turn off pin A7.
}
```

- `furi_hal_pwm_start(FuriHalPwmOutputIdTim1PA7, 4, 50);` will configure PWM for pin A7 (`FuriHalPwmOutputIdTim1PA7`).  The `4` is the frequency, so this means you will have 4 cycles per second.  The `50` is the percentage of time the signal will be high.  A frequency of 4 means `1.0 second/4` = 250ms per cycle.  At 50% duty cycle means pin A7 will be 3.3 Volts for 125ms, then it will fall to 0 volts for the remainder of the time (125ms); then the signal will repeat.

### Timer GPIO
You can use a Timer API to control GPIO.  The Timer has Alternate functions that can be tied to particular GPIO pins.  It is also possible to use interrupt code or Direct Memory Access (DMA) to toggle a GPIO pin, which may be required if the GPIO pin doesn't have a timer associated with it.

|Pin|Fn|Timer|
|--|--|--|
|Pin A7 | GpioAltFn1TIM1 | TIM1, CH1N
|Pin A6 | GpioAltFn14TIM16 | TIM16, CH1
|Pin A4 | GpioAltFn14LPTIM2 | LPTIM2, OUT
|Pin A14 (SWC) | GpioAltFn1LPTIM1 | LPTIM1, OUT
|Pin B14 (1W) | GpioAltFn1TIM1 | TIM1, CH2N
|Pin B7 (RX) | GpioAltFn14TIM17 | TIM17, CH1N
|Pin B6 (TX) | GpioAltFn14TIM16 | TIM16, CH1N
|Pin B3 | GpioAltFn1TIM2 | TIM2, CH2
|Pin B2 | GpioAltFn1LPTIM1 | LPTIM1, OUT
|Pin C1 | GpioAltFn1LPTIM1 | LPTIM1, OUT

### Timer Toggle
Below is an example of using a timer (TIM1) with CH1N to control pin A7 in Toggle mode.  The Flipper Zero runs with an internal clock at 64000000 Hz.  We divide that frequency using `DIV1`, giving us the same 64000000 Hz.  We then trigger with a prescaler of 64000-1, so every 64000 input we get one pulse.  This means we have 1000 pulses per second (1 kHz) or a pulse every 1ms.  We set an Autoreload to 150-1 (so every 150 pulses, which is 150ms) we have an event.  We set the event to OCMODE_TOGGLE so we toggle between HIGH and LOW output on CH1N.  The result is a toggle every 150ms, so 150ms+150ms = 300ms, which is a frequency of 3.333 Hz with a duty cycle of 50%.

```c
#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>

void toggle() {
    furi_hal_gpio_init_ex(
        &gpio_ext_pa7, GpioModeAltFunctionPushPull, GpioPullNo, GpioSpeedVeryHigh, GpioAltFn1TIM1);

    furi_hal_bus_enable(FuriHalBusTIM1);

    LL_TIM_InitTypeDef tim_init = {
        .CounterMode = LL_TIM_COUNTERMODE_UP,
        .ClockDivision = LL_TIM_CLOCKDIVISION_DIV1,
        .Prescaler = 64000 - 1,
        .RepetitionCounter = 0,
        .Autoreload = 150 - 1,
    };
    LL_TIM_Init(TIM1, &tim_init);
    LL_TIM_SetClockSource(TIM1, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_EnableARRPreload(TIM1);

    LL_TIM_OC_InitTypeDef tim_oc_init = {
        .OCMode = LL_TIM_OCMODE_TOGGLE,
        .OCNPolarity = LL_TIM_OCPOLARITY_HIGH,
        .OCNState = LL_TIM_OCSTATE_ENABLE,
        .OCNIdleState = LL_TIM_OCIDLESTATE_LOW,
        // In this example, we are only using CH1N so we don't need to set these...
        //.OCPolarity = LL_TIM_OCPOLARITY_HIGH,
        //.OCState = LL_TIM_OCSTATE_ENABLE,
        //.OCIdleState = LL_TIM_OCIDLESTATE_LOW,
    };
    LL_TIM_OC_Init(TIM1, LL_TIM_CHANNEL_CH1, &tim_oc_init);
    LL_TIM_CC_EnableChannel(TIM1, LL_TIM_CHANNEL_CH1N);
    LL_TIM_EnableCounter(TIM1);
    LL_TIM_EnableAllOutputs(TIM1);
}

void toggle_done() {
    // Uninit GPIO
    furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);

    LL_TIM_DisableAllOutputs(TIM1);
    LL_TIM_DisableCounter(TIM1);
    furi_hal_bus_disable(FuriHalBusTIM1);
}
```

- `RepetitionCounter` is a counter value that decrements at the end of each cycle.  When it goes negative, any Direct Memory Access (DMA) action will occur.  We will use this counter later for counting a given number of pulses, but for now our examples will set this to 0.

### Timer PWM
Below is an example of using a timer (TIM1) with CH1N to control pin A7 in PWM mode.  The Flipper Zero runs with an internal clock at 64000000 Hz.  We divide that frequency using `DIV1`, giving us the same 64000000 Hz.  We then trigger with a prescaler of 64000-1, so every 64000 input we get one pulse.  This means we have 1000 pulses per second (1 kHz).  We set an `Autoreload` to 300-1 (so every 300 pulses, which is 300ms) we have an event (the end of our PWM signal).  We set the event to `OCMODE_PWM1` so we have a PWM output on CH1N.  We set the `CompareValue` to 1/2 of our `Autoreload `value, so when the count matches the CompareValue (on the 150th pulse) we will go from HIGH to LOW for the remainder of the cycle.  The result is a PWM of 300ms, which is a frequency of 3.333 Hz with a duty cycle of 50% (due to our CompareValue being 50% of the Autoreload.)

```c
#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>

void pwm() {
    furi_hal_gpio_init_ex(
        &gpio_ext_pa7, GpioModeAltFunctionPushPull, GpioPullNo, GpioSpeedVeryHigh, GpioAltFn1TIM1);

    furi_hal_bus_enable(FuriHalBusTIM1);

    LL_TIM_InitTypeDef tim_init = {
        .CounterMode = LL_TIM_COUNTERMODE_UP,
        .ClockDivision = LL_TIM_CLOCKDIVISION_DIV1,
        .Prescaler = 64000 - 1,
        .RepetitionCounter = 0,
        .Autoreload = 300 - 1,
    };
    LL_TIM_Init(TIM1, &tim_init);
    LL_TIM_SetClockSource(TIM1, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_EnableARRPreload(TIM1);

    LL_TIM_OC_InitTypeDef tim_oc_init = {
        .CompareValue = tim_init.Autoreload / 2,
        .OCMode = LL_TIM_OCMODE_PWM1,
        .OCNPolarity = LL_TIM_OCPOLARITY_HIGH,
        .OCNState = LL_TIM_OCSTATE_ENABLE,
        .OCNIdleState = LL_TIM_OCIDLESTATE_LOW,
        // In this example, we are only using CH1N so we don't need to set these...
        //.OCPolarity = LL_TIM_OCPOLARITY_HIGH,
        //.OCState = LL_TIM_OCSTATE_ENABLE,
        //.OCIdleState = LL_TIM_OCIDLESTATE_LOW,
    };
    LL_TIM_OC_Init(TIM1, LL_TIM_CHANNEL_CH1, &tim_oc_init);
    // EnablePreload for the CompareValue to work...
    LL_TIM_OC_EnablePreload(TIM1, LL_TIM_CHANNEL_CH1N);
    LL_TIM_CC_EnableChannel(TIM1, LL_TIM_CHANNEL_CH1N);
    LL_TIM_EnableCounter(TIM1);
    LL_TIM_EnableAllOutputs(TIM1);
}

void pwm_done() {
    // Uninit GPIO
    furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);

    LL_TIM_DisableAllOutputs(TIM1);
    LL_TIM_DisableCounter(TIM1);
    furi_hal_bus_disable(FuriHalBusTIM1);
}
```

### Toggle using DMA to update duration
In this example we use Direct Memory Access (DMA) to update the timer's `ARR` register (which is the Autoreload counter).  We configure DMA to read the word (32-bit) values from a buffer, incrementing the index, running in a circular mode (when it gets to the end it loops back to the start of the buffer).  We write to the `AAR` register` and don't increment (so each write is to the Autoreload counter).  We do the DMA action each time TIM1 completes.

```c
#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>

uint32_t durations[] = {100 - 1, 100 - 1, 200 - 1, 200 - 1, 500 - 1, 500 - 1, 1000 - 1, 1000 - 1};

void toggle_with_dma_duration() {
    LL_DMA_InitTypeDef dma_led_transition_timer = {
        .Direction = LL_DMA_DIRECTION_MEMORY_TO_PERIPH,
        .PeriphOrM2MSrcAddress = (uint32_t)&TIM1->ARR,
        .PeriphOrM2MSrcIncMode = LL_DMA_PERIPH_NOINCREMENT,
        .PeriphOrM2MSrcDataSize = LL_DMA_PDATAALIGN_WORD,
        .MemoryOrM2MDstAddress = (uint32_t)durations,
        .MemoryOrM2MDstIncMode = LL_DMA_MEMORY_INCREMENT,
        .MemoryOrM2MDstDataSize = LL_DMA_MDATAALIGN_WORD,
        .Mode = LL_DMA_MODE_CIRCULAR,
        .NbData = COUNT_OF(durations),
        .PeriphRequest = LL_DMAMUX_REQ_TIM1_UP,
        .Priority = LL_DMA_PRIORITY_HIGH,
    };
    LL_DMA_Init(DMA1, LL_DMA_CHANNEL_1, &dma_led_transition_timer);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_1);

    furi_hal_gpio_init_ex(
        &gpio_ext_pa7, GpioModeAltFunctionPushPull, GpioPullNo, GpioSpeedVeryHigh, GpioAltFn1TIM1);

    furi_hal_bus_enable(FuriHalBusTIM1);

    LL_TIM_InitTypeDef tim_init = {
        .CounterMode = LL_TIM_COUNTERMODE_UP,
        .ClockDivision = LL_TIM_CLOCKDIVISION_DIV1,
        .Prescaler = 64000 - 1,
        .RepetitionCounter = 0,
        .Autoreload = 100 - 1,
    };
    LL_TIM_Init(TIM1, &tim_init);
    LL_TIM_SetClockSource(TIM1, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_EnableARRPreload(TIM1);

    LL_TIM_OC_InitTypeDef tim_oc_init = {
        .OCMode = LL_TIM_OCMODE_TOGGLE,
        .OCNPolarity = LL_TIM_OCPOLARITY_HIGH,
        .OCNState = LL_TIM_OCSTATE_ENABLE,
        .OCNIdleState = LL_TIM_OCIDLESTATE_LOW,
    };
    LL_TIM_OC_Init(TIM1, LL_TIM_CHANNEL_CH1, &tim_oc_init);
    LL_TIM_EnableAllOutputs(TIM1);
    LL_TIM_EnableCounter(TIM1);
    LL_TIM_EnableUpdateEvent(TIM1);
    LL_TIM_EnableDMAReq_UPDATE(TIM1);
    LL_TIM_GenerateEvent_UPDATE(TIM1);
}

void toggle_dma_done() {
    // Uninit GPIO
    furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);

    LL_TIM_DisableDMAReq_UPDATE(TIM1);
    LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_1);

    LL_TIM_DisableAllOutputs(TIM1);
    LL_TIM_DisableCounter(TIM1);
    furi_hal_bus_disable(FuriHalBusTIM1);
}
```

### PWM using DMA to update duty cycle
In this example we use Direct Memory Access (DMA) to update the timer's `CCR1` register (which is the CompareValue).  We configure DMA to read the word (32-bit) values from a buffer, incrementing the index, running in a circular mode (when it gets to the end it loops back to the start of the buffer).  We write to the `CCR1` register` and don't increment (so each write is to the CompareValue counter).  We do the DMA action each time TIM1 completes (each cycle we update the duty cycle).

```c
#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>

uint32_t duty_cycles[] =
    {10 - 1, 20 - 1, 30 - 1, 40 - 1, 50 - 1, 60 - 1, 70 - 1, 80 - 1, 90 - 1, 100 - 1};

void pwm_dma_duty() {
    LL_DMA_InitTypeDef dma_led_transition_timer = {
        .Direction = LL_DMA_DIRECTION_MEMORY_TO_PERIPH,
        .PeriphOrM2MSrcAddress = (uint32_t)&TIM1->CCR1,
        .PeriphOrM2MSrcIncMode = LL_DMA_PERIPH_NOINCREMENT,
        .PeriphOrM2MSrcDataSize = LL_DMA_PDATAALIGN_WORD,
        .MemoryOrM2MDstAddress = (uint32_t)duty_cycles,
        .MemoryOrM2MDstIncMode = LL_DMA_MEMORY_INCREMENT,
        .MemoryOrM2MDstDataSize = LL_DMA_MDATAALIGN_WORD,
        .Mode = LL_DMA_MODE_CIRCULAR,
        .NbData = COUNT_OF(duty_cycles),
        .PeriphRequest = LL_DMAMUX_REQ_TIM1_UP,
        .Priority = LL_DMA_PRIORITY_HIGH,
    };
    LL_DMA_Init(DMA1, LL_DMA_CHANNEL_1, &dma_led_transition_timer);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_1);

    furi_hal_gpio_init_ex(
        &gpio_ext_pa7, GpioModeAltFunctionPushPull, GpioPullNo, GpioSpeedVeryHigh, GpioAltFn1TIM1);

    furi_hal_bus_enable(FuriHalBusTIM1);

    LL_TIM_InitTypeDef tim_init = {
        .CounterMode = LL_TIM_COUNTERMODE_UP,
        .ClockDivision = LL_TIM_CLOCKDIVISION_DIV1,
        .Prescaler = 64000 - 1,
        .RepetitionCounter = 0,
        .Autoreload = 100 - 1,
    };
    LL_TIM_Init(TIM1, &tim_init);
    LL_TIM_SetClockSource(TIM1, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_EnableARRPreload(TIM1);

    LL_TIM_OC_InitTypeDef tim_oc_init = {
        .OCMode = LL_TIM_OCMODE_PWM1,
        .CompareValue = 5, // set by DMA
        .OCNPolarity = LL_TIM_OCPOLARITY_HIGH,
        .OCNState = LL_TIM_OCSTATE_ENABLE,
        .OCNIdleState = LL_TIM_OCIDLESTATE_LOW,
    };
    LL_TIM_OC_Init(TIM1, LL_TIM_CHANNEL_CH1, &tim_oc_init);
    LL_TIM_OC_EnablePreload(TIM1, LL_TIM_CHANNEL_CH1); // TIM1_CCR1
    LL_TIM_EnableAllOutputs(TIM1);
    LL_TIM_EnableCounter(TIM1);
    LL_TIM_EnableUpdateEvent(TIM1);
    LL_TIM_EnableDMAReq_UPDATE(TIM1);
    LL_TIM_GenerateEvent_UPDATE(TIM1);
}

void pwm_dma_done() {
    // Uninit GPIO
    furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);

    LL_TIM_DisableDMAReq_UPDATE(TIM1);
    LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_1);

    LL_TIM_DisableAllOutputs(TIM1);
    LL_TIM_DisableCounter(TIM1);
    furi_hal_bus_disable(FuriHalBusTIM1);
}
```

### PWM using DMA to update duty cycle and ISR to update DMA buffer
In this example we use Direct Memory Access (DMA) to update the timer's `CCR1` register (which is the CompareValue).  We configure DMA to read the word (32-bit) values from a buffer, incrementing the index, running in a circular mode (when it gets to the end it loops back to the start of the buffer).  We write to the `CCR1` register` and don't increment (so each write is to the CompareValue counter).  We do the DMA action each time TIM1 completes (each cycle we update the duty cycle).

The DMA buffer we are reading from is configured in our interrupt routine.  At the Half-Transfer (HT) point we fill the inactive buffer with data.  At the Transfer-Complete (TC) point we swap buffers that DMA1 CH1 is using.  This allows us to have two small buffers that we keep changing the data in, without having to precompute the entire signal.  NOTE: The interrupt routine at the HT needs to be quick enough to finish computing the other buffer data before the TC point is reached.  This technique may be useful if you have a compact way of representing data, but the GPIO wire protocol has many values (e.g. a byte of data may translate to 16+ DMA values, like start-bit, stop-bit, data bits, parity, etc.)

```c
#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>

uint32_t buff1[8] = {99, 99, 99, 99, 99, 99, 99, 99};
uint32_t buff2[8] = {0};
volatile bool buff1_is_active = true;
volatile uint32_t delay = 100;

static void dma_isr(void* context) {
    UNUSED(context);

    if(LL_DMA_IsActiveFlag_HT1(DMA1)) {
        LL_DMA_ClearFlag_HT1(DMA1);
        delay += 100;
        if(delay > 400) {
            delay = 100;
        }
        uint32_t* buff = (!buff1_is_active) ? buff1 : buff2;
        for(size_t i = 0; i < COUNT_OF(buff1); i++) {
            buff[i] = delay - 1;
        }
    }

    if(LL_DMA_IsActiveFlag_TC1(DMA1)) {
        LL_DMA_ClearFlag_TC1(DMA1);
        buff1_is_active = !buff1_is_active;
        if(buff1_is_active) {
            LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_1, (uint32_t)buff1);
        } else {
            LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_1, (uint32_t)buff2);
        }
    }
}

void toggle_with_dma_duration_isr_buffer() {
    LL_DMA_InitTypeDef dma_led_transition_timer = {
        .Direction = LL_DMA_DIRECTION_MEMORY_TO_PERIPH,
        .PeriphOrM2MSrcAddress = (uint32_t)&TIM1->ARR,
        .PeriphOrM2MSrcIncMode = LL_DMA_PERIPH_NOINCREMENT,
        .PeriphOrM2MSrcDataSize = LL_DMA_PDATAALIGN_WORD,
        .MemoryOrM2MDstAddress = (uint32_t)buff1,
        .MemoryOrM2MDstIncMode = LL_DMA_MEMORY_INCREMENT,
        .MemoryOrM2MDstDataSize = LL_DMA_MDATAALIGN_WORD,
        .Mode = LL_DMA_MODE_CIRCULAR,
        .NbData = COUNT_OF(buff1),
        .PeriphRequest = LL_DMAMUX_REQ_TIM1_UP,
        .Priority = LL_DMA_PRIORITY_HIGH,
    };
    LL_DMA_Init(DMA1, LL_DMA_CHANNEL_1, &dma_led_transition_timer);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_1);

    LL_DMA_ClearFlag_HT1(DMA1);
    LL_DMA_ClearFlag_TC1(DMA1);
    LL_DMA_EnableIT_HT(DMA1, LL_DMA_CHANNEL_1);
    LL_DMA_EnableIT_TC(DMA1, LL_DMA_CHANNEL_1);
    furi_hal_interrupt_set_isr_ex(FuriHalInterruptIdDma1Ch1, 4, dma_isr, NULL);

    furi_hal_gpio_init_ex(
        &gpio_ext_pa7, GpioModeAltFunctionPushPull, GpioPullNo, GpioSpeedVeryHigh, GpioAltFn1TIM1);

    furi_hal_bus_enable(FuriHalBusTIM1);

    LL_TIM_InitTypeDef tim_init = {
        .CounterMode = LL_TIM_COUNTERMODE_UP,
        .ClockDivision = LL_TIM_CLOCKDIVISION_DIV1,
        .Prescaler = 64000 - 1,
        .RepetitionCounter = 0,
        .Autoreload = 100 - 1,
    };
    LL_TIM_Init(TIM1, &tim_init);
    LL_TIM_SetClockSource(TIM1, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_EnableARRPreload(TIM1);

    LL_TIM_OC_InitTypeDef tim_oc_init = {
        .OCMode = LL_TIM_OCMODE_TOGGLE,
        .OCNPolarity = LL_TIM_OCPOLARITY_HIGH,
        .OCNState = LL_TIM_OCSTATE_ENABLE,
        .OCNIdleState = LL_TIM_OCIDLESTATE_LOW,
    };
    LL_TIM_OC_Init(TIM1, LL_TIM_CHANNEL_CH1, &tim_oc_init);
    LL_TIM_EnableAllOutputs(TIM1);
    LL_TIM_EnableCounter(TIM1);
    LL_TIM_EnableUpdateEvent(TIM1);
    LL_TIM_EnableDMAReq_UPDATE(TIM1);
    LL_TIM_GenerateEvent_UPDATE(TIM1);
}

void toggle_dma_isr_done() {
    // Uninit GPIO
    furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);

    furi_hal_interrupt_set_isr_ex(FuriHalInterruptIdDma1Ch1, 4, NULL, NULL);

    LL_TIM_DisableDMAReq_UPDATE(TIM1);
    LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_1);

    LL_TIM_DisableAllOutputs(TIM1);
    LL_TIM_DisableCounter(TIM1);
    furi_hal_bus_disable(FuriHalBusTIM1);
}
```

### PWM using DMA to update repetition counts and enabled output
In this example we use Direct Memory Access (DMA) CH1 to update the timer's `RCR` register (which is the RepetitionCounter).  We configure DMA to read the word (32-bit) values from a buffer, incrementing the index, running in a circular mode (when it gets to the end it loops back to the start of the buffer).  We write to the `RCR` register` and don't increment (so each write is to the Repetition counter).  The RepetitionCounter will decrement every time the Autoreload count is met, but the DMA actions will only fire when the RepetitionCounter is 0 & the Autoreload count is met.  This means the counter represents how many cycles to output.

We use DMA CH2 to update the timer's `CCMR1` register (which is the state of the OCMode).  We configure DMA to read the word value from a buffer, incrementing the index, running in a circular mode.  The data read switches between FORCED_INACTIVE (so GPIO PIN is LOW) vs PWM1 mode (so GPIO PIN is PWM signal).

In the below sample we blink 3, 5 and 8 times with a duty cycle of 75%. (Using PWM2, we are off for the first 100ms of the 400ms cycle) and a frequency of 1000/400 = 2.5 Hz.  We also have off for 2 cycles (800ms) between the blink counts (which is a total of 900ms because 800ms+100ms of the beginning off).

```c
#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>

// 3 pulses, 5 pulses, 8 pulses.
uint32_t counts[] = {3 - 1, 1, 5 - 1, 1, 8 - 1, 1};

#define CCMR_OFF LL_TIM_OCMODE_FORCED_INACTIVE
#define CCMR_ON LL_TIM_OCMODE_PWM1

uint32_t enabled[] = {CCMR_OFF, CCMR_ON};

void pwm_dma_repeat_enabled() {
    LL_DMA_InitTypeDef dma_led_transition_timer = {
        .Direction = LL_DMA_DIRECTION_MEMORY_TO_PERIPH,
        .PeriphOrM2MSrcAddress = (uint32_t)&TIM1->RCR,
        .PeriphOrM2MSrcIncMode = LL_DMA_PERIPH_NOINCREMENT,
        .PeriphOrM2MSrcDataSize = LL_DMA_PDATAALIGN_WORD,
        .MemoryOrM2MDstAddress = (uint32_t)counts,
        .MemoryOrM2MDstIncMode = LL_DMA_MEMORY_INCREMENT,
        .MemoryOrM2MDstDataSize = LL_DMA_MDATAALIGN_WORD,
        .Mode = LL_DMA_MODE_CIRCULAR,
        .NbData = COUNT_OF(counts),
        .PeriphRequest = LL_DMAMUX_REQ_TIM1_UP,
        .Priority = LL_DMA_PRIORITY_HIGH,
    };
    LL_DMA_Init(DMA1, LL_DMA_CHANNEL_1, &dma_led_transition_timer);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_1);

    LL_DMA_InitTypeDef dma_led_transition_enabled = {
        .Direction = LL_DMA_DIRECTION_MEMORY_TO_PERIPH,
        .PeriphOrM2MSrcAddress = (uint32_t)&TIM1->CCMR1,
        .PeriphOrM2MSrcIncMode = LL_DMA_PERIPH_NOINCREMENT,
        .PeriphOrM2MSrcDataSize = LL_DMA_PDATAALIGN_WORD,
        .MemoryOrM2MDstAddress = (uint32_t)enabled,
        .MemoryOrM2MDstIncMode = LL_DMA_MEMORY_INCREMENT,
        .MemoryOrM2MDstDataSize = LL_DMA_MDATAALIGN_WORD,
        .Mode = LL_DMA_MODE_CIRCULAR,
        .NbData = COUNT_OF(enabled),
        .PeriphRequest = LL_DMAMUX_REQ_TIM1_UP,
        .Priority = LL_DMA_PRIORITY_HIGH,
    };
    LL_DMA_Init(DMA1, LL_DMA_CHANNEL_2, &dma_led_transition_enabled);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_2);

    furi_hal_gpio_init_ex(
        &gpio_ext_pa7, GpioModeAltFunctionPushPull, GpioPullNo, GpioSpeedVeryHigh, GpioAltFn1TIM1);

    furi_hal_bus_enable(FuriHalBusTIM1);

    LL_TIM_InitTypeDef tim_init = {
        .CounterMode = LL_TIM_COUNTERMODE_UP,
        .ClockDivision = LL_TIM_CLOCKDIVISION_DIV1,
        .Prescaler = 64000 - 1,
        .RepetitionCounter = 0,
        .Autoreload = 400 - 1,
    };
    LL_TIM_Init(TIM1, &tim_init);
    LL_TIM_SetClockSource(TIM1, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_EnableARRPreload(TIM1);

    LL_TIM_OC_InitTypeDef tim_oc_init = {
        .OCMode = LL_TIM_OCMODE_FORCED_INACTIVE, // LL_TIM_OCMODE_PWM1,
        .CompareValue = 100 - 1,
        .OCNPolarity = LL_TIM_OCPOLARITY_HIGH,
        .OCNState = LL_TIM_OCSTATE_ENABLE,
        .OCNIdleState = LL_TIM_OCIDLESTATE_LOW,
    };
    LL_TIM_OC_Init(TIM1, LL_TIM_CHANNEL_CH1, &tim_oc_init);
    LL_TIM_OC_EnablePreload(TIM1, LL_TIM_CHANNEL_CH1); // TIM1_CCR1
    LL_TIM_EnableAllOutputs(TIM1);
    LL_TIM_EnableCounter(TIM1);
    LL_TIM_EnableUpdateEvent(TIM1);
    LL_TIM_EnableDMAReq_UPDATE(TIM1);
    LL_TIM_GenerateEvent_UPDATE(TIM1);
}

void pwm_dma_done() {
    // Uninit GPIO
    furi_hal_gpio_init(&gpio_ext_pa7, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);

    LL_TIM_DisableDMAReq_UPDATE(TIM1);
    LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_1);
    LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_2);

    LL_TIM_DisableAllOutputs(TIM1);
    LL_TIM_DisableCounter(TIM1);
    furi_hal_bus_disable(FuriHalBusTIM1);
}
```
