from debugger.modules.core.typecheck import (
	Callable,
	List,
)
from debugger.modules import ui

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
	def __init__(self, callbacks: DebuggerPanelCallbacks) -> None:
		super().__init__()
		self.state = STOPPED
		self.callbacks = callbacks
		self.name = ''

	def setState(self, state: int) -> None:
		self.state = state
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


