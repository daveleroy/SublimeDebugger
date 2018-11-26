from sublime_db.core.typecheck import (List, Callable, Optional)
from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Scope,
	Thread,
	DebugAdapterClient
)

from .variable_component import ScopeComponent

class VariablesPanel (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.scopes = [] #type: List[Scope]

	def clear(self) -> None:
		self.scopes = []
		self.dirty()

	def set_scopes(self, scopes: List[Scope]) -> None:
		self.scopes = scopes
		self.dirty()

	def render(self) -> ui.components:
		items = [
			ui.Segment(items = [ui.Label('Variables')])
		] #type: List[ui.Component]

		scopes_items = [] #type: List[ui.Component]

		# expand the first scope only
		first = True
		for v in self.scopes:
			scopes_item = ScopeComponent(v)
			if first:
				first = False
				scopes_item.scope.toggle_expand()
			scopes_items.append(scopes_item)
		
		items.append(ui.Table(items = scopes_items))
		
		return [
			ui.HorizontalSpacer(250),
			ui.Panel(items = items)
		]
