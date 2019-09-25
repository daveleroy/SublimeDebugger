from ..typecheck import *

import sublime

from .. import ui


class UnderlineComponent(ui.Block):
	def __init__(self) -> None:
		super().__init__()

	def height(self, layout: ui.Layout) -> float:
		return 0.05

	def render(self) -> ui.Block.Children:
		return [
			ui.HorizontalSpacer(1000)
		]


class SelectedLineText(ui.Block):
	def __init__(self, text: str) -> None:
		super().__init__()
		self.text = text

	def render(self) -> ui.Block.Children:
		return [
			ui.Padding(ui.block(ui.Label(self.text)), left=1, top=-0.125)
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