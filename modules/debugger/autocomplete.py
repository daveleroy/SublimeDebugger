from ..typecheck import *
from .. import core
from .. import dap

import sublime
import sublime_plugin

class Autocomplete:
	_for_window = {} #type: Dict[int, Autocomplete]

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
		del Autocomplete._for_window[self.id]

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
		core.run(self.get_completions(view, text))
