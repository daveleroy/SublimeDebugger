
from sublime_db.modules.core.typecheck import List, Optional
from sublime_db.modules import ui


class LoadingComponent (ui.Inline):
	def __init__(self) -> None:
		super().__init__()
		self.timer = None #type: Optional[ui.Timer]
		self.tick = 0
		self.images = [] #type: List[ui.Img]

		image = ui.Image.named('dot0.png')
		self.images.append(ui.Img(image))

		image = ui.Image.named('dot3.png')
		self.images.append(ui.Img(image))
		self.images.append(ui.Img(image))

	def on_timer(self) -> None:
		self.images.insert(0, self.images.pop()) #rotate images
		self.dirty()

	def added(self, layout: ui.Layout) -> None:
		if self.timer:
			self.timer.dispose()
		self.timer = ui.Timer(self.on_timer, 0.3, repeat=True)

	def removed(self) -> None:
		if self.timer:
			self.timer.dispose()

	def render(self) -> ui.Inline.Children:
		return self.images
