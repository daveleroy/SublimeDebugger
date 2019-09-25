from ..typecheck import *

import os
import sublime
import functools

from .. import ui
from .. import core

from ..debugger.breakpoints import Breakpoints, Breakpoint, Filter
from ..commands import AutoCompleteTextInputHandler
from ..commands import breakpoint_menus

from .layout import breakpoints_panel_width


def show_breakpoint_options(breakpoints: Breakpoints):
	core.run(_show_breakpoint_options(breakpoints))

@core.async
def _show_breakpoint_options(breakpoints: Breakpoints) -> core.awaitable[None]:
	def add_function_breakpoint():
		input = AutoCompleteTextInputHandler("name of function")
		def run(text):
			breakpoints.add_function_breakpoint(text)
		ui.run_input_command(input, run)

	items = [
		("Add function breakpoint", add_function_breakpoint),
		("Clear all breakpoints", breakpoints.clear_all_breakpoints)
	]
	names = list(map(lambda x: x[0], items))
	selected_index = yield from core.sublime_show_quick_panel_async(sublime.active_window(), names, 0)
	if selected_index < 0:
		return
	items[selected_index][1]()

class BreakpointsPanel(ui.Block):
	def __init__(self, breakpoints: Breakpoints, on_expand: Callable[[Breakpoint], None]) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		self.selected = None #type: Optional[Breakpoint]
		# FIXME put in on activate/deactivate
		self.breakpoints.onUpdatedFunctionBreakpoint.add(self._updated)
		self.breakpoints.onUpdatedBreakpoint.add(self._updated)
		self.breakpoints.onUpdatedFilter.add(self._updated)		
		self.on_expand = on_expand

	def _updated(self, data: Any) -> None:
		self.dirty()

	def on_select(self, breakpoint: Breakpoint) -> None:
		self.selected = breakpoint
		breakpoint_menus.edit_breakpoint(self.breakpoints, breakpoint)
		self.dirty()
	def on_toggle(self, breakpoint: Breakpoint) -> None:
		self.selected = breakpoint
		self.breakpoints.toggle_enabled(breakpoint)
		self.dirty()

	def item(self, item: Any, image, name: str, tag: str, enabled: bool):
		if item == self.selected:
			color  = 'primary'
		else:
			color  = 'secondary'

		toggle_button = ui.Button(on_click=functools.partial(self.on_toggle, item), items=[
			ui.Img(image),
		])
		fileAndLine =  ui.Button(on_click=functools.partial(self.on_select, item), items=[
			# line number
			ui.Padding(ui.Box(ui.Label(tag, color=color, width=3)), left=0.5, right=0.5),
			# filename
			ui.Label(name, color=color, padding_left=0.25, width=13.6, align=0),
		])
		return ui.Padding(ui.block(toggle_button, fileAndLine), top=0.1, bottom=0.1)

	def render(self) -> ui.Block.Children:
		items = [] #type: List[ui.TableItem]
		colors = [ 'secondary', 'primary']

		for filter in self.breakpoints.filters:
			color = colors[filter == self.selected]

			def on_click(filter=filter):
				self.breakpoints.toggle_filter(filter) #type: ignore
				self.selected = filter
			items.append(ui.block(
				ui.Button(on_click=on_click, items=[
					ui.Img((ui.Images.shared.dot, ui.Images.shared.dot_disabled)[not filter.enabled]),
				]),
				ui.Label(filter.name, color=color, padding_left=0.25, width=13.6, align=0)
			))

		for function_breakpoint in self.breakpoints.functionBreakpoints:
			color = colors[function_breakpoint == self.selected]
			name = function_breakpoint.name
			i = self.item(function_breakpoint, function_breakpoint.image(), name, "ƒn", function_breakpoint.enabled)
			items.append(i)

		for breakpoint in self.breakpoints.breakpoints:
			base, name = os.path.split(breakpoint.file)
			i = self.item(breakpoint, breakpoint.image(), name, str(breakpoint.line), breakpoint.enabled)
			items.append(i)

		return [
			ui.Table(items)
		]
