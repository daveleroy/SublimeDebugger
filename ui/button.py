
from sublime_db.core.typecheck import (
	List,
	Sequence,
	Callable
)
from .component import Component, ComponentInline
from .layout import Layout

class OnClick (ComponentInline):
	def __init__(self, on_click: Callable[[], None], items: List[Component]) -> None:
		super().__init__()
		self.items = items
		self.on_click = on_click
		self.html_tag = 'a'

	def render (self) -> Sequence[Component]:
		return self.items
		
	def html(self, layout: Layout) -> str:
		self.html_tag_extra = 'href = "{}"'.format(layout.register_on_click_handler(self.on_click))
		return super().html(layout)

# TODO add an indication that the button was clicked?
class Button (OnClick):
	def __init__(self, on_click: Callable[[], None], items: List[Component]) -> None:
		super().__init__(self.on_clicked, items)
		self.items = items
		self.on_click_callback = on_click

	def on_clicked(self) -> None:
		self.on_click_callback()

	def render (self) -> Sequence[Component]:
		return self.items