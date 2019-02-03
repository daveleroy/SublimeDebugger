
from sublime_db.core.typecheck import List
from sublime_db import ui


class LoadingComponent (ui.ComponentInline):
	def __init__(self) -> None:
		super().__init__()
		self.timer = None #type: ui.Timer
		self.tick = 0
		self.images = [] #type: List[ui.Component]

		image = ui.Image.named('dot0.png')
		self.images.append(ui.Img(image))

		image = ui.Image.named('dot3.png')
		self.images.append(ui.Img(image))
		self.images.append(ui.Img(image))

	def on_timer(self) -> None:
		self.images.insert(0, self.images.pop()) #rotate images
		self.dirty()

	def added(self, layout: ui.Layout) -> None:
		if timer:
			self.timer.dispose()
		self.timer = ui.Timer(self.on_timer, 0.3, repeats=True)

	def removed(self) -> None:
		if timer:
			self.timer.dispose()

	def render(self) -> ui.components:
		return self.images
