
from sublime_db.modules.core.typecheck import (
	List,
	Sequence,
	Callable,
	Optional
)
from .component import Component, Inline
from .layout import Layout
from .render import Timer
from time import time


class OnClick (Inline):
	def __init__(self, on_click: Callable[[], None], items: Inline.Children) -> None:
		super().__init__()
		self.items = items
		self.on_click = on_click
		self.html_tag = 'a'

	def render(self) -> Inline.Children:
		return self.items

	def html(self, layout: Layout) -> str:
		self.html_tag_extra = 'href = "{}"'.format(layout.register_on_click_handler(self.on_click))
		return super().html(layout)


class Button (OnClick):
	def __init__(self, on_click: Callable[[], None], items: Inline.Children) -> None:
		super().__init__(self.on_clicked, items)
		self.items = items
		self.on_click_callback = on_click

	def on_clicked(self) -> None:
		self.on_click_callback()

	def render(self) -> Inline.Children:
		return self.items


class ButtonDoubleClick (OnClick):
	def __init__(self, on_double_click: Callable[[], None], on_click: Optional[Callable[[], None]], items: Inline.Children) -> None:
		super().__init__(self.on_clicked, items)
		self.items = items
		self.on_click_callback = on_click
		self.on_double_click = on_double_click
		self.last_single_click_time = 0.0

	def on_clicked(self) -> None:
		now = time()
		if now - self.last_single_click_time < 0.5:
			self.on_double_click()
			self.last_single_click_time = 0.0
		else:
			self.last_single_click_time = now

		if self.on_click_callback:
			self.on_click_callback()

	def render(self) -> Inline.Children:
		return self.items
