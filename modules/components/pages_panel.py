from ..typecheck import *

from .. import ui
from .layout import pages_panel_width

class TabbedPanelItem:
	def __init__(self, id: int, item: ui.Block, name: str, index: int = 0, buttons: List[Tuple[ui.Image, Callable]] = []):
		self.id = id
		self.item = item
		self.name = name
		self.index = index
		self.buttons = buttons
		self.modified = False
		self.column = -1
		self.row = -1

class TabbedPanel(ui.Block):
	def __init__(self, items: List[TabbedPanelItem], selected_index: int) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index
	
	def update(self, items: List[TabbedPanelItem]):
		self.items = items
		if len(items) < self.selected_index:
			self.selected_index =  0
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

	def render(self) -> ui.Block.Children:
		assert self.layout
		if not self.items:
			return []

		tabs = [] #type: List[ui.Inline]
		for index, item in enumerate(self.items):
			def on_click(index: int = index):
				self.show(index)
			tabs.append(ui.Button(on_click, items=[
				Tab(item, index == self.selected_index)
			]))
			tabs.append(ui.HorizontalSpacer(0.25)) #type: ignore
		return [
			ui.block(*tabs),
			ui.HorizontalSpacer(pages_panel_width(self.layout)),
			ui.Panel(items=[
				self.items[self.selected_index].item
			]),
		]


class Tab (ui.Inline):
	def __init__(self, item: TabbedPanelItem, selected: bool) -> None:
		super().__init__()
		
		if selected:
			self.add_class('selected')
			self.items = [
				ui.Label(item.name.upper(), width=12, align=0, color="secondary"),
			]
			for image, on_click in item.buttons:
				self.items.append(				
					ui.Button(on_click, items=[
						ui.Img(image)
					])
				)

		elif item.modified:
			self.items = [
				ui.Label(item.name.upper(), width=12, align=0, color="secondary"),
				ui.Label('◯', width=ui.WIDTH, align=0, color="secondary")
			]
		else:
			self.items = [
				ui.Label(item.name.upper(), width=12 + ui.WIDTH, align=0, color="secondary"),
			]

	def render(self) -> ui.Inline.Children:
		return self.items
