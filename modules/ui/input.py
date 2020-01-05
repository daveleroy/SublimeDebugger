from ..typecheck import *
from ..import core
from . import view_drag_select

import sublime
import sublime_plugin

class CommandPaletteInputCommand:
	running_command = None #type: Optional[CommandPaletteInputCommand]

	def __init__(self, window, input, on_cancel):
		self.window = window
		self.input = input

		def _on_cancel():
			CommandPaletteInputCommand.running_command = None
			if on_cancel: on_cancel()

		input._on_cancel_internal = _on_cancel

		# if you don't clear the text then the debugger_input command can't be found in the command pallete....
		self.window.run_command("show_overlay", {
			"overlay": "command_palette",
			"text": "",
		})

		self.hide_overlay()

		CommandPaletteInputCommand.running_command = self

		self.window.run_command("show_overlay", {
			"overlay": "command_palette",
			"command": "debugger_input",
		})

	def hide_overlay(self):
		self.window.run_command("hide_overlay", {
			"overlay": "command_palette",
		})


class DebuggerInputCommand(sublime_plugin.WindowCommand):
	def __init__(self, window):
		super().__init__(window)
		view_drag_select.add(self.on_view_drag_select)

	def input(self, args):
		if not CommandPaletteInputCommand.running_command:
			raise core.Error("expected running_command")

		input = CommandPaletteInputCommand.running_command.input
		CommandPaletteInputCommand.running_command = None
		return input

	def is_visible(self):
		return CommandPaletteInputCommand.running_command is not None

	def on_view_drag_select(self, event):
		if CommandPaletteInputCommand.running_command is not None:
			CommandPaletteInputCommand.running_command.hide_overlay()

class InputListItem:
	def __init__(self, run, text, name=None):
		self.text = text
		self.run = run
		self.name = name

class InputList(sublime_plugin.ListInputHandler):
	id = 0

	def __init__(self, values: List[InputListItem], placeholder=None, index=0):
		super().__init__()
		self._next_input = None
		self.values = values
		self._placeholder = placeholder
		self.index = index
		self._on_cancel_internal = None
		self.arg_name = "list_{}".format(InputList.id)
		InputList.id += 1

	def run(self):
		CommandPaletteInputCommand(sublime.active_window(), self, None)

	def name(self):
		return self.arg_name

	def placeholder(self):
		return self._placeholder

	def list_items(self):
		items = []
		for index, value in enumerate(self.values):
			items.append([value.text, index])
		return (items, self.index)

	def confirm(self, value):
		run = self.values[value].run
		if callable(run):
			run()
		else:
			self._next_input = run
		return value

	def validate(self, value):
		return True

	def next_input(self, args):
		n = self._next_input
		self._next_input = None
		return n

	def cancel(self):
		if self._on_cancel_internal:
			self._on_cancel_internal()

	def description(self, value, text):
		return self.values[value].name or self.values[value].text

class InputEnable (Protocol):
	def enable(self):
		...
	def disable(self):
		...

class InputText(sublime_plugin.TextInputHandler):
	id = 0

	def __init__(self, run=None, placeholder=None, initial=None, enable_when_active: Optional[InputEnable] = None):
		super().__init__()
		self._placeholder = placeholder
		self._initial = initial
		self._on_cancel_internal = None
		self._run = run
		self._enable = enable_when_active
		self.arg_name = "text_{}".format(InputText.id)
		InputText.id += 1

	def placeholder(self):
		if self._enable:
			self._enable.enable()
		return self._placeholder

	def initial_text(self):
		return self._initial

	def next_input(self, args):
		if callable(self._run):
			self._run(args[self.arg_name])
			return None
		return self._run

	def name(self):
		return self.arg_name

	def cancel(self):
		if self._enable:
			self._enable.disable()
		if self._on_cancel_internal:
			self._on_cancel_internal()

	def run(self):
		if self._enable:
			self._enable.disable()

		CommandPaletteInputCommand(sublime.active_window(), self, None)

def InputListItemCheckedText(run: Callable[[str], None], name: str, description: str, value: Optional[str]):
	if value:
		input_name = "● {}: {}".format(name, value)
	else:
		input_name = "○ {}: {}".format(name, description)

	return InputListItem(
		InputText(
			run,
			description,
			value
		),
		input_name,
		name
	)

def InputListItemChecked(run: Callable[[], None], true: str, false: str, value: bool):
	if value:
		input_name = "● {}".format(true)
	else:
		input_name = "○ {}".format(false)

	return InputListItem(
		run,
		input_name,
	)
