

from sublime_db.core.typecheck import (
	List,
	Sequence,
	Callable,
	Optional,
	Union
)
from .component import Component, Inline, Block, components
from .layout import Layout


class Padding(Component):
	def __init__(self, item: Union[Block, Inline], top: float = 0, bottom: float = 0, left: float = 0, right: float = 0) -> None:
		super().__init__()
		self.item = item
		self.top = top
		self.bottom = bottom
		self.left = left
		self.right = right

		if issubclass(type(item), Inline):
			self.inline = True
		elif issubclass(type(item), Block):
			self.inline = False
		else:
			self.inline = False

	def render(self) -> components:
		return [self.item]

	def height(self, layout: Layout) -> float:
		return self.item.height(layout) + self.top + self.bottom

	def html(self, layout: Layout) -> str:
		content = self.item.html(layout)
		style = 'style="padding-top:{}rem;padding-bottom:{}rem;padding-left:{}rem;padding-right:{}rem;"'.format(self.top, self.bottom, self.left, self.right)
		if self.inline:
			return '<span class="{}" {}>{}</span>'.format(self.className, style, content)
		else:
			return '<div class="{}" {}>{}</div>'.format(self.className, style, content)
