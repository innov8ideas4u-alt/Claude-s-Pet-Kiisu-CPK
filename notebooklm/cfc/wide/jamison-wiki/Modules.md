# ** Page under development
This page is currently under development.

# Introduction
Modules are a [User Interface](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/User-Interface#modules) concept, but the topic is so big I decided to make a separate page for them.  The code for all of the modules is found in the applications/services/gui/modules folder in the firmware. 

Modules are views that you can configure with specific data, then leverage the view in your own application.  All modules expose _alloc, _free and _get_view methods.  Many modules also expose methods to configure the module and to set additional callbacks needed by the module (like result_callback, validator_callback, etc.)  

For a list of all of the modules available in applications/services/gui, please see [A Visual Guide to Flipper Zero GUI Components](https://brodan.biz/blog/a-visual-guide-to-flipper-zero-gui-components/) over on brodan.biz/blog.

Lots of information we can add about Widget. I wonder if Instantiator has anything written already?

# TODO - Write about each module

# TextBox
<img alt='text-box' src='https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/7d908217-06d5-44c7-9c6f-61fedc2c1801'><br />
TextBox is a Module that handles display of large amounts of text, and supports scrolling.

## header file
Import the header file for the TextBox object.

```c
#include <gui/modules/text_box.h>
```
## text_box_alloc

Returns a TextBox object & allocates resources (such as model).

```c
TextBox* text_box = text_box_alloc();
```

## text_box_reset

Resets the allocated TextBox object to default state (text set to NULL, font reset to default, focus is at the beginning of the text).

```c
text_box_reset(text_box);
```


## text_box_get_view

Returns the View associated with a TextBox.

```c
TextBox* text_box_view = text_box_get_view(text_box);
// Typically, apps register the returned View with a view dispatcher, then switch to it to show the view.
```

## text_box_set_text

Sets the text which will be displayed in the text box. The length of the text is only limited by Flipper availble resources, so take appropriate recautions if you plan to display a text with unknown length (such as some log for example).

```c
text_box_set_text(text_box, "Enter your name");
```

## text_box_set_font

<img alt='text-box-font-text' src='https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/89870a7e-14bd-46f1-b445-e356a0c8e23f'>
<img alt='text-box-font-hex' src='https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/9d664af4-ce87-4763-99b6-d031bc5490a5'>

Sets the display font for TextBox (`TextBoxFontText` or `TextBoxFontHex`).
Font is set to `TextBoxFontText` when `text_box_alloc()` or `text_box_reset()` called.

```c
text_box_set_font(text_box, TextBoxFontHex);
```

## text_box_set_focus

Sets the cursor position in a TextBox. `TextBoxFocusStart` puts cursor at the beginning of the text, `TextBoxFocusEnd` puts the cursor at the end of ext. `text_box_alloc()` or `text_box_reset()` both put cursor at the beginning of the text.

```c
text_box_set_focus(text_box, TextBoxFocusEnd);
```

## text_box_free

Frees all resources allocated by text_box_alloc.



# TextInput
<img alt='text-input' src='https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/a37a36c7-53cf-430f-aff3-95f4d74140a4' width=30%><br/>
TextInput is a Module that has a header row (prompt text) and a keyboard for the user to enter data.  When the user clicks on 'ENTER' it will run a validator.  If the validation fails, it will show the validation messsage.  If the validation passes (or there is no validator) then it will invoke the result callback with the text from the user.  Long press on the keyboard inverts the case (lower/upper) from what is displayed.  This keyboard only seems to support uppercase A-Z, lowercase a-z, digits 0-9, space, underscore.

## header file
Import the header file for the TextInput object.

```c
#include <gui/modules/text_input.h>
```

## text_input_alloc
Returns a TextInput object & allocates resources (such as model and timer).

```c
TextInput* text_input = text_input_alloc();
```

## text_input_reset
Clears the buffers, cursors and header text that is associated with the TextInput.  This is already called for your during ``text_input_alloc``.

```c
// Clear everything, including the header text.
text_input_reset(text_input);
```

## text_input_set_header_text
Sets the header text (prompt at the top of input).  

```c
text_input_set_header_text(text_input, "Enter your name");
```

## text_input_set_validator
<img alt='text-input' src='https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/ccb4fb21-92c2-499d-b1cf-e329e869b9fb' width=30%><br/>
When ENTER is pressed on the keyboard, if a validator is set it will invoke the validation callback to confirm the entry is valid.  The callback returns true if the entry is valid, and false if it is invalid. ``text_input_set_validator`` sets the ``TextInputValidatorCallback`` and context parameter to pass to the validation callback.  The TextInputValidator takes three parameters.  The first parameter (const char* text) is the text to validate. The second parameter is a FuriString* with the error message to display.  The third parameter is the context that was originally passed to ``text_input_set_validator``.  NOTE: The validation message does not automatically wrap, so you need to test your message to ensure it fits properly (use \n for forced line breaks).  

```c
// The first parameter is the text the user entered.
// The second parameter is a FuriString that you can set for returning error message.
// The third parameter is the context that was passed when registering the callback.
bool text_input_validator(const char* text, FuriString* error, void* context) {
    UNUSED(context);
    bool validated = true;
    if(strlen(text) < 3) {
        furi_string_set(error, "123456789012345\nWWWWWWWWWWWW\niiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii!");
        validated = false;
    }

    return validated;
}
```

When configuring your text_input, you would use code similar to the following:
  ```c
  // The context parameter will be the void* context your callback will get.
  text_input_set_validator(app->text_input, text_input_validator, my_context);
  ```

## text_input_set_result_callback
Sets the result callback that gets invoked when the user presses ENTER on the keyboard and validation passed (or no validator was present).

```c
void text_input_callback(void* context) {
  UNUSED(context);
  // User has entered text, which is stored in the buffer we provided when registering this callback.
}
```

When configuring your text_input, you would use code similar to the following:
  ```c
  uint8_t user_name_size = 16;
  char* user_name = malloc(user_name_size);
  text_input_set_result_callback(text_input, text_input_callback, my_context, user_name, user_name_size, true);
  ```

## text_input_get_view
Returns the View associated with a TextInput.

```c
View* input_view = text_input_get_view(text_input);
// Typically, apps register the returned View with a view dispatcher, then switch to it to show the view.
```

## text_input_free
Frees all resources allocated by text_input_alloc, including the timer resource.

```c
text_input_free(text_input);
```

# VariableItemList
<img alt='variable item list' src='https://github.com/jamisonderek/flipper-zero-tutorials/assets/7028096/8c0e3041-d64e-44b3-bf05-88c36245df6f' width=30%><br/>
VariableItemList is a Module that is often used for configuration.  Each added item has a label, a current value, an index, a count, and a callback.  Left and right arrows appear/disappear depending on where your index is relative to the count.  When left or right button is pressed, a callback for that item is invoked.  The callback has access to context and the new index.  The callback typically returns the updated text to display.  When up or down is pressed, the selected item changes.  When OK is pressed, the enter callback is invoked.


## header file
Import the header file for the VariableItemList object.

```c
#include <gui/modules/variable_item_list.h>
```

## variable_item_list_alloc
Returns a VariableItemList object & allocates resources (such as model).

```c
VariableItemList* variable_item_list = variable_item_list_alloc();
```

## variable_item_list_reset
Clears the items and strings associated with the list.  TODO: It does not clear out position or window_position; so what happens if different size number of items are added?

```c
// Remove all the items from the list.
variable_item_list_reset(variable_item_list);
```

## variable_item_list_add
Adds an item to the list.  Specify the label, total entries for this item, callback, and a context for the item.  The returned object is a VariableItem*, which is updated with ``variable_item_set_current_value_index`` and ``variable_item_set_current_value_text`` to display the current values.

Typically, you have a callback that will update the text based on current item index:
```c
void x_offset_change_callback(VariableItem* item) {
   App* app = variable_item_get_context(item); // get context passed during variable_item_list_add.
   uint8_t index = variable_item_get_current_value_index(item);
   variable_item_set_current_value_text(item, x_offset_strings[index]);
   app->x_offset = x_offset_values[index];
}
```

Here is the code that adds an item to the list...
```c
VariableItem* item = variable_item_list_add(variable_item_list, 
                                            "X offset", // label to display
                                            COUNT_OF(x_offset_strings), // number of choices
                                            x_offset_change_callback, // callback
                                            app); // context [use variable_item_get_context(item) to access]
```

And then you will want to use the returned value to add the current index and text...
```c
variable_item_set_current_value_index(item, 0);
variable_item_set_current_value_text(item, x_offset_strings[0]);
```

## variable_item_set_current_value_index
Used to set the current index of the VariableItem* that was returned by ``variable_item_list_add``.  This should be less than the total count that was passed to the add method.  If the index is 0, there will be no left arrow icon.  If the index is (total-1) there will be no right arrow icon.

```c
variable_item_set_current_value_index(item, 0);
```

## variable_item_set_current_value_text
Used to set the current text of the VariableItem* that was returned by ``variable_item_list_add``.  This is used both to set the initial value and also in the update callback to change the text based on the ``variable_item_get_current_value_index``.

```c
variable_item_set_current_value_text(item, x_offset_strings[i]);
```

## variable_item_get_context
Gets the context of the VariableItem* that was specified when the item was added.

```c
App* app = variable_item_get_context(item); // get context passed during variable_item_list_add.
```

## variable_item_get_current_value_index
Gets the current index of the VariableItem*.  Typically, this is used in the update callback to get the current index and then set the new text based on this index.

```c
uint8_t index = variable_item_get_current_value_index(item);
```

## variable_item_list_get_view
Returns the View associated with a VariableItemList.

```c
View* list_view = variable_item_list_get_view(variable_item_list);
// Typically, apps register the returned View with a view dispatcher, then switch to it to show the view.
```

## variable_item_list_set_enter_callback
Sets a callback to invoke when the OK button is pressed.

Define a callback to invoke:
```c
// The selected item index is a uint32_t but the internal position index is actually a uint8_t.
void enter_callback(void* context, uint32_t index) {
}
```

Register the callback to invoke when the OK button is pressed
```c
variable_item_list_set_enter_callback(variable_item_list, 
                                      enter_callback, // callback function to invoke on OK press
                                      app); // context object to pass to the callback function
```

## variable_item_list_free
Frees all resources allocated by variable_item_list_alloc.

```c
variable_item_list_free(variable_item_list);
```

## advanced scenarios
### variable_item_list_set_selected_item
Sets which item is selected.  This is helpful if you want restore a previous selection (like have a config screen that continues where it was before).

```c
variable_item_list_set_selected_item(variable_item_list, index);
```

### variable_item_set_current_value_index
Sets which entry is selected within the item.

```c
variable_item_set_current_value_index(variable_item, index);
```

### variable_item_set_values_count
Sets the total number of entries for an item.

```c
### variable_item_set_values_count(variable_item, new_count);
```

### variable_item_list_get_selected_item_index
Gets which item index is selected.  Typically, you would register an enter callback, which will already be provided this index.

```c
uint8_t current_index = variable_item_list_get_selected_item_index(variable_item_list);
```