from __future__ import annotations
from typing import TYPE_CHECKING, Any

from . import core
from . import dap

from .views.selected_line import SelectedLine
from .debugger import Project

if TYPE_CHECKING:
	from .debugger import Debugger

import sublime

syntax_name_for_mime_type: dict[str | None, str] = {
	'text/plain': 'text.plain',
	'text/javascript': 'source.js',
	'text/java': 'source.java',
	'text/x-lldb.disassembly': 'source.disassembly',
}


@core.sublime_edit
def replace_contents(view: sublime.View, edit: sublime.Edit, characters: str):
	view.replace(edit, sublime.Region(0, view.size()), characters)
	view.sel().clear()


@core.sublime_edit
def show_line(view: sublime.View, edit: sublime.Edit, line: int, column: int, move_cursor: bool):
	point = view.text_point(line, column)
	view.show(point)
	view.sel().clear()

	if move_cursor:
		view.sel().add(point)


class SourceNavigationProvider:
	def __init__(self, project: Project, debugger: Debugger):
		super().__init__()

		self.debugger = debugger
		self.project = project

		self.updating: Any | None = None
		self.selected_frame_line_time_out: Any | None = None

		self.generated_view: sublime.View | None = None
		self.selected_frame_line: SelectedLine | None = None

	def dispose(self):
		self.clear()

	def select_source_location(self, source: dap.SourceLocation, thread: dap.Thread):
		if self.updating:
			self.updating.cancel()

		def on_error(error: BaseException):
			if error is not core.CancelledError:
				core.error(error)

		async def select_async(source: dap.SourceLocation, thread: dap.Thread):
			delay = core.run(core.delay(1.0 / 30.0))

			view = await self.navigate_to_source(source)

			# delay least 1 frame at 30 fps so that a selected source at the same location right after clearing the previous one will briefly be removed before shown again
			# this is just always done since its easy and the screen is scrolling to the source location anyway
			await delay

			self.clear_selected()
			self.selected_frame_line = SelectedLine(view, source.line or 1, source.column, thread)

		self.updating = core.run(select_async(source, thread), on_error=on_error)

	def show_source_location(self, source: dap.SourceLocation):
		if self.updating:
			self.updating.cancel()

		def on_error(error: BaseException):
			if error is not core.CancelledError:
				core.alert(f'Unable to navigate to source @ {source.source.path} {error}')

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
		# Check if adapter want to provide content
		if session := self.debugger.session:
			adapter_content = await session.adapter.on_navigate_to_source(source)
		else:
			adapter_content = None

		# if we aren't going to reuse the previous generated view throw away any generated view
		if adapter_content or source.source.sourceReference:
			self.clear_generated_view()

		line = (source.line or 1) - 1
		column = (source.column or 1) - 1

		if adapter_content or source.source.sourceReference:
			if adapter_content:
				content, mime_type, custom_settings = adapter_content
			else:
				session = self.debugger.session
				if not session:
					raise core.Error('No Active Debug Session')
				content, mime_type = await session.get_source(source.source)
				custom_settings = []

			# the generated view was closed (no buffer) throw it away
			if self.generated_view and not self.generated_view.buffer_id():
				self.clear_generated_view()

			view = self.generated_view or self.project.window.new_file()
			self.project.window.set_view_index(view, 0, len(self.project.window.views_in_group(0)))
			self.generated_view = view
			view.set_name(source.source.name or '')
			view.set_read_only(False)
			view.settings().update(custom_settings)

			syntax = syntax_name_for_mime_type.get(mime_type, 'text.plain')
			view.assign_syntax(sublime.find_syntax_by_scope(syntax)[0])

			replace_contents(view, content)

			view.set_read_only(True)
			view.set_scratch(True)
		elif source.source.path:
			view = await core.sublime_open_file_async(self.project.window, source.source.path, group=0)
		else:
			raise core.Error('source has no reference or path')

		if source.line_regex:
			match = view.find(source.line_regex, 0)
			if not match.empty():
				line = view.rowcol(match.a)[0]

		show_line(view, line, column, move_cursor)
		return view
