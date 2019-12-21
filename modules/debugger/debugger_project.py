from ..typecheck import *

import sublime
from .. import core

class DebuggerProject:
	def __init__(self, window: sublime.Window):
		self.window = window

	def is_source_file(self, view: sublime.View) -> bool:
		return bool(self.source_file(view))

	def source_file(self, view: sublime.View) -> Optional[str]:
		if view.window() != self.window:
			return None

		return view.file_name()

	def extract_variables(self) -> dict:
		variables = self.window.extract_variables()
		variables["package"] = core.current_package()
		project = variables.get('project_path')
		if project:
			variables['workspaceFolder'] = project
		return variables

	def current_file_line_column(self) -> Tuple[str, int, int]:
		view = self.window.active_view()
		file = self.source_file(view)
		if not file or not view:
			raise core.Error("No source file selected, no view open or file is not saved")

		r, c = view.rowcol(view.sel()[0].begin())
		return file, r + 1, c + 1

	def current_file_line(self) -> Tuple[str, int]:
		line, col, _ = self.current_file_line_column()
		return line, col
