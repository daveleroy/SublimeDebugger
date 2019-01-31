from sublime_db.core.typecheck import (
	Sequence
)
from .component import Component, ComponentInline
from .layout import Layout

class Segment (Component):
	def __init__(self, items: Sequence[Component]) -> None:
		super().__init__()
		self.items = items
		
	def render (self) -> Sequence[Component]:
		return self.items

class Box (ComponentInline):
	def __init__(self, items: Sequence[Component]) -> None:
		super().__init__()
		self.items = items
		
	def render (self) -> Sequence[Component]:
		return self.items

class Panel (Component):
	def __init__(self, items: Sequence[Component]) -> None:
		super().__init__()
		self.items = items
	def render (self) -> Sequence[Component]:
		return self.items
	def html (self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return '<{} class="{}" {}><img class="width">{}</{}>'.format(self.html_tag, self.className, self.html_tag_extra, inner, self.html_tag)

class HorizontalSpacer (Component):
	def __init__(self, width: float) -> None:
		super().__init__()
		self.width = width
	def html (self, layout: Layout) -> str:
		return '<img style="width:{}rem">'.format(self.width)

class Items (Component):
	def __init__(self, items: Sequence[Component]) -> None:
		super().__init__()
		self.items = items

	def render (self) -> Sequence[Component]:
		return self.items