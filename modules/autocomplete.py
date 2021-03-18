from __future__ import annotations
from .typecheck import *

from .import core

from .dap import types as dap

import sublime
import sublime_plugin

class Autocomplete:
	_for_window = {} #type: dict[int, Autocomplete]

	@staticmethod
	def for_window(window: sublime.Window):
		id = window.id()
		if id in Autocomplete._for_window:
			return Autocomplete._for_window[id]
		return None

	@staticmethod
	def create_for_window(window: sublime.Window):
		id = window.id()
		if id in Autocomplete._for_window:
			return Autocomplete._for_window[id]
		r = Autocomplete(id)
		return r

	def __init__(self, id: int):
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
		self.completions = [] #type: list[dap.CompletionItem]
		self.getting_completions_text = "."
		self.used_completions = False
		self.ignore_next_modification = False

	def on_query_completions(self, view: sublime.View, prefix: str, locations: list[int]) -> Any:
		window = view.window()
		if not window:
			return
		autocomplete = Autocomplete.for_window(window)
		if not autocomplete or not autocomplete.enabled:
			return

		from .debugger import Debugger
		debugger = Debugger.get(view.window())
		if not debugger or not debugger.sessions.has_active:
			return

		completions = sublime.CompletionList()

		text = view.substr(sublime.Region(0, view.size()))
		row, col = view.rowcol(locations[0])

		@core.schedule
		async def fetch():
			items = []
			for completion in await debugger.sessions.active.completions(text, col + 1):
				items.append([completion.label, completion.text or completion.label])
			completions.set_completions(items)

		core.run(fetch())

		return completions

	def on_modified(self, view: sublime.View) -> None:
		window = view.window()
		if not window:
			return
		autocomplete = Autocomplete.for_window(window)
		if not autocomplete or not autocomplete.enabled:
			return

		view.run_command("auto_complete", {
			'disable_auto_insert': True,
			'next_completion_if_showing': False
		})
