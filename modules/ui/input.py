from ..typecheck import *

import sublime
import sublime_plugin
import threading

from .. import core
from . import view_drag_select

command_id = 0
command_data = {}
sublime_command_visible = False
is_running_input = False

class DebuggerInputCommand(sublime_plugin.WindowCommand):
	def run(self, command_id, **args):
		global is_running_input
		is_running_input = False
		run_main = command_data[command_id][1]
		run_not_main = command_data[command_id][2]
		if run_not_main:
			run_not_main(**args)
		def call():
			run_main(**args)
		core.call_soon_threadsafe(call)

	def input(self, args):
		return command_data[args["command_id"]][0]
	def is_visible(self):
		return sublime_command_visible

def on_view_drag_select(event):
	if is_running_input:
		window = sublime.active_window()
		window.run_command("hide_overlay", {
			"overlay": "command_palette",
		})

view_drag_select.add(on_view_drag_select)
def run_input_command(input, run, on_cancel=None, run_not_main=None):
	global command_id
	command_id += 1
	current_command = command_id
	command_data[current_command] = [input, run, run_not_main]

	window = sublime.active_window()
	def on_cancel_internal():
		def cb():
			# since we are async here we don't want to hide the panel if a new one was presented
			if current_command == command_id:
				window.run_command("hide_overlay", {
						"overlay": "command_palette",
					})
		#when we do this while a command is closing it crashes sublime
		sublime.set_timeout(cb, 0)
		global is_running_input
		is_running_input = False

	input._on_cancel_internal = on_cancel_internal
	if on_cancel:
		input._on_cancel = on_cancel

	def cb():
		global sublime_command_visible
		sublime_command_visible = True
		
		# if you don't clear the text then the debugger_input command can't be found in the command pallete....
		window.run_command("show_overlay", {
				"overlay": "command_palette",
				"text": "",
			}
		)
		window.run_command("hide_overlay", {
				"overlay": "command_palette",
			}
		)
		global is_running_input
		is_running_input = True
		window.run_command("show_overlay", {
				"overlay": "command_palette",
				"command": "debugger_input",
				"args": {
					"command_id" : command_id
				}
			}
		)
		sublime_command_visible = False
	sublime.set_timeout(cb, 0)


class TextInput(sublime_plugin.TextInputHandler):
	def __init__(self, placeholder=None, initial=None, on_cancel=None, arg_name="text"):
		super().__init__()
		self._placeholder = placeholder
		self._initial = initial
		self.arg_name = arg_name
		self._on_cancel = on_cancel
		self._on_cancel_internal = None
	def placeholder(self):
		return self._placeholder
	def initial_text(self):
		return self._initial
	def next_input(self, args):
		return None
	def name(self):
		return self.arg_name
	def cancel(self):
		print('canceld')
		if self._on_cancel_internal:
			self._on_cancel_internal()
		if self._on_cancel:
			self._on_cancel()

class ListInputItem:
	def __init__(self, text, name = None, next_input = None):
		self.text = text
		self.name = name
		self.next_input = next_input

class ListInput(sublime_plugin.ListInputHandler):
	def __init__(self, values, placeholder=None, index=0, on_cancel=None, arg_name="list"):
		super().__init__()
		self._next_input = None
		self.values = values
		self._placeholder = placeholder
		self.index = index
		self._on_cancel = on_cancel
		self.arg_name = arg_name
		self._on_cancel_internal = None

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
		self._next_input = self.values[value].next_input
		return value
	def validate(self, value):
		return True

	def next_input(self, args):
		return self._next_input

	def cancel(self):
		if self._on_cancel_internal:
			self._on_cancel_internal()
		if self._on_cancel:
			self._on_cancel()

	def description(self, value, text):
		return self.values[value].name or self.values[value].text



class InputListItem:
	def __init__(self, run, text, name = None):
		self.text = text
		self.run = run
		self.name = name

class InputList(sublime_plugin.ListInputHandler):
	id = 0

	def __init__(self, values: List[InputListItem], placeholder=None, index=0, on_cancel=None, arg_name="list"):
		super().__init__()
		self._next_input = None
		self.values = values
		self._placeholder = placeholder
		self.index = index
		self._on_cancel = on_cancel
		self._on_cancel_internal = None

		self.arg_name = "list_{}".format(InputList.id)
		InputList.id += 1
	def run (self):
		def on_run(**args):
			pass
		run_input_command(self, on_run)
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
			core.call_soon_threadsafe(run)
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
		if self._on_cancel:
			self._on_cancel()

	def description(self, value, text):
		return self.values[value].name or self.values[value].text


class InputText(sublime_plugin.TextInputHandler):
	id = 0
	def __init__(self, run=None, placeholder=None, initial=None, on_cancel=None):
		super().__init__()
		self._placeholder = placeholder
		self._initial = initial
		self._on_cancel = on_cancel
		self._on_cancel_internal = None
		self._run = run
		self.arg_name = "text_{}".format(InputText.id)
		InputText.id += 1

	def placeholder(self):
		return self._placeholder
	def initial_text(self):
		return self._initial
	def next_input(self, args):
		if callable(self._run):
			core.call_soon_threadsafe(self._run, args[self.arg_name])
			return None
		return self._run
	def name(self):
		return self.arg_name
	def cancel(self):
		print('canceld')
		if self._on_cancel_internal:
			self._on_cancel_internal()
		if self._on_cancel:
			self._on_cancel()

	def run (self):
		def on_run(**args):
			pass
		run_input_command(self, on_run)

def InputListItemCheckedText(run: Callable[[str], None], name: str, description: str, value: Optional[str]):
	if value:
		input_name ="● {}: {}".format(name, value)
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
		input_name ="● {}".format(true)
	else:
		input_name = "○ {}".format(false)

	return InputListItem(
		run,
		input_name,
	)
