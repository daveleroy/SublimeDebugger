# import Debugger; Debugger.modules.debugger.commands.Commands.generate_commands_and_menus();

from sublime import windows
from ..typecheck import *
from ..import core
from .debugger import Debugger
from .adapter import Adapters

import sublime_plugin
import sublime
import json


visible_always = 0
visible_created = 1
visible_not_created = 2

menu_context = 1
menu_main = 1 << 1
menu_commands = 1 << 2
menu_no_prefix = 1 << 3

class Command:
	menu_context = 1
	menu_main = 1 << 1
	menu_commands = 1 << 2
	menu_no_prefix = 1 << 3

	def __init__(self, name, action, menus=menu_commands|menu_main):
		self.name = name
		self.action = action
		self.menus = menus
		self.command = action.__name__

	def parameters(self, window):
		return window,

	def run(self, window):
		self.action(window)

	def is_visible(self, window):
		return True

	def is_enabled(self, window):
		return True

class CommandDebugger(Command):
	def __init__(self, name: str, action:Callable[[Debugger], None], enabled: Optional[Callable[[Debugger], bool]]=None, visible=visible_always, menus=menu_commands|menu_main):
		self.name = name
		self.action = action
		self.visible = visible
		self.enabled = enabled
		self.menus = menus
		self.command = action.__name__

	def parameters(self, window):
		return window, Debugger.get(window)

	def run(self, window, debugger):
		# only run command when the debugger is visible otherwise make the debugger visible (or create it)
		if not debugger or not debugger.is_panel_visible():
			Debugger.get(window, True)
			return

		self.action(debugger)

	def is_visible(self, window, debugger):
		if self.visible == visible_created:
			return bool(debugger)
		if self.visible == visible_not_created:
			return not bool(debugger)
		return True

	def is_enabled(self, window, debugger):
		if not self.enabled:
			return True
		if debugger:
			return self.enabled(debugger)
		return False

def open_settings(window: sublime.Window):
	window.run_command('edit_settings', {
		'base_file': '${packages}/Debugger/debugger.sublime-settings'
	})

def generate_commands(window: sublime.Window):
	Commands.generate_commands_and_menus()


commands = [
	CommandDebugger (
		name="Open",
		action=Debugger.open,
	),
	CommandDebugger (
		name="Quit",
		action=Debugger.quit,
		visible=visible_created,
	),
	Command(
		name="Settings",
		action=open_settings,
		menus=menu_main
	),
	Command(
		name="Preferences: Debugger Settings",
		action=open_settings,
		menus=menu_commands | menu_no_prefix
	),
	Command(
		name="Generate Commands",
		action=generate_commands,
		menus=menu_commands
	),
	None,
	CommandDebugger (
		name="Install Adapters",
		action=Debugger.install_adapters,
	),
	CommandDebugger (
		name="Add or Select Configuration",
		action=Debugger.change_configuration,
	),
	None,
	CommandDebugger (
		name="Start",
		action=Debugger.on_play,
	),
	CommandDebugger (
		name="Start (no debug)",
		action=Debugger.on_play_no_debug,
	),
	CommandDebugger (
		name="Stop",
		action=Debugger.on_stop,
		enabled=Debugger.is_stoppable
	),
	None,
	CommandDebugger (
		name="Resume",
		action=Debugger.on_resume,
		enabled=Debugger.is_paused
	),
	CommandDebugger (
		name="Pause",
		action=Debugger.on_pause,
		enabled=Debugger.is_running,
	),
	CommandDebugger (
		name="Step Over",
		action=Debugger.on_step_over,
		enabled=Debugger.is_paused
	),
	CommandDebugger (
		name="Step In",
		action=Debugger.on_step_in,
		enabled=Debugger.is_paused
	),
	CommandDebugger (
		name="Step Out",
		action=Debugger.on_step_out,
		enabled=Debugger.is_paused
	),
	None,
	CommandDebugger (
		name="Input Command",
		action=Debugger.on_input_command,
	),
	CommandDebugger (
		name="Run Task",
		action=Debugger.on_run_task,
	),
	CommandDebugger (
		name="Run Last Task",
		action=Debugger.on_run_last_task,
		menus=menu_main,
	),
	CommandDebugger (
		name="Add Function Breakpoint",
		action=Debugger.add_function_breakpoint,
	),
	CommandDebugger (
		name="Add Watch Expression",
		action=Debugger.add_watch_expression,
	),
	CommandDebugger (
		name="Force Save",
		action=Debugger.save_data,
	),
	None,
	CommandDebugger (
		name="Toggle Breakpoint",
		action=Debugger.toggle_breakpoint,
		menus=menu_context,
	),
	CommandDebugger (
		name="Toggle Column Breakpoint",
		action=Debugger.toggle_column_breakpoint,
		menus=menu_context,
	),
	CommandDebugger (
		name="Run To Selected Line",
		action=Debugger.run_to_current_line,
		enabled=Debugger.is_paused,
		menus=menu_context,
	),
	None,
]

