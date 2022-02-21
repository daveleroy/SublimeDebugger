from __future__ import annotations
from ..typecheck import *

from ..import ui
from . import css

import sublime

underline_top_padding_css = ui.css(padding_bottom=0.2, padding_top=0)
underline_css = ui.css(padding_bottom=0, padding_top=0, background_color='color(var(--accent) alpha(0.3))')

class UnderlineComponent(ui.div):
	def __init__(self, top: bool) -> None:
		if top:
			super().__init__(css=underline_top_padding_css)
		else:
			super().__init__()

	def render(self) -> ui.div.Children:
		return ui.div(width=1000, height=0.1, css=underline_css)


class SelectedLineText(ui.div):
	def __init__(self, text: str) -> None:
		super().__init__()
		self.text = text

	def render(self) -> ui.div.Children:
		return [
			ui.div(height=2.6)[
				ui.text(self.text, css=css.selected_text),
			],
		]


class SelectedLine:
	def __init__(self, view: sublime.View, line: int, text: str):
		# note sublime lines are 0 based not 1 based
		pt_current_line = view.text_point(line - 1, 0)
		pt_prev_line = view.text_point(line - 2, 0)
		pt_next_line = view.text_point(line, 0)

		line_prev = view.line(pt_current_line)
		line_current = view.line(pt_prev_line)

		end_of_selected_line = view.line(pt_current_line).b

		self.text = ui.Phantom(view, sublime.Region(end_of_selected_line, end_of_selected_line), sublime.LAYOUT_INLINE)[
			SelectedLineText(text)
		]
		if line != 1:
			self.top_line = ui.Phantom(view, sublime.Region(line_current.a, line_current.a), sublime.LAYOUT_BLOCK) [
				UnderlineComponent(True)
			]
		else:
			self.top_line = None

		self.bottom_line = ui.Phantom(view, line_prev, sublime.LAYOUT_BLOCK)[
			UnderlineComponent(False)
		]

	def dispose(self):
		if self.top_line: self.top_line.dispose()
		self.text.dispose()
		self.bottom_line.dispose()
