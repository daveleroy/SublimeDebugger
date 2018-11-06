
from sublime_db.core.typecheck import (
	List,
	Sequence,
	Callable,
	Optional
)
from .component import Component, ComponentInline
from .layout import Layout
from .render import Timer, add_timer

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


class Button (OnClick):
	def __init__(self, on_click: Callable[[], None], items: List[Component]) -> None:
		super().__init__(self.on_clicked, items)
		self.items = items
		self.on_click_callback = on_click

	def on_clicked(self) -> None:
		self.on_click_callback()

	def render (self) -> Sequence[Component]:
		return self.items

class ButtonDoubleClick (OnClick):
	def __init__(self, on_double_click: Callable[[], None], on_click: Optional[Callable[[], None]], items: List[Component]) -> None:
		super().__init__(self.on_clicked, items)
		self.items = items
		self.on_click_callback = on_click
		self.on_double_click = on_double_click
		self.is_double_click = False
		self.is_double_click_timer = None #type: Optional[Timer]

	def removed(self) -> None:
		if self.is_double_click_timer:
			self.is_double_click_timer.dispose()

	def on_is_double_click_timer(self) -> None:
		self.is_double_click = False

	def on_clicked(self) -> None:
		if self.is_double_click:
			self.is_double_click = False
			self.on_double_click()

		self.is_double_click = True
		if self.is_double_click_timer:
			self.is_double_click_timer.dispose()

		self.is_double_click_timer = Timer(0.5, self.on_is_double_click_timer)
		add_timer(self.is_double_click_timer)

		if self.on_click_callback:
			self.on_click_callback()

	def render (self) -> Sequence[Component]:
		return self.items