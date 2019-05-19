from sublime_db.core.typecheck import (List, Callable, Optional)

import sublime

from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Variable,
)

from sublime_db.main.commands import AutoCompleteTextInputHandler

class VariableStateful:
	def __init__(self, variable: Variable, on_dirty: Callable[[], None]) -> None:
		self.variable = variable
		self.on_dirty = on_dirty

		self._expanded = False
		self.fetched = False
		self.loading = False
		self.variables = [] #type: List[VariableStateful]
		self.expandedCount = 0

	@property
	def name(self) -> str:
		return self.variable.name

	@property
	def value(self) -> str:
		return self.variable.value

	@property
	def expanded(self) -> bool:
		return self._expanded

	@property
	def expandable(self) -> bool:
		return self.variable.variablesReference != 0

	def toggle_expand(self) -> None:
		if self._expanded:
			self._expanded = False
			self.expandedCount = 0
		else:
			self._expanded = True
			self.expandedCount = 20
			self._fetch_if_needed()
		self.on_dirty()

	def expand(self) -> None:
		if not self._expanded:
			self.toggle_expand()

	def show_more(self) -> None:
		self.expandedCount += 20
		self.on_dirty()

	def number_expanded(self) -> int:
		return min(len(self.variables), self.expandedCount)

	def has_more(self) -> int:
		if self.expandedCount >= len(self.variables):
			return 0
		return len(self.variables) - self.expandedCount

	def collapse(self) -> None:
		if self._expanded:
			self.toggle_expand()

	@core.async
	def _set_value(self, value: str) -> core.awaitable[None]:
		try:
			variable = yield from self.variable.client.setVariable(self.variable, value)
			self.variable = variable
			if self.fetched:
				self._fetch_if_needed(True)
			self.on_dirty()

		except Exception as e:
			core.log_exception()
			core.display(e)

	def set_value(self, value: str) -> None:
		core.run(self._set_value(value))

	def _fetch_if_needed(self, force_refetch: bool = False) -> None:
		if (not self.fetched or force_refetch) and self.variable.variablesReference:
			self.loading = True
			core.run(self.variable.client.GetVariables(self.variable.variablesReference), self._on_fetched)

	def _on_fetched(self, variables: List[Variable]) -> None:
		self.fetched = True
		self.loading = False
		self.variables = []
		for variable in variables:
			self.variables.append(VariableStateful(variable, self.on_dirty))

		self.on_dirty()


class VariableStatefulComponent (ui.Block):
	def __init__(self, variable: VariableStateful, syntax_highlight=True, itemRight: Optional[ui.Inline] = None) -> None:
		super().__init__()
		self.syntax_highlight = syntax_highlight
		self.variable = variable
		self.itemRight = itemRight or ui.Inline()

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
					value_item,
				]),
				self.itemRight)
			]

		if self.variable.expanded:
			image = ui.Img(ui.Images.shared.open)
		else:
			image = ui.Img(ui.Images.shared.close)

		items = [
			ui.block(
				ui.Button(self.variable.toggle_expand, [
					image
				]),
				ui.ButtonDoubleClick(self.on_edit, None, [
					ui.Label(name, padding_right=1),
					value_item,
				]),
				self.itemRight
			)
		] #type: List[ui.Block]

		if self.variable.expanded:
			inner = [] #type: List[ui.Block]
			count = self.variable.number_expanded()
			syntax_highlight = count < 25
			for i in range(0, count):
				variable = self.variable.variables[i]
				inner.append(VariableStatefulComponent(variable, syntax_highlight))

			more_count = self.variable.has_more()
			if more_count:
				inner.append(
					ui.block(ui.Button(self.variable.show_more, [
						ui.Label("  {} more items...".format(more_count), color="secondary")
					]))
				)
			table = ui.Table(items=inner)
			table.add_class('inset')
			items.append(table)

		return items