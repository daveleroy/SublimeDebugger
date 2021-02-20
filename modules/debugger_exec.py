import sublime_plugin

from .debugger import Debugger
from .dap import Task

# allow using debugger_exec to run a build system as a Debugger Task
class DebuggerExec(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		debugger = Debugger.get(self.window, create=True)

		task = Task.from_json(kwargs)
		debugger.run_task(task)