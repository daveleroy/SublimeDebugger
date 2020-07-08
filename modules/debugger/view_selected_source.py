from .. typecheck import *
from .. import core, ui, dap
from .views.selected_line import SelectedLine

from .debugger_sessions import DebuggerSessions
from .debugger_project import DebuggerProject
from .variables import Source

import sublime
import sublime_plugin

class DebuggerShowLineCommand(sublime_plugin.TextCommand):
	def run(self, edit, line: int, column: int, move_cursor: bool): #type: ignore
		a = self.view.text_point(line, column)
		region = sublime.Region(a, a)
		self.view.show_at_center(region)
		if move_cursor:
			self.view.sel().clear()
			self.view.sel().add(region)

class DebuggerReplaceContentsCommand(sublime_plugin.TextCommand):
	def run(self, edit, characters):
		self.view.replace(edit, sublime.Region(0, self.view.size()), characters)
		self.view.sel().clear()

class ViewSelectedSourceProvider:
	def __init__(self, project: DebuggerProject, sessions: DebuggerSessions):
		self.sessions = sessions
		self.project = project
		self.updating = None #type: Optional[Any]
		self.generated_view = None #type: Optional[sublime.View]
		self.selected_frame_line = None #type: Optional[SelectedLine]

	def select(self, source: Source, stopped_reason: str):
		if self.updating:
			self.updating.cancel()
		def on_error(error):
			if error is not core.CancelledError:
				core.log_error(error)

		async def select_async(source: Source, stopped_reason: str):
			self.clear_selected()
			view = await self.navigate_to_source(source)

			# r = view.line(view.text_point(line - 1, 0))
			# view.add_regions("asdfasdf", [r], scope="region.bluish", flags=sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_SOLID_UNDERLINE)
			self.selected_frame_line = SelectedLine(view, source.line or 1, stopped_reason)

		self.updating = core.run(select_async(source, stopped_reason), on_error=on_error)

	def navigate(self, source: Source):
		if self.updating:
			self.updating.cancel()

		def on_error(error):
			if error is not core.CancelledError:
				core.log_error(error)

		async def navigate_async(source: Source):
			self.clear_generated_view()
			await self.navigate_to_source(source, move_cursor=True)

		self.updating = core.run(navigate_async(source), on_error=on_error)

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

	async def navigate_to_source(self, source: Source, move_cursor: bool = False) -> sublime.View:

		# if we aren't going to reuse the previous generated view
		# or the generated view was closed (no buffer) throw it away
		if not source.source.sourceReference or self.generated_view and not self.generated_view.buffer_id():
			self.clear_generated_view()

		line = (source.line or 1) - 1
		column = (source.column or 1) - 1

		if source.source.sourceReference:
			session = self.sessions.active
			content = await session.client.GetSource(source.source)

			view = self.generated_view or self.project.window.new_file()
			self.generated_view = view
			view.set_name(source.source.name or "")
			view.set_read_only(False)
			view.run_command('debugger_replace_contents', {
				'characters': content
			})
			view.set_read_only(True)
			view.set_scratch(True)
		elif source.source.path:
			view = await core.sublime_open_file_async(self.project.window, source.source.path, source.line, source.column)
		else:
			raise core.Error('source has no reference or path')

		view.run_command("debugger_show_line", {
			'line': line,
			'column': column,
			'move_cursor': move_cursor
		})
		return view
