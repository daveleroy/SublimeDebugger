from ...typecheck import *
from ...import ui
from . import css

if TYPE_CHECKING:
	from ..debugger import Debugger

STOPPED = 0
RUNNING = 1
PAUSED = 2
LOADING = 3


class DebuggerPanel(ui.div):
	def __init__(self, callbacks: 'Debugger', breakpoints: ui.div) -> None:
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
			DebuggerCommandButton(self.callbacks.on_settings, ui.Images.shared.settings),
			DebuggerCommandButton(self.callbacks.on_play, ui.Images.shared.play),
		]

		if self.callbacks.is_stoppable():
			items.append(DebuggerCommandButton(self.callbacks.on_stop, ui.Images.shared.stop))
		else:
			items.append(DebuggerCommandButton(self.callbacks.on_stop, ui.Images.shared.stop_disable))

		if self.state == STOPPED or self.state == LOADING:
			items.append(DebuggerCommandButton(self.callbacks.on_pause, ui.Images.shared.pause_disable))
		elif self.state == PAUSED:
			items.append(DebuggerCommandButton(self.callbacks.on_resume, ui.Images.shared.resume))
		else:
			items.append(DebuggerCommandButton(self.callbacks.on_pause, ui.Images.shared.pause))

		if self.callbacks.is_paused():
			items.extend([
				DebuggerCommandButton(self.callbacks.on_step_over, ui.Images.shared.down),
				DebuggerCommandButton(self.callbacks.on_step_out, ui.Images.shared.left),
				DebuggerCommandButton(self.callbacks.on_step_in, ui.Images.shared.right),
			])
		else:
			items.extend([
				DebuggerCommandButton(self.callbacks.on_step_over, ui.Images.shared.down_disable),
				DebuggerCommandButton(self.callbacks.on_step_out, ui.Images.shared.left_disable),
				DebuggerCommandButton(self.callbacks.on_step_in, ui.Images.shared.right_disable),
			])

		return [
			ui.div()[
				ui.div(height=3.5)[items],
				ui.div(width=30, height=100, css=css.rounded_panel)[
					self.breakpoints,
				],
			]
		]


class DebuggerCommandButton (ui.span):
	def __init__(self, callback: Callable[[], None], image: ui.Image) -> None:
		super().__init__()

		self.image = image
		self.callback = callback

	def render(self) -> ui.span.Children:
		return [
			ui.span(css=css.padding)[
				ui.click(self.callback)[
					ui.icon(self.image),
				]
			]
		]
