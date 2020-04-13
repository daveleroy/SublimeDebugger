from ...typecheck import *
from ...import ui

from .layout import pages_panel_width
from .import css

import sublime


class TabbedPanelItem:
	def __init__(self, id: int, item: ui.div, name: str, index: int = 0):
		self.id = id
		self.item = item
		self.name = name
		self.index = index
		self.modified = False
		self.visible = True
		self.column = -1
		self.row = -1

class TabbedPanel(ui.div):
	def __init__(self, items: List[TabbedPanelItem], selected_index: int) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index

	def update(self, items: List[TabbedPanelItem]):
		self.items = items
		if len(items) < self.selected_index:
			self.selected_index = 0
		self.dirty()

	def add(self, item: TabbedPanelItem):
		self.items.append(item)
		self.dirty()

	def remove(self, id: int):
		for item in self.items:
			if item.id == id:
				self.items.remove(item)
				break
		
		if len(self.items) < self.selected_index:
			self.selected_index = 0
		self.dirty()

	def select(self, id: int):
		for index, item in enumerate(self.items):
			if item.id == id:
				self.selected_index = index
				item.modified = False
				self.dirty()
				return

	def set_visible(self, id: int, visible: bool):
		for index, item in enumerate(self.items):
			if item.id == id:
				item.visible = visible
				self.patch_selected()
				self.dirty()
				return

	def patch_selected(self):
		if not self.items[self.selected_index].visible:
			for index, item in enumerate(self.items):
				if item.visible:
					self.selected_index = index
					return

	def show(self, index: int):
		self.selected_index = index
		self.items[index].modified = False
		self.dirty()

	def modified(self, index: int):
		item = self.items[index]
		if not item.modified and self.selected_index != index:
			item.modified = True
			self.dirty()

	def render(self) -> ui.div.Children:
		assert self.layout
		if not self.items:
			return []

		tabs = [] #type: List[ui.span]
		for index, item in enumerate(self.items):
			if not item.visible:
				continue

			tabs.append(ui.click(lambda index=index: self.show(index))[ #type: ignore
				Tab(item, index == self.selected_index)
			])
		return [
			ui.div(height=css.header_height)[tabs],
			ui.div(width=pages_panel_width(self.layout), height=1000, css=css.rounded_panel)[
				self.items[self.selected_index].item
			],
		]

class Tab (ui.span):
	def __init__(self, item: TabbedPanelItem, selected: bool) -> None:
		super().__init__(height=css.header_height, css=css.tab_panel_selected if selected else css.tab_panel)
		name = item.name.upper().ljust(20)

		if not selected and item.modified:
			self.items = [
				ui.text(name, css=css.label_secondary),
				ui.text('◯', css=css.label_secondary),
			]
		else:
			self.items = [
				ui.text(name, css=css.label_secondary),
				ui.text(' ', css=css.label_secondary),
			]

	def render(self) -> ui.span.Children:
		return self.items
