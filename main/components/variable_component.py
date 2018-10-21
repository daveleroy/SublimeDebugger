
from debug.core.typecheck import List
from debug.main.debug_adapter_client.types import Variable

from debug import ui, core

class VariableComponent (ui.Component):
	def __init__(self, variable: Variable) -> None:
		super().__init__()
		self.variable = variable
		self.expanded = False
		self.fetched = False
		self.variables = [] #type: List[Variable]

	def toggle(self) -> None:
		self.expanded = not self.expanded
		if self.expanded:
			@core.async
			def onVariables() -> core.awaitable[None]:
				self.variables = yield from self.variable.adapter.GetVariables(self.variable.reference)
				self.dirty()
			core.run(onVariables())
			self.fetched = True
		self.dirty()

	def render(self) -> ui.components:
		v = self.variable
		
		if v.reference == 0:
			return [
				ui.Label(v.name, padding_left = 0.5, padding_right = 1),
				ui.Label(v.value, color = 'secondary'),
			]

		if self.expanded:
			inner = [] #type: List[ui.Component]
			for variable in self.variables:
				inner.append(VariableComponent(variable))
			table = ui.Table(items = inner)
			table.add_class('inset')
			items = [
				ui.Button(self.toggle, items = [
					ui.Img(ui.Images.shared.down)
				]),
				ui.Label(v.name, padding_right = 1),
				ui.Label(v.value, color = 'secondary'),
				table
			]
			return items
		else:
			return [
				ui.Button(self.toggle, items = [
					ui.Img(ui.Images.shared.right)
				]),
				ui.Label(v.name, padding_right = 1),
				ui.Label(v.value, color = 'secondary'),
			]

class VariablesComponent (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.variables = [] #type: List[Variable]
		self.no_scope = True
	def clear(self) -> None:
		self.no_scope = True
		self.variables = []
		self.dirty()
	def set_variables(self, locals: List[Variable]) -> None:
		self.no_scope = False
		self.variables = locals
		self.dirty()
	def render(self) -> ui.components:
		
		if self.no_scope:
			item = ui.Label('No stack frame selected', padding_left = 0.5, color = 'secondary') #type: ui.Component
		else:
			items = [] #type: List[ui.Component]
			for v in self.variables:
				items.append(VariableComponent(v))
			item = ui.Table(items = items)
		return [
			ui.Panel(items = [
				ui.Segment(items = [
					ui.Label('Variables')
				]),
				item
			])
		]
