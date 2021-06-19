from __future__ import annotations
from .typecheck import *

# import Debugger; Debugger.modules.debugger.commands.Commands.generate_commands_and_menus();


from .import core
from .debugger import Debugger
from .adapters_registry import AdaptersRegistry

import sublime_plugin
import sublime
import json



menu_context = 1 << 0
menu_main = 1 << 1
menu_commands = 1 << 2
menu_no_prefix = 1 << 3
menu_widget = 1 << 4
open_without_running = 1 << 5
visible_debugger_open = 1 << 6
visible_debugger_closed = 1 << 7

class Command:
	menu_context = 1
	menu_main = 1 << 1
	menu_commands = 1 << 2
	menu_no_prefix = 1 << 3
	menu_widget = 1 << 4

	def __init__(self, name: str, command: str, action: Callable[[sublime.Window], None], flags:int=menu_commands|menu_main):
		self.name = name
		self.action = action
		self.flags = flags
		self.command = command

	def run(self, window: sublime.Window):
		self.action(window)

	def is_visible(self, window: sublime.Window) -> bool:
		return True

	def is_enabled(self, window: sublime.Window) -> bool:
		return True

class CommandDebugger(Command):
	def __init__(self, name: str, command: str, action:Callable[[Debugger], None], enabled: Callable[[Debugger], bool] | None = None, flags: int = menu_commands|menu_main):
		self.name = name
		self.action = action
		self.enabled = enabled
		self.flags = flags
		self.command = command

	def parameters(self, window: sublime.Window) -> tuple[sublime.Window, Debugger|None]:
		return window, Debugger.get(window)

	def run(self, window: sublime.Window):
		debugger = Debugger.get(window)
		if not debugger or not debugger.is_panel_visible():
			debugger = Debugger.get(window, True)
			
			# don't run this command if the debugger is not visible
			if self.flags & open_without_running:
				return

		if not debugger:
			return

		self.action(debugger)

	def is_visible(self, window: sublime.Window):
		debugger = Debugger.get(window)
		if self.flags & visible_debugger_open:
			return bool(debugger)
		if self.flags &  visible_debugger_closed:
			return not bool(debugger)
		return True

	def is_enabled(self, window: sublime.Window):
		debugger = Debugger.get(window)
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
		name='Open',
		command='open',
		action=Debugger.open,
	),
	CommandDebugger (
		name='Quit',
		command='quit',
		action=Debugger.quit,
		flags=menu_commands|menu_main|visible_debugger_open,
	),
	Command(
		name='Settings',
		command='settings',
		action=open_settings,
		flags=menu_main
	),
	Command(
		name='Preferences: Debugger Settings',
		command='settings',
		action=open_settings,
		flags=menu_commands | menu_no_prefix
	),
	Command(
		name='Generate Commands',
		command='generate_commands',
		action=generate_commands,
		flags=menu_commands
	),
	None,
	CommandDebugger (
		name='Install Adapters',
		command='install_adapters',
		action=Debugger.install_adapters,
	),
	CommandDebugger (
		name='Add or Select Configuration',
		command='change_configuration',
		action=Debugger.change_configuration,
	),
	None,
	CommandDebugger (
		name='Start',
		command='start',
		action=Debugger.on_play,
		flags=menu_commands|menu_main|open_without_running
	),
	CommandDebugger (
		name='Start (no debug)',
		command='start_no_debug',
		action=Debugger.on_play_no_debug,
	),
	CommandDebugger (
		name='Stop',
		command='stop',
		action=Debugger.on_stop,
		enabled=Debugger.is_stoppable
	),
	None,
	CommandDebugger (
		name='Resume',
		command='resume',
		action=Debugger.on_resume,
		enabled=Debugger.is_paused
	),
	CommandDebugger (
		name='Pause',
		command='pause',
		action=Debugger.on_pause,
		enabled=Debugger.is_running,
	),
	CommandDebugger (
		name='Step Over',
		command='step_over',
		action=Debugger.on_step_over,
		enabled=Debugger.is_paused
	),
	CommandDebugger (
		name='Step In',
		command='step_in',
		action=Debugger.on_step_in,
		enabled=Debugger.is_paused
	),
	CommandDebugger (
		name='Step Out',
		command='step_out',
		action=Debugger.on_step_out,
		enabled=Debugger.is_paused
	),
	None,
	CommandDebugger (
		name='Input Command',
		command='input_command',
		action=Debugger.on_input_command,
		enabled=Debugger.is_active
	),
	CommandDebugger (
		name='Run Task',
		command='run_task',
		action=Debugger.on_run_task,
	),
	CommandDebugger (
		name='Run Last Task',
		command='run_last_task',
		action=Debugger.on_run_last_task,
		flags=menu_main,
	),
	CommandDebugger (
		name='Add Function Breakpoint',
		command='add_function_breakpoint',
		action=Debugger.add_function_breakpoint,
	),
	CommandDebugger (
		name='Clear Breakpoints',
		command='clear_breakpoints',
		action=Debugger.clear_all_breakpoints,
	),
	CommandDebugger (
		name='Clear Console',
		command='clear_console',
		action=Debugger.clear_terminal_panel,
		flags=menu_widget,
	),
	CommandDebugger (
		name='Show Protocol',
		command='show_protocol',
		action=Debugger.show_protocol_panel,
		flags=menu_widget,
	),
	CommandDebugger (
		name='Add Watch Expression',
		command='add_watch_expression',
		action=Debugger.add_watch_expression,
	),
	CommandDebugger (
		name='Force Save',
		command='save_data',
		action=Debugger.save_data,
	),
	None,
	CommandDebugger (
		name='Toggle Breakpoint',
		command='toggle_breakpoint',
		action=Debugger.toggle_breakpoint,
		flags=menu_context,
	),
	CommandDebugger (
		name='Toggle Column Breakpoint',
		command='toggle_column_breakpoint',
		action=Debugger.toggle_column_breakpoint,
		flags=menu_context,
	),
	CommandDebugger (
		name='Run To Selected Line',
		command='run_to_current_line',
		action=Debugger.run_to_current_line,
		enabled=Debugger.is_paused,
		flags=menu_context,
	),
	None,
]

