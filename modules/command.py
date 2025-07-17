from __future__ import annotations
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Iterable

from .settings import Settings

from . import core
from .ansi import generate_ansi_syntax
import sublime_plugin
import sublime

from . import ui
from . import dap

if TYPE_CHECKING:
	from .debugger import Debugger

class DebuggerCommand(sublime_plugin.WindowCommand):
	def want_event(self) -> bool:
		return True

	def run(self, action: str, **kwargs: dict[str, Any]):
		core.info(f'Debugger.{action}', kwargs)
		return DebuggerCommand.action_run(self.window, action, **kwargs)

	def is_enabled(self, action: str, **kwargs: dict[str, Any]):  # type: ignore
		return DebuggerCommand.action_is_enabled(self.window, action, **kwargs)

	def is_visible(self, action: str, **kwargs: dict[str, Any]):  # type: ignore
		return DebuggerCommand.action_is_visible(self.window, action, **kwargs)

	actions: list[CommandProtocol | None] = []
	actions_by_key: dict[str, CommandProtocol] = {}

	@staticmethod
	def register(action: CommandProtocol):
		if action.key:
			DebuggerCommand.actions.append(action)
			DebuggerCommand.actions_by_key[action.key] = action

	@staticmethod
	def action_run(view: sublime.View | sublime.Window, action: str, **kwargs: dict[str, Any]):  # type: ignore
		DebuggerCommand.actions_by_key[action]._run(view, **kwargs)

	@staticmethod
	def action_is_enabled(view: sublime.View | sublime.Window, action: str, **kwargs: dict[str, Any]):  # type: ignore
		return DebuggerCommand.actions_by_key[action]._is_enabled(view, **kwargs)

	@staticmethod
	def action_is_visible(view: sublime.View | sublime.Window, action: str, **kwargs: dict[str, Any]):  # type: ignore
		act = DebuggerCommand.actions_by_key[action]
		if act.development and not Settings.development:
			return False
		return act._is_visible(view, **kwargs)

	@staticmethod
	def generate_commands_and_menus():
		print('Generating commands')

		def generate_commands(commands: Iterable[CommandProtocol | None], prefix: str = '', include_seperators: bool = True):
			out_commands: list[Any] = []

			last_was_section = False
			for command in commands:
				if not command or not command.name:
					if include_seperators and not last_was_section:
						last_was_section = True
						out_commands.append({'caption': '-'})
					continue

				last_was_section = False

				if command.prefix_menu_name:
					caption = prefix + command.name
				else:
					caption = command.name

				out_commands.append(
					{
						'caption': caption,
						'command': 'debugger_text' if command.is_text_command else 'debugger',
						'args': {
							'action': command.key,
						},
					}
				)
			return out_commands

		def save_commands(path: str, commands: Any) -> None:
			core.json_write_file(core.package_path(path), commands, pretty=True)
			# with open(core.package_path(path), 'w') as f:
			# 	json.dump(commands, f, indent=4, separators=(',', ': '))

		menu_commands = filter(lambda c: not c or c.is_menu_commands, DebuggerCommand.actions)
		menu_main_commands = filter(lambda c: not c or c.is_menu_main, DebuggerCommand.actions)
		menu_context_commands = filter(lambda c: not c or c.is_menu_context, DebuggerCommand.actions)
		menu_widget_commands = filter(lambda c: not c or c.is_menu_widget, DebuggerCommand.actions)

		commands_palette = generate_commands(menu_commands, prefix='Debugger: ', include_seperators=False)
		# hidden command used for gathering input from the command palette
		commands_palette.append({'caption': 'Debugger', 'command': 'debugger_input'})

		save_commands('contributes/Commands/Default.sublime-commands', commands_palette)

		main = [
			{
				'id': 'tools',
				'children': [
					{
						'id': 'debugger',
						'caption': 'Debugger',
						'children': generate_commands(menu_main_commands),
					}
				],
			}
		]
		save_commands('contributes/Commands/Main.sublime-menu', main)

		commands_context = generate_commands(menu_context_commands)
		save_commands('contributes/Commands/Context.sublime-menu', commands_context)

		commands_context = generate_commands(menu_widget_commands)
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


