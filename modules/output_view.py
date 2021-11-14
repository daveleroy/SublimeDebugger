from __future__ import annotations
from .typecheck import *
from .console_view import ConsoleView

from .import core
from .import ui
from .settings import Settings

import re
import sublime
import sublime_plugin

class OutputView(ConsoleView):	
	@staticmethod
	def layout_double_column(window: sublime.Window):
		if window.num_groups() == 1:
			window.run_command('set_layout', {'cells': [[0, 0, 1, 1], [1, 0, 2, 1]], 'cols': [0.0, 0.5, 1.0], 'rows': [0.0, 1.0]})
			window.set_minimap_visible(False)

		window.run_command('focus_group', { 'group': 1})

	@staticmethod
	def layout_single_column(window: sublime.Window):
		if window.num_groups() >= 2 and not window.views_in_group(1):
			window.run_command('set_layout', {'cells': [[0, 0, 1, 1]], 'cols': [0.0, 1.0], 'rows': [0.0, 1.0]})
			window.set_minimap_visible(True)

	def __init__(self, window: sublime.Window, name: str, on_close: Callable[[], None]|None = None):
		OutputView.layout_double_column(window)

		view = window.new_file(flags=sublime.TRANSIENT)
		super().__init__(view)

		self.on_close = on_close
		self.window = window

		self.on_pre_view_closed_handle = core.on_pre_view_closed.add(self.view_closed)
		self.view.set_name(name)

	def close(self):
		if not self.is_closed:
			self.view.close()

	@property
	def is_closed(self):
		return not self.view.is_valid()

	def view_closed(self, view: sublime.View):
		if view == self.view:
			sublime.set_timeout(self.dispose, 0)

	def dispose(self):
		super().dispose()
		self.close()
		if self.on_close: self.on_close()
		OutputView.layout_single_column(self.window)

