# VS Code Mock Debug

Mock Debug allows to "debug" markdown files (like this).
The text of the markdown is considered the "program to debug" and certain keywords trigger specific functionality (Yes, this language is not "Turing Complete" :-)

## Running or Debugging

With the "Run/Debug" split button in the editor header you can easily "run" or "debug" a Markdown file without having to configure a debug configuration.
"Running" a Markdown file has no visible effect. "Debugging" a Markdown file starts the debugger and stops on the first line.
  
## Stacks

If debugging stops on a line, the line becomes a stack in the CALL STACK with the individual words shown as frames.
The following line results in a long stack trace and shows the paging feature:
a b c d e f g h i j k l m n o p q r s t u v w x y z a b c d e f g h i j k l m n o p q r s t u v w x y z a b c d e f g h i j k l m n o p q r s t u v w x y z

## Variables

Words starting with `$` are treated as variables. Letter casing doesn't matter.

Writing to a variable is done with the `$variable=value` syntax. The format of the value determines the type of the variable. Here are examples for all types:
- Integer: $i=123
- String: $s="abc"
- Boolean: $b1=true $b2=false
- Float: $f=3.14
- Object: $o={abc}

Variables are shown in the VARIABLES view under the "Locals" and "Globals" scopes whenever the debugger stops.
In addition a variable's value is shown when hovering over a variable and VS Code's Inline Values features shows the value at the end of the line.

A variable where the name contains the string "lazy" will be shown in the VARIABLES view with a UI that requires an additional click to retrieve the value. Two examples:
- Lazy Integer: $lazyInteger=999
- Lazy Object: $lazyObject={foo}

## Breakpoints

Breakpoints can be set in the breakpoint margin of the editor (even before a Mock Debug session was started).
If a Mock Debug session is active, breakpoints are "validated" according to these rules:

* if a line is empty or starts with `+` we don't allow to set a breakpoint but move the breakpoint down
* if a line starts with `-` we don't allow to set a breakpoint but move the breakpoint up
* a breakpoint on a line containing the word `lazy` is not immediately validated, but only after hitting it once.

## Data Breakpoints

Data Breakpoints can be set for different access modes in the VARIABLES view of the editor via the context menu.
The syntax `$variable` triggers a read access data breakpoint, the syntax `$variable=value` a write access data breakpoint.
r
Examples:
- Read Access: $i
- Write Access: $i=999

## Disassembly View

If a markdown line contains the word 'disassembly', the context menu's "Open Disassembly View" command is enabled and the Disassembly view shows (fake) assembly instructions and "instruction stepping" and "instruction breakpoints" are supported.

## Exceptions

If a line contains the word `exception` or the pattern `exception(name)` an exception is thrown.
To make the debugger stop when an exception is thrown, two "exception options" exist in the BREAKPOINTS view:
- **Named Exception**: if enabled and configured with a condition (e.g. `xxx`) the debugger will break on the `exception(xxx)` pattern.
- **Other Exceptions**: if enabled the debugger will break on the word `exception` and the `exception(...)` pattern.

## Output events

* If a line containes patterns like `log(xxx)`, `prio(xxx)`, `out(xxx)`, or `err(xxx)` the argument `xxx` is shown in the debug console as follows:
  * **log**: text is shown in debug console's default color to indicate that it is received from the debugger itself
  * **prio**: text is shown as a notification to indicate that it is received from the debugger itself and has high priority
  * **out**: text is shown in blue to indicate program output received from "stdout"
  * **err**: text is shown in red to indicate program output received from "stderr"
* If the argument `xxx` is `start` or `end`, a "log group" is started or ended.

Some examples:
```
prio(a high priority message)
out(some text from stdout)
err(some text from stderr)

log(start)
log(some text in group)
log(start)
log(some text on level 2 group)
log(more text on level 2 group)
log(end)
log(startCollapsed)
log(some text on a collapsed group)
log(end)
log(more text in group)
log(end)
````

## The End