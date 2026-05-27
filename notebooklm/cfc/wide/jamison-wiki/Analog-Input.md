For understanding analog sensors...
https://youtu.be/xRCe_3W-WAk?si=31TsBAtL3GYhSf0v

For reading analog voltage in C code... 
https://youtu.be/Dot2onogjqY?si=3749szGyiqmE9oiF

More advanced project in C code, leveraging analog sensors...
https://youtu.be/QzKk8iYSV80?si=H37EZ28NYriZ_j36

For reading analog voltage in JavaScript code...
https://youtu.be/ETn9E4L6EY0?si=-pS4Vh8yPhm_sgsh

```c
const GpioPin* adc_input_gpio = &gpio_ext_pc3;
const FuriHalAdcChannel adc_input_channel = FuriHalAdcChannel4;
FuriHalAdcHandle* adc_handle = furi_hal_adc_acquire();
furi_hal_adc_configure_ex(
        adc_handle,
        FuriHalAdcScale2048,
        FuriHalAdcClockSync64,
        FuriHalAdcOversample64,
        FuriHalAdcSamplingtime247_5);
furi_hal_gpio_init(adc_input_gpio, GpioModeAnalog, GpioPullNo, GpioSpeedVeryHigh);
uint16_t adc_value = furi_hal_adc_read(adc_handle, adc_input_channel);
float mV = furi_hal_adc_convert_to_voltage(adc_handle, adc_value);
furi_hal_adc_release(adc_handle);
```

To get the GpioPin and related AdcChannel, I just hard-coded in most of my examples. See `furi_hal_resources_pin_by_name(...)` and `furi_hal_resources_pin_by_number(...)` for the pin_record APIs to get the data.