from sublime_debug.modules.core.typecheck import (
	Sequence
)
from .component import Component, Inline, Block
from .layout import Layout


class Segment (Block):
	def __init__(self, items: Block.Children) -> None:
		super().__init__()
		self.items = items

	def render(self) -> Block.Children:
		return self.items


class Box (Inline):
	def __init__(self, *items: Inline) -> None:
		super().__init__()
		self.items = items

	def render(self) -> Inline.Children:
		return self.items


class Panel (Block):
	def __init__(self, items: Block.Children) -> None:
		super().__init__()
		self.items = items

	def render(self) -> Block.Children:
		return self.items

	def height(self, layout: Layout) -> float:
		return max(super().height(layout), 100)


class HorizontalSpacer (Block):
	def __init__(self, width: float) -> None:
		super().__init__()
		self.width = width

	def html(self, layout: Layout) -> str:
		return '<img style="width:{}rem">'.format(self.width)
