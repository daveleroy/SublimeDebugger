from sublime_db.core.typecheck import (
	Callable,
	Any,
	List,
	Sequence
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

class DebuggerPanelCallbacks: 
	def on_play(self) -> None:
		pass
	def on_resume(self) -> None:
		pass
	def on_pause(self) -> None:
		pass
	def on_stop(self) -> None:
		pass
	def on_step_over(self) -> None:
		pass
	def on_step_in(self) -> None:
		pass
	def on_step_out(self) -> None:
		pass

class DebuggerPanel(ui.Component):
	def __init__(self, breakpoints: Breakpoints, callbacks: DebuggerPanelCallbacks) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		
		self.state = STOPPED
		self.callbacks = callbacks
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

		play = False
		stop = False
		pause = False
		controls = False

		if self.state == RUNNING:
			stop = True
			play = True
			pause = True
			controls = True

		if self.state == PAUSED:
			stop = True
			play = True
			pause = False
			controls = True

		if self.state == STOPPED:
			stop = False
			play = True
			controls = False

		if self.state == LOADING:
			stop = True
			play = True
			controls = False

		items = []

		if play:
			items.append(
				DebuggerItem(self.callbacks.on_play, items = [
					ui.Img(ui.Images.shared.play)
				])
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_play, items = [
					ui.Img(ui.Images.shared.play_disable)
				])
			)
		if stop:
			items.append(
				DebuggerItem(self.callbacks.on_stop, items = [
					ui.Img(ui.Images.shared.stop)
				])
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_stop, items = [
					ui.Img(ui.Images.shared.stop_disable)
				])
			)

		
		if not controls:
			items.append(
				DebuggerItem(self.callbacks.on_pause, items = [
					ui.Img(ui.Images.shared.pause_disable)
				])
			)
		elif pause:
			items.append(
				DebuggerItem(self.callbacks.on_pause, items = [
					ui.Img(ui.Images.shared.pause)
				])
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_resume, items = [
					ui.Img(ui.Images.shared.resume)
				])
			)

		if controls:
			items.extend([
				DebuggerItem(self.callbacks.on_step_over, items = [
					ui.Img(ui.Images.shared.down)
				]),
				DebuggerItem(self.callbacks.on_step_out, items = [
					ui.Img(ui.Images.shared.left)
				]),
				DebuggerItem(self.callbacks.on_step_in, items = [
					ui.Img(ui.Images.shared.right)
				]),
			])
		else:
			items.extend([
				DebuggerItem(self.callbacks.on_step_over, items = [
					ui.Img(ui.Images.shared.down_disable)
				]),
				DebuggerItem(self.callbacks.on_step_out, items = [
					ui.Img(ui.Images.shared.left_disable)
				]),
				DebuggerItem(self.callbacks.on_step_in, items = [
					ui.Img(ui.Images.shared.right_disable)
				]),
			])

		return [
			ui.Panel(items = items), 
		]

class Div (ui.Component):
	def __init__(self, items: [ui.Component]) -> None:
		super().__init__()
		self.items = items
		
	def render (self) -> Sequence[ui.Component]:
		return self.items

class DebuggerItem (ui.Component):
	def __init__(self, callback: Callable[[], None], items: ui.components) -> None:
		super().__init__()
		self.items = items
		self.callback = callback
		
	def render (self) -> ui.components:
		return ui.Button(self.callback, items = self.items),


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
				# line number
				ui.Box(items = [
					ui.Label(str(breakpoint.line), color = color, width = 3),
				]),
				# filename
				ui.Label(name, color = color, padding_left = 0.25, width = 15, align = 0),
				
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


class UnderlineComponent(ui.Component):
	def __init__(self) -> None:
		super().__init__()
	def render(self) -> ui.components:
		return [
			ui.HorizontalSpacer(1000)
		]