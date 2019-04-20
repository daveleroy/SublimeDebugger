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

from sublime_db.main.commands import AutoCompleteTextInputHandler

class VariableComponent (ui.Block):
	def __init__(self, variable: Variable, syntax_highlight=True) -> None:
		super().__init__()
		self.syntax_highlight = syntax_highlight
		self.variable = VariableState(variable, self.dirty)

	def on_edit(self) -> None:
		label = "edit variable {}: {}".format(self.variable.name, self.variable.value)
		input = AutoCompleteTextInputHandler(label)
		def run(**args):
			self.variable.set_value(args['text'])
		ui.run_input_command(input, run)

	def render(self) -> ui.Block.Children:
		v = self.variable
		name = v.name
		value = v.value

		if self.syntax_highlight:
			value_item = ui.CodeBlock(value)
		else:
			value_item = ui.Label(value)

		if not self.variable.expandable:
			return [
				ui.block(ui.ButtonDoubleClick(self.on_edit, None, [
					ui.Label(name, padding_left=0.5, padding_right=1),
					value_item
				]))
			]

		if self.variable.expanded:
			image = ui.Img(ui.Images.shared.down)
		else:
			image = ui.Img(ui.Images.shared.right)

		items = [
			ui.block(
				ui.Button(self.variable.toggle_expand, [
					image
				]),
				ui.ButtonDoubleClick(self.on_edit, None, [
					ui.Label(name, padding_right=1),
					value_item,
				])
			)
		] #type: List[ui.Block]

		if self.variable.expanded:
			inner = [] #type: List[ui.Block]
			syntax_highlight = len(self.variable.variables) < 100
			for variable in self.variable.variables:
				inner.append(VariableComponent(variable, syntax_highlight))
			table = ui.Table(items=inner)
			table.add_class('inset')
			items.append(table)

		return items


class ScopeComponent (ui.Block):
	def __init__(self, scope: Scope) -> None:
		super().__init__()
		self.scope = ScopeState(scope, self.dirty)

	def render(self) -> ui.Block.Children:
		if self.scope.expanded:
			image = ui.Img(ui.Images.shared.down)
		else:
			image = ui.Img(ui.Images.shared.right)

		scope_item = ui.block(
			ui.Button(self.scope.toggle_expand, items=[
				image
			]),
			ui.Label(self.scope.name, padding_left=0.5, padding_right=1),
		)

		if self.scope.expanded:
			variables = [] #type: List[ui.Block]
			syntax_highlight = len(self.scope.variables) < 100
			for variable in self.scope.variables:
				variables.append(VariableComponent(variable, syntax_highlight))
			table = ui.Table(items=variables)
			table.add_class('inset')
			return [scope_item, table]

		return [scope_item]
