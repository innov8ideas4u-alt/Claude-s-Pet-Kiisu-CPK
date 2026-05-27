The FuriMessageQueue is typically used in an application for communicating events.  In your callback routine you will _put items into the queue and in your processing routine you will _get items from the queue.  Items are processed in First-In-First-Out (FIFO) order.

Once you _put an item into the queue, the next line of your code will run -- which allows for a non-blocking coding pattern.  However, if the queue is full, then your _put statement will block for up to the duration specified.  If you have a value other than FuriWaitForever, you should check the return status to see if it is FuriStatusOk (or something else) if you care to handle timeouts, etc.

In your processing code you _get an item from the queue.  This call will block if the queue is empty for up to the duration specified.  If you have a value other than FuriWaitForever, you should check the return status to see if it is FuriStatusOk (or something else) if you care to handle timeouts, etc.


# Key concepts
## Import furi.h
Import furi.h to bring in the message queue feature.
```c
#include <furi.h>  // does a #include "core/message_queue.h"
```

## Enumeration of event types
Create an enumeration of event types that you want to be able to queue. 
```c
typedef enum {
    MyEventTypeKey,
} MyEventType;
```

## Struct w/event type & data
Create a structure with the event type and the associated data.
```c
typedef struct {
    MyEventType type; // The reason for this event.
    InputEvent input; // This data is specific to keypress data.
    // TODO: Add additional properties that are helpful for your events.
} MyEvent;
```

## Allocate queue
Allocate a queue.  The capacity of the queue (first parameter to furi_message_queue_alloc) mostly depends on how often you are dequeuing messages.  Typically, applications use sizes around 8, but 16 and 32 are also used in various examples.  The subghz_chat application uses 80, which is the largest I've seen so far. 
```c
FuriMessageQueue* queue = furi_message_queue_alloc(8, sizeof(MyEvent));
// If the allocation fails, then queue will be set to NULL 
//  (so you cannot use it & should probably just exit the app.)
```

## Queue message
In one of your callback routines, queue a message.
```c
// For example, an input_callback has "InputEvent* input_event" as the first parameter and 
// a context as the second parameter. Typically, from the context you are able to access 
// the queue object.  This is accomplished by having FuriMessageQueue as the callback context, 
// or storing the queue as a property in your context.
MyEvent event = {.type = MyEventTypeKey, .input = *input_event};
furi_message_queue_put(queue, &event, FuriWaitForever);
```

## Dequeue message
Dequeue messages in a loop until you get done event.
```c
MyEvent event;
bool keep_processing = true;
while (keep_processing) {
   if(furi_message_queue_get(queue, &event, FuriWaitForever) == FuriStatusOk) {
      // Process the event, set keep_processing to false if this is the done event.
   } else {
      // We failed to get a message from a queue when timeout was FuriWaitForever!
      keep_processing = false;
   }
}
```

## Free queue
Free the queue when your application is exiting.
```c
furi_message_queue_free(queue);
```