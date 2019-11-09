from ..typecheck import *

import sublime
import sublime_plugin
import json

from .. import core
from .debugger_interface import DebuggerInterface
from .debugger import DebuggerStateful
from ..commands.install_adapters_menu import open_install_adapter_menu
from ..commands import select_configuration


# commands look like...

"""
"command": "debugger_command",
"args": {
	action": "..."
}
"""

# window.run_command("debugger_run", {"action": "generate_commands"})

actions_window = [
	{
		"action": "open",
		"caption": "Open",
		"opens": True,
	},
	{
		"action": "quit",
		"caption": "Quit",
		"run": lambda window, debugger: debugger.dispose(),
	},
	{	"caption": "-" },
	{
		"action": "install_adapters",
		"caption": "Install Adapters",
		"run": lambda window, debugger: open_install_adapter_menu(debugger),
		"opens": True,
	},
	{
		"action": "change_configuration",
		"caption": "Change Configuration",
		"run": lambda window, debugger: select_configuration.run(debugger),
	},
	{	"caption": "-" },
	{
		"action": "start",
		"caption": "Start",
		"command": lambda window, debugger: debugger.on_play,
		"opens": True
	},
	{
		"action": "stop",
		"caption": "Stop",
		"command": lambda window, debugger: debugger.on_stop,
	},
	{	"caption": "-" },
	{
		"action": "pause",
		"caption": "Pause",
		"command": lambda window, debugger: debugger.on_pause,
	},
	{
		"action": "continue",
		"caption": "Continue",
		"command": lambda window, debugger: debugger.on_resume,
	},
	{
		"action": "step_over",
		"caption": "Step Over",
		"command": lambda window, debugger: debugger.on_step_over,
	},
	{
		"action": "step_in",
		"caption": "Step In",
		"command": lambda window, debugger: debugger.on_step_in,
	},
	{
		"action": "step_out",
		"caption": "Step Out",
		"command": lambda window, debugger: debugger.on_step_out,
	},
	{
		"action": "run_command",
		"caption": "Run Command",
		"command": lambda window, debugger: debugger.on_run_command,
	},
	{	"caption": "-" },
	{
		"action": "add_function_breakpoint",
		"caption": "Add Function Breakpoint",
		"command": lambda window, debugger: debugger.add_function_breakpoint,
	},
	{
		"action": "add_watch_expression",
		"caption": "Add Watch Expression",
		"command": lambda window, debugger: debugger.add_watch_expression,
	},
	{	"caption": "-" },
	{
		"action": "save_data",
		"caption": "Save Breakpoints/Watch Expressions/...",
		"command": lambda window, debugger: debugger.save_data,
	},
	{
		"action": "refresh_phantoms",
		"caption": "Refresh Phantoms",
		"run": lambda window, debugger: debugger.refresh_phantoms(),
	},
] #type: List[Dict[str, Any]]


actions_context = [
	{	"caption": "-" },
	{
		"action": "toggle_breakpoint",
		"caption": "Toggle Breakpoint",
		"command": lambda window, debugger: debugger.toggle_breakpoint,
	},
	{
		"action": "toggle_column_breakpoint",
		"caption": "Toggle Column Breakpoint",
		"command": lambda window, debugger: debugger.toggle_column_breakpoint,
	},
	{
		"action": "run_to_current_line",
		"caption": "Run To Cursor",
		"command": lambda window, debugger: debugger.run_to_current_line,
	},
	{	"caption": "-" },
]

actions_window_map = {} #type: Dict[str, Dict[str, Any]]
for actions in (actions_window, actions_context):
	for action in actions:
		action_name = action.get('action')
		if action_name:
			actions_window_map[action_name] = action

class DebuggerCommand (sublime_plugin.WindowCommand):
	def run(self, action: str): #type: ignore
		if action == "generate_commands":
			generate_commands_and_menus()
			return

		core.call_soon_threadsafe(self.run_main, actions_window_map[action])

	def run_main(self, action: dict):
		debugger_interface = DebuggerInterface.for_window(self.window, create=action.get('opens', False))
		
		command = action.get('command')
		if command:
			result = command(self.window, debugger_interface)
			result()

		run = action.get('run')
		if run:
			run(self.window, debugger_interface)

	def is_enabled(self, action: str): #type: ignore
		if action == "generate_commands":
			return True
		action_item = actions_window_map[action]
		

		opens = action_item.get('opens', False)
		if opens:
			return True

		debugger_interface = DebuggerInterface.for_window(self.window)
		if not debugger_interface:
			return False

		command = action_item.get('command')
		if command:
			result = command(self.window, debugger_interface)
			return result.enabled()

		return True

	def is_visible(self, action: str): #type: ignore
		if action == "generate_commands":
			return True

		action_item = actions_window_map[action]
		opens = action_item.get('opens', False)
		return opens or DebuggerInterface.for_window(self.window) != None


def generate_commands_and_menus():
	current_package = core.current_package()
	
	preferences = {
		"caption": "Preferences: Debugger Settings",
		"command": "edit_settings",
		"args": {
		  "base_file": "${packages}/Debugger/debugger.sublime-settings"
		}
	}
	settings = {
		"caption": "Settings",
		"command": "edit_settings",
		"args": {
		  "base_file": "${packages}/Debugger/debugger.sublime-settings"
		}
	}


	def generate_commands(actions, commands, prefix="", include_seperators=True):
		for action in actions:
			if action['caption'] == '-':
				if include_seperators:
					commands.append({"caption" : action['caption']})
				continue

			commands.append(
				{
					"caption" : prefix + action['caption'],
					"command" : "debugger",
					"args": {
						"action": action['action'],
					}
				}
			)

	commands_palette = []
	generate_commands(actions_window, commands_palette, prefix="Debugger: ", include_seperators=False)

	commands_palette.insert(0, preferences)

	# hidden command used for gathering input from the command palette 
	input = {
		"caption" : "_",
		"command" : "debugger_input"
	}
	commands_palette.append(input)
	
	with open(current_package + '/Commands/Commands.sublime-commands', 'w') as file:
		json.dump(commands_palette, file, indent=4, separators=(',', ': '))


	commands_menu = []
	generate_commands(actions_window, commands_menu)
	commands_menu.insert(2, settings)

	main = [{ 
		"caption": "Debugger", 
		"id": "debugger", 
		"children" : commands_menu}
	]
	with open(current_package + '/Commands/Main.sublime-menu', 'w') as file:
		json.dump(main, file, indent=4, separators=(',', ': '))

	print('Generating commands')


	commands_context = []
	generate_commands(actions_context, commands_context)

	with open(current_package + '/Commands/Context.sublime-menu', 'w') as file:
		json.dump(commands_context, file, indent=4, separators=(',', ': '))



	keymap_commands = []

	for action in actions_window + actions_context:
		if action['caption'] == '-':
			continue

		keymap_commands.append(
			{
				"keys" : action.get('keys', "UNBOUND"),
				"command" : "debugger",
				"args": {
					"action": action['action'],
				}
			}
		)

	with open(current_package + '/Commands/Default.sublime-keymap', 'w') as file:
		json.dump(keymap_commands, file, indent=4, separators=(',', ': '))

		