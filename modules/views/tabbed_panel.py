from __future__ import annotations
from ..typecheck import *

from ..import ui
from .import css
from functools import partial


class Panel(ui.div):
	name: str
	parent: TabbedPanel|None
	on_show: Callable[[], None]|None = None

	def __init__(self, name: str):
		super().__init__()
		self.name = name
		self.parent = None

	def panel_header(self, expanded: bool) -> list[ui.span] | None:
		if expanded:
			csss = css.tab_panel_selected
		else:
			csss = css.tab_panel

		return [
			ui.span(css=csss) [
				ui.text(self.name, css=css.label_secondary),
			]
		]

	def visible(self) -> bool:
		return True

	def dirty_header(self):
		if not self.parent: return
		self.parent.dirty()

class TabbedPanel(ui.div):
	def __init__(self, items: list[Panel], selected_index: int, width_scale: float, width_additional: float) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index
		self.width_scale = width_scale
		self.width_additional = width_additional

	def update(self, items: list[Panel]):
		self.items = items
		for item in items:
			item.parent = self
				

		if len(items) < self.selected_index:
			self.selected_index = 0
		self.dirty()

	def add(self, item: Panel):
		item.parent = self

		self.items.append(item)
		self.dirty()

	def remove(self, panel: Any):
		self.items.remove(panel)
		panel.parent = None

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
		# if self.selected_index == index and self.items[index].show_options:
		# 	self.items[index].show_options()
		# 	return
		on_show = self.items[index].on_show
		if on_show: on_show()
		
		self.selected_index = index
		self.dirty()

	def render(self) -> ui.div.Children:
		assert self.layout
		if not self.items:
			return []

		self.patch_selected()

		# each phantom takes up 10 extra dip 5 on each side it looks like
		layout_width = self.layout.width() -  self.layout.from_dip(30)

		width = (layout_width + self.width_additional) * self.width_scale

		tabs: list[ui.span] = []
		for index, item in enumerate(self.items):
			if not item.visible():
				continue

			tab = item.panel_header(index == self.selected_index)

			
			tabs.append(ui.click(partial(self.show, index))[
				tab
			])

		return [
			ui.div(width=width, height=4)[
				ui.align()[
					tabs
				]
			],
			ui.div(width=width - css.rounded_panel.padding_width, height=1000, css=css.rounded_panel)[
				self.items[self.selected_index]
			],
		]
