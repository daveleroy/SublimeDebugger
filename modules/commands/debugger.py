import sublime_plugin
import sublime

from .. import core
from .. debugger.debugger_interface import DebuggerInterface


class DebuggerReplaceContentsCommand(sublime_plugin.TextCommand):
	def run(self, edit, characters) -> None:
		self.view.replace(edit, sublime.Region(0, self.view.size()), characters)
		self.view.sel().clear()


class DebuggerShowLineCommand(sublime_plugin.TextCommand):
	def run(self, edit, line: int, move_cursor: bool):
		a = self.view.text_point(line, 0)
		region = sublime.Region(a, a)
		self.view.show_at_center(region)
		if move_cursor:
			self.view.sel().clear()
			self.view.sel().add(region)
