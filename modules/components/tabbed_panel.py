from ..typecheck import *
from ..import ui
from .layout import pages_panel_width
from .import css

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
				ui.text('◯', css=css.label_secondary)
			]
		else:
			self.items = [
				ui.text(item.name.upper(), css=css.label_secondary),
			]

	def render(self) -> ui.span.Children:
		return self.items