class DebuggerTextCommand(sublime_plugin.TextCommand):
	def want_event(self) -> bool:
		return True

	def run(self, edit: sublime.Edit, action: str, **kwargs: dict[str, Any]):
		return DebuggerCommand.action_run(self.view, action, **kwargs)

	def is_enabled(self, action: str, **kwargs: dict[str, Any]):  # type: ignore
		return DebuggerCommand.action_is_enabled(self.view, action, **kwargs)

	def is_visible(self, action: str, **kwargs: dict[str, Any]):  # type: ignore
		return DebuggerCommand.action_is_visible(self.view, action, **kwargs)


class DebuggerInputCommand(sublime_plugin.WindowCommand):
	def input(self, args: Any):  # type: ignore
		if not ui.CommandPaletteInputCommand.running_command:
			raise dap.Error('expected running_command')

		input = ui.CommandPaletteInputCommand.running_command.input
		ui.CommandPaletteInputCommand.running_command = None
		return input

	def run(self, **args: Any):  # type: ignore
		...

	def is_visible(self):
		return ui.CommandPaletteInputCommand.running_command is not None


class CommandsRegistry(type):
	def __new__(cls, name, bases, dct):
		kclass = type.__new__(cls, name, bases, dct)
		DebuggerCommand.register(kclass())
		return kclass


def Section():
	DebuggerCommand.actions.append(None)


class CommandProtocol(metaclass=CommandsRegistry):
	name: str = ''
	key: str = ''

	is_text_command: bool = False

	is_menu_context: bool = False
	is_menu_main: bool = False
	is_menu_commands: bool = False
	is_menu_widget: bool = False
	prefix_menu_name: bool = True

	development: bool = False

	def _run(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		return

	def _is_enabled(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]) -> bool:
		return True

	def _is_visible(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]) -> bool:
		return True


class Action(CommandProtocol):
	name: str = ''
	key: str = ''

	is_menu_commands = True
	is_menu_main = True

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]): ...

	def action(self, debugger: Debugger) -> Any: ...

	def action_with_args(self, debugger: Debugger, **kwargs: Any) -> Any: ...

	def is_visible(self, debugger: Debugger) -> bool:
		return True

	def is_enabled(self, debugger: Debugger) -> bool:
		return True

	def _run(self, view: sublime.View | sublime.Window, **kwargs: Any):
		from .debugger import Debugger

		self.action_raw(view, kwargs)

		debugger = Debugger.get(view)
		if not debugger:
			return

		if not debugger.is_open():
			debugger.open()

		self.action(debugger)
		self.action_with_args(debugger, **kwargs)

	def _is_visible(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		from .debugger import Debugger

		if debugger := Debugger.get(view):
			return self.is_visible(debugger)
		return bool(self.action_raw)

	def _is_enabled(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		from .debugger import Debugger

		if debugger := Debugger.get(view):
			return self.is_enabled(debugger)
		return bool(self.action_raw)


T = TypeVar('T')


class ActionElement(Generic[T], CommandProtocol):
	name: str = ''
	key: str = ''

	element: type[T]

	is_menu_widget = True
	is_text_command = True

	def action(self, debugger: Debugger, element: T): ...

	def is_visible(self, debugger: Debugger, element: T) -> bool:
		return True

	def is_enabled(self, debugger: Debugger, element: T) -> bool:
		return True

	def parameters(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		from .debugger import Debugger

		if not isinstance(view, sublime.View):
			return

		event = kwargs.get('event')
		if not event:
			return

		debugger = Debugger.get(view)
		if not debugger:
			return

		position = view.window_to_layout((event['x'], event['y']))

		# note: this currently only looks at the y position
		if layout := ui.Layout.layout_at_layout_position(view, position):
			element = layout.element_at_layout_position(position, self.element)
			if element:
				return debugger, element

	def _run(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		if args := self.parameters(view, **kwargs):
			self.action(*args)

	def _is_visible(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		if args := self.parameters(view, **kwargs):
			return self.is_visible(*args)
		return False

	def _is_enabled(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		if args := self.parameters(view, **kwargs):
			return self.is_enabled(*args)
		return False
