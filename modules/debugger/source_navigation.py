from .. typecheck import *
from .. import core
from .views.selected_line import SelectedLine

from . import dap
from .debugger import Project

import sublime
import sublime_plugin


def replace_contents(view, characters):
	def run(edit):
		view.replace(edit, sublime.Region(0, view.size()), characters)
		view.sel().clear()

	core.edit(view, run)

def show_line(view, line: int, column: int, move_cursor: bool):
	def run(edit):
		a = view.text_point(line, column)
		region = sublime.Region(a, a)
		view.show_at_center(region)
		if move_cursor:
			view.sel().clear()
			view.sel().add(region)

	core.edit(view, run)

class SourceNavigationProvider:
	def __init__(self, project: Project, sessions: dap.Sessions):
		self.sessions = sessions
		self.project = project
		self.updating = None #type: Optional[Any]
		self.generated_view = None #type: Optional[sublime.View]
		self.selected_frame_line = None #type: Optional[SelectedLine]

	def dispose(self):
		self.clear()

	def select_source_location(self, source: dap.SourceLocation, stopped_reason: str):
		if self.updating:
			self.updating.cancel()
		def on_error(error):
			if error is not core.CancelledError:
				core.log_error(error)

		async def select_async(source: dap.SourceLocation, stopped_reason: str):
			self.clear_selected()
			view = await self.navigate_to_source(source)

			# r = view.line(view.text_point(source.line - 1, 0))
			# view.add_regions("asdfasdf", [r], scope="region.bluish", annotations=[stopped_reason.ljust(200, '\u00A0')], annotation_color='var(--bluish)', flags=sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_SOLID_UNDERLINE)
			self.selected_frame_line = SelectedLine(view, source.line or 1, stopped_reason)

		self.updating = core.run(select_async(source, stopped_reason), on_error=on_error)

	def show_source_location(self, source: dap.SourceLocation):
		if self.updating:
			self.updating.cancel()

		def on_error(error):
			if error is not core.CancelledError:
				core.log_error(error)

		async def navigate_async(source: dap.SourceLocation):
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

	async def navigate_to_source(self, source: dap.SourceLocation, move_cursor: bool = False) -> sublime.View:

		# if we aren't going to reuse the previous generated view
		# or the generated view was closed (no buffer) throw it away
		if not source.source.sourceReference or self.generated_view and not self.generated_view.buffer_id():
			self.clear_generated_view()

		line = (source.line or 1) - 1
		column = (source.column or 1) - 1

		if source.source.sourceReference:
			session = self.sessions.active
			content = await session.get_source(source.source)

			view = self.generated_view or self.project.window.new_file()
			self.generated_view = view
			view.set_name(source.source.name or "")
			view.set_read_only(False)

			replace_contents(view, content)

			view.set_read_only(True)
			view.set_scratch(True)
		elif source.source.path:
			view = await core.sublime_open_file_async(self.project.window, source.source.path, source.line, source.column)
		else:
			raise core.Error('source has no reference or path')


		show_line(view, line, column, move_cursor)

		return view
