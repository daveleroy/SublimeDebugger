import sublime_plugin
import sublime

from sublime_db.core.typecheck import List

from sublime_db import core
from sublime_db.libs import asyncio

from sublime_db.main.main import Main
from sublime_db.main.debug_adapter_client.client import DebugAdapterClient
from sublime_db.main.adapter_configuration import AdapterConfiguration, install_adapter
from .configurations import add_configuration

from sublime_db.main.debugger import DebuggerState

def DebuggerInState(window: sublime.Window, state: int) -> bool:
	debugger = Main.debuggerForWindow(window)
	if debugger and debugger.state == state:
		return True
	return False

class RunMainCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		core.main_loop.call_soon_threadsafe(self.run_main)
	def run_main (self) -> None:
		pass

class DebugWindowCommand(RunMainCommand):
	def is_visible(self) -> bool:
		return Main.forWindow(self.window) != None

class SublimeDebugOpenCommand(RunMainCommand):
	def run_main (self) -> None:
		main = Main.forWindow(self.window, True)
		assert main
		main.show()

class SublimeDebugToggleBreakpointCommand(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window, True)
		assert main
		view = self.window.active_view()
		x, y = view.rowcol(view.sel()[0].begin())
		line = x + 1
		file = view.file_name()
		breakpoint = main.breakpoints.get_breakpoint(file, line)
		if breakpoint is not None:
			main.breakpoints.remove_breakpoint(breakpoint)
		else:
			main.breakpoints.add_breakpoint(file, line)

	def is_enabled(self) -> bool:
		return Main.forWindow(self.window) != None

class SublimeDebugQuitCommand(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main:
			main.dispose()

class SublimeDebugStartCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window, True)
		if main: main.OnPlay()
		
	def is_enabled(self) -> bool:
		return not Main.forWindow(self.window) or DebuggerInState(self.window, DebuggerState.stopped)
		
class SublimeDebugStopCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStop()
	def is_enabled(self) -> bool:
		return not DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugPauseCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnPause()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.running)

class SublimeDebugStepOverCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepOver()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)

class SublimeDebugStepInCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepIn()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)

class SublimeDebugStepOutCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepOut()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)

class SublimeDebugResumeCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnResume()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.paused)

class SublimeDebugRunCommandCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window, True)
		main.open_repl_console()

class SublimeDebugAddConfiguration(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window, True)
		core.run(add_configuration(self.window, main.adapters))
		
class SublimeDebugInstallAdapter(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window, True)
		self.adapters = main.adapters
		core.run(self.install())
		
	@core.async
	def install(self) -> core.awaitable[None]:
		names = []
		adapters = []

		for adapter in self.adapters.values():
			if not adapter.installation:
				continue
			if adapter.installed:
				names.append(adapter.installation.name + ' ✓')
			else:
				names.append(adapter.installation.name)
			adapters.append(adapter)

		names.append('-- Install All --')

		index = yield from core.sublime_show_quick_panel_async(self.window, names, 0)
		if index < 0:
			return

		status = "Installing adapters... "
		view = self.window.active_view()
		view.set_status('sublime_db_adapter_install', status)

		adapters_to_install = [] #type: List[AdapterConfiguration]
		if index >= len(adapters):
			adapters_to_install = adapters
		else:
			adapters_to_install = [adapters[index]]

		for adapter in adapters_to_install:
			try:
				yield from install_adapter(adapter)
				status = 'Installing adapters... Installed {}'.format(adapter.installation.name)
			except Exception as e:
				core.log_exception()
				status = 'Installing adapters... Failed {} {}'.format(adapter.installation.name, e)

			view.set_status('sublime_db_adapter_install', status)

		yield from asyncio.sleep(2)
		view.erase_status('sublime_db_adapter_install')
