from __future__ import annotations
from ..typecheck import *

from ..import ui
from ..import core
from ..import dap

from ..breakpoints import (
	Breakpoints,
	IBreakpoint,
	SourceBreakpoint,
	DataBreakpoint,
	FunctionBreakpoint,
	ExceptionBreakpointsFilter,
)

from .import css

from functools import partial

class BreakpointsPanel(ui.div):
	def __init__(self, breakpoints: Breakpoints, on_navigate: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		self.selected = None
		self.on_navigate = on_navigate
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
			self.on_navigate(dap.SourceLocation.from_path(breakpoint.file, breakpoint.line, breakpoint.column))
			self.breakpoints.source.edit(breakpoint).run()
			return

		assert False, "unreachable"

	def on_toggle(self, breakpoint: IBreakpoint) -> None:
		if isinstance(breakpoint, DataBreakpoint):
			self.breakpoints.data.toggle_enabled(breakpoint)
			return
		if isinstance(breakpoint, FunctionBreakpoint):
			self.breakpoints.function.toggle_enabled(breakpoint)
			return
		if isinstance(breakpoint, ExceptionBreakpointsFilter):
			self.breakpoints.filters.toggle_enabled(breakpoint)
			return
		if isinstance(breakpoint, SourceBreakpoint):
			self.breakpoints.source.toggle_enabled(breakpoint)
			return

		assert False, "unreachable"

	def render(self) -> ui.div.Children:
		items: list[ui.div] = []

		for breakpoints in (self.breakpoints.filters, self.breakpoints.function, self.breakpoints.data, self.breakpoints.source):
			for breakpoint in breakpoints:
				items.append(
					ui.div(height=css.row_height)[
						ui.align()[
							ui.click(partial(self.on_toggle, breakpoint))[
								ui.icon(breakpoint.image),
							],
							ui.click(partial(self.on_select, breakpoint), title=breakpoint.description)[
								ui.text(breakpoint.name, css=css.label_secondary),
								[
									ui.spacer(),
									ui.text(breakpoint.tag, css=css.button),
								] 
								if breakpoint.tag else None
							]
						]
					])

		return items
