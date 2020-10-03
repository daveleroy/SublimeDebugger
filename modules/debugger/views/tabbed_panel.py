from ...typecheck import *
from ...import ui
from .import css


class TabbedPanelItem:
	def __init__(self, id: Any, item: ui.div, name: str, index: int = 0, show_options: Optional[Callable[[], None]] = None):
		self.id = id
		self.item = item
		self.name = name
		self.index = index
		self.modified = False
		self.visible = True
		self.column = -1
		self.row = -1
		self.show_options = show_options


class TabbedPanel(ui.div):
	def __init__(self, items: List[TabbedPanelItem], selected_index: int, width_scale: float, width_additional: float) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index
		self.width_scale = width_scale
		self.width_additional = width_additional

	def update(self, items: List[TabbedPanelItem]):
		self.items = items
		if len(items) < self.selected_index:
			self.selected_index = 0
		self.dirty()

	def add(self, item: TabbedPanelItem):
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

	def set_visible(self, id: Any, visible: bool):
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

		width = (self.layout.width() + self.width_additional) * self.width_scale

		tabs = [] #type: List[ui.span]
		for index, item in enumerate(self.items):
			if not item.visible:
				continue

			tabs.append(ui.click(lambda index=index: self.show(index))[ #type: ignore
				ui.span(css=css.tab_panel_selected if index == self.selected_index else css.tab_panel)[
					ui.spacer(1),
					ui.text(item.name, css=css.label_secondary),
					ui.spacer(2),
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
