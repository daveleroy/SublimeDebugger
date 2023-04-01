from __future__ import annotations
from typing import Any, Callable, Iterable, Sequence

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

	def header(self, is_selected: bool) -> ui.span.Children:
		return ui.span(css=css.tab_selected if is_selected else css.tab) [
			ui.text(self.name, css=css.label if is_selected else css.secondary),
		]

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

	def __getitem__(self, values: TabbedView|Sequence[TabbedView]): #type: ignore
		self.items = values if isinstance(values, Iterable) else [values]

		for item in self.items:
			item.parent = self

		if len(self.items) < self.selected_index:
			self.selected_index = 0

		self.dirty()

		return self

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

	def render(self) -> ui.div.Children:
		assert self.layout
		if not self.items:
			return []

		self.patch_selected()

		if self._width:
			width = self._width
		else:
			# each phantom takes up 10 extra dip 5 on each side it looks like
			layout_width = self.layout.width() + self._width_additional + self.layout.from_dip(self._width_additional_dip)
			width = layout_width * self._width_scale if self._width_scale else layout_width

		tabs: list[ui.span] = []

		for index, item in enumerate(self.items):
			if not item.visible():
				continue

			tabs.append(ui.span(on_click=partial(self.show, index))[
				item.header(index == self.selected_index)
			])

		return [
			ui.div(width=width, height=4)[
				tabs
			],
			ui.div(width=width - css.panel.padding_width, height=500, css=css.panel)[
				self.items[self.selected_index]
			],
		]
