import sublime_plugin
import sublime

from sublime_db.core.typecheck import List

from sublime_db import core
from sublime_db.libs import asyncio

from sublime_db.main.debugger_interface import DebuggerInterface
from sublime_db.main.adapter_configuration import AdapterConfiguration, install_adapter
from .configurations import add_configuration

from sublime_db.main.debugger import DebuggerState


def DebuggerInState(window: sublime.Window, state: int) -> bool:
	debugger = DebuggerInterface.debuggerForWindow(window)
	if debugger and debugger.state == state:
		return True
	return False


class RunDebuggerInterfaceCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		core.main_loop.call_soon_threadsafe(self.run_main)

	def run_main(self) -> None:
		main = DebuggerInterface.forWindow(self.window)
		if main:
			main.show()
			self.on_main(main)
		else:
			print('No debugger open for window, ignoring command')

	def on_main(self, main: DebuggerInterface) -> None:
		pass


class DebuggerCommand(RunDebuggerInterfaceCommand):
	def is_visible(self) -> bool:
		return DebuggerInterface.forWindow(self.window) is not None


class SublimeDebugOpenCommand(RunDebuggerInterfaceCommand):
	def run_main(self) -> None:
		main = DebuggerInterface.forWindow(self.window, True)
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


class SublimeDebugStartCommand(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.on_play()

	def is_enabled(self) -> bool:
		return not DebuggerInterface.forWindow(self.window) or DebuggerInState(self.window, DebuggerState.stopped)


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


class SublimeDebugChangeConfiguration(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		core.run(main.SelectConfiguration())


class SublimeDebugRefreshPhantoms(RunDebuggerInterfaceCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		main.refresh_phantoms()


class SublimeDebugInstallAdapter(DebuggerCommand):
	def on_main(self, main: DebuggerInterface) -> None:
		core.run(self.install(main))

	@core.async
	def install(self, main: DebuggerInterface) -> core.awaitable[None]:
		names = []
		adapters = []

		for adapter in main.adapters.values():
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
