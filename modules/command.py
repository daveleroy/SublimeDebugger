from __future__ import annotations
from .typecheck import *

from .import core
from .debugger import Debugger
from .adapters_registry import AdaptersRegistry
from .console_view import generate_console_syntax
import sublime_plugin
import sublime
import json

from .import ui

class Command:
	menu_context = 1 << 0
	menu_main = 1 << 1
	menu_commands = 1 << 2
	menu_no_prefix = 1 << 3
	menu_widget = 1 << 4

	open_without_running = 1 << 5
	visible_debugger_open = 1 << 6
	visible_debugger_closed = 1 << 7

	section_start = 1 << 8


	def __init__(self, name: str, action: Callable[[sublime.Window], Any], flags:int = 0):
		self.name = name
		self.action = action
		
		if not flags or flags == Command.section_start:
			self.flags = Command.menu_commands|Command.menu_main
		else:
			self.flags = flags

		self.command: str|None = None 

	def run(self, window: sublime.Window):
		self.action(window)

	def is_visible(self, window: sublime.Window) -> bool:
		return True

	def is_enabled(self, window: sublime.Window) -> bool:
		return True

class CommandDebugger(Command):
	def __init__(self, name: str, action:Callable[[Debugger], Any], enabled: Callable[[Debugger], bool] | None = None, flags: int = 0):
		super().__init__(name, action, flags)
		self.enabled = enabled
		self.action = action

	def parameters(self, window: sublime.Window) -> tuple[sublime.Window, Debugger|None]:
		return window, Debugger.get(window)

	def run(self, window: sublime.Window):
		debugger = Debugger.get(window)
		if not debugger or not debugger.interface.is_open():
			debugger = Debugger.get(window, True)
			
			# don't run this command if the debugger is not visible
			if self.flags & Command.open_without_running:
				return

		if not debugger:
			return

		self.action(debugger)

	def is_visible(self, window: sublime.Window):
		debugger = Debugger.get(window)
		if self.flags & Command.visible_debugger_open:
			return bool(debugger)
		if self.flags &  Command.visible_debugger_closed:
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

class DebuggerCommand (sublime_plugin.WindowCommand):
	def run(self, action: str):
		command = CommandsRegistry.commands_by_action[action]
		command.run(self.window)

	def is_enabled(self, action: str):
		command = CommandsRegistry.commands_by_action[action]
		return command.is_enabled(self.window)

	def is_visible(self, action: str):
		command = CommandsRegistry.commands_by_action[action]
		return command.is_visible(self.window)


# allow using debugger_exec to run a build system as a Debugger Task
class DebuggerExecCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs: dict[str, Any]):
		from .debugger import Debugger
		from .dap import Task
		
		debugger = Debugger.create(self.window)

		task = Task.from_json(kwargs)
		debugger.run_task(task)

class DebuggerInputCommand(sublime_plugin.WindowCommand):
	def input(self, args: Any):
		if not ui.CommandPaletteInputCommand.running_command:
			raise core.Error('expected running_command')

		input = ui.CommandPaletteInputCommand.running_command.input
		ui.CommandPaletteInputCommand.running_command = None
		return input

	def run(self, **args: Any):
		...

	def is_visible(self):
		return ui.CommandPaletteInputCommand.running_command is not None

class CommandsRegistry:
	commands: list[Command] = []
	commands_by_action: dict[str, Command] = {}

	@staticmethod
	def register(command: Command, name: str):
		name = name or command.name
		name = name.rstrip('_')

		core.debug('command:', name or command.name)
		command.command = name
		CommandsRegistry.commands.append(command)
		CommandsRegistry.commands_by_action[name] = command

	@staticmethod
	def generate_commands_and_menus():
		AdaptersRegistry.recalculate_schema()
		
		current_package = core.current_package()

		def generate_commands(menu: int, prefix: str = "", include_seperators: bool = True):
			out_commands: list[Any] = []

			for command in CommandsRegistry.commands:
				if command.flags & Command.section_start:
					if include_seperators:
						out_commands.append({"caption": '-'})

				if not (command.flags & menu):
					continue

				if command.flags & Command.menu_no_prefix:
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

		commands_palette = generate_commands(Command.menu_commands, prefix="Debugger: ", include_seperators=False)
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
					"children": generate_commands(Command.menu_main),
				}
			]}
		]
		save_commands('/Commands/Main.sublime-menu', main)


		print('Generating commands')

		commands_context = generate_commands(Command.menu_context)
		save_commands('/Commands/Context.sublime-menu', commands_context)


		commands_context = generate_commands(Command.menu_widget)
		save_commands('/Commands/Widget Debug.sublime-menu', commands_context)

		syntax = generate_console_syntax()
		with open(current_package + '/Commands/DebuggerConsole.sublime-syntax', 'w') as f:
			f.write(syntax)


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

	@staticmethod
	def initialize_class(Class):
		core.debug('--', Class.__name__, '--')
		for object in vars(Class):
			obj = getattr(Class, object)
			if isinstance(obj, Command):
				CommandsRegistry.register(obj, object)

	@staticmethod
	def initialize():
		from .commands import Commands

		CommandsRegistry.initialize_class(Commands)
		for Class in Commands.__subclasses__():
			CommandsRegistry.initialize_class(Class)

	


# generate_commands_and_menus()




		

	