from ... typecheck import *
from ... import ui
from ..watch import Watch, WatchView
from ..variables import Variables, VariableComponent

import sublime


class VariablesView (ui.div):
	def __init__(self, variables: Variables) -> None:
		super().__init__()
		self.variables = variables
		variables.on_updated.add(self.dirty)

	def render(self) -> ui.div.Children:
		variables = [VariableComponent(variable) for variable in self.variables.variables]
		if variables:
			variables[0].toggle_expand()
		return variables


class VariablesPanel (ui.div):
	def __init__(self, variables: Variables, watch: Watch) -> None:
		super().__init__()
		self.watch_view = WatchView(watch)
		self.variables_view = VariablesView(variables)

	def render(self) -> ui.div.Children:
		return [
			self.watch_view,
			self.variables_view,
		]
