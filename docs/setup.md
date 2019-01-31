# Getting Started Guide
This project attemps to match Visual Studio Code's Debugger fairly closely so their documentation can be pretty helpful. See [https://code.visualstudio.com/docs/editor/debugging](https://code.visualstudio.com/docs/editor/debugging)

## Setting up your debugger
- Opening the debug panel
  - from the command palette `Debugger: Open`

- Install a debug adapter by running: ```Debugger: Install adapter``` from the command palette.
  - These are just a few of the debug adapters out there
  - You can add your own to the [settings file](https://github.com/daveleroy/sublime_db/blob/master/debug.sublime-settings)

- Add a configuration ```Debugger: Add Configuration``` from the command palette (or add one manually, see below).
  - Configurations are added to `debug.configurations` in project settings and use the same configuration format as Visual Studio Code. Most adapters come with some configuration snippets. 
  - Add configuration can also be accessed by clicking the gear icon and selecting `-- Add Configuration --`.
  - If you are running in a sublime project these configuration snippets can be inserted automatically into your settings in your project file.
  - Example configuration
```
"debug.configurations" : [
	{
		"name" : "Name of your configuration", 
		"request" : "launch",
		"type" : "adapter name",
		...
	}
]
```

- Start debugging
  - click the gear icon to select a configuration to use while debugging
  - click the play icon to start the debugger or run `Debugger: Start` (if no configuration is selected it will ask you to select or add one)


## Settings
Settings can either be set at the project level or globally.
Project settings can be changed by appending `debug.` to the setting name 

Within a `.sublime_settings` file
- `open_at_startup` `false` the debug panel will open the first that a window with this setting is activated
- `display` `output` this chooses where the debug UI is renderer
- `ui_scale` `12` scales the entire debugger UI

Within a `.sublime_project` file settings object
- `debug.open_at_startup`
- `debug.display`
- `debug.ui_scale`

## Default Debuggers
This project comes with some pre-configured debuggers
* chrome - https://github.com/Microsoft/vscode-chrome-debug
* python - https://github.com/Microsoft/vscode-python
* go - https://github.com/Microsoft/vscode-go
* php - https://github.com/felixfbecker/vscode-php-debug
* lldb - https://github.com/vadimcn/vscode-lldb

## Debugger Specific Information
- python
  - See vscode [https://code.visualstudio.com/docs/python/debugging](https://code.visualstudio.com/docs/python/debugging)

## Troubleshooting
- Look in the debug console for errors (usually red)
- Look in the sublime console for errors
- Try the same configuration/adapter in Visual Studio Code (There is a good chance your issue is with the adapter so check out the outstanding issues for it)
