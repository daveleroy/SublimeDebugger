from sublime_db.core.typecheck import (
	Callable,
	Any,
	List
)
import os
import sublime
from sublime_db import ui

from sublime_db.main.breakpoints import Breakpoints, Breakpoint, Filter
from .loading_component import LoadingComponent

STOPPED = 0
RUNNING = 1
PAUSED = 2
LOADING = 3

class BreakpintsComponent(ui.Component):
	def __init__(self, breakpoints: Breakpoints, on_expand: Callable[[Breakpoint], None]) -> None:
		super().__init__()
		self.breakpoints = breakpoints

		#FIXME put in on activate/deactivate
		self.breakpoints.onChangedBreakpoint.add(self._updated)
		self.breakpoints.onMovedBreakpoints.add(self._updated)
		self.breakpoints.onResultBreakpoint.add(self._updated)
		self.breakpoints.onSelectedBreakpoint.add(self._updated)
		self.on_expand = on_expand

	def _updated(self, data: Any) -> None:
		self.dirty()

	def onClicked(self, breakpoint: Breakpoint) -> None:
		self.breakpoints.select_breakpoint(breakpoint)

	def on_toggle(self, breakpoint: Breakpoint) -> None:
		self.breakpoints.toggle_enabled(breakpoint)
		
	def render(self) -> ui.components:
		items = [] #type: List[ui.TableItem]
		for breakpoint in self.breakpoints.breakpoints:
			base, name = os.path.split(breakpoint.file)

			if breakpoint == self.breakpoints.selected_breakpoint:
				color = 'primary'
			else:
				color = 'secondary'

			on_toggle = lambda bp=breakpoint: self.on_toggle(bp) #type: ignore
			on_click = lambda bp=breakpoint: self.onClicked(bp) #type: ignore

			toggle_button = ui.Button(on_click = on_toggle, items = [
				ui.Img(breakpoint.image()),
			])
			fileAndLine = ui.Button(on_click = on_click, items = [
				# filename
				ui.Label(name, color = color, padding_left = 0.25, width = 15, align = 0),
				# line number
				ui.Box(items = [
					ui.Label(str(breakpoint.line), color = color, width = 3),
				]),
			])
			items.append(ui.TableItem(items = [
				toggle_button, fileAndLine
			]))	
		return [
			ui.Table(table_items = items)
		]

class FiltersComponent(ui.Component):
	def __init__(self, breakpoints: Breakpoints) -> None:
		super().__init__()
		self.breakpoints = breakpoints

		#FIXME put in on activate/deactivate		
		self.breakpoints.onChangedFilter.add(self._updated)

	def _updated(self, data: Any) -> None:
		self.dirty()

	def onClicked(self, filter: Filter) -> None:
		self.breakpoints.toggle_filter(filter)
		# view = sublime.active_window().open_file("{}:{}".format(breakpoint.file, breakpoint.line), sublime.ENCODED_POSITION)
		# sel = view.sel()
		# line = view.line(view.text_point(breakpoint.line - 1, 0))
		# sel.add(line)
		# view.run_command('select', {"selection" : [[line.a, line.b]]})
		# print('Navigating to breakpoint:', breakpoint)

	def render(self) -> ui.components:
		items = [] #type: List[ui.TableItem]
		for filter in self.breakpoints.filters:
			on_click = lambda filter=filter: self.onClicked(filter) #type: ignore
			
			
			items.append(ui.TableItem(items = [
				ui.Button(on_click = on_click, items = [
					ui.Img((ui.Images.shared.dot, ui.Images.shared.dot_disabled)[not filter.enabled]),
				]),
				ui.Label(filter.name, color = 'secondary', padding_left = 0.25, width = 15, align = 0)
			]))
		return [
			ui.Table(table_items = items)
		]

class DebuggerComponentListener: 
	def OnPlay(self) -> None:
		pass
	def OnResume(self) -> None:
		pass
	def OnPause(self) -> None:
		pass
	def OnStop(self) -> None:
		pass
	def OnSettings(self) -> None:
		pass
	def OnStepOver(self) -> None:
		pass
	def OnStepIn(self) -> None:
		pass
	def OnStepOut(self) -> None:
		pass
	def OnExpandBreakpoint(self, breakpoint: Breakpoint) -> None:
		pass

class DebuggerComponent(ui.Component):
	def __init__(self, breakpoints: Breakpoints, listener: DebuggerComponentListener) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		
		self.state = STOPPED
		self.listener = listener
		self.name = ''

	def setState(self, state: int) -> None:
		self.state = state 
		self.dirty()
	def _updated_breakpoints(self, data: Any) -> None:
		self.dirty();
	def set_name(self, name: str) -> None:
		self.name = name
		self.dirty()
	def render(self) -> ui.components:
		buttons = [] #type: List[ui.Component]
		if self.state == RUNNING:
			buttons = [
				ui.Label("Running", width = 6, color="white"),
				ui.Button(self.listener.OnSettings, items = [
					ui.Img(ui.Images.shared.settings)
				]),
				ui.Button(self.listener.OnStop, items = [
					ui.Img(ui.Images.shared.stop)
				]),
				ui.Button(self.listener.OnPause, items = [
					ui.Img(ui.Images.shared.pause)
				]),
			]
		if self.state == PAUSED:
			buttons = [
				ui.Label("Paused", width = 6, color="white"),
				ui.Button(self.listener.OnSettings, items = [
					ui.Img(ui.Images.shared.settings)
				]),
				ui.Button(self.listener.OnStop, items = [
					ui.Img(ui.Images.shared.stop)
				]),
				ui.Button(self.listener.OnResume, items = [
					ui.Img(ui.Images.shared.play)
				]),
				ui.Button(self.listener.OnStepOver, items = [
					ui.Img(ui.Images.shared.down)
				]),
				ui.Button(self.listener.OnStepOut, items = [
					ui.Img(ui.Images.shared.left)
				]),
				ui.Button(self.listener.OnStepIn, items = [
					ui.Img(ui.Images.shared.right)
				]),
			]
		if self.state == STOPPED:
			buttons = [
				ui.Label(self.name, width = 6, color="white"),
				ui.Button(self.listener.OnSettings, items = [
					ui.Img(ui.Images.shared.settings)
				]),
				ui.Button(self.listener.OnPlay, items = [
					ui.Img(ui.Images.shared.play)
				]),
			]
		if self.state == LOADING:
			buttons = [
				ui.Label(self.name, width = 6, color="white"),
				ui.Button(self.listener.OnSettings, items = [
					ui.Img(ui.Images.shared.settings)
				]),
				ui.Button(self.listener.OnStop, items = [
					ui.Img(ui.Images.shared.stop)
				]),
				LoadingComponent()
			]

		return [
			ui.Panel(items = [
				ui.Segment(items = buttons),
				FiltersComponent(self.breakpoints),
				BreakpintsComponent(self.breakpoints, self.listener.OnExpandBreakpoint), 
			]), 
		]
