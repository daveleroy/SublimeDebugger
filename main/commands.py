import sublime_plugin
import sublime

from debug import core

from debug.main.main import Main
from debug.main.debug_adapter_client.client import DebuggerState, DebugAdapterClient

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

class SublimeDebugQuitCommand(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main:
			main.dispose()

class SublimeDebugStartCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnPlay()
		
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient == None:
			return True
		return False
		
class SublimeDebugStopCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStop()
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient:
			return True
		return False

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
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugStepInCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepIn()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugStepOutCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepOut()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugResumeCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnResume()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)