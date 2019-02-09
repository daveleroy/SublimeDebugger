from sublime_db.core.typecheck import (List, Callable, Optional)
from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Scope,
	Thread,
	DebugAdapterClient
)

from .variable_component import ScopeComponent
from . import constants


class VariablesPanel (ui.Block):
	def __init__(self) -> None:
		super().__init__()
		self.scopes = [] #type: List[Scope]

	def clear(self) -> None:
		self.scopes = []
		self.dirty()

	def set_scopes(self, scopes: List[Scope]) -> None:
		self.scopes = scopes
		self.dirty()

	def render(self) -> ui.Block.Children:
		items = [
		] #type: List[ui.Block]

		scopes_items = [] #type: List[ui.Block]

		# expand the first scope only
		first = True
		for v in self.scopes:
			scopes_item = ScopeComponent(v)
			if first:
				first = False
				scopes_item.scope.toggle_expand()
			scopes_items.append(scopes_item)

		items.append(ui.Table(items=scopes_items))

		return [
			ui.HorizontalSpacer(constants.VARIABLE_PANEL_MIN_WIDTH),
			ui.Panel(items=items)
		]
