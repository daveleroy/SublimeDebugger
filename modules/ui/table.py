from ..typecheck import *

from .component import Block, Layout, Component
from .size import HEIGHT, WIDTH


class TableItem (Block):
	def __init__(self, items: Block.Children) -> None:
		super().__init__()
		self.items = items

	def width(self, layout: Layout) -> float:
		return WIDTH

	def render(self) -> Block.Children:
		return self.items


class Table (Block):
	def __init__(self, items: Block.Children, selected_index=-1) -> None:
		super().__init__()
		self.selected_index = selected_index
		for index, item in enumerate(items):
			if selected_index == index:
				item.add_class('table-item-selected')

		self.items = items

	def render(self) -> Block.Children:
		return self.items
