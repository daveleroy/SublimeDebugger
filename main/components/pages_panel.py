from sublime_db.core.typecheck import (
	Callable,
	Any,
	List,
	Sequence,
	Tuple
)

from sublime_db import ui
from .constants import VARIABLE_PANEL_MIN_WIDTH

class TabbedPanel(ui.Component):
	def __init__(self, items: List[Tuple[str, ui.Component]], selected_index: int) -> None:
		super().__init__()
		self.items = items
		self.selected_index = selected_index
		self._modified = []
		for item in items:
			self._modified.append(False)

	def selected(self, index: int):
		self.selected_index = index
		self._modified[index] = False
		self.dirty()

	def modified(self, index: int):
		if self._modified[index] != True and self.selected_index != index:
			self._modified[index] = True
			self.dirty()

	def render(self) -> ui.components:
		tabs = []
		for index, item in enumerate(self.items):
			def on_callback():
				pass
			tabs.append(ui.Button(lambda index=index: self.selected(index), items = [
				PageTab(item[0], index == self.selected_index, self._modified[index])
			]))
		return [
			ui.HorizontalSpacer(self.layout.width() - VARIABLE_PANEL_MIN_WIDTH - 5),
			Div(items = tabs),		
			ui.Panel(items = [
				self.items[self.selected_index][1]
			]),
		]

class Div (ui.Component):
	def __init__(self, items: [ui.Component]) -> None:
		super().__init__()
		self.items = items
		
	def render (self) -> Sequence[ui.Component]:
		return self.items

class PageTab (ui.ComponentInline):
	def __init__(self, name: str, selected: bool, modified: bool) -> None:
		super().__init__()
		if selected:
			self.add_class('selected')
			self.items = [ui.Label(name, width = 15, align = 0)]
		elif modified:
			self.items = [ui.Label(name + '*', width = 15, align = 0, color = "secondary")]
		else:
			self.items = [ui.Label(name, width = 15, align = 0, color = "secondary")]

	def render (self) -> Sequence[ui.Component]:
		return self.items

