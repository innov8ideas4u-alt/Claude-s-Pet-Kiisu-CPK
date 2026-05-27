# Introduction
The Flipper Zero user interface is composed of a LCD monochrome display (128x64) and a directional pad (Up/Down/Left/Right/Ok) with Back button.  There are lots of other ways for the Flipper Zero to get input and provide output (GPIO, Sub 1-GHz, IR, USB-C, Micro SD, RFID NFC, RFID 125KHz, iButton, vibration, LED, timers, etc.) but those will all be covered in different sections of this wiki.

For this section of the wiki, User Interface, is focused on rendering and d-pad input.

Basic applications use a [ViewPort](#viewport) and do all of the draw and input handling themselves.  For drawing, your callback is invoked with a [Canvas](#canvas) that has methods you can use to draw or render text on.  A little more advanced application will use a [View](#view) and a [ViewDispatcher](#viewdisptacher) to switch between Views.  Each view has its own draw and input routines.  A [View](#view) also has the concept of the previous View that you can set (which makes handling the Back button to go back one screen easy).  [Modules](#modules) are configurable components that contain a [View](#view) and typically have a method to return the view.  For even more complex applications, a [SceneManager](#scenemanager) is typically used -- which maintains a stack of scene identifiers.  A [SceneManager](#scenemanager) allows for pressing back multiple times to go back many scenes.  When transitioning to a new scene, you can choose how to manipulate the stack of scene identifiers.  The typical usage of the [SceneManager](#scenemanager) is to have the Scene's on_enter callback leverage a [ViewDispatcher](#viewdispatcher) and switch which [View](#view) is being displayed.  NOTE: There is no "Scene" class, but the SceneManager has you register a list of on_enter callbacks, on_exit callbacks, on_event callbacks -- so conceptually a Scene is one entry from **each** of the lists [on_enter, on_event, on_exit, id].


# ViewPort
The most basic UI application uses a ViewPort object.  In this case, the GUI will invoke your callback for Draw and Input.  Orientation is handled for you, mapping the screen canvas and directional pad.  Your code can enable/disable rendering.

An application using ViewPort typically registers the callbacks on application start and uses the draw/input callbacks for the lifetime of the application.  Currently official firmware allows view_port_draw_callback_set and view_port_input_callback_set to be invoked multiple times (and subsequent calls will replace the current callbacks) so it is possible to have your input handler switch the draw_callback/input_callback methods to render very different experiences.  Most applications using ViewPort have a single input_callback and a single draw_callback and call different helper methods rather than swapping the callbacks (or they use a [ViewDispatcher](#viewdispatcher) instead of the ViewPort).  

## Key concepts
### Import <gui/gui.h> 
Import the gui header file, which will import view_port, canvas. NOTE: This will also end up importing input/input.h, furi_hal_resources.h, furi.h and a few other headers.
```c
#include <gui/gui.h>
```

### Define drawing callback
Define a callback function to get invoked for drawing.  You can name the function anything. In this example, we use "my_draw_callback".  Typically, your callback will render on the [Canvas](#canvas).
```c
static void my_draw_callback(Canvas* canvas, void* context) {
  // TODO: If we need the context, cast the context to the correct type.
  // TODO: Render something on the canvas.
}
```

### Define input callback
Define a callback function to get invoked for input.  You can name the function anything.  In this example, we use "my_input_callback".  Typically, your callback will _put messages in the [MessageQueue](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Message-Queue) to be processed by your application.
```c
static void my_input_callback(InputEvent* input_event, void* context) {
  // TODO: queue an input event 
}
```

### Allocate ViewPort
Allocate the ViewPort using the view_port_alloc method.
```c
ViewPort* view_port = view_port_alloc();
```

### Register callbacks
Register our draw callback.
```c
view_port_draw_callback_set(view_port, my_draw_callback, my_context);
```

Register our input callback.
```c
view_port_input_callback_set(view_port, my_input_callback, my_context);
```

### Set orientation
The default orientation for the Flipper Zero is ViewPortOrientationHorizontal.  The other options are:  ViewOrientationHorizontalFlip (upside down), ViewPortOrientationVertical (D-pad on bottom), ViewPortOrientationVerticalFlip (D-pad on top).

```c
view_port_set_orientation(view_port, ViewPortOrientationVertical); // USB/D-pad on bottom
```

### Add ViewPort to Gui
Get a reference to the Gui and add the viewport.  Although there are additional layouts GuiLayerWindow, GuiLayerStatusBarLeft, GuiLayerStatusBarRight & (system reserved GuiLayerDesktop) you should typically use GuiLayerFullscreen.  The reason is that the GuiLayer will attempt to render GuiLayerFullscreen (and only if not present will it render Window and StatusBar).  The application loader (which is the typical way your application will be launched) uses a GuiLayerFullscreen with an animated hour-glass when it transfers execution to your application.  Therefore, if you use Window and StatusBar they will not show, since you will see the Fullscreen hour-glass animation.  (In some firmware, it may be possible for the Desktop to direction launch your application, so potentially in this case you could use Window.)

```c
Gui* gui = furi_record_open(RECORD_GUI);
gui_add_view_port(gui, view_port, GuiLayerFullscreen);
```

### Free resources
When your application is done, you should disable the viewport and free the resources you allocated.
```c
view_port_enabled_set(view_port, false);
gui_remove_view_port(gui, view_port);
furi_record_close(RECORD_GUI);
view_port_free(view_port);
```

## Advanced topics
### Enabling ViewPort
You can enable and disable a ViewPort using ``view_port_enabled_set``.  If multiple ViewPort objects are registered and enabled, the one in the 'front' (added most recently) will render.

```c
view_port_enabled_set(view_port,false); // disable view_port
view_port_enabled_set(view_port,true); // enable view_port
```

### Updating ViewPort
You can request a redraw using ``view_port_update``.

```c
view_port_update(view_port);
```

### Height and Width
Height and Width for ViewPort are only used by GuiLayoutStatusBarLeft/GuiLayoutStatusBarRight.  In general, your code should not use ``view_port_set_width``, ``view_port_get_width``, ``view_port_set_height`` & ``view_port_get_height``; since your ViewPort is likely FullScreen.  You can use ``view_port_get_orientation(view_port);`` to determine the Horizontal/Vertical orientation.

## Sample
- [Viewport example app](https://github.com/jamisonderek/flipper-zero-tutorials/tree/main/ui/viewport_demo) shows a basic application that uses ViewPort for its UI.
 
# Canvas
The Canvas is an object for drawing on the LCD monochrome display (128x64).  Depending on the orientation, the display may be a 64x128.  Methods are exposed to get the canvas_width and canvas_height of a canvas.  Typically, your drawing callback is invoked with a Canvas object that you can use to draw on.

## Key concepts
### Clear buffer
Clear the canvas buffer, so the display memory is in the reset state.
```c
canvas_clear(canvas)
```

### Set drawing color
Set the color used for drawing.  The choices are ColorWhite, ColorBlack and ColorXOR.  If you use XOR then drawing will invert the existing pixels state (Black->White, White->Black).
```c
canvas_set_color(canvas, ColorWhite);
```

### Set font
Set the font used for drawing strings.  The choices are FontPrimary, FontSecondary, FontKeyboard and FontBigNumbers.
```c
canvas_set_font(canvas, FontPrimary);
```

### Draw string
Draw a string using the current font (Left/bottom aligned).  NOTE: The message is a cstr (e.g. a pointer to a null-terminated array of char). If you have a FuriString, you can call furi_string_get_cstr(furiString) to get the cstr.
```c
uint8_t x = 30;
uint8_t y = 10;
char* message = "hello";
canvas_draw_str(canvas, x, y, message);
```

### Draw aligned string
Draw an aligned string using the current font.  NOTE: The message is a cstr (e.g. a pointer to a null-terminated array of char). If you have a FuriString, you can call furi_string_get_cstr(furiString) to get the cstr.  Horizontal values are AlignLeft, AlignRight & AlignCenter.  Vertical values are AlignBottom, AlignTop & AlignCenter.
```c
uint8_t x = 30;
uint8_t y = 10;
char* message = "hello";
canvas_draw_str(canvas, x, y, AlignLeft, AlignBottom, message);
```

### Draw pixel
Draw a pixel using the current color.
```c
uint8_t x = 50;
uint8_t y = 30;
canvas_draw_dot(canvas, x, y);
```

### Draw box
Draw a box or frame of the specified width and height.
```c
uint8_t x = 50;
uint8_t y = 30;
uint8_t w = 20;
uint8_t h = 5;
canvas_draw_box(canvas, x, y, w, h);
canvas_draw_frame(canvas, x, y, w, h);
```

### Draw rounded box/frame
Draw a rounded corner box or frame of the specified width and height.
```c
uint8_t x = 50;
uint8_t y = 30;
uint8_t w = 20;
uint8_t h = 5;
uint8_t r = 2;
canvas_draw_rbox(canvas, x, y, w, h, r);
canvas_draw_rframe(canvas, x, y, w, h, r);
```

### Draw line
Draws a line from (x1,y1) to (x2,y2).
```c
uint8_t x1 = 10;
uint8_t y1 = 20;
uint8_t x2 = 30;
uint8_t y2 = 25;
canvas_draw_line(canvas, x1, y1, x2, y2);
```

### Draw circle
Draws a circle at (x,y) with radius r.
```c
uint8_t x = 63;
uint8_t y = 20;
uint8_t r = 10;
canvas_draw_circle(canvas, x, y, r);
```

### Draw icon
Draws an icon.  In this example, the file MyImage_96x59.png is in the folder specified in the fap_icon_assets property of the application.fam file. 

First you need to include the auto-generated icon file that will get created by your fap_icon_assets property being set.  The file will be named "the name of your appid followed by underscore icons.h".  For example, if your appid is "awesome_demo" then you would include "awesome_demo_icons.h", which should get auto-generated in the "\\build\\latest\\.extapps\\awesome_demo" folder.
```c
#include "awesome_demo_icons.h"
```

You can then draw the icon on the canvas.  (NOTE: Icons are prefixed by "I_").
```c
uint8_t x = 63;
uint8_t y = 20;
Icon* icon = &I_MyImage_96x59;
canvas_draw_icon(canvas, x, y, icon);
```

# ViewDispatcher
The view dispatcher is used for applications that want multiple [View](#view) objects. The application can easily switch between views.  Views are registered with an id, and then the dispatcher can switch between the views. If the back button is pressed and the view does not return true from the input callback, then the view's navigation callback is used to determine the view id to switch to.

## Key concepts
### Import <gui/view_dispatcher.h>
Import the view_dispatcher header file, which will import view, gui, and scene_manager.  NOTE: the gui header file, will import view_port, canvas, which will also end up importing input/input.h, furi_hal_resources.h, furi.h and a few other headers.
```c
#include <gui/view_dispatcher.h>
```

### Allocate ViewDispatcher 
Allocate a ViewDispatcher and enable its queue.
```c
ViewDispatcher* view_dispatcher = view_dispatcher_alloc();
view_dispatcher_enable_queue(view_dispatcher);
```

### Enumeration of identifiers
Create an enum of view identifiers.
```c
typedef enum {
  MyDemoViewId,
  MyOtherDemoViewId,
} MyViewIds;
```

### Add view to view dispatcher
Add the [View](#view) to your view dispatcher using the custom id.  See the [View](#view) section for more information on how to create a populated View object.
```c
// View* view = replace_with_function_to_get_a_view_object(); // Get a populated View* object.
view_dispatcher_add_view(view_dispatcher, MyDemoViewId, view);

// view = replace_with_function_to_get_another_view_object(); // Get a populated View* object.
view_dispatcher_add_view(view_dispatcher, MyOtherDemoViewId, view);
```

### Navigation events
If the View's previous_callback is not set, or returns VIEW_IGNORE, then the navigation_event_callback will be invoked.  If navigation_event_callback returns false, then the view_dispatcher_stop will be invoked.  You must use ``view_dispatcher_set_navigation_event_callback`` if you want the back button to eventually terminate your application.  There is currently a comment in ``view_dispatcher_handle_input`` that says ``TODO: should we allow view_dispatcher to stop without navigation_event_callback?``, so this requirement may change in the future.

```c
bool my_view_dispatcher_navigation_event_callback(void* context) {
  // Return true if you handled the event, or if you want to ignore the event.
  // Only return false if you want the ViewDispatcher to stop.
  return true; 
}
view_dispatcher_set_navigation_event_callback(view_dispatcher, my_view_dispatcher_navigation_event_callback);
```

### Attach view dispatcher to Gui
Attach the view dispatcher to the GUI.
```c
Gui* gui = furi_record_open(RECORD_GUI);
view_dispatcher_attach_to_gui(view_dispatcher, gui, ViewDispatcherTypeFullscreen);
```

### Switch to view
Switch to one of the registered views and start running the dispatcher.
```c
view_dispatcher_switch_to_view(view_dispatcher, MyDemoViewId);
view_dispatcher_run(view_dispatcher);
```

### Switch to another view
In your callback code: switch to a different view when something interesting happens.
```c
view_dispatcher_switch_to_view(view_dispatcher, MyOtherDemoViewId);
```

### Stop view dispatcher
In your callback code: stop view needed.
```c
view_dispatcher_stop(view_dispatcher);
```

### Free resources
When your application is done, you should disable the free the resources you allocated.
```c
view_dispatcher_remove_view(view_dispatcher, MyDemoViewId); // Be sure to remove your view.
view_free(view);
view_dispatcher_free(view_dispatcher);
furi_record_close(RECORD_GUI);
```

## Advanced Topics
### Custom events
view_dispatcher_send_custom_event can be used to send an event_id to the registered custom_event_callback method.  The view_dispatcher_send_custom_event will queue the event using the ViewDispatcher's queue.  The event will first be passed to the View's custom_callback handler, but it that returns false then the ViewDispatcher custom_event_callback will be invoked.  The context is set using ``view_dispatcher_set_event_callback_context`` (which impacts the void* context for navigation, tick and custom).

```c
bool my_view_dispatcher_custom_event_callback(void* context, uint32_t event) {
  // NOTE: The return value is not currently used by the ViewDispatcher,
  // however I recommend returning true if you handled the event and false
  // if it is still unhandled, since the API may change in the future.
  return true; 
}
view_dispatcher_set_event_callback_context(view_dispatcher, my_context);
view_dispatcher_set_custom_event_callback(view_dispatcher, my_view_dispatcher_custom_event_callback);

uint32_t event_id = 42; // Send a custom event of 42 to the custom_event_callback.
view_dispatcher_send_custom_event(view_dispatcher, event_id);
```

### Tick events
The Tick event callback will get invoked whenever the ViewDispatcher did not have any events in its queue for the tick_period.

```c
void my_view_dispatcher_tick_event_callback(void* context) {
}
uint32_t tick_period = furi_ms_to_ticks(1000);
view_dispatcher_set_tick_event_callback(view_dispatcher, my_view_dispatcher_tick_event_callback, tick_period);
```
## Sample
- [ViewDispatcher example app](https://github.com/jamisonderek/flipper-zero-tutorials/tree/main/ui/viewdispatcher_demo) shows a basic application that uses ViewDispatcher for its UI.

# View
A View is the objects that are added to the [ViewDispatcher](#viewdispatcher) and referenced later in the ViewDispatcher by id.  A View is similar to a ViewPort, in that callbacks can be set for draw and input (view_set_draw_callback and view_set_input_callback), but there are a lot more callbacks that can also be registered with a View.  There are many Gui modules for various tasks, like input, file dialogs, menus, etc. and each of them have a View associated with the module (typically *module_name*_get_view(module) is the function that returns the View).

In a View, a custom callback can be set which is invoked by the view_dispatcher_send_custom_event method.  A previous callback can be set, which gets invoked when the Back button is pressed.  If the previous callback returns a view id (that was previously registered with the ViewDispatcher) then the navigation is changed to view associated with that id.  There are also enter/exit callbacks that can be registered to know when a View is switched to/or away from.

There are many pre-built modules, which expose a configured View object. You can use the View* that is returned from the [Modules](#modules) _get_view(...) function.

## Key concepts
### Import <gui/view.h>
Import the view header file, which will import canvas, input/input.h, and a few other headers.
```c
#include <gui/view.h>
```

### Define drawing callback
Define a callback function to get invoked for drawing.  You can name the function anything. In this example, we use "my_draw_callback".  Typically, your callback will render on the [Canvas](#canvas).
```c
static void my_draw_callback(Canvas* canvas, void* model) {
  // TODO: If we need the model, cast the model to the correct type.
  // TODO: Render something on the canvas.
}
```

### Define input callback
Define a callback function to get invoked for input.  You can name the function anything.  In this example, we use "my_input_callback".  Typically, your callback will _put messages in the [MessageQueue](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Message-Queue) to be processed by your application.
```c
static void my_input_callback(InputEvent* input_event, void* context) {
  // TODO: queue an input event 
}
```

### Allocate View
Allocate the View using the view_alloc method.
```c
View* view = view_alloc();
```

### Struct for model (data)
Create a model structure to hold your View's data.
```c
typedef struct MyModel {
  FuriString* buffer;
  uint32_t counter;  
} MyModel;
```

### Allocate model
Allocate a model. If the model is all atomic types and partial update is okay use ViewModelTypeLockFree, otherwise use ViewModelTypeLocking to have the model guarded by a mutex.  The model is a void*, so you need to specify the sizeof your model struct.
```c
view_allocate_model(view, ViewModelTypeLockFree, sizeof(MyModel));
```

### Register callbacks
Register our draw callback.
```c
// The callback will be invoked with the model, if it was allocated.
view_set_draw_callback(view_port, my_draw_callback);
```

Register our input callback and context.
```c
// Set context to whatever context you want when input callback gets invoked.
void* context = NULL; 
view_set_context(view_port, context);
view_set_input_callback(view_port, my_input_callback);
```

### Free resources
When your application is done, you should free the resources you allocated.
```c
view_free(view);
```

## Advanced Topics
### Previous callback
The navigation callback method will get invoked when the Back button is pressed.  This method should return the view id that matches one of the identifiers registered in the ViewDispatcher.  You can use VIEW_NONE to hide the view_port and VIEW_IGNORE to ignore the request.  The context passed to the callback is the object specified in ```view_set_context(view, context);```

Create the callback method that will get invoked when the Back button is pressed.  
```c
uint32_t my_view_navigation_callback(void* context) {
  return MyDemoViewId; // Return the view id that is registered in the ViewDispatcher.
}
```

Register the callback method.
```c
view_set_previous_callback(view, my_view_navigation_callback);
```

### Enter callback
The enter callback method will get invoked when the view_dispatcher_set_current_view is called and the view is switched to.

Create the callback method that will get invoked when the view is switched.
```c
void my_enter_view_callback(void* context) {
}
```

Register the callback method.
```c
view_set_enter_callback(view, my_enter_view_callback)
```

### Exit callback
The exit callback method will get invoked on the previous View when the view_dispatcher_set_current_view is called.

Create the callback method that will get invoked when the view is switched.
```c
void my_exit_view_callback(void* context) {
}
```

Register the callback method.
```c
view_set_exit_callback(view, my_exit_view_callback)
```

### With view model
We used view_allocate_model to create storage for our view's model (data).  We also specified if access should be guarded or not (ViewModelTypeLockFree or ViewModelTypeLocking). When we want to access the view, we use the with_view_model method.

- The first parameter is the view. This is typically accessed via ->view or using a {componentName}_get_view method.
- The second parameter is a declaration for our model variable.
- The third parameter is a code block, which access the model parameter defined in the second parameter.
- The fourth parameter is a boolean expression, specifying if the model should be updated.  If true, then update_callback will get invoked.
If you update the model, a value of false does not put the view into the previous state.

```c
with_view_model(
   module->view,
   ModuleModel * model,
   {
     // code that updates model.
   },
   true);
```

### Update callback w/context
When the last parameter of with_view_model is set to true, then update_callback will get invoked.  update_callback will also get invoked when view_commit_model is invoked with the second parameter (update) set to true.  The third way update_callback will get invoked is when view_icon_animation_callback gets invoked.

The callback method with a signature like:
   ```c
   void callback_name(View* view, void* context)
   ```

This callback routine is set via view_set_update_callback(view, callback).  The context parameter is set via view_set_update_callback_context(view, context).

### Custom callback
When "bool view_custom(View* view, uint32_t event)" gets invoked, it will invoke the custom_callback if set and return the value from the callback.  If no callback routine is set, then view_custom will return false.

The callback method with a signature like:
   ```c
  bool callback_name(uint32_t event, void* context)
  ```

This callback routine is set via view_set_custom_callback(view, callback).  The context parameter is set via view_set_context(view, context) -- which is shared across input_callback, previous_callback, enter_callback & exit_callback (so caution should be used if changing the context).

### Set orientation
The ViewDispatcher's set_current_view method will use the View's orientation to rotate keyboard input & rendering.

view_alloc will set the orientation to ViewOrientationHorizontal by default.  You can call view_set_orientation with a second parameter of ViewOrientationHorizontalFlip, ViewOrientationVertical, ViewOrientationVerticalFlip or ViewOrientationHorizontal to change the orientation.  The call to view_set_orientation needs to happen before the call to set_current_view, or else the update data will not be picked up.

```c
view_set_orientation(view, ViewOrientationVertical);
```

### Get model
You should probably use with_view_model to access the model.  If you decide instead to use view_get_model(view) the call will acquire the lock if the view model is ViewModelTypeLocking.  You must later call view_commit_model with a second parameter of true to invoke the update_callback or false to not invoke the update_callback.  If you update the model, a value of false does not put the view into the previous state.

```c
// You should probably use with_view_model instead.

ModuleModel* model = view_get_model(view);
// do something here...
view_commit_moodel(view, true);
```

### Commit model
view_commit_model is used to release the mutex that was acquired via view_get_model.  The second parameter indicates if the update_callback should be invoked.  NOTE: If you update the model, a value of false does not put the view into the previous state.

```c
// You should probably use with_view_model instead.

ModuleModel* model = view_get_model(view);
// do something here...
view_commit_moodel(view, true);
```

# Modules
Modules are such a big topic that a separate [Modules page](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Modules) has been created.  They are views that you can configure with specific data, then leverage the view in your own application.  All modules expose _alloc, _free and _get_view methods.  Many modules also expose methods to configure the module and to set additional callbacks needed by the module (like result_callback, validator_callback, etc.)  

## Key concepts
Modules typically expose three core methods:

### Allocate 
- Allocate the module.
```c
Modulename* module = modulename_alloc();
```

### Get View*
- Get View* associated with the module.
```c
View* view = modulename_get_view(module);
```

### Free
- Free the module when our program exits.
```c
modulename_free(module);
```

For example, the Loading module:
```c
Loading* module = loading_alloc();
View* view = loading_get_view(module);
// Free the module when our program exits.
loading_free(module);
```


# SceneManager
The scene manager is typically used in conjunction with the view dispatcher.  When you allocate the scene manager, you pass configuration to register your scenes (each scene has an on_enter, on_event and on_exit callback handler).  The scene manager has methods to navigate (previous, back, another, next) to a scene.  Each scene has a state (which is a 32-bit number, or more specifically a uint32_t) with methods to get and set the state for a scene.  When a scene is transitioned the ```on_exit``` handler will be invoked for the current scene and the ```on_enter``` handler will be invoked for the new scene.  Tick, Back and Custom events will invoke the ```on_event``` handler for the current scene.  In the case of Back, if the ```on_event``` returns false, then the ```scene_manager_previous_scene``` will be invoked.

## Key Concepts
### Create on_enter callbacks
The on_enter callbacks take a single void* context.  This method will get invoked when the scene manager switches to a scene with matching this registered on_enter handler.
```c
// In our demo we have two scenes: MainMenu and GreetingMessage.  We define on_enter handlers...
void demo_main_menu_scene_on_enter(void* context) {
  UNUSED(context);
}

void demo_greeting_message_scene_on_enter(void* context) {
  UNUSED(context);
}
```

### Create on_exit callbacks
The on_exit callbacks take a single void* context.  This method will get invoked when the scene manager switches away from a scene with matching this registered on_exit handler.
```c
// In our demo we have two scenes: MainMenu and GreetingMessage.  We define on_exit handlers...
void demo_main_menu_scene_on_exit(void* context) {
  UNUSED(context);
}

void demo_greeting_message_scene_on_exit(void* context) {
  UNUSED(context);
}
```

### Create on_event callbacks
The on_event callbacks take a void* context and an event.  The event has a type (SceneManagerEventTypeCustom, SceneManagerEventTypeBack or SceneManagerEventTypeTick) and optionally an event (uint32_t). This method will get invoked on the current scene when custom, back or tick events happen.  If the event was handled, the method should return true.
```c
// In our demo we have two scenes: MainMenu and GreetingMessage.  We define on_event handlers...
bool demo_main_menu_scene_on_event(void* context, SceneManagerEvent event) {
  UNUSED(context);
  UNUSED(event);
  return false; // event not handled.
}

bool demo_greeting_message_scene_on_event(void* context, SceneManagerEvent event) {
  UNUSED(context);
  UNUSED(event);
  return false; // event not handled.
}
```

### Populate SceneManagerHandlers
The SceneManagerHandlers object has the various callbacks (handlers) and the total number of scenes.  Often an enum is created with the IDs of all of the scenes.  Sometimes macros are used to create the callback definitions (in the below example they are all created manually).

```c
// In our demo we have two scenes: MainMenu and GreetingMessage.
typedef enum {
    DemoMainMenuScene,
    DemoGreetingMessageScene,
    DemoSceneCount, // Last element should be "Count".
} DemoScene;
void (*const demo_scene_on_enter_handlers[])(void*) = {
    demo_main_menu_scene_on_enter,
    demo_greeting_message_scene_on_enter,
};
void (*const demo_scene_on_exit_handlers[])(void*) = {
    demo_main_menu_scene_on_exit,
    demo_greeting_message_scene_on_exit,
};
bool (*const demo_scene_on_event_handlers[])(void*, SceneManagerEvent) = {
    demo_main_menu_scene_on_event,
    demo_greeting_message_scene_on_event,
};
static const SceneManagerHandlers demo_scene_manager_handlers = {
    .on_enter_handlers = demo_scene_on_enter_handlers,
    .on_event_handlers = demo_scene_on_event_handlers,
    .on_exit_handlers = demo_scene_on_exit_handlers,
    .scene_num = DemoSceneCount,
};
```

### Define an object for context
Typically, you will define an application object context.  This object will be passed as the void* context to your on_enter, on_exit and on_event handlers.  You could define any object you wanted for context; but it is common to pass on object containing the SceneManager, ViewDispatcher and various registered modules (so your ```on_enter``` callback can configure a view and then request the view dispatcher to switch to a particular view).

```c
typedef struct App {
    SceneManager* scene_manager;
    ViewDispatcher* view_dispatcher;
    Submenu* submenu;
    Widget* widget;
} App;
```

### Allocate the scene manager
```c
App* app = malloc(sizeof(App));
app->scene_manager = scene_manager_alloc(&demo_scene_manager_handlers, app);
```

### Switch to another scene
Every time you switch to another scene (even with the same id) the current scene will have the ``on_exit`` handler get called, and the new scene will have the ``on_enter`` handler get called.  The new scene is pushed onto the stack of visited scenes. Later, the code can use either the ``scene_manager_handle_back_event`` or ``scene_manager_previous_scene`` to go back to the previous scenes.  When you are initially creating a scene manager, you can still use ``scene_manager_next_scene`` to load the initial scene (and its ``on_enter`` will get invoked).

```c
scene_manager_next_scene(app->scene_manager, BasicScenesMainMenuScene);
```

### Handle back event
In your code that gets invoked when the back button is pressed, you want to notify the scene manager.  ``scene_manager_handle_back_event`` will first invoke the current scenes ``on_event`` handler with a ``SceneManagerEventTypeBack`` type event.  If that method returns false, then it will invoke the ``scene_manager_previous_scene`` method.

```c
scene_manager_handle_back_event(app->scene_manager);
```

### Stop scene manager
Calling ``scene_manager_stop`` will invoke the current scene's ``on_exit`` handler.

```c
scene_manager_stop(app->scene_manager);
```

### Free scene manager
Calling ``scene_manager_free`` will free any resources used by the scene_manager.  You should call ``scene_manager_stop``, if you need to ensure the current scene had its ``on_exit`` handler invoked.

```c
scene_manager_free(app->scene_manager);
```

## SceneManager with ViewDispatcher
If you are using the SceneManager in combination with a ViewDispatcher, there are some common patterns that you may find helpful.

### Handle back event
- Create a back_event callback for your view dispatcher, that will invoke the ``scene_manager_handle_back_event`` method:
   ```c
   bool demo_back_event_callback(void* context) {
     furi_assert(context);
     App* app = context;
     return scene_manager_handle_back_event(app->scene_manager);
   }
   ```
- In the method that allocates the view dispatcher, register your navigation callback with the view dispatcher:
   ```c
   view_dispatcher_set_event_callback_context(app->view_dispatcher, app); // make sure context is app.
   view_dispatcher_set_navigation_event_callback(app->view_dispatcher, demo_back_event_callback);
   ```

### Handle custom callback event
- Create a custom callback for your view dispatcher, that will invoke the ``scene_manager_handle_custom_event`` method:
   ```c
   bool demo_custom_callback(void* context, uint32_t custom_event) {
     furi_assert(context);
     App* app = context;
     return scene_manager_handle_custom_event(app->scene_manager, custom_event);
   }
   ```
- In the method that allocates the view dispatcher, register your custom callback with the view dispatcher:
   ```c
   app->view_dispatcher = view_dispatcher_alloc();
   view_dispatcher_enable_queue(app->view_dispatcher);
   view_dispatcher_set_event_callback_context(app->view_dispatcher, app); // make sure context is app.
   view_dispatcher_set_custom_event_callback(app->view_dispatcher, demo_custom_callback); // here
   // navigation callback from previous step.
   view_dispatcher_set_navigation_event_callback(app->view_dispatcher, demo_back_event_callback);
   ```

### on_enter switches View
- In your on_enter callbacks, you should configure your view (or module) and then switch to the view.
   ```c
   void demo_greeting_message_scene_on_enter(void* context) {
      App* app = context;
      widget_reset(app->widget);
      widget_add_string_element(
        app->widget, 25, 15, AlignLeft, AlignCenter, FontPrimary, "Hello World!");
      view_dispatcher_switch_to_view(app->view_dispatcher, DemoWidgetView);
   }
   ```
- This example assumes that "DemoWidgetView" is defined in an enum (similar to ``typedef enum { DemoWidgetView, } DemoView;``) and was registered earlier (typically in an ``app_alloc`` method) with code similar to the following:
   ```c
   app->widget = widget_alloc();
   view_dispatcher_add_view(app->view_dispatcher, DemoWidgetView, widget_get_view(app->widget));
   ```

### callbacks forward to on_event
- If you have a callback (like a menu callback) that callback should leverage ``scene_manager_handle_custom_event`` passing a custom event id as the second parameter.  This will end up forwarding the event back to your on_event callback for the scene.  This helps keep all of the scene's logic in the on_event method.
   ```c
   void demo_menu_callback(void* context, uint32_t index) {
      App* app = context;
      switch(index) {
        case DemoMenuSceneGreeting:
          scene_manager_handle_custom_event(
            app->scene_manager,
            DemoGreetingEvent); // Some custom event id that we will handle.
        break;
      }
   }
   ```
- In your on_event for the scene handle the custom events that you sent.
   ```c
   bool basic_scenes_main_menu_scene_on_event(void* context, SceneManagerEvent event) {
      App* app = context;
      bool consumed = false; // by default return false (so back logic, etc. will work)
      switch(event.type) {
         case SceneManagerEventTypeCustom:
            switch(event.event) {
               case DemoGreetingEvent:
                  scene_manager_next_scene(app->scene_manager, DemoGreetingScene);
                  consumed = true; // We handled event, so return true.
                break;
            }
        break;
    default:
        break;
    }
    return consumed;
   }
   ```

## Advanced Topics
### scene_manager_set_scene_state
``scene_manager_set_scene_state`` sets the state (uint32_t) associated with a given scene_id.  This is often used when a menu item is selected, so that when the user returns to the scene, the current menu item can be reselected.

Example:
   ```c
   scene_manager_set_scene_state(
      app->scene_manager, StorageSettingsStart, StorageSettingsStartSubmenuIndexSDInfo);
   ```

### scene_manager_get_scene_state
``scene_manager_get_scene_state`` gets the state (uint32_t) associated with a given scene_id.  This is often used to recall which menu item was previously selected, so reselect the menu item when the scene's on_enter is getting invoked due to a back button being pressed.

Example:
   ```c
    submenu_set_selected_item(
        submenu, scene_manager_get_scene_state(app->scene_manager, StorageSettingsStart));
    view_dispatcher_switch_to_view(app->view_dispatcher, StorageSettingsViewSubmenu);
   ```

### scene_manager_handle_custom_event
``scene_manager_handle_custom_event`` invokes the current scene's on_event callback, passing the custom_event (uint32_t) data in .event & .type = SceneManagerEventTypeCustom, and returns the result of the callback.

Example:
   ```c
   bool demo_custom_callback(void* context, uint32_t custom_event) {
     furi_assert(context);
     App* app = context;
     return scene_manager_handle_custom_event(app->scene_manager, custom_event); // invoke on_event for current scene.
   }
   ```

### scene_manager_handle_tick_event
``scene_manager_handle_tick_event`` invokes the current scene's on_event callback, passing .type = SceneManagerEventTypeTick, and returns the result of the callback.  This is sometimes used to update progress bars in applications (but those applications still return false instead of true).  There doesn't appear to be any fallback behavior defined for when false is retuned from the callback so I'm not sure why they don't return true for the consumed value (maybe it's a bug in the code that everyone is copying)?

Example:
   ```c
   static void file_browser_app_tick_event_callback(void* context) {
      furi_assert(context);
      FileBrowserApp* app = context;
      scene_manager_handle_tick_event(app->scene_manager);
   }
   ```

### scene_manager_has_previous_scene
``scene_manager_has_previous_scene`` returns true if any of the previous scenes have an id matching the specified scene id.  This is sometimes used when the app wants to switch to a specific scene based on some past scenes.  It is also used when the app wants to award some behavior based on how you got to a specific scene; for example, rewarding the Dolphin experience points [XP](https://docs.flipperzero.one/basics/dolphin#h0Vo-) for an iButton add action.

Example:
   ```c
   if(scene_manager_has_previous_scene(
      ibutton->scene_manager, iButtonSceneAddType)) {
         DOLPHIN_DEED(DolphinDeedIbuttonAdd);
   }
   ```

### scene_manager_search_and_switch_to_previous_scene
If a previous scene with matching id is found on the stack, ``scene_manager_search_and_switch_to_previous_scene`` will remove all scenes between the current scene and this past scene (it searches most recent scenes to oldest - LIFO).  It will then call on_exit handler for the current scene followed by on_enter handler for the previous scene with matching id, and then return true.  If the stack of scenes did not match the requested id, then this method will return false.

Example:
   ```c
   scene_manager_search_and_switch_to_previous_scene(
      app->scene_manager, AvrIspSceneChipDetect);
   ```

### scene_manager_search_and_switch_to_previous_scene_one_of
``scene_manager_search_and_switch_to_previous_scene_one_of`` takes a list of scene ids and the total number of scenes in the list.  It will start at the beginning of the list and if that scene is anywhere on the stack, it will invoke ``scene_manager_search_and_switch_to_previous_scene`` with that scene.  The list of scene ids are a prioritized list of scenes to switch to, with the higher priority choices being at the beginning of the list.  If none of the choices are found, then it will return false.

Example:
   ```c
   const uint32_t possible_scenes[] = {
      iButtonSceneReadKeyMenu, iButtonSceneSavedKeyMenu, iButtonSceneAddType};
   scene_manager_search_and_switch_to_previous_scene_one_of(
      ibutton->scene_manager, possible_scenes, COUNT_OF(possible_scenes));
   ```

### scene_manager_search_and_switch_to_another_scene
``scene_manager_search_and_switch_to_another_scene`` will remove all but the first scene and then add the second scene.  It will then call on_exit on the current scene and on_enter new scene.

Example:
   ```c
   // ibutton_scene_save_success_on_event code...
   if(event.event == iButtonCustomEventBack) {
      scene_manager_search_and_switch_to_another_scene(
         ibutton->scene_manager, iButtonSceneSelectKey);
   }
   ```

## Sample
- [Scenes example app](https://github.com/jamisonderek/flipper-zero-tutorials/tree/main/ui/basic_scenes) shows a basic application that uses SceneManager and ViewDispatcher for controlling its UI.

# Additional Resources
- My [plugins](https://github.com/jamisonderek/flipper-zero-tutorials/tree/main/plugins) tutorials cover various UI topics.
- Instantiator.dev has written about the Flipper Zero in these [posts](https://instantiator.dev).
- Instantiator also wrote some additional [experimental apps](https://github.com/instantiator/flipper-zero-experimental-apps) for learning about Flipper Zero.