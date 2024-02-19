from __future__ import annotations
from typing import Any, Callable

from ..import ui
from ..import dap
from ..import core

from ..breakpoints import (
	Breakpoints,
	IBreakpoint,
	SourceBreakpoint,
	DataBreakpoint,
	FunctionBreakpoint,
	ExceptionBreakpointsFilter,
)

from .import css


class BreakpointsView(ui.div, core.Dispose):
	def __init__(self, breakpoints: Breakpoints, on_navigate: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		self.on_navigate = on_navigate

	def added(self) -> None:
		self.dispose_add(
			self.breakpoints.source.on_updated.add(self._updated),
			self.breakpoints.filters.on_updated.add(self._updated),
			self.breakpoints.data.on_updated.add(self._updated),
			self.breakpoints.function.on_updated.add(self._updated),
		)

	def removed(self) -> None:
		self.dispose()

	def _updated(self, data: Any) -> None:
		self.dirty()

	def _on_edit(self, breakpoint: IBreakpoint) -> None:
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

	def _on_navigate(self, breakpoint: IBreakpoint) -> None:
		if isinstance(breakpoint, SourceBreakpoint):
			self.on_navigate(dap.SourceLocation.from_path(breakpoint.file, breakpoint.line, breakpoint.column))

	def _on_toggle(self, breakpoint: IBreakpoint) -> None:
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

	def render(self):
		for breakpoints in (self.breakpoints.filters, self.breakpoints.function, self.breakpoints.data, self.breakpoints.source):
			for breakpoint in breakpoints:
				with ui.div():
					ui.icon(breakpoint.image, on_click=partial(self._on_toggle, breakpoint))
					ui.text(breakpoint.name, css=css.secondary, on_click=partial(self._on_edit, breakpoint))
					if breakpoint.tag:
						ui.spacer()
						ui.text(breakpoint.tag, css=css.button, on_click=partial(self._on_navigate, breakpoint))
