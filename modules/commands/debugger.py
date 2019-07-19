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

class DebuggerCommand(RunDebuggerInterfaceCommand):
	def is_visible(self) -> bool:
		return DebuggerInterface.for_window(self.window) is not None


class DebuggerOpenCommand(RunDebuggerInterfaceCommand):
	def run_main(self) -> None:
		main = DebuggerInterface.for_window(self.window, True)
		assert main
		main.show()


class DebuggerToggleBreakpointCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		view = self.window.active_view()
		x, y = view.rowcol(view.sel()[0].begin())
		line = x + 1
		file = view.file_name()
		breakpoint = main.breakpoints.get_breakpoint(file, line)
		if breakpoint is not None:
			main.breakpoints.remove_breakpoint(breakpoint)
		else:
			main.breakpoints.add_breakpoint(file, line)


class DebuggerQuitCommand(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.dispose()

class DebuggerStartCommand(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_play()

class DebuggerStopCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_stop()

	def is_enabled(self) -> bool:
		return not DebuggerInState(self.window, DebuggerStateful.stopped)


class DebuggerPauseCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_pause()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerStateful.running)


class DebuggerStepOverCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_step_over()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerStateful.paused)


class DebuggerStepInCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_step_in()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerStateful.paused)


class DebuggerStepOutCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_step_out()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerStateful.paused)


class DebuggerResumeCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_resume()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerStateful.paused)


class DebuggerRunCommandCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.open_repl_console()


class DebuggerRefreshPhantomsCommand(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		print("Refresh phantoms")
		main.refresh_phantoms()

class DebuggerChangeConfigurationCommand(DebuggerCommand):
	def on_main(self, debugger: 'DebuggerInterface') -> None:
		select_configuration.run(debugger)


class DebuggerShowLineCommand(sublime_plugin.TextCommand):
	def run(self, edit, line: int, move_cursor: bool):
		a = self.view.text_point(line, 0)
		region = sublime.Region(a, a)
		self.view.show_at_center(region)
		if move_cursor:
			self.view.sel().clear()
			self.view.sel().add(region)