from .. typecheck import *
from .. import core, ui

from . import dap
from .project import Project
from .breakpoints import Breakpoints

import sublime

class BreakpointCommandsProvider(core.Disposables):
	def __init__(self, project: Project, sessions: dap.Sessions, breakpoints: Breakpoints):
		super().__init__()

		self.run_to_line_breakpoint = None
		self.breakpoints = breakpoints
		self.sessions = sessions
		self.project = project

		self += core.on_view_gutter_clicked.add(self.view_gutter_clicked)
		#self += self.debugger.state_changed.add(self.on_debugger_state_change)

	def view_gutter_clicked(self, event: Tuple[sublime.View, int, int]):
		(view, line, button) = event

		file = self.project.source_file(view)
		if not file:
			return

		if button == 1:
			self.toggle_file_line(file, line + 1)
			return True

		if button == 2:
			self.edit_breakpoints_at_line(file, line + 1)
			return True

	def clear_run_to_line(self):
		if self.run_to_line_breakpoint:
			self.breakpoints.source.remove(self.run_to_line_breakpoint)
			self.run_to_line_breakpoint = None

	def run_to_current_line(self):
		...
		# fix me for multiple sessions
		# file, line = self.project.current_file_line()
		# self.clear_run_to_line()
		# if self.debugger.state != DebuggerSession.paused:
		# 	raise core.Error("Debugger not paused")

		# self.run_to_line_breakpoint = self.breakpoints.source.add_breakpoint(file, line)
		# core.run(self.debugger.resume())

	#def on_debugger_state_change(self):
		# if self.debugger.state != DebuggerSession.running:
		# 	self.clear_run_to_line()

	def toggle_file_line(self, file: str, line: int):
		bps = self.breakpoints.source.get_breakpoints_on_line(file, line)
		if bps:
			for bp in bps:
				self.breakpoints.source.remove(bp)
		else:
			self.breakpoints.source.add_breakpoint(file, line)

	def toggle_current_line(self):
		file, line = self.project.current_file_line()
		self.toggle_file_line(file, line)

	def toggle_current_line_column(self):
		file, line, column = self.project.current_file_line_column()
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
