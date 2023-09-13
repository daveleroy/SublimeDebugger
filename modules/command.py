from __future__ import annotations
from typing import Any, Callable, Protocol

from .settings import Settings

from .import core
from .debugger import Debugger
from .ansi import generate_ansi_syntax
import sublime_plugin
import sublime
import json

from .import ui

class CommandActionKwargs(Protocol):
	def __call__(self, debugger: Debugger, **kwargs) -> Any: ...
class CommandAction(Protocol):
	def __call__(self, debugger: Debugger) -> Any: ...

class CommandWindowActionKwargs(Protocol):
	def __call__(self, window: sublime.Window, **kwargs) -> Any: ...
class CommandWindowAction(Protocol):
	def __call__(self, window: sublime.Window) -> Any: ...

class Command:
	menu_context = 1 << 0
	menu_main = 1 << 1
	menu_commands = 1 << 2
	menu_no_prefix = 1 << 3
	menu_widget = 1 << 4

	open_without_running = 1 << 5
	visible_debugger_open = 1 << 6
	visible_debugger_closed = 1 << 7

	development = 1 << 9

	allow_debugger_outside_project = 1 << 9

	def __init__(self, name: str, key: str|None = None, action:CommandActionKwargs|CommandAction|None = None, window_action:CommandWindowActionKwargs|CommandWindowAction|None=None, enabled: Callable[[Debugger], bool] | None = None, flags: int = -1):

		self.name = name
		self.action = action
		self.key = key

		if flags < 0:
			self.flags = Command.menu_commands|Command.menu_main
		else:
			self.flags = flags

		CommandsRegistry.register(self)

		self.enabled = enabled
		self.action = action
		self.window_action = window_action

	def parameters(self, window: sublime.Window) -> tuple[sublime.Window, Debugger|None]:
		return window, Debugger.get(window)

	def run(self, window: sublime.Window, args: dict[str, Any]):
		debugger = Debugger.get(window)
		if not debugger or not debugger.is_open():
			debugger = Debugger.create(window, skip_project_check = bool(self.flags & Command.allow_debugger_outside_project))

			# don't run this command if the debugger is not visible
			if self.flags & Command.open_without_running:
				return

		if action := self.window_action:
			action(window, **args)

		if action := self.action:
			if debugger: action(debugger, **args)

	def is_visible(self, window: sublime.Window):
		if self.flags & Command.development and not Settings.development:
			return False

		debugger: Debugger | None = Debugger.get(window)
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

class DebuggerCommand (sublime_plugin.WindowCommand):
	def run(self, action: str, **kwargs: dict[str, Any]): #type: ignore
		command = CommandsRegistry.commands_by_action[action]
		command.run(self.window, kwargs)

	def is_enabled(self, action: str, **kwargs: dict[str, Any]): #type: ignore
		command = CommandsRegistry.commands_by_action[action]
		return command.is_enabled(self.window)

	def is_visible(self, action: str, **kwargs: dict[str, Any]): #type: ignore
		command = CommandsRegistry.commands_by_action[action]
		return command.is_visible(self.window)


# allow using debugger_exec to run a build system as a Debugger Task
class DebuggerExecCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs: dict[str, Any]): #type: ignore
		from .debugger import Debugger
		from .dap import Task

		debugger = Debugger.create(self.window)

		task = Task.from_json(kwargs)
		debugger.run_task(task)

class DebuggerInputCommand(sublime_plugin.WindowCommand):
	def input(self, args: Any): #type: ignore
		if not ui.CommandPaletteInputCommand.running_command:
			raise core.Error('expected running_command')

		input = ui.CommandPaletteInputCommand.running_command.input
		ui.CommandPaletteInputCommand.running_command = None
		return input

	def run(self, **args: Any): #type: ignore
		...

	def is_visible(self):
		return ui.CommandPaletteInputCommand.running_command is not None

class CommandsRegistry:
	commands: list[Command] = []
	commands_by_action: dict[str, Command] = {}

	@staticmethod
	def register(command: Command):
		CommandsRegistry.commands.append(command)
		if command.key:
			CommandsRegistry.commands_by_action[command.key] = command

	@staticmethod
	def generate_commands_and_menus():

		def generate_commands(menu: int, prefix: str = "", include_seperators: bool = True):
			out_commands: list[Any] = []


			last_was_section = False
			for command in CommandsRegistry.commands:

				if command.name == '-':
					if include_seperators and not last_was_section:
						last_was_section = True
						out_commands.append({"caption": '-'})
					continue

				if not (command.flags & menu):
					continue

				last_was_section = False

				if command.flags & Command.menu_no_prefix:
					caption = command.name
				else:
					caption = prefix + command.name

				out_commands.append(
					{
						"caption": caption,
						"command": "debugger",
						"args": {
							"action": command.key,
						}
					}
				)
			return out_commands

		def save_commands(path: str, commands: Any) -> None:
			with open(core.package_path(path), 'w') as f:
				json.dump(commands, f, indent=4, separators=(',', ': '))

		commands_palette = generate_commands(Command.menu_commands, prefix="Debugger: ", include_seperators=False)
		# hidden command used for gathering input from the command palette
		commands_palette.append({
			"caption": "Debugger",
			"command": "debugger_input"
		})

		save_commands('contributes/Commands/Default.sublime-commands', commands_palette)


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
		save_commands('contributes/Commands/Main.sublime-menu', main)


		print('Generating commands')

		commands_context = generate_commands(Command.menu_context)
		save_commands('contributes/Commands/Context.sublime-menu', commands_context)


		commands_context = generate_commands(Command.menu_widget)
		save_commands('contributes/Commands/DebuggerWidget.sublime-menu', commands_context)

		syntax = generate_ansi_syntax()
		with open(core.package_path('contributes/Syntax/DebuggerConsole.sublime-syntax'), 'w') as f:
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
