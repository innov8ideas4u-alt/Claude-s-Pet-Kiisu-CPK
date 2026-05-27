# FlipperZero Game Engine (Video Game Engine)

## Overview
The FlipperZero Game Engine is a git submodule that you can include in your own Flipper Zero application. Because it is a sub-module, you should clone applications that use the engine using the `git clone --recursive` option (or `--recurse-submodules`).

The engine is located at [https://github.com/flipperdevices/flipperzero-game-engine](https://github.com/flipperdevices/flipperzero-game-engine) and typically people create a submodule in an **engine** directory.

The game engine contains two main parts:
- Game engine for playing games
  - [`Game`](#game) has a bunch of `Level`* objects; described by [`LevelBehaviour`](#levelbehaviour)
  - [`Level`](#level) has a bunch of `Entity`* objects (e.g. player, ball, coin, wall, etc. entity); described by [`EntityDescription`](#entitydescription)
  - [`Entity`](#entity) can have a [rectangular](#entity_collider_add_rect) or [circular](#entity_collider_add_circle) collider
  - [`Sprite`](#sprite) (.png transformed to .fxbm image) can be loaded and rendered to Canvas
  - [`Vector`](#vector) (x & y position) and APIs for manipulating the vector
  - [`GameManager`](#gamemanager) for getting `InputState`, switching `Level`, loading `Sprite` objects, showing frames-per-second, overall game context, etc.
- Sensor library for accessing the [Video Game Module](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/Video-Game-Module)
  - Pitch : Assuming screen facing up & IR port facing left, then pitch is the tilt Left(+) / Right(-)
  - Roll : Assuming screen facing up & IR port facing left, then roll is the GPIO ports Down(+) / GPIO ports Up(-) 
  - Yaw : Assuming screen facing up & IR port facing left, then yaw is Counter-Clockwise(+) / Clockwise(-)

I created the following YouTube video [https://youtu.be/qw7OX-aREHo](https://youtu.be/qw7OX-aREHo) about the Flipper Zero Game Engine.

## Existing Games
The game engine was used by the [Air Arkanoid](https://lab.flipper.net/apps/air_arkanoid) game.

I wrote the [Air Labyrinth](https://lab.flipper.net/apps/air_labyrinth) game using the game engine.

JBlanked wrote [Flip World](https://lab.flipper.net/apps/flip_world) game using the game engine.

There is also an [example](https://github.com/flipperdevices/flipperzero-game-engine-example) game using the game engine. This example only has one level and does not leverage the Video Game Module for motion.

## Adding to your project
To add the submodule to your project, you typically run the following command in the same directory as your **application.fam** file.
  
`git submodule add https://github.com/flipperdevices/flipperzero-game-engine.git engine`

## IMU (Inertial Measurement Unit)
If you have a Video Game Module (VGM) attached to your Flipper Zero you can access the orientation in your application.  You need all of the code under the [sensors](https://github.com/flipperdevices/flipperzero-game-engine/tree/dev/sensors) folder, but it has no other dependencies.

Your application will need to [`#include "sensors/imu.h"`](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/sensors/imu.h)

You can then call: `Imu* imu = imu_alloc();` to obtain an Imu* object. When you call this method, it will try to acquire the IMU connected to the VGM (using pins 2-7, plus power [3v3] and GND). If it detects the module, it will also do a calibration. For best results, you should have the device in the expected orientation and not moving during this time. 

Calling `bool imu_present = imu_present(imu);` will return **true** if the IMU was present during the allocation call, otherwise it will return **false**. NOTE: If you are running custom firmware on the Video Game Module, it is possible that the onboard PI may be using the IMU and will be unavailable to the Flipper Zero.

To get orientation data...
```c
float pitch = imu_pitch_get(imu);
float roll = imu_roll_get(imu);
float yaw = imu_yaw_get(img);
```

When you are done with the IMU, you should release the resource using `imu_free(imu);`.

## Creating a game
Create a submodule for the engine. See [Adding to your project](#adding-to-your-project) for commands.

### Entry point
The [engine\main.c](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/main.c) file defines an entry point of `game_app`. Your **application.fam** file should set the entry point using `entry_point="game_app",`. 

### Game
You application should `#include "engine/engine.h"`

The [engine\engine.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/engine.h) declares `extern const Game game;` which will get executed by the game engine. You must define the `game` variable in your game, setting all of the properties.

The [engine\engine.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/engine.h) defines the `Game` structure as:
```c
typedef struct {
    float target_fps;
    bool show_fps;
    bool always_backlight;
    void (*start)(GameManager* game_manager, void* context);
    void (*stop)(void* context);
    size_t context_size;
} Game;
```

#### Game.target_fps
- `target_fps` : The number of frames per second to try to render. A value of **30** is probably a good starting point.

#### Game.show_fps
- `show_fps` : Useful for debugging to see the actual frames per second. Typically set to **false**.

#### Game.always_backlight
- `always_backlight` : Set to **true** so the screen is always visible while playing the game.

#### Game.start
- **`start`** : Callback that should add the levels & allocate Imu* object

#### Game.stop
- **`stop`** : Callback that should free Imu* object

#### Game.context_size
- `context_size` : Set to `sizeof(` your context structure `)`. The context will be allocated for you and passed to your `start` and `stop` methods.

#### Game example
The Air Arkanoid game uses the following in their game.c file:
```c
void game_start(GameManager* game_manager, void* ctx);
void game_stop(void* ctx);

// The various levels that are created.
typedef struct {
    Level* menu;
    Level* settings;
    Level* game;
    Level* message;
} Levels;

// Settings that are saved on SD card.
typedef struct {
    bool sound;
    bool show_fps;
} Settings;

// Game (App) related data
typedef struct {
    Imu* imu; // VGM data
    bool imu_present; // cache of imu_present(imu)
    Levels levels; // All of the levels in the game
    Settings settings; // Settings associated with game (like sound)
    NotificationApp* app; // For sound/vibrate
    GameManager* game_manager; // Used to set showing/hiding fps info
} GameContext;

const Game game = {
    .target_fps = 30, // Update screen 30 frames per second
    .show_fps = false, // Don't display the current frames per second
    .always_backlight = true, // Keep screen on so it is easy to see
    .start = game_start, // Callback that should add the levels & allocate Imu* object
    .stop = game_stop, // Callback that should free Imu* object
    .context_size = sizeof(GameContext), // Context for storing Game related data.
};
```

Your `game_start` will allocate the Imu* (if you have motion), allocate NotificationApp* (if you have sound) and will use the GameManager to add levels. If you have game settings on the SD card, it should also load and apply those settings.

Your `game_end` will free the Imu* object and release the NotificationApp.

### LevelBehaviour
When your application did `#include "engine/engine.h"` that also included the [engine/level.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/level.h) file.

Your [game_start](#Gamestart) callback add levels using the GameManager. It calls the following function to create a new Level* object: `Level* game_manager_add_level(GameManager* manager, const LevelBehaviour* behaviour)` function.

The [engine\level.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/level.h) defines the `LevelBehaviour` structure as:
```c
typedef struct {
    void (*alloc)(Level* level, GameManager* manager, void* context);
    void (*free)(Level* level, GameManager* manager, void* context);
    void (*start)(Level* level, GameManager* manager, void* context);
    void (*stop)(Level* level, GameManager* manager, void* context);
    size_t context_size;
} LevelBehaviour;
```

#### LevelBehaviour.alloc
- **`alloc`** : Callback to allocate the level. Invoked when a level is added to the game manager (at game_start). Often Entity objects are added to the level in the `alloc` function, but sometimes they are added in the `start` function instead.

#### LevelBehaviour.free
- **`free`** : Callback to free level. Invoked when game manager is shutting down.

#### LevelBehaviour.start
- **`start`** : Callback when a level is started. Invoked when a level is switched to (or the first level added to the game manager). Usually, entity objects have their position set; but some games will also spawn (create) new entity objects in this function.

#### LevelBehaviour.stop
- **`stop`** : Callback when a level is ended. Invoked when a level is switched away (or game manager is stopping). For games that spawn entity in the `start` function, the `stop` function often calls `level_clear` to remove all Entity objects.

#### LevelBehaviour.context_size
- `context_size` : Set to `sizeof(` your context structure `)`. The context will be allocated for you and passed to your methods.

#### LevelBehaviour example
The Air Arkanoid game uses the following in their [levels/level_game.c](https://github.com/flipperdevices/flipperzero-good-faps/blob/dev/air_arkanoid/levels/level_game.c) file:
```c
const LevelBehaviour level_game = {
    .alloc = NULL,
    .free = NULL,
    .start = level_game_start,
    .stop = level_game_stop,
    .context_size = 0,
};
```
In the above example (`level_game`), all of the Entity objects are created in level_game_start. The level is cleared in level_game_stop. This is probably because many of the Entity objects are removed as the game is played.

However, in the [levels/level_menu.c](https://github.com/flipperdevices/flipperzero-good-faps/blob/dev/air_arkanoid/levels/level_menu.c) file the Entity objects are created in level_menu_alloc. The position of the Entity objects are reset in level_menu_start. In the menu, none of the entity are ever destroyed, they are just animated.
```c
const LevelBehaviour level_menu = {
    .alloc = level_menu_alloc,
    .free = NULL,
    .start = level_menu_start,
    .stop = NULL,
    .context_size = sizeof(LevelMenuContext),
};
```

### EntityDescription
When your application did `#include "engine/engine.h"` that also included the [engine/entity.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/entity.h) file.

Your [level_alloc](#levelbehaviouralloc) or [level_start](#levelbehaviourstart) callback add entity using the Level. It calls the following function to create a new Entity* object: `Entity* level_add_entity(Level* level, const EntityDescription* behaviour)` function.

The [engine\entity.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/entity.h) defines the `EntityDescription` structure as:
```c
typedef struct {
    void (*start)(Entity* self, GameManager* manager, void* context);
    void (*stop)(Entity* self, GameManager* manager, void* context);
    void (*update)(Entity* self, GameManager* manager, void* context);
    void (*render)(Entity* self, GameManager* manager, Canvas* canvas, void* context);
    void (*collision)(Entity* self, Entity* other, GameManager* manager, void* context);
    void (*event)(Entity* self, GameManager* manager, EntityEvent event, void* context);
    size_t context_size;
} EntityDescription;
```

#### EntityDescription.start
- **`start`** : Callback when an entity is added to a level.

#### EntityDescription.stop
- **`stop`** : Callback when an entity is removed from a level (or game switches level).

#### EntityDescription.update
- **`update`** : Callback for an entity to update its position or state. Often this will use Imu* or GameInput* for a player entity.

#### EntityDescription.render
- **`render`** : Callback for an entity to render on the canvas. NOTE: This function will typically still be called one additional time after the stop function is invoked!

#### EntityDescription.collision
- **`collision`** : Callback when this entity collider intersects another entity collider. Collision often adjusts the position and may remove one of the objects from the level.

#### EntityDescription.event
- **`event`** : Callback when a custom event matches this entity description.

#### EntityDescription example
The Air Arkanoid game uses the following in their [levels/level_game.c](https://github.com/flipperdevices/flipperzero-good-faps/blob/dev/air_arkanoid/levels/level_game.c) file:
```c
static const EntityDescription ball_desc = {
    .start = ball_start,
    .stop = NULL,
    .update = ball_update,
    .render = ball_render,
    .collision = NULL,
    .event = NULL,
    .context_size = sizeof(Ball),
};
```
In the above example (ball_desc), the ball_start adds a collider to the ball entity. The update changes the position of the ball entity, sending a custom event to the paddle entity if the ball is off-screen. The render draws the ball on the canvas. The collision callback is not used on the ball entity (when it collides with the paddle or block entity, those callbacks handle the interaction.)

The block_desc below uses the callbacks slightly differently. When the block_desc is created, it's position is set, and a rectangular collider is added to the entity; so the start callback is NULL. The block doesn't move, so the update is also NULL. The render draws the block on the canvas. The collision callback checks if the other object is a ball, and if so, it adjusts the ball speed vector, removes the block entity from the level, plays a sound, and if there are 0 blocks remaining it switches the level to a "You win!" message level.
```c
static const EntityDescription block_desc = {
    .start = NULL,
    .stop = NULL,
    .update = NULL,
    .render = block_render,
    .collision = block_collision,
    .event = NULL,
    .context_size = sizeof(Block),
};
```

### GameManager
When your application did `#include "engine/engine.h"` that also included the [engine/game_manager.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/game_manager.h) file.

#### game_manager_add_level
Your Game start callback will want to add levels to the game. You add a level using the following API: `Level* game_manager_add_level(GameManager* manager, const LevelBehaviour* behaviour);` NOTE: The first level that is added to the game is automatically started.

#### game_manager_sprite_load
Your Entity may decide to render an image, known as a Sprite. You typically create .PNG images and the build process converts the file into .FXBM image files. You can load a Sprite using the following API: `Sprite* game_manager_sprite_load(GameManager* manager, const char* path);` NOTE: If the path was already loaded, the cached image instance will be returned.

#### game_manager_input_get
Your Entity update code may want to get user input, to move the player object. You can get the InputState using the following API: `InputState game_manager_input_get(GameManager* manager);` The InputState has three properties: `pressed`, `held` and `released`. Possible flags are `GameKeyLeft`, `GameKeyRight`, `GameKeyUp`, `GameKeyDown`, `GameKeyOk` & `GameKeyBack`. `(input.held & GameKeyLeft)` and `(input.pressed & GameKeyBack)` are examples of using the InputState. 

#### game_manager_current_level_get
You can get the current level that is being rendered. The API is: `Level* game_manager_current_level_get(GameManager* manager);`

#### game_manager_next_level_set
To switch to a different level, use the following API: `void game_manager_next_level_set(GameManager* manager, Level* level);`

#### game_manager_game_stop
To exit the application, use the following API: `void game_manager_game_stop(GameManager* manager);`

#### game_manager_show_fps_set
When you configure the game variable, you set if the fps (frames per second) information should be displayed. If your application wants to dynamically enable displaying the information, you can use the following API: `void game_manager_show_fps_set(GameManager* manager, bool show_fps);`

#### game_manager_entity_level_get
A new API was added that gets the level an entity was added to. This API is fairly slow, so only use if you can't figure out a different way? `Level* game_manager_entity_level_get(GameManager* manager, Entity* entity);`

#### game_manager_engine_get
Most games shouldn't need direct access to the GamEngine. If you need direct access you can use `GameEngine* game_manager_engine_get(GameManager* manager);`

### Level
When your application did `#include "engine/engine.h"` that also included the [engine/level.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/level.h) file.

You get a Level* object when you call [`Level* game_manager_add_level(GameManager* manager, const LevelBehaviour* behaviour);`](#game_manager_add_level), typically within your game_start callback.

#### Level.level_add_entity
You add an Entity to your level using the following API: `Entity* level_add_entity(Level* level, const EntityDescription* behaviour);`

#### Level.level_remove_entity
You remove an Entity from your level using the following API: `void level_remove_entity(Level* level, Entity* entity);`  You typically end up doing this during a collision, or when an object (like bonus coin) has been rendered past a certain duration.

#### Level.level_clear
You can remove ALL Entity objects from a level using the following API: `void level_clear(Level* level, LevelClearCallback callback, void* context); // void cb(Level* level, void* context);`. NOTE: in the past this API only took a single `Level* level` parameter.

#### Level.level_context_get
You can get the context object associated with this Level* object using the following API: `void* level_context_get(Level* level);`

#### Level.level_send_event
You can send events to all entities matching receiver_desc (or NULL for all entity object in the level) using the following API: `void level_send_event(Level* level, Entity* sender, const EntityDescription* receiver_desc, uint32_t type, EntityEventValue value);`

#### Level.level_entity_count
You can get the number of entities matching desc (or NULL for all entities) using the following API: `size_t level_entity_count(const Level* level, const EntityDescription* desc);`

#### Level.level_entity_get
A new API was added that lets you get a specific entity in a level: `Entity* level_entity_get(const Level* level, const EntityDescription* description, size_t index);`

### Entity
When your application did `#include "engine/engine.h"` that also included the [engine/entity.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/entity.h) file.

You get an Entity* object when you call [`Entity* level_add_entity(Level* level, const EntityDescription* behaviour);`](#levellevel_add_entity), typically within your [level_alloc](#levelbehaviouralloc) or [level_start](#levelbehaviourstart) callback.

#### entity_context_get
You can get the context object associated with this Entity* object using the following API: `void* entity_context_get(Entity* entity);`

#### entity_pos_get
You can get the current position of the Entity using the following API: `Vector entity_pos_get(Entity* entity);` The [Vector](#vector) structure is defined below.

#### entity_pos_set
You can set the position of the Entity using the following API: `void entity_pos_set(Entity* entity, Vector position);` The [Vector](#vector) structure is defined below.

#### entity_collider_add_circle
An entity can have one collider associated with it. You can add a circle collider using `void entity_collider_add_circle(Entity* entity, float radius);`. When two colliders intersect the [entity_collision](#entitydescriptioncollision) callback will be invoked.

#### entity_collider_add_rect
An entity can have one collider associated with it. You can add a rectangular collider using `void entity_collider_add_rect(Entity* entity, float width, float height);`. When two colliders intersect the [entity_collision](#entitydescriptioncollision) callback will be invoked.

#### entity_collider_remove
An entity can have one collider associated with it. To remove the existing collider call `void entity_collider_remove(Entity* entity);`

#### entity_collider_offset_set
The position of the entity is assumed to be the center. If your render is using a different offset, you can create an offset for your collider using `void entity_collider_offset_set(Entity* entity, Vector offset);`

#### entity_collider_offset_get
The position of the entity is assumed to be the center. If your render is using a different offset, you can create get the offset for your collider using `Vector entity_collider_offset_get(Entity* entity);`

#### entity_send_event
You can send an event to a specific Entity using `void entity_send_event(Entity* sender, Entity* receiver, GameManager* manager, uint32_t type, EntityEventValue value);`.  If you want to send to multiple Entities, see [Level.level_send_event](#levellevel_send_event) instead.

#### entity_description_get
You can get the EntityDescription that was used to create the Entity* object using the following API: `const EntityDescription* entity_description_get(Entity* entity);`. This can be helpful, in a collider where you want to see if an entity is of a particular type.

### Vector
When your application did `#include "engine/engine.h"` that also included the [engine/entity.h] file which included the [engine/vector.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/vector.h) file. The file defined functions for manipulation and also the Vector structure (with x and y being float values).
```c
typedef struct {
    float x;
    float y;
} Vector;

#define VECTOR_ZERO ((Vector){0, 0})
```

The Entity (and their collider) use a Vector to represent position.

#### vector_add
You can add two vectors using `Vector vector_add(Vector a, Vector b);`. For the second parameter you can also use `Vector vector_addf(Vector a, float b);` which adds b amount to both the x and y. In latest API there is also a `vector_add(a,b)` that supports float, int or Vector for the b param.

#### vector_sub
You can subtract two vectors using `Vector vector_sub(Vector a, Vector b);`. For the second parameter you can also use `Vector vector_subf(Vector a, float b);` which subtracts b amount from both the x and y. In latest API there is also a `vector_sub(a,b)` that supports float, int or Vector for the b param.

#### vector_mul
You can multiply two vectors using `Vector vector_mul(Vector a, Vector b);`. For the second parameter you can also use `Vector vector_mulf(Vector a, float b);` which multiplies b amount from both the x and y. In latest API there is also a `vector_mul(a,b)` that supports float, int or Vector for the b param.

#### vector_div
You can divide two vectors using `Vector vector_div(Vector a, Vector b);`. For the second parameter you can also use `Vector vector_divf(Vector a, float b);` which divides b amount from both the x and y. In latest API there is also a `vector_div(a,b)` that supports float, int or Vector for the b param.

#### vector_lev
In latest API you can get the length of the vector (sqrt(x^2+y^2)) using the following API: `float vector_length(Vector v);`

#### vector_normalize
In latest API you can normalize a vector so the distance is 1.0 (or 0) using `Vector vector_normalize(Vector v);`

#### vector_dot
In the latest API you can calculate a dot product (a.x*b.x + a.y*b.y) using `float vector_dot(Vector a, Vector b);`

#### vector_rand
In the latest API you can create a random vector (both x and y will be a value between 0 and 1.0) using `Vector vector_rand();`

### Sprite
When your application did `#include "engine/engine.h"` that also included the [engine/game_manager.h] file which included the [engine/sprite.h](https://github.com/flipperdevices/flipperzero-game-engine/blob/dev/sprite.h) file.

Sprites are typically .png files that are converted into an .fxbm image. Your **application.fam** file should have the following commands, which will convert the .png files in the **sprites** folder into the .fxbm files in the **assets/sprites** folder:
```
    fap_extbuild=(
        ExtFile(
            path="${FAP_SRC_DIR}/assets",
            command="${PYTHON3} ${FAP_SRC_DIR}/engine/scripts/sprite_builder.py ${FAP_SRC_DIR.abspath}/sprites ${TARGET.abspath}/sprites",
        ),
    ),
```

To load a sprite, you use the [`Sprite* game_manager_sprite_load(GameManager* manager, const char* path);`](#game-manager-sprite-load) function. The path is just the name of the sprite, such as **"logo_air.xfbm"**. The path will automatically search in the assets/sprites folder. Using the GameManager function means that it will manage the asset, so you do not need to use `Sprite* sprite_alloc(const char* path);` or `void sprite_free(Sprite* sprite);`. The GameManager also does caching of the image, so calling `game_manager_sprite_load` is fairly lightweight (strcmp thru a single link list of loaded Sprite* objects).

#### sprite_get_width
You can get the width of a sprite using `size_t sprite_get_width(Sprite* sprite);` This returns a property that was populated when the Sprite was loaded.

#### sprite_get_height
You can get the height of a sprite using `size_t sprite_get_height(Sprite* sprite);` This returns a property that was populated when the Sprite was loaded.

#### canvas_draw_sprite
You can draw a sprite on a Canvas* using `void canvas_draw_sprite(Canvas* canvas, Sprite* sprite, int32_t x, int32_t y);`. The x and y are left and top coordinates of the Sprite image. 

A Sprite is usually used with an Entity, which has its position as a Vector in the center of the image. In that case, something like the following is fairly common to recenter the Sprite:
```c
static void my_entity_render(Entity* entity, GameManager* manager, Canvas* canvas, void* context) {
    UNUSED(manager);
    MyContext* my_context = context; // Replace MyContext with your Entity context type (having a "Sprite* sprite" property).
    if (my_context->sprite) {
        Vector pos = entity_pos_get(entity); // Get position of entity.
        Vector size = (Vector){sprite_get_width(my_context->sprite), sprite_get_height(my_context->sprite)}; // Width & height of sprite
        pos = vector_sub(pos, vector_divf(size, 2.0f)); // Divide size in half to find center point, then subtract from the entity position
        canvas_draw_sprite(canvas, my_context->sprite, pos.x, pos.y); // Render the sprite
    }
}
```

## Sequence

### Starting game
- **game_start** - Adds all levels to the game (each `game_manager_add_level` function call will invoke **level_alloc**). NOTE: The first call to `game_manager_add_level` will also invoke **level_start**.
- **level_alloc** - Adds all entity to the level (each `level_add_entity` function call will invoke **entity_start**). NOTE: Some games add entity in **level_start** instead.
- **entity_start** - Sets the context for the entity and sets the entity position. It also typically adds a collider (either rectangle or circle).
- **level_start** - Resets the entity position. In some games, this function will call `level_add_entity` which invokes **entity_start**.

### Playing game
- **entity_update** - Sets new position of Entity. This may use IMU or game manager input to get the new position. Some items (like a ball) may just change position based on some preset vector.
- **entity_collision** - Handles when two object collide. May change context, play sound, vibrate, blink, etc. Can remove entity, check remaining level entity count, or change level (e.g. transition to game over/won screen)
- **entity_event** - Handles custom event that was sent to the entity (either directly or from the Level).
- **entity_render** - Renders the Entity on the canvas. This may use a Sprite.

### Level remove entity
Entities are typically removed when:
- collision
- only supposed to spawn for x seconds (bonus coin)
- switching levels

- **entity_stop** - Called when an Entity is removed from the level. You can release resources the Entity created (see **entity_render** below).
- **entity_render** - This will typically get called one more time after the **entity_stop** was invoked, so if resources are released, your render needs to detect and not render.

### Switching Levels
- **entity_stop** - Called on each entity in the previous level. Release any resources used in start.
- **level_stop** - Called on previous level. Release any resources used in start.
- **level_start** - Reset entity positions, or spawn new entities.
- **entity_start** - called if level_start allocated an Entity. Set context for entity & set entity position. Add entity collider.

### Exiting Game
- **level_stop** - Release any resources used in start.
- **level_free** - Release any resource used in alloc.
- **entity_stop** - Release any resources used in start.
- **game_stop** - Release any resource used in start.
