from __future__ import annotations
from typing import Any, Callable, Iterable, Sequence, cast

from ..import ui
from .import css
from functools import partial


class TabbedView(ui.div):
	name: str
	parent: TabbedViewContainer|None
	on_show: Callable[[], None]|None = None

	def __init__(self, name: str):
		super().__init__()
		self.name = name
		self.parent = None

	def header(self, is_selected: bool):
		with ui.span(css=css.tab_selected if is_selected else css.tab):
			ui.text(self.name, css=css.label if is_selected else css.secondary)

		ui.spacer_dip(10)

	def visible(self) -> bool:
		return True

	def dirty_header(self):
		if not self.parent or not self.visible(): return
		self.parent.dirty()


class TabbedViewContainer(ui.div):
	def __init__(self, width: float|None = None, width_scale: float|None = None, width_additional: float = 0, width_additional_dip: float = 0) -> None:
		super().__init__()
		self.selected_index = 0

		self._width = width
		self._width_scale = width_scale
		self._width_additional = width_additional
		self._width_additional_dip = width_additional_dip

		self.items: Sequence[TabbedView] = []

	def modified_children(self):
		self.items = cast('list[TabbedView]', self.children)

		for item in self.items:
			item.parent = self

		if len(self.items) < self.selected_index:
			self.selected_index = 0

		self.dirty()

	def select(self, panel: Any):
		for index, item in enumerate(self.items):
			if item == panel:
				if self.selected_index != index:
					self.selected_index = index
					self.dirty()
				return

	def patch_selected(self):
		selected =  self.items[self.selected_index] if self.selected_index < len(self.items) else None
		if selected and selected.visible():
			return

		for index, item in enumerate(self.items):
			if item.visible():
				self.selected_index = index
				return

	def show(self, index: int):
		on_show = self.items[index].on_show
		if on_show: on_show()

		self.selected_index = index
		self.dirty()

	def render(self):
		if not self.items:
			return

		self.patch_selected()

		if self.layout.scrolling:
			height = 500
		else:
			height = self.layout.height +self.layout.viewport_position_y

		if self._width:
			width = self._width
		else:
			layout_width = self.layout.width + self._width_additional + self.layout.from_dip(self._width_additional_dip) + self.layout.internal_width_modifier
			width = layout_width * self._width_scale if self._width_scale else layout_width

		with ui.div(width=width, height=500, css=css.panel):
			# this inner panel controls how much content is actually displayed
			# while scrolling the tab bar disappears revealing all the content
			# while not scrolling this panel clips the content
			with ui.div(height=height-css.panel_content.padding_height - css.header_height, css=css.panel_content):
				self.items[self.selected_index].append_stack()

			with ui.div(width=width, height=4):
				for index, item in enumerate(self.items):
					if not item.visible():
						continue

					with ui.span(on_click=partial(self.show, index)):
						item.header(index == self.selected_index)
