FURI is the **F**lipper **U**niversal **R**egistry **I**mplementation.  The Flipper Zero is still in version 0.x so a lot of things are still changing.  This wiki and the samples will try to keep up, but please use the Issues tab to report any breaking issues (and if something isn't working for you, look there before spending a bunch of time debugging it.)

There is a good (but perhaps a little outdated) [diagram](https://forum.flipperzero.one/t/how-to-develop-a-3rd-party-module-plugin/2076/10) in the flipper zero forum.  The image seems to indicate that FURI Core, FURI HAL and Services are the key to building apps.

```c
#include <furi.h>       // FURI Core
#include <furi_hal.h>   // FURI Hardware Abstraction Layer
```

The FURI core is under the [Furi](https://github.com/flipperdevices/flipperzero-firmware/tree/dev/furi) folder (and most of it is in core).

The FURI HAL is under the [Furi_hal_include](https://github.com/flipperdevices/flipperzero-firmware/tree/dev/firmware/targets/furi_hal_include) folder.

The services are under the [Services](https://github.com/flipperdevices/flipperzero-firmware/tree/dev/applications/services) folder.
