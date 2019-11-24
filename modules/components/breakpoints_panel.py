from ..typecheck import *
from ..import ui
from ..import core
from ..debugger.breakpoints import (
	Breakpoints,
	IBreakpoint,
	SourceBreakpoint,
	DataBreakpoint,
	FunctionBreakpoint,
	ExceptionBreakpointsFilter,
)

from .layout import breakpoints_panel_width
from .import css

import os
import sublime

class BreakpointsPanel(ui.div):
	def __init__(self, breakpoints: Breakpoints) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		self.selected = None
		# FIXME put in on activate/deactivate
		breakpoints.source.on_updated.add(self._updated)
		breakpoints.filters.on_updated.add(self._updated)
		breakpoints.data.on_updated.add(self._updated)
		breakpoints.function.on_updated.add(self._updated)

	def _updated(self, data: Any) -> None:
		self.dirty()

	def on_select(self, breakpoint: IBreakpoint) -> None:
		if isinstance(breakpoint, DataBreakpoint):
			self.breakpoints.data.edit(breakpoint).run()
			return
		if isinstance(breakpoint, FunctionBreakpoint):
			self.breakpoints.function.edit(breakpoint).run()
			return
		if isinstance(breakpoint, ExceptionBreakpointsFilter):
			self.breakpoints.filters.edit(breakpoint).run()
			return
		if isinstance(breakpoint, SourceBreakpoint):
			self.breakpoints.source.edit(breakpoint).run()
			return

		assert False, "unreachable"

	def on_toggle(self, breakpoint: IBreakpoint) -> None:
		if isinstance(breakpoint, DataBreakpoint):
			self.breakpoints.data.toggle(breakpoint)
			return
		if isinstance(breakpoint, FunctionBreakpoint):
			self.breakpoints.function.toggle(breakpoint)
			return
		if isinstance(breakpoint, ExceptionBreakpointsFilter):
			self.breakpoints.filters.toggle(breakpoint)
			return
		if isinstance(breakpoint, SourceBreakpoint):
			self.breakpoints.source.toggle(breakpoint)
			return

		assert False, "unreachable"

	def render(self) -> ui.div.Children:
		items = [] #type: List[ui.div]

		for breakpoints in (self.breakpoints.filters, self.breakpoints.function, self.breakpoints.data, self.breakpoints.source):
			for breakpoint in breakpoints: #type: ignore
				if breakpoint.tag:
					tag_and_name = [
						ui.span(height=2, css=css.button)[
							ui.text(breakpoint.tag, css=css.label),
						],
						ui.text(breakpoint.name, css=css.label_secondary_padding),
					]
				else:
					tag_and_name = [
						ui.text(breakpoint.name, css=css.label_secondary),
					]

				items.append(ui.div(height=3)[
					ui.click(lambda breakpoint=breakpoint: self.on_toggle(breakpoint))[
						ui.icon(breakpoint.image),
					],
					ui.click(lambda breakpoint=breakpoint: self.on_select(breakpoint))[
						tag_and_name
					]
				])

		return items