class DebuggerCommand (sublime_plugin.WindowCommand):
	def run(self, action: str): #type: ignore
		command = Commands.commands_by_action[action]
		command.run(self.window)

	def is_enabled(self, action: str): #type: ignore
		command = Commands.commands_by_action[action]
		return command.is_enabled(self.window)

	def is_visible(self, action: str): #type: ignore
		command = Commands.commands_by_action[action]
		return command.is_visible(self.window)


# allow using debugger_exec to run a build system as a Debugger Task
class DebuggerExecCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		from .debugger import Debugger
		from .dap import Task
		
		debugger = Debugger.get(self.window, create=True)

		task = Task.from_json(kwargs)
		debugger.run_task(task)


class Commands:
	commands_by_action: dict[str, Command] = {}

	@staticmethod
	def initialize():
		for command in commands:
			if not command:
				continue
			Commands.commands_by_action[command.command] = command

		for adapter in AdaptersRegistry.all:
			for command in adapter.commands():
				Commands.commands_by_action[command.command] = command

	@staticmethod
	def generate_commands_and_menus():
		all_commands: list[Command|None] = []
		all_commands.extend(commands)

		for adapter in AdaptersRegistry.all:
			c = adapter.commands()
			if c:
				all_commands.extend(c)

		current_package = core.current_package()

		def generate_commands(menu: int, prefix: str = "", include_seperators: bool = True):
			out_commands: list[Any] = []

			for command in all_commands:
				if not command:
					if include_seperators:
						out_commands.append({"caption": '-'})
					continue

				if not (command.flags & menu):
					continue

				if command.flags & menu_no_prefix:
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
			return out_commands

		def save_commands(file: str, commands: Any):
			with open(current_package + file, 'w') as f:
				json.dump(commands, f, indent=4, separators=(',', ': '))

		commands_palette = generate_commands(menu_commands, prefix="Debugger: ", include_seperators=False)
		# hidden command used for gathering input from the command palette
		commands_palette.append({
			"caption": "Debugger",
			"command": "debugger_input"
		})

		save_commands('/Commands/Commands.sublime-commands', commands_palette)


		main = [{
			"id": "tools",
			"children": [
				{
					"id": "debugger",
					"caption": "Debugger",
					"children": generate_commands(menu_main),
				}
			]}
		]
		save_commands('/Commands/Main.sublime-menu', main)


		print('Generating commands')

		commands_context = generate_commands(menu_context)
		save_commands('/Commands/Context.sublime-menu', commands_context)


		commands_context = generate_commands(menu_widget)
		save_commands('/Commands/Widget Debug.sublime-menu', commands_context)


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
