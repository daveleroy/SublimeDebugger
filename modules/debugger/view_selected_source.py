from .. typecheck import *
from .. import core, ui, dap
from .. components.selected_line import SelectedLine

from .debugger import DebuggerStateful
from .debugger_project import DebuggerProject

import sublime
import sublime_plugin

class DebuggerShowLineCommand(sublime_plugin.TextCommand):
	def run(self, edit, line: int, move_cursor: bool):
		a = self.view.text_point(line, 0)
		region = sublime.Region(a, a)
		self.view.show_at_center(region)
		if move_cursor:
			self.view.sel().clear()
			self.view.sel().add(region)

class DebuggerReplaceContentsCommand(sublime_plugin.TextCommand):
	def run(self, edit, characters) -> None:
		self.view.replace(edit, sublime.Region(0, self.view.size()), characters)
		self.view.sel().clear()

class ViewSelectedSourceProvider:
	def __init__(self, project: DebuggerProject, debugger: DebuggerStateful):
		self.debugger = debugger
		self.project = project
		self.updating = None #type: Optional[Any]
		self.generated_view = None #type: Optional[sublime.View]
		self.selected_frame_line = None #type: Optional[SelectedLine]

	def select(self, source: dap.Source, line: int, stopped_reason: str):
		if self.updating:
			self.updating.cancel()
		def on_error(error):
			if error is not core.CancelledError:
				core.log_error(error)

		@core.coroutine
		def select_async(source: dap.Source, line: int, stopped_reason: str):
			view = yield from self.navigate_to_source(source, line)
			self.selected_frame_line = SelectedLine(view, line, stopped_reason)

		self.updating = core.run(select_async(source, line, stopped_reason), on_error=on_error)

	def navigate(self, source: dap.Source, line: int):
		if self.updating:
			self.updating.cancel()
		def on_error(error):
			if error is not core.CancelledError:
				core.log_error(error)

		@core.coroutine
		def navigate_async(source: dap.Source, line: int):
			self.clear_generated_view()
			self.navigate_to_source(source, line, move_cursor=True)

		self.updating = core.run(navigate_async(source, line), on_error=on_error)


	def clear(self):
		if self.updating:
			self.updating.cancel()

		self.clear_selected()
		self.clear_generated_view()

	def clear_selected(self):
		if self.selected_frame_line:
			self.selected_frame_line.dispose()
			self.selected_frame_line = None
	
	def clear_generated_view(self):
		if self.generated_view:
			self.generated_view.close()
			self.generated_view = None

	def dispose(self):
		self.clear()

	@core.coroutine
	def navigate_to_source(self, source: dap.Source, line: int, move_cursor: bool = False) -> core.awaitable[sublime.View]:
		self.clear_selected()

		# if we aren't going to reuse the previous generated view
		# or the generated view was closed (no buffer) throw it away
		if not source.sourceReference or self.generated_view and not self.generated_view.buffer_id():
			self.clear_generated_view()

		if source.sourceReference:
			if not self.debugger.adapter:
				raise core.Error('Debugger not running')

			content = yield from self.debugger.adapter.GetSource(source)			

			view = self.generated_view or self.project.window.new_file()
			self.generated_view = view
			view.set_name(source.name or "")
			view.set_read_only(False)
			view.run_command('debugger_replace_contents', {
				'characters': content
			})
			view.set_read_only(True)
			view.set_scratch(True)
		elif source.path:
			view = yield from core.sublime_open_file_async(self.project.window, source.path)
		else:
			raise core.Error('source has no reference or path')

		view.run_command("debugger_show_line", {
			'line' : line - 1,
			'move_cursor' : move_cursor
		})

		return view