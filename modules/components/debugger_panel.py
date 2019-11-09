from ..typecheck import *

from .. import ui

STOPPED = 0
RUNNING = 1
PAUSED = 2
LOADING = 3


class DebuggerPanelCallbacks:
	def on_play(self) -> None:
		...
	def on_resume(self) -> None:
		...
	def on_pause(self) -> None:
		...
	def on_stop(self) -> None:
		...
	def on_step_over(self) -> None:
		...
	def on_step_in(self) -> None:
		...
	def on_step_out(self) -> None:
		...
	def on_settings(self) -> None:
		...


class DebuggerPanel(ui.Block):
	def __init__(self, callbacks: DebuggerPanelCallbacks, breakpoints: ui.Block) -> None:
		super().__init__()
		self.state = STOPPED
		self.callbacks = callbacks
		self.name = ''
		self.breakpoints = breakpoints
	
	def setState(self, state: int) -> None:
		self.state = state
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

		items = [DebuggerItem(self.callbacks.on_settings, ui.Img(ui.Images.shared.settings))]

		if play:
			items.append(
				DebuggerItem(self.callbacks.on_play, ui.Img(ui.Images.shared.play))
			)
		else:
			items.append(
				DebuggerItem(self.callbacks.on_play, ui.Img(ui.Images.shared.play))
			)

		items.append(
			DebuggerItem(self.callbacks.on_stop, ui.Img(ui.Images.shared.stop), ui.Img(ui.Images.shared.stop_disable))
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

		items.extend([
			DebuggerItem(self.callbacks.on_step_over, ui.Img(ui.Images.shared.down), ui.Img(ui.Images.shared.down_disable)),
			DebuggerItem(self.callbacks.on_step_out, ui.Img(ui.Images.shared.left), ui.Img(ui.Images.shared.left_disable)),
			DebuggerItem(self.callbacks.on_step_in, ui.Img(ui.Images.shared.right), ui.Img(ui.Images.shared.right_disable)),
		])
			

		items_new = []
		for item in items:
			items_new.append(item)
		return [
			ui.block(*items_new),
			ui.Panel(items= [self.breakpoints]),
		]


class DebuggerItem (ui.Inline):
	def __init__(self, callback: Callable[[], None], enabled_image: ui.Img, disabled_image: Optional[ui.Img] = None) -> None:
		super().__init__()
		
		if not callback.enabled() and disabled_image:
			self.image = disabled_image
		else:
			self.image = enabled_image

		self.callback = callback


	def render(self) -> ui.Inline.Children:
		return [
			ui.Padding(ui.Button(self.callback, items=[self.image]), left=0.6, right=0.6, top=0.0, bottom=0.0)
		]


