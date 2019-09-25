from ..typecheck import *
from ..import core, ui, dap

import sublime

from .debugger import DebuggerStateful
from .debugger_project import DebuggerProject
from .breakpoints import Breakpoints

class BreakpointCommandsProvider(core.Disposables):
	def __init__(self, project: DebuggerProject, debugger: DebuggerStateful, breakpoints: Breakpoints):
		super().__init__()

		self.run_to_line_breakpoint = None
		self.breakpoints = breakpoints
		self.debugger = debugger
		self.project = project

		self += self.debugger.state_changed.add(self.on_debugger_state_change)

	def current_file_line(self) -> Tuple[str, int]:
		view = self.project.window.active_view()
		x, y = view.rowcol(view.sel()[0].begin())
		line = x + 1
		file = self.project.source_file(view)
		if not file:
			raise core.Error("No source file selected, either no selection in current window or file is not saved")

		return file, line

	def clear_run_to_line(self):
		if self.run_to_line_breakpoint:
			self.breakpoints.remove_breakpoint(self.run_to_line_breakpoint)
			self.run_to_line_breakpoint = None
	
	def run_to_current_line(self):
		file, line = self.current_file_line()
		self.clear_run_to_line()
		if self.debugger.state != DebuggerStateful.paused:
			raise core.Error("Debugger not paused")

		self.run_to_line_breakpoint = self.breakpoints.add_breakpoint(file, line)
		core.run(self.debugger.resume())

	def on_debugger_state_change(self):
		if self.debugger.state != DebuggerStateful.running:
			self.clear_run_to_line()

	def toggle_current_line(self):
		file, line = self.current_file_line()
		bp = self.breakpoints.get_breakpoint(file, line)
		if bp:
			self.breakpoints.remove_breakpoint(bp)
		else:
			self.breakpoints.add_breakpoint(file, line)