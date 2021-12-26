from __future__ import annotations
from .typecheck import *

from .import core

from .import dap

import sublime
import sublime_plugin

class Autocomplete:
	_for_window: dict[int, Autocomplete] = {}

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
		self.completions: list[dap.CompletionItem] = []
		self.getting_completions_text = "."
		self.used_completions = False
		self.ignore_next_modification = False

	def on_query_completions(self, view: sublime.View, prefix: str, locations: list[int]) -> Any:
		if not view.settings().get('debugger.autocomplete'):
			return

		window = view.window()
		if not window:
			return

		from .debugger import Debugger
		debugger = Debugger.get(window)
		if not debugger or not debugger.is_active:
			return

		completions = sublime.CompletionList()

		text = view.substr(sublime.Region(0, view.size()))
		row, col = view.rowcol(locations[0])

		@core.schedule
		async def fetch():
			items: list[sublime.CompletionItem] = []
			for completion in await debugger.active.completions(text, col + 1):
				item = sublime.CompletionItem(
					completion.sortText or completion.label,
					annotation=completion.label,
					completion=completion.text or completion.label,
					completion_format=sublime.COMPLETION_FORMAT_TEXT,
					kind=sublime.KIND_AMBIGUOUS
				)
				items.append(item)
			completions.set_completions(items)

		core.run(fetch())

		return completions

	def on_modified(self, view: sublime.View) -> None:
		if not view.settings().get('debugger.autocomplete'):
			return

		view.run_command("auto_complete", {
			'disable_auto_insert': True,
			'next_completion_if_showing': False
		})
