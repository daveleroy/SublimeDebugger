from ..typecheck import *
from ..import ui
from . import css

STOPPED = 0
RUNNING = 1
PAUSED = 2
LOADING = 3

class DebuggerPanelCallbacks(Protocol):
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

class DebuggerPanel(ui.div):
	def __init__(self, callbacks: DebuggerPanelCallbacks, breakpoints: ui.div) -> None:
		super().__init__()
		self.state = STOPPED
		self.callbacks = callbacks
		self.name = ''
		self.breakpoints = breakpoints
	
	def setState(self, state: int) -> None:
		self.state = state
		self.dirty()

	def render(self) -> ui.div.Children:
		buttons = [] #type: List[ui.span]
		items = [
			DebuggerItem(self.callbacks.on_settings, ui.Images.shared.settings),
			DebuggerItem(self.callbacks.on_play, ui.Images.shared.play),
			DebuggerItem(self.callbacks.on_stop, ui.Images.shared.stop, ui.Images.shared.stop_disable),
		]

		if self.state == STOPPED or self.state == LOADING:
			items.append(DebuggerItem(self.callbacks.on_pause, ui.Images.shared.pause_disable))
		elif self.state == PAUSED:
			items.append(DebuggerItem(self.callbacks.on_resume, ui.Images.shared.resume))
		else:
			items.append(DebuggerItem(self.callbacks.on_resume, ui.Images.shared.pause))

		items.extend([
			DebuggerItem(self.callbacks.on_step_over, ui.Images.shared.down, ui.Images.shared.down_disable),
			DebuggerItem(self.callbacks.on_step_out, ui.Images.shared.left, ui.Images.shared.left_disable),
			DebuggerItem(self.callbacks.on_step_in, ui.Images.shared.right, ui.Images.shared.right_disable),
		])

		return [
			ui.div()[
				ui.div(height=3.5)[items],
				ui.div(width=30, height=100, css=css.rounded_panel)[
					self.breakpoints,
				],
			]
		]

class DebuggerItem (ui.span):
	def __init__(self, callback: Callable[[], None], enabled_image: ui.Image, disabled_image: Optional[ui.Image] = None) -> None:
		super().__init__()

		if not callback.enabled() and disabled_image:
			self.image = disabled_image
		else:
			self.image = enabled_image

		self.callback = callback

	def render(self) -> ui.span.Children:
		return [
			ui.span(css=css.padding)[
				ui.click(self.callback)[
					ui.icon(self.image),
				]
			]
		]
