from __future__ import annotations
from .typecheck import *
from .console_view import ConsoleView

from .import core
from .settings import Settings

import sublime
import sublime_plugin


class DebuggerPreConsoleWindowHooks(sublime_plugin.WindowCommand):
	def run(self):
		if not _window_has_output_views(self.window):
			for command in Settings.console_layout_begin:
				self.window.run_command(command['command'],  args=command.get('args'))

		for command in Settings.console_layout_focus:
			self.window.run_command(command['command'],  args=command.get('args'))

class DebuggerPostConsoleViewHooks(sublime_plugin.TextCommand):
	def run(self):
		self.view.settings().set('debugger.OutputView', True)

class DebuggerPostConsoleWindowHooks(sublime_plugin.WindowCommand):
	def run(self):
		def run():
			if not _window_has_output_views(self.window):
				for command in Settings.console_layout_end:
					self.window.run_command(command['command'],  args=command.get('args'))

		sublime.set_timeout(run, 0)

def _window_has_output_views(window: sublime.Window):
	for view in window.views():
		if view.settings().has('debugger.OutputView'):
			return True
	return False


class ConsoleOutputView(ConsoleView):	
	def __init__(self, window: sublime.Window, name: str, on_close: Callable[[], None]|None = None):

		DebuggerPreConsoleWindowHooks(window).run()
		view = window.new_file(flags=sublime.SEMI_TRANSIENT)
		DebuggerPostConsoleViewHooks(view).run()

		super().__init__(view)

		self.on_close = on_close
		self.window = window
		self.name = name
		self.on_pre_view_closed_handle = core.on_pre_view_closed.add(self.view_closed)
		self.view.set_name(name)
		self.write('')

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