class DebuggerCommand (sublime_plugin.WindowCommand):
	def run(self, action: str): #type: ignore
		command = Commands.commands_by_action[action]
		instance = command.parameters(self.window)
		command.run(*instance)

	def is_enabled(self, action: str): #type: ignore
		command = Commands.commands_by_action[action]
		instance = command.parameters(self.window)
		return command.is_enabled(*instance)

	def is_visible(self, action: str): #type: ignore
		command = Commands.commands_by_action[action]
		instance = command.parameters(self.window)
		return command.is_visible(*instance)


class Commands:
	commands_by_action = {}

	@staticmethod
	def initialize():
		for command in commands:
			if not command:
				continue
			Commands.commands_by_action[command.command] = command

		for adapter in Adapters.all:
			for command in adapter.commands():
				Commands.commands_by_action[command.command] = command

	@staticmethod
	def generate_commands_and_menus():
		all_commands = []
		all_commands.extend(commands)

		for adapter in Adapters.all:
			c = adapter.commands()
			if c:
				all_commands.extend(c)

		current_package = core.current_package()

		def generate_commands(menu, out_commands, prefix="", include_seperators=True):
			for command in all_commands:
				if not command:
					if include_seperators:
						out_commands.append({"caption": '-'})
					continue
				if not (command.menus & menu):
					continue

				if command.menus & menu_no_prefix:
					caption = command.name
				else:
					caption = prefix + command.name

				out_commands.append(
					{
						"caption": caption,
						"command": "debugger",
						"args": {
							"action": command.command,
						}
					}
				)

		commands_palette = [] #type: List[Any]
		generate_commands(menu_commands, commands_palette, prefix="Debugger: ", include_seperators=False)

		# hidden command used for gathering input from the command palette
		input = {
			"caption": "Debugger",
			"command": "debugger_input"
		}
		commands_palette.append(input)

		with open(current_package + '/Commands/Commands.sublime-commands', 'w') as file:
			json.dump(commands_palette, file, indent=4, separators=(',', ': '))

		commands_menu = [] #type: List[Any]
		generate_commands(menu_main, commands_menu)

		main = [{
			"caption": "Debugger",
			"id": "debugger",
			"children": commands_menu}
		]
		with open(current_package + '/Commands/Main.sublime-menu', 'w') as file:
			json.dump(main, file, indent=4, separators=(',', ': '))

		print('Generating commands')

		commands_context = [] #type: List[Any]
		generate_commands(menu_context, commands_context)

		with open(current_package + '/Commands/Context.sublime-menu', 'w') as file:
			json.dump(commands_context, file, indent=4, separators=(',', ': '))

		# keymap_commands = []

		# for action in actions_window + actions_context:
		# 	if action['caption'] == '-':
		# 		continue

		# 	keymap_commands.append(
		# 		{
		# 			"keys": action.get('keys', "UNBOUND"),
		# 			"command": "debugger",
		# 			"args": {
		# 				"action": action['action'],
		# 			}
		# 		}
		# 	)

		# with open(current_package + '/Commands/Default.sublime-keymap', 'w') as file:
		# 	json.dump(keymap_commands, file, indent=4, separators=(',', ': '))

# generate_commands_and_menus()
