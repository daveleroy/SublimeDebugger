from sublime_db.core.typecheck import (List, Callable, Optional)

import sublime

from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Variable, 
	VariableState,
	Scope, 
	ScopeState
)

class VariableComponent (ui.Component):
	def __init__(self, variable: Variable) -> None:
		super().__init__()
		self.variable = VariableState(variable, self.dirty)

	def on_edit(self) -> None:
		def on_done(value: Optional[str]) -> None:
			if not value is None:
				self.variable.set_value(value)
		def on_change(value: str) -> None:
			pass	

		window = sublime.active_window()
		title = self.variable.name
		value = self.variable.value

		input_handler = ui.create_input_handler_for_window(window, title, value, on_done = on_done, on_change = on_change)

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

		if not self.variable.expandable:
			return [
				ui.ButtonDoubleClick(self.on_edit, None, [
					ui.Label(name, padding_left = 0.5, padding_right = 1),
					ui.Label(value, color = 'secondary')
				])
			]

		if self.variable.expanded:
			image = ui.Img(ui.Images.shared.down)
		else:
			image = ui.Img(ui.Images.shared.right)

		items = [
			ui.Button(self.variable.toggle_expand, items = [
				image
			]),
			ui.ButtonDoubleClick(self.on_edit, None, [
				ui.Label(name, padding_right = 1),
				ui.Label(value, color = 'secondary'),
			])
		] #type: List[ui.Component]

		if self.variable.expanded:
			inner = [] #type: List[ui.Component]
			for variable in self.variable.variables:
				inner.append(VariableComponent(variable))
			table = ui.Table(items = inner)
			table.add_class('inset')
			items.append(table)

		return items

class ScopeComponent (ui.Component):
	def __init__(self, scope: Scope) -> None:
		super().__init__()
		self.scope = ScopeState(scope, self.dirty)

	def render (self) -> ui.components:
		if self.scope.expanded:
			image = ui.Img(ui.Images.shared.down)
		else:
			image = ui.Img(ui.Images.shared.right)

		items = [
			ui.Button(self.scope.toggle_expand, items = [
				image
			]),
			ui.Label(self.scope.name, padding_left = 0.5, padding_right = 1),
		] #type: List[ui.Component]

		if self.scope.expanded:
			variables = [] #type: List[ui.Component]
			for variable in self.scope.variables:
				variables.append(VariableComponent(variable))
			table = ui.Table(items = variables)
			table.add_class('inset')
			items.append(table)

		return items

