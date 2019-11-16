from ..typecheck import *

import sublime
import sublime_plugin

from .. import core
from .. import ui
from .. import dap

def DebuggerInterface_for_window(window: sublime.Window):
	from ..debugger.debugger_interface import DebuggerInterface
	debugger = DebuggerInterface.for_window(window)
	return debugger

def Debugger_for_window(window: sublime.Window):
	return DebuggerInterface_for_window(window).debugger

class DebuggerWindowCommand(sublime_plugin.WindowCommand):
	def run(self, **args) -> None:
		core.call_soon_threadsafe(self._run_main, args)

	def _run_main(self, args) -> None:
		self.run_main(**args)
	def run_main(self, **args) -> None:
		from ..debugger.debugger_interface import DebuggerInterface
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

class AutocompleteEventListener(sublime_plugin.EventListener):
	def __init__(self) -> None:
		super().__init__()
		self.completions = [] #type: List[dap.CompletionItem]
		self.getting_completions_text = "."
		self.used_completions = False
		self.ignore_next_modification = False

	@core.coroutine
	def get_completions(self, view: sublime.View, text: str) -> core.awaitable[None]:
		from ..debugger.debugger_interface import DebuggerInterface
		window = view.window()
		m = DebuggerInterface.for_window(window)
		if not m:
			return
		adapter = m.debugger.adapter
		if not adapter:
			return
		self.completions = yield from adapter.Completions(text, len(text) + 1, m.debugger.selected_frame)
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
