from __future__ import annotations
from ..typecheck import *

from ..import ui
from .. import dap
from .. import core

import sublime


class Annotation:
	def __init__(self, view: sublime.View, region: sublime.Region, html: str):
		self.view = view
		self.id = str(id(self))
		view.add_regions(self.id, [region], annotation_color="#fff0", annotations=[html])

	def dispose(self):
		self.view.erase_regions(self.id)


class SelectedLine:
	def __init__(self, view: sublime.View, line: int, thread: dap.Thread):
		view.settings().set('highlight_line', True)
		# note sublime lines are 0 based not 1 based
		pt_current_line = view.text_point(line - 1, 0)

		end_of_selected_line = view.line(pt_current_line).b
		start_of_selected_line = view.line(pt_current_line).a

		view.add_regions('debugger.selection', [sublime.Region(start_of_selected_line, end_of_selected_line+1)], scope='region.bluish debugger.selection', flags=sublime.DRAW_NO_OUTLINE)
		stopped_reason = thread.stopped_reason or 'Stopped'

		characters_before_wrap = (view.viewport_extent()[0] - view.text_to_layout(end_of_selected_line)[0])

		name = ui.html_escape(f'{stopped_reason}')
		html = f'''
			<body id="debugger">
				<style>
					html {{
						color: var(--accent);
					}}
					div.content {{
						text-align: right;
						width: {characters_before_wrap - 20}px;
					}}
				</style>
				<div class="content">
					{name}
				</div>
			</body>
		'''

		self.end_of_selected_line = end_of_selected_line
		self.view = view

		self.text = ui.RawPhantom(view, sublime.Region(end_of_selected_line, end_of_selected_line), html, layout=sublime.LAYOUT_INLINE)
		
		self.more = None
		self.fetch = None

		if thread.stopped_event and thread.stopped_event.reason == 'exception':
			self.fetch = core.run(self.fetch_exception_info(thread))

	
	async def fetch_exception_info(self, thread: dap.Thread):
		if not thread.session.capabilities.supportsExceptionInfoRequest:
			return

		info = await thread.session.exception_info(thread.id)
		
		text_more = ''

		if info.exceptionId:
			text_more = ui.html_escape_multi_line(info.exceptionId)

		if info.description and info.description:
			text_more += '<br>'
			text_more += ui.html_escape_multi_line(info.description)

		if info.details and info.details.stackTrace:
			text_more += '<br>'
			text_more += ui.html_escape_multi_line(info.details.stackTrace)

		if not text_more:
			return

		html_more = f'''
			<body id="debugger">
				<style>
					div.content {{
						color: var(--accent);
						padding: 5px;
						border-radius: 3px;
						background-color: color(var(--accent) alpha(0.1));
					}}
				</style>
				<div class="content">
					{text_more}
				</div>
			</body>
		'''
		self.more = ui.RawPhantom(self.view, sublime.Region(self.end_of_selected_line, self.end_of_selected_line), html_more, layout=sublime.LAYOUT_BLOCK)


	def dispose(self):
		self.view.erase_regions('debugger.selection')
		self.text.dispose()
		if self.fetch: self.fetch.cancel()
		if self.more: self.more.dispose()
