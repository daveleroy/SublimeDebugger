from ...typecheck import *
from ...import ui

from .layout import pages_panel_width
from .import css

import sublime


class TabbedPanelItem:
	def __init__(self, id: int, item: ui.div, name: str, index: int = 0, buttons: List[Tuple[ui.Image, Callable]] = []):
		self.id = id
		self.item = item
		self.name = name
		self.index = index
		self.buttons = buttons
		self.modified = False
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
			tabs.append(ui.click(lambda index=index: self.show(index))[
				Tab(item, index == self.selected_index)
			])
		return [
			ui.div(height=3.5)[tabs],
			ui.div(width=pages_panel_width(self.layout), height=1000, css=css.rounded_panel)[
				self.items[self.selected_index].item
			],
		]


class Tab (ui.span):
	def __init__(self, item: TabbedPanelItem, selected: bool) -> None:
		super().__init__(height=3.5, css=css.tab_panel_selected if selected else css.tab_panel)

		if not selected and item.modified:
			self.items = [
				ui.text(item.name.upper(), css=css.label_secondary),
				ui.text('◯', css=css.modified_label),
			]
		else:
			self.items = [
				ui.text(item.name.upper(), css=css.label_secondary),
			]

	def render(self) -> ui.span.Children:
		return self.items


class Panels:
	def __init__(self, view: sublime.View, phantom_location: int, columns: int):
		self.panels = [] #type: List[TabbedPanelItem]
		self.pages = [] #type: List[TabbedPanel]
		self.columns = columns

		for i in range(0, columns):
			pages = TabbedPanel([], 0)
			self.pages.append(pages)
			phantom = ui.Phantom(pages, view, sublime.Region(phantom_location + i, phantom_location + i), sublime.LAYOUT_INLINE)

	def add(self, panels: List[TabbedPanelItem]):
		self.panels.extend(panels)
		self.layout()

	def modified(self, panel: TabbedPanelItem):
		column = panel.column
		row = panel.row
		if row >= 0 and column >= 0:
			self.pages[column].modified(row)

	def remove(self, id: int):
		for item in self.panels:
			if item.id == id:
				self.panels.remove(item)
				self.layout()
				return

	def show(self, id: int):
		for panel in self.panels:
			if panel.id == id:
				column = panel.column
				row = panel.row
				self.pages[column].show(row)

	def layout(self):
		items = [] #type: Any
		for i in range(0, self.columns):
			items.append([])

		for panel in self.panels:
			panel.column = panel.index % self.columns
			panel.row = len(items[panel.column])
			items[panel.column].append(panel)

		for i in range(0, self.columns):
			self.pages[i].update(items[i])
