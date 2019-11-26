from .. typecheck import *
from . layout import Layout

components = Sequence['Component']


class Component:
	def __init__(self) -> None:
		self.layout = None #type: Optional[Layout]
		self.children = [] #type: Sequence[Component]
		self.className = self.__class__.__name__
		self.requires_render = True

	def added(self, layout: Layout) -> None:
		...

	def removed(self) -> None:
		...

	def render(self) -> components:
		...

	def height(self, layout: Layout) -> float:
		max = 0.0
		for item in self.children:
			h = item.height(layout)
			if h > max:
				max = h
		return max

	def add_class(self, name: str) -> None:
		self.className += ' '
		self.className += name

	def dirty(self):
		if self.layout:
			self.layout.dirty()
		self.requires_render = True

	def html_inner(self, layout: Layout) -> str:
		html = []
		for child in self.children:
			html.append(child.html(layout))
		return ''.join(html)

	def html(self, layout: Layout) -> str:
		...
