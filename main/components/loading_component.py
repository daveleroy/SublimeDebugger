
from sublime_db.core.typecheck import List
from sublime_db import ui


class LoadingComponent (ui.ComponentInline):
	def __init__(self) -> None:
		super().__init__()
		self.timer = ui.Timer(0.3, self.on_timer)
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
		ui.add_timer(self.timer)

	def removed(self) -> None:
		ui.remove_timer(self.timer)

	def render(self) -> ui.components:
		return self.images
