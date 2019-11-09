from .. typecheck import *
from .. import core, ui, dap

from .debugger import DebuggerStateful
from .debugger_project import DebuggerProject
from .breakpoints import Breakpoints

import sublime

class BreakpointCommandsProvider(core.Disposables):
	def __init__(self, project: DebuggerProject, debugger: DebuggerStateful, breakpoints: Breakpoints):
		super().__init__()

		self.run_to_line_breakpoint = None
		self.breakpoints = breakpoints
		self.debugger = debugger
		self.project = project

		self += self.debugger.state_changed.add(self.on_debugger_state_change)


	def current_file_line_column(self) -> Tuple[str, int, int]:
		view = self.project.window.active_view()
		file = self.project.source_file(view)
		if not file:
			raise core.Error("No source file selected, either no selection in current window or file is not saved")

		r, c = view.rowcol(view.sel()[0].begin())
		return file, r + 1, c + 1

	def current_file_line(self) -> Tuple[str, int]:
		line, col, _ = self.current_file_line_column()
		return line, col

	def clear_run_to_line(self):
		if self.run_to_line_breakpoint:
			self.breakpoints.remove_breakpoint(self.run_to_line_breakpoint)
			self.run_to_line_breakpoint = None
	
	def run_to_current_line(self):
		file, line = self.current_file_line()
		self.clear_run_to_line()
		if self.debugger.state != DebuggerStateful.paused:
			raise core.Error("Debugger not paused")

		self.run_to_line_breakpoint = self.breakpoints.source.add_breakpoint(file, line)
		core.run(self.debugger.resume())

	def on_debugger_state_change(self):
		if self.debugger.state != DebuggerStateful.running:
			self.clear_run_to_line()

	def toggle_current_line(self):
		file, line = self.current_file_line()
		bp = self.breakpoints.source.get_breakpoint(file, line)
		if bp:
			self.breakpoints.source.remove(bp)
		else:
			self.breakpoints.source.add_breakpoint(file, line)

	def toggle_current_line_column(self):
		file, line, column = self.current_file_line_column()
		bp = self.breakpoints.source.get_breakpoint(file, line, column)
		if bp:
			self.breakpoints.source.remove(bp)
		else:
			self.breakpoints.source.add_breakpoint(file, line, column)

	def edit_breakpoints_at_line(self, file: str, line: int):
		breakpoints = self.breakpoints.source.get_breakpoints_on_line(file, line)
		if not breakpoints:
			return
		if len(breakpoints) == 1:
			self.breakpoints.source.edit(breakpoints[0]).run()
			return

		items = [] 
		for breakpoint in breakpoints:
			items.append(
				ui.InputListItem(
					self.breakpoints.source.edit(breakpoint),
					"Breakpoint @ {}".format(breakpoint.tag),
				)
			)

		ui.InputList(items).run()

