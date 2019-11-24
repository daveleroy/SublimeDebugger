from .. typecheck import *
from .. import ui

import sublime


class UnderlineComponent(ui.div):
	def __init__(self) -> None:
		super().__init__()

	def render(self) -> ui.div.Children:
		return [
			ui.div(width=1000, height=0.1),
		]


class SelectedLineText(ui.div):
	def __init__(self, text: str) -> None:
		super().__init__()
		self.text = text

	def render(self) -> ui.div.Children:
		return [
			ui.div(width=25, height=2.5)[
				ui.text(self.text),
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

		self.top_line = ui.Phantom(UnderlineComponent(), view, line_current, sublime.LAYOUT_BELOW)
		self.text = ui.Phantom(SelectedLineText(text), view, sublime.Region(pt_next_line - 1, pt_next_line - 1), sublime.LAYOUT_INLINE)
		self.bottom_line = ui.Phantom(UnderlineComponent(), view, line_prev, sublime.LAYOUT_BELOW)

	def dispose(self):
		self.top_line.dispose()
		self.text.dispose()
		self.bottom_line.dispose()
