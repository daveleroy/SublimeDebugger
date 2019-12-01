from .. typecheck import *
from .. import core
from .. import ui
from .. import dap
from .. debugger.breakpoints import Breakpoints
from .. debugger.watch import Watch, WatchView
from .. debugger.variables import Variables, VariableComponent
from . layout import variables_panel_width

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
