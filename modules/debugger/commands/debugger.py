import sublime_plugin
import sublime

from sublime_db.modules.core.typecheck import List

from sublime_db.modules import core
from sublime_db.modules.libs import asyncio

from sublime_db.modules.debugger.debugger_interface import DebuggerInterface
from sublime_db.modules.debugger.adapter_configuration import AdapterConfiguration, install_adapter

from sublime_db.modules.debugger.debugger import DebuggerState
from sublime_db.modules.debugger.commands import select_configuration

def DebuggerInState(window: sublime.Window, state: int) -> bool:
	debugger = DebuggerInterface.debuggerForWindow(window)
	if debugger and debugger.state == state:
		return True
	return False


class SublimeDebugReplaceContentsCommand(sublime_plugin.TextCommand):
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


class SublimeDebugOpenCommand(RunDebuggerInterfaceCommand):
	def run_main(self) -> None:
		main = DebuggerInterface.for_window(self.window, True)
		assert main
		main.show()


class SublimeDebugToggleBreakpointCommand(DebuggerCommand):
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


class SublimeDebugQuitCommand(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.dispose()

class SublimeDebugStartCommand(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_play()

class SublimeDebugStopCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_stop()

	def is_enabled(self) -> bool:
		return not DebuggerInState(self.window, DebuggerState.stopped)


class SublimeDebugPauseCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_pause()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.running)


class SublimeDebugStepOverCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_step_over()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)


class SublimeDebugStepInCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_step_in()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)


class SublimeDebugStepOutCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_step_out()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)


class SublimeDebugResumeCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_resume()

	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)


class SublimeDebugRunCommandCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.open_repl_console()


class SublimeDebugRefreshPhantoms(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.refresh_phantoms()

class SublimeDebugChangeConfiguration(DebuggerCommand):
	def on_main(self, debugger: 'DebuggerInterface') -> None:
		select_configuration.run(debugger)