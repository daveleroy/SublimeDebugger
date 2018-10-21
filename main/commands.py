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
	
class SublimeDebugOpenCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		core.main_loop.call_soon_threadsafe(self.run_main)
	def run_main (self) -> None:
		main = Main.forWindow(self.window, True)
		assert main
		main.show()

class SublimeDebugQuitCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		core.main_loop.call_soon_threadsafe(self.run_main)
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		assert main
		main.dispose()
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		return not main is None

class SublimeDebugStartCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient == None:
			core.run(main.LaunchDebugger())
		
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient == None:
			return True
		return False
		
class SublimeDebugStopCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient:
			main.KillDebugger()
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient:
			return True
		return False

class SublimeDebugStepOverCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		debugger = Main.debuggerForWindow(self.window)
		if debugger and debugger.state == DebuggerState.stopped:
			core.run(debugger.StepOver())
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugStepInCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		debugger = Main.debuggerForWindow(self.window)
		if debugger and debugger.state == DebuggerState.stopped:
			core.run(debugger.StepIn())
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugStepOutCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		debugger = Main.debuggerForWindow(self.window)
		if debugger and debugger.state == DebuggerState.stopped:
			core.run(debugger.StepOut())
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugPauseCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		debugger = Main.debuggerForWindow(self.window)
		if debugger and debugger.state == DebuggerState.running:
			core.run(debugger.Pause())
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.running)

class SublimeDebugResumeCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		debugger = Main.debuggerForWindow(self.window)
		if debugger and debugger.state == DebuggerState.stopped:
			core.run(debugger.Resume())
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)