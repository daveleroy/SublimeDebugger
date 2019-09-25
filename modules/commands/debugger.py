import sublime_plugin
import sublime

from .. import core

from ..debugger.debugger import DebuggerStateful
from ..debugger.debugger_interface import DebuggerInterface
from ..debugger.adapter_configuration import AdapterConfiguration, install_adapter

from . import select_configuration

def DebuggerInState(window: sublime.Window, state: int) -> bool:
	debugger = DebuggerInterface.debuggerForWindow(window)
	if debugger and debugger.state == state:
		return True
	return False


class DebuggerReplaceContentsCommand(sublime_plugin.TextCommand):
	def run(self, edit, characters) -> None:
		self.view.replace(edit, sublime.Region(0, self.view.size()), characters)


class RunDebuggerInterfaceCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		core.call_soon_threadsafe(self.run_main)

	def run_main(self) -> None:
		main = DebuggerInterface.for_window(self.window)
		if main:
			main.show()
			self.on_main(main)
		else:
			print('No debugger open for window, ignoring command')

	def on_main(self, main: DebuggerInterface) -> None:
		pass

class DebuggerShowLineCommand(sublime_plugin.TextCommand):
	def run(self, edit, line: int, move_cursor: bool):
		a = self.view.text_point(line, 0)
		region = sublime.Region(a, a)
		self.view.show_at_center(region)
		if move_cursor:
			self.view.sel().clear()
			self.view.sel().add(region)