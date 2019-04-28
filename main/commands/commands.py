from sublime_db.core.typecheck import (
	Any,
	Callable,
	Optional
)
import sublime
import sublime_plugin

from sublime_db import core
from sublime_db import ui
from sublime_db.main.debug_adapter_client.types import Variable

def DebuggerInterface_for_window(window: sublime.Window):
	from sublime_db.main.debugger_interface import DebuggerInterface
	debugger = DebuggerInterface.for_window(window)
	return debugger

def Debugger_for_window(window: sublime.Window):
	return DebuggerInterface_for_window(window).debugger

class WindowCommand(sublime_plugin.WindowCommand):
	def run(self, **args) -> None:
		core.call_soon_threadsafe(self._run_main, args)

	def _run_main(self, args) -> None:
		self.run_main(**args)
	def run_main(self, **args) -> None:
		from sublime_db.main.debugger_interface import DebuggerInterface
		debugger = DebuggerInterface.for_window(self.window)
		if debugger:
			debugger.show()
			self.run_main_debugger_interface(debugger, **args)
		else:
			print('No debugger open for window, ignoring command')

	def run_main_debugger_interface(self, debugger: 'DebuggerInterface', **args) -> None:
		assert False, "expected run_main_debugger_interface or run_main to be overriden"

class Autocomplete:
	_for_window = {}

	@staticmethod
	def for_window(window):
		id = window.id() 
		if id in Autocomplete._for_window:
			return Autocomplete._for_window[id]
		return None

	@staticmethod
	def create_for_window(window):
		id = window.id() 
		if id in Autocomplete._for_window:
			return Autocomplete._for_window[id]
		r = Autocomplete(id)
		
		return r

	def __init__(self, id):
		self.enabled = False
		self.id = id
		Autocomplete._for_window[id] = self

	def dispose(self):
		del Autocomplete.for_window[self.id]

	def enable(self):
		self.enabled = True

	def disable(self):
		self.enabled = False


class AutoCompleteTextInputHandler(ui.TextInput):
	text_input_handlers = []
	def __init__(self, placeholder=None, initial=None, on_cancel=None, arg_name="text"):
		super().__init__(placeholder, initial, on_cancel, arg_name)
		window = sublime.active_window()
		if window:
			self.autocomplete  = Autocomplete.for_window(window)
		
	def preview(self, args):
		if self.autocomplete:
			self.autocomplete.enable()

	def cancel(self):
		if self.autocomplete:
			self.autocomplete.disable()
		return super().cancel()
	def validate(self, args):
		if self.autocomplete:
			self.autocomplete.disable()
		return super().validate(args)

class AutocompleteEventListener(sublime_plugin.EventListener):
	def __init__(self) -> None:
		super().__init__()
		self.completions = [] #type: List[CompletionItem]
		self.getting_completions_text = "."
		self.used_completions = False
		self.ignore_next_modification = False

	@core.async
	def get_completions(self, view: sublime.View, text: str) -> core.awaitable[None]:
		from sublime_db.main.debugger_interface import DebuggerInterface
		window = view.window()
		m = DebuggerInterface.for_window(window)
		if not m:
			return
		adapter = m.debugger.adapter
		if not adapter:
			return
		self.completions = yield from adapter.Completions(text, len(text) + 1, m.debugger.frame)
		view.run_command("hide_auto_complete")
		view.run_command("auto_complete", {
                    'disable_auto_insert': True,
                    'next_completion_if_showing': False
                })

	def on_query_completions(self, view, prefix, locations) -> Any:
		window = view.window()
		if not window:
			return
		autocomplete = Autocomplete.for_window(window)
		if not autocomplete or not autocomplete.enabled:
			return

		items = []
		for completion in self.completions:
			items.append([completion.label, completion.text or completion.label])
		return items

	def on_modified(self, view: sublime.View) -> None:
		window = view.window()
		if not window:
			return
		autocomplete = Autocomplete.for_window(window)
		if not autocomplete or not autocomplete.enabled:
			return
		text = view.substr(sublime.Region(0, view.size()))
		print('auto complete: ', text)
		core.run(self.get_completions(view, text))

all_commands_visible = False
def run_command_from_pallete(command, args):
	window = sublime.active_window()
	def cb():
		global all_commands_visible
		all_commands_visible = True
		window.run_command("hide_overlay", {
				"overlay": "command_palette",
			}
		)
		window.run_command("show_overlay", {
				"overlay": "command_palette",
				"text" : "Debugger:",
				"command": command,
				"args" : args
			}
		)
		all_commands_visible = False
	sublime.set_timeout(cb, 0)
	

class InvisibleWindowCommand(WindowCommand):
	def is_visible(self):
		return all_commands_visible
	def close(self):
		def cb():
			self.window.run_command("hide_overlay", {
					"overlay": "command_palette",
				})
		#when we do this while a command is closing it crashes sublime
		sublime.set_timeout(cb, 0)

	def description(self, **args):
		return "????asdf"
class TextInputHandler(sublime_plugin.TextInputHandler):
	def __init__(self, callback=None, placeholder=None, initial=None, name="text"):
		super().__init__()
		# self.name = name
		self.callback = callback
		self._placeholder = placeholder
		self._initial = initial
		self._name = name

	def placeholder(self):
		return self._placeholder
	def initial_text(self):
		return self._initial
	def confirm(self, text):
		if self.callback:
			self.callback(text)
	def next_input(self, args):
		return None

	def name(self):
		return self._name

class ListInputItem:
	def __init__(self, name, description = None, next_input = None):
		self.name = name
		self.description = description
		self.next_input = next_input

class ListInputHandler(sublime_plugin.ListInputHandler):
	def __init__(self, values, placeholder=None, index=0, on_cancel=None, name="list"):
		super().__init__()
		self._next_input = None
		self.values = values
		self._placeholder = placeholder
		self._index = index
		self._on_cancel = on_cancel
		self._confirmed = False
		self._name = name

	def name(self):
		return self._name

	def placeholder(self):
		return self._placeholder

	def list_items(self):
		items = []
		for index, value in enumerate(self.values):
			items.append([value.name, index])
		return (items, self._index)

	def confirm(self, value):
		self._next_input = self.values[value].next_input
		self._confirmed = True
		return value
	def validate(self, value):
		return True

	def next_input(self, args):
		return self._next_input

	def cancel(self):
		print("cancel")
		self._on_cancel_internal()
		if self._on_cancel:
			self._on_cancel()


	def description(self, value, text):
		return self.values[value].description or self.values[value].name



all_commands = []
command_id = 0
command_data = {}

def run_input_command(input, run):
	global command_id
	command_id += 1
	command_data[command_id] = [input, run]

	window = sublime.active_window()
	def on_cancel():
		def cb():
			window.run_command("hide_overlay", {
					"overlay": "command_palette",
				})
		#when we do this while a command is closing it crashes sublime
		sublime.set_timeout(cb, 0)

	input._on_cancel_internal = on_cancel

		
	def cb():
		global all_commands_visible
		all_commands_visible = True
		window.run_command("hide_overlay", {
				"overlay": "command_palette",
			}
		)
		window.run_command("show_overlay", {
				"overlay": "command_palette",
				"command": "sublime_debug_input",
				"args": {
					"command_id" : command_id
				}
			}
		)
		all_commands_visible = False
	sublime.set_timeout(cb, 0)

# class SublimeDebugInputCommand(InvisibleWindowCommand):
# 	def run(self, **args):
# 		command_data[args["command_id"]][1](**args)
# 	def input(self, args):
# 		return command_data[args["command_id"]][0]
