# Getting Started Guide

## Settings
Settings can either be set at the project level or globally.
Project settings can be changed by appending `debug.` to the setting name 

Within a `.sublime_settings` file
- `open_at_startup` `false` the debug panel will open the first that a window with this setting is activated
- `display` `output` this chooses where the debug UI is renderer

Within a `.sublime_project` file
- `debug.open_at_startup`
- `debug.display`


## Setting up your debugger
This project is configured to work in mostly the same way as VSCode. Configurations are added to `configurations` in user settings or `debug.configurations` in project settings and use the same configuration format as VSCode.

Example configuration
```
{
	"name" : "Name of your configuration", 
	"request" : "launch",
	"type" : "adapter name",
	...
}

```
## Default Debuggers
This project comes with some pre-configured debuggers
* chrome
* python
* go
* php
* lldb

## Adding a new debugger
The list of supported debuggers can be found in the `adapters` setting. The `type` attribute in a configuration tells us which adapter we will be running. 
Example adapter configuration
```
"adapter name" : {
	"command" : ["node", ".../adapter.js"]
}
```
