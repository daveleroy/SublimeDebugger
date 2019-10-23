from ..typecheck import *

import sublime

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
