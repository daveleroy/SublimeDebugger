
from sublime_db.core.typecheck import List
from sublime_db.main.debug_adapter_client.types import Variable

from sublime_db import ui, core

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
		name = v.name

		MAX_LENGTH = 40
		if len(name) > MAX_LENGTH:
			name = name[:MAX_LENGTH-1] + '…'
		
		MAX_LENGTH -= len(name)
		value = v.value
		if len(value) > MAX_LENGTH:
			value = value[:MAX_LENGTH-1] + '…'

		if v.reference == 0:
			return [
				ui.Label(name, padding_left = 0.5, padding_right = 1),
				ui.Label(value, color = 'secondary'),
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
				ui.Label(name, padding_right = 1),
				ui.Label(value, color = 'secondary'),
				table
			]
			return items
		else:
			return [
				ui.Button(self.toggle, items = [
					ui.Img(ui.Images.shared.right)
				]),
				ui.Label(name, padding_right = 1),
				ui.Label(value, color = 'secondary'),
			]

class VariablesComponent (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.variables = [] #type: List[Variable]

	def clear(self) -> None:
		self.variables = []
		self.dirty()
	def set_variables(self, locals: List[Variable]) -> None:
		self.variables = locals
		self.dirty()
	def render(self) -> ui.components:
		items = [
			ui.Segment(items = [ui.Label('Variables')])
		] #type: List[ui.Component]

		variables = [] #type: List[ui.Component]
		for v in self.variables:
			variables.append(VariableComponent(v))
		items.append(ui.Table(items = variables))
		
		return [
			ui.HorizontalSpacer(250),
			ui.Panel(items = items)
		]
