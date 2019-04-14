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
from .layout import breakpoints_panel_width

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


class DebuggerPanel(ui.Block):
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
		self.dirty()

	def set_name(self, name: str) -> None:
		self.name = name
		self.dirty()

	def render(self) -> ui.Block.Children:
		buttons = [] #type: List[ui.Block]

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
				DebuggerItem(self.callbacks.on_play, ui.Img(ui.Images.shared.play))
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_play, ui.Img(ui.Images.shared.play))
			)
		if stop:
			items.append(
				DebuggerItem(self.callbacks.on_stop, ui.Img(ui.Images.shared.stop))
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_stop, ui.Img(ui.Images.shared.stop_disable))
			)

		if not controls:
			items.append(
				DebuggerItem(self.callbacks.on_pause, ui.Img(ui.Images.shared.pause_disable))
			)
		elif pause:
			items.append(
				DebuggerItem(self.callbacks.on_pause, ui.Img(ui.Images.shared.pause))
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_resume, ui.Img(ui.Images.shared.resume))
			)

		if controls:
			items.extend([
				DebuggerItem(self.callbacks.on_step_over, ui.Img(ui.Images.shared.down)),
				DebuggerItem(self.callbacks.on_step_out, ui.Img(ui.Images.shared.left)),
				DebuggerItem(self.callbacks.on_step_in, ui.Img(ui.Images.shared.right)),
			])
		else:
			items.extend([
				DebuggerItem(self.callbacks.on_step_over, ui.Img(ui.Images.shared.down_disable)),
				DebuggerItem(self.callbacks.on_step_out, ui.Img(ui.Images.shared.left_disable)),
				DebuggerItem(self.callbacks.on_step_in, ui.Img(ui.Images.shared.right_disable)),
			])

		items_new = []
		for item in items:
			items_new.append(ui.Padding(item, bottom=0.2))
		return [
			ui.Panel(items=items_new),
		]


class DebuggerItem (ui.Block):
	def __init__(self, callback: Callable[[], None], image: ui.Img) -> None:
		super().__init__()
		self.image = image
		self.callback = callback

	def render(self) -> ui.Block.Children:
		return [
			ui.block(
				ui.Padding(ui.Button(self.callback, items=[self.image]), left=0.6, right=0.6)
			)
		]


class BreakpointsComponent(ui.Block):
	def __init__(self, breakpoints: Breakpoints, on_expand: Callable[[Breakpoint], None]) -> None:
		super().__init__()
		self.breakpoints = breakpoints

		# FIXME put in on activate/deactivate
		self.breakpoints.onChangedBreakpoint.add(self._updated)
		self.breakpoints.onMovedBreakpoints.add(self._updated)
		self.breakpoints.onResultBreakpoint.add(self._updated)
		self.breakpoints.onSelectedBreakpoint.add(self._updated)
		self.breakpoints.onChangedFilter.add(self._updated)
		self.on_expand = on_expand

	def _updated(self, data: Any) -> None:
		self.dirty()

	def onClicked(self, breakpoint: Breakpoint) -> None:
		self.breakpoints.select_breakpoint(breakpoint)

	def on_toggle(self, breakpoint: Breakpoint) -> None:
		self.breakpoints.toggle_enabled(breakpoint)

	def render(self) -> ui.Block.Children:
		items = [] #type: List[ui.TableItem]
		for filter in self.breakpoints.filters:
			def on_click(filter=filter):
				self.breakpoints.toggle_filter(filter) #type: ignore

			items.append(ui.block(
				ui.Button(on_click=on_click, items=[
					ui.Img((ui.Images.shared.dot, ui.Images.shared.dot_disabled)[not filter.enabled]),
				]),
				ui.Label(filter.name, color='secondary', padding_left=0.25, width=15, align=0)
			))
		for breakpoint in self.breakpoints.breakpoints:
			base, name = os.path.split(breakpoint.file)

			if breakpoint == self.breakpoints.selected_breakpoint:
				color = 'primary'
			else:
				color = 'secondary'

			def on_toggle(bp=breakpoint):
				return self.on_toggle(bp) #type: ignore

			def on_click(bp=breakpoint):
				return self.onClicked(bp) #type: ignore

			toggle_button = ui.Button(on_click=on_toggle, items=[
				ui.Img(breakpoint.image()),
			])
			fileAndLine = ui.Button(on_click=on_click, items=[
				# line number
				ui.Padding(ui.Box(ui.Label(str(breakpoint.line), color=color, width=3)), left=0.5, right=0.5),
				# filename
				ui.Label(name, color=color, padding_left=0.25, width=15, align=0),

			])
			items.append(ui.Padding(ui.block(toggle_button, fileAndLine), top=0.1, bottom=0.1))
		return [
			ui.Table(items)
		]
