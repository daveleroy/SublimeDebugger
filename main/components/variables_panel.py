from sublime_db.core.typecheck import (List, Callable, Optional)
from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Scope,
	Thread,
	DebugAdapterClient
)

from .variable_component import Variable, VariableStateful, VariableStatefulComponent
from .layout import variables_panel_width


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
			variable = Variable(v.client, v.name, "", v.variablesReference)
			variable_stateful = VariableStateful(variable, None)
			component = VariableStatefulComponent(variable_stateful)
			variable_stateful.on_dirty = component.dirty

			if first:
				first = False
				variable_stateful.expand()

			scopes_items.append(component)

		items.append(ui.Table(items=scopes_items))

		return [
			ui.HorizontalSpacer(variables_panel_width(self.layout)),
			ui.Panel(items=items)
		]
