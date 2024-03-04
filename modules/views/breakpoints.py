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

	def render(self):
		for breakpoints in (self.breakpoints.filters, self.breakpoints.function, self.breakpoints.data, self.breakpoints.source):
			for breakpoint in breakpoints:
				BreakpointView(self.breakpoints, breakpoint, self.on_navigate)


class BreakpointView(ui.div):
	def __init__(self, breakpoints: Breakpoints, breakpoint: DataBreakpoint|ExceptionBreakpointsFilter|FunctionBreakpoint|SourceBreakpoint, on_navigate: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		self.breakpoint = breakpoint
		self.on_navigate = on_navigate

	def render(self):
		ui.icon(self.breakpoint.image, on_click=self._on_toggle)
		ui.text(self.breakpoint.name, css=css.secondary, on_click=self._on_navigate)
		if self.breakpoint.tag:
			ui.spacer()
			ui.text(self.breakpoint.tag, css=css.button, on_click=self._on_navigate)

	def _on_navigate(self) -> None:
		if isinstance(self.breakpoint, SourceBreakpoint):
			self.on_navigate(dap.SourceLocation.from_path(self.breakpoint.file, self.breakpoint.line, self.breakpoint.column))

	def _on_toggle(self) -> None:
		if isinstance(self.breakpoint, DataBreakpoint):
			self.breakpoints.data.toggle_enabled(self.breakpoint)
		elif isinstance(self.breakpoint, FunctionBreakpoint):
			self.breakpoints.function.toggle_enabled(self.breakpoint)
		elif isinstance(self.breakpoint, ExceptionBreakpointsFilter):
			self.breakpoints.filters.toggle_enabled(self.breakpoint)
		elif isinstance(self.breakpoint, SourceBreakpoint):
			self.breakpoints.source.toggle_enabled(self.breakpoint)
		else:
			assert False, 'unreachable'

	def is_removeable(self):
		return not isinstance(self.breakpoint, ExceptionBreakpointsFilter)

	def remove(self) -> None:
		if isinstance(self.breakpoint, ExceptionBreakpointsFilter):
			...
		elif isinstance(self.breakpoint, DataBreakpoint):
			self.breakpoints.data.remove(self.breakpoint)
		elif isinstance(self.breakpoint, FunctionBreakpoint):
			self.breakpoints.function.remove(self.breakpoint)
		elif isinstance(self.breakpoint, SourceBreakpoint):
			self.breakpoints.source.remove(self.breakpoint)
		else:
			assert False, 'unreachable'

	def edit(self) -> None:
		if isinstance(self.breakpoint, DataBreakpoint):
			self.breakpoints.data.edit(self.breakpoint).run()
		elif isinstance(self.breakpoint, FunctionBreakpoint):
			self.breakpoints.function.edit(self.breakpoint).run()
		elif isinstance(self.breakpoint, ExceptionBreakpointsFilter):
			self.breakpoints.filters.edit(self.breakpoint).run()
		elif isinstance(self.breakpoint, SourceBreakpoint):
			self.breakpoints.source.edit(self.breakpoint).run()
		else:
			assert False, 'unreachable'
