from __future__ import annotations
from ..typecheck import *

from ..import ui
from .import css
from functools import partial

class TabbedPanelItem:
	def __init__(self, id: Any, item: ui.div, name: str, index: int = 0, show_options: Optional[Callable[[], None]] = None):
		self.id = id
		self.item = item
		self.name = name
		self.index = index
		self.modified = False
		self.column = -1
		self.row = -1
		self.show_options = show_options

class Panel(ui.div):
	name: str
	parent: TabbedPanel|None

	def __init__(self, name: str):
		super().__init__()
		self.name = name
		self.parent = None

	def panel_header(self, expanded: bool) -> list[ui.span] | None:
		return [
			ui.spacer(1),
			ui.text(self.name, css=css.label_secondary),
			ui.spacer(2),
		]

	def visible(self) -> bool:
		return True

	def dirty_header(self):
		if not self.parent: return
		self.parent.dirty()

class TabbedPanel(ui.div):
	def __init__(self, items: list[TabbedPanelItem], selected_index: int, width_scale: float, width_additional: float) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index
		self.width_scale = width_scale
		self.width_additional = width_additional

	def update(self, items: list[TabbedPanelItem]):
		self.items = items
		for item in items:
			if isinstance(item.item, Panel):
				item.item.parent = self

		if len(items) < self.selected_index:
			self.selected_index = 0
		self.dirty()

	def add(self, item: TabbedPanelItem):
		if isinstance(item.item, Panel):
			item.item.parent = self

		self.items.append(item)
		self.dirty()

	def remove(self, id: Any):
		for item in self.items:
			if item.id == id:
				self.items.remove(item)
				break

		if len(self.items) < self.selected_index:
			self.selected_index = 0
		self.dirty()

	def select(self, id: Any):
		for index, item in enumerate(self.items):
			if item.id == id:
				self.selected_index = index
				item.modified = False
				self.dirty()
				return

	def patch_selected(self):
		selected =  self.items[self.selected_index] if self.selected_index < len(self.items) else None
		if selected and (not isinstance(selected.item, Panel) or selected.item.visible()):
			return

		for index, item in enumerate(self.items):
			if not isinstance(item.item, Panel):
				self.selected_index = index
				return
			elif item.item.visible():
				self.selected_index = index
				return

	def show(self, index: int):
		if self.selected_index == index and self.items[index].show_options:
			self.items[index].show_options()
			return

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

		self.patch_selected()

		width = (self.layout.width() + self.width_additional) * self.width_scale

		tabs = [] #type: list[ui.span]
		for index, item in enumerate(self.items):
			if isinstance(item.item, Panel):
				if not item.item.visible():
					continue

				tab = item.item.panel_header(index == self.selected_index)
			else:
				tab = [
					ui.spacer(1),
					ui.text(item.name, css=css.label_secondary),
					ui.spacer(2),
				]
			
			tabs.append(ui.click(partial(self.show, index))[
				ui.span(css=css.tab_panel_selected if index == self.selected_index else css.tab_panel)[
					tab
				]
			])

		return [
			ui.div(width=width, height=css.header_height)[
				ui.align()[
					tabs
				]
			],
			ui.div(width=width, height=1000, css=css.rounded_panel)[
				self.items[self.selected_index].item
			],
		]
