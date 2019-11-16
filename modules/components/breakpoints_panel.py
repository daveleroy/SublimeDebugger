from .. typecheck import *
from .. import ui
from .. import core

from .. debugger.breakpoints import (
	Breakpoints,
	IBreakpoint,
	SourceBreakpoint,
	DataBreakpoint, 
	FunctionBreakpoint, 
	ExceptionBreakpointsFilter,
)

from .layout import breakpoints_panel_width

import os
import sublime
import functools

class BreakpointsPanel(ui.Block):
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

	def item(self, item: Any, image, name: str, tag: str, enabled: bool):
		if item == self.selected:
			color  = 'primary'
		else:
			color  = 'secondary'

		toggle_button = ui.Button(on_click=functools.partial(self.on_toggle, item), items=[
			ui.Img(image),
		])

		if tag:
			if len(tag) > 4:
				width = 4
			else:
				width = 3
			fileAndLine =  ui.Button(on_click=functools.partial(self.on_select, item), items=[
				# line number
				ui.Padding(ui.Box(ui.Label(tag, color=color, width=width)), left=0.5, right=0.5),
				# filename
				ui.Label(name, color=color, padding_left=0.25, width=13.6, align=0),
			])
		else:
			fileAndLine =  ui.Button(on_click=functools.partial(self.on_select, item), items=[
				# filename
				ui.Label(name, color=color, padding_left=0.25, width=13.6, align=0),
			])
		return ui.Padding(ui.block(toggle_button, fileAndLine), top=0.1, bottom=0.1)

	def render(self) -> ui.Block.Children:
		items = [] #type: List[ui.Block]

		for breakpoints in (self.breakpoints.filters, self.breakpoints.function, self.breakpoints.data, self.breakpoints.source):
			for breakpoint in breakpoints: #type: ignore
				i = self.item(breakpoint, breakpoint.image, breakpoint.name, breakpoint.tag, breakpoint.enabled)
				items.append(i)

		return [
			ui.Table(items)
		]
