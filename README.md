# This project is a work in progress

Graphical Debugger for sublime text for languages that support the debug adapter protocol.

See [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/)

# Getting started
![Image of GUI](https://raw.githubusercontent.com/daveleroy/sublime_db/master/docs/images/basic.png)

- Opening the debug panel
  - from the command palette `Debugger: Open`
- Add breakpoints by double tapping on the gutter. 
  - Hover over the breakpoint to edit it or click on it in the breakpoint panel (bottom left)

# Installing

1. Clone into your sublime Packages directory
2. Install a debug adapter by running: ```Debugger: Install adapter``` inside sublime text.
  - These are just a few of the debug adapters out that that have been added
  - You can add your own to the [settings file](https://github.com/daveleroy/sublime_db/blob/master/debug.sublime-settings)
