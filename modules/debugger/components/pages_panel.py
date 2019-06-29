from sublime_debug.modules.core.typecheck import (
	Callable,
	Any,
	List,
	Sequence,
	Tuple
)

from sublime_debug.modules import ui
from .layout import pages_panel_width


class TabbedPanel(ui.Block):
	def __init__(self, items: List[Tuple[str, ui.Block, None]], selected_index: int) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index
		self._modified = [] #type: List[bool]
		for item in items:
			self._modified.append(False)

	def selected(self, index: int):
		self.selected_index = index
		self._modified[index] = False
		self.dirty()

	def modified(self, index: int):
		if not self._modified[index] and self.selected_index != index:
			self._modified[index] = True
		self.dirty()

	def render(self) -> ui.Block.Children:
		assert self.layout
		tabs = [] #type: List[ui.Inline]
		for index, item in enumerate(self.items):
			def on_click(index: int = index):
				self.selected(index)
			tabs.append(ui.Button(on_click, items=[
				PageTab(item[0], index == self.selected_index, self._modified[index], item[2])
			]))
			tabs.append(ui.HorizontalSpacer(0.25)) #type: ignore
		return [
			ui.block(*tabs),
			ui.HorizontalSpacer(pages_panel_width(self.layout)),
			ui.Panel(items=[
				self.items[self.selected_index][1]
			]),
		]


class PageTab (ui.Inline):
	def __init__(self, name: str, selected: bool, modified: bool, on_more_callback) -> None:
		super().__init__()
		self.on_more_callback = on_more_callback
		if selected:
			self.add_class('selected')
			self.items = [
				ui.Label(name, width=15, align=0),
				ui.Button(self.on_more, items=[
					ui.Img(ui.Images.shared.more)
				])
			]
		elif modified:
			self.items = [
				ui.Label(name, width=15, align=0, color="secondary"),
				ui.Label('◯', width=ui.WIDTH, align=0, color="secondary")
			]
		else:
			self.items = [
				ui.Label(name, width=15 + ui.WIDTH, align=0, color="secondary"),
			]

	def on_more(self) -> None:
		if self.on_more_callback:
			self.on_more_callback()

	def render(self) -> ui.Inline.Children:
		return self.items
