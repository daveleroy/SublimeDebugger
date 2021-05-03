from __future__ import annotations
from ..typecheck import *

from ..import core
from ..import ui
from ..import dap

from . import css

import sublime

class VariableComponentState:
	def __init__(self):
		self._expanded: dict[int, bool] = {}
		self._number_expanded: dict[int, int] = {}

	def is_expanded(self, variable: dap.Variable) -> bool:
		return self._expanded.get(id(variable), False)

	def set_expanded(self, variable: dap.Variable, value: bool):
		self._expanded[id(variable)] = value

	def number_expanded(self, variable: dap.Variable) -> int:
		return self._number_expanded.get(id(variable), 20)

	def set_number_expanded(self, variable: dap.Variable, value: int):
		self._number_expanded[id(variable)] = value


class VariableComponent (ui.div):
	def __init__(self, variable: dap.Variable, source: Optional[dap.SourceLocation] = None, on_clicked_source: Optional[Callable[[dap.SourceLocation], None]] = None, state: VariableComponentState = VariableComponentState()) -> None:
		super().__init__()
		self.variable = variable
		self.state = state
		self.item_right = ui.span()
		
		self.variable_children: Optional[list[dap.Variable]] = None
		self.error: Optional[core.Error] = None

		self.edit_variable_menu = None
		self.on_clicked_source = on_clicked_source
		self.source = source

		if self.state.is_expanded(self.variable):
			self.set_expanded()

	@core.schedule
	async def edit_variable(self) -> None:
		if not isinstance(self.variable.reference, dap.types.Variable):
			raise core.Error("Not able to set value of this item")

		variable = self.variable.reference
		session = self.variable.session
		info = None
		expression = variable.evaluateName or variable.name
		value = variable.value or ""

		if session.capabilities.supportsDataBreakpoints:
			info = await session.data_breakpoint_info(variable)

		async def on_edit_variable_async(value: str):
			try:
				self.variable.reference = await session.set_variable(variable, value)
				self.variable.fetched = None
				self.dirty()
			except core.Error as e:
				core.log_exception()
				core.display(e)

		def on_edit_variable(value: str):
			core.run(on_edit_variable_async(value))

		@core.schedule
		async def copy_value():
			session = self.variable.session
			if variable.evaluateName:
				try:
					# Attempt to match vscode behavior 
					# If the adapter supports clipboard use it otherwise send the none standard 'variables' context
					context = 'clipboard' if session.capabilities.supportsClipboardContext else 'variables'
					v = await self.variable.session.evaluate_expression(variable.evaluateName, context)
					sublime.set_clipboard(v.result)
					return

				except dap.Error as e:
					core.log_exception()

			sublime.set_clipboard(value)

		def copy_expr():
			sublime.set_clipboard(expression)

		def add_watch():
			session.watch.add(expression)

		items = [
			ui.InputListItem(
				ui.InputText(
					on_edit_variable,
					"editing a variable",
				),
				"Edit Variable",
			),
			ui.InputListItem(
				copy_expr,
				"Copy Expression",
			),
			ui.InputListItem(
				copy_value,
				"Copy Value\t Click again to select",
			),
			ui.InputListItem(
				add_watch,
				"Add Variable To Watch",
			),
		]

		if self.edit_variable_menu:
			copy_value()
			self.edit_variable_menu.cancel()
			return

		if info and info.id:
			types = info.accessTypes or [""]
			labels = {
				dap.DataBreakpoint.write: "Break On Value Write",
				dap.DataBreakpoint.readWrite: "Break On Value Read or Write",
				dap.DataBreakpoint.read: "Break On Value Read",
			}

			def on_add_data_breakpoint(accessType: str):
				assert info
				session.breakpoints.data.add(info, accessType or None)

			for acessType in types:
				items.append(ui.InputListItem(
					lambda: on_add_data_breakpoint(acessType),
					labels.get(acessType) or "Break On Value Change"
				))
		self.edit_variable_menu = ui.InputList(items, '{} {}'.format(variable.name, variable.value)).run()
		await self.edit_variable_menu
		self.edit_variable_menu = None

	@core.schedule
	async def set_expanded(self) -> None:
		self.state.set_expanded(self.variable, True)
		self.error = None
		self.dirty()
		
		try:
			self.variable_children = await self.variable.children()
		except core.Error as error:
			self.error = error

		self.dirty()

	@core.schedule
	async def toggle_expand(self) -> None:
		is_expanded = self.state.is_expanded(self.variable)
		if is_expanded:
			self.state.set_expanded(self.variable, False)
			self.dirty()
		else:
			await self.set_expanded()

	def show_more(self) -> None:
		count = self.state.number_expanded(self.variable)
		self.state.set_number_expanded(self.variable, count + 20)
		self.dirty()

	def render(self) -> ui.div.Children:
		name =  self.variable.name
		value = self.variable.value
		is_expanded = self.state.is_expanded(self.variable)
		source = self.source.name if self.source else None

		if name:
			value_item = ui.click(self.edit_variable)[
				ui.text(name, css=css.label_secondary),
				ui.spacer(1),
				ui.code(value),
			]
		else:
			value_item = ui.click(self.edit_variable)[
				ui.code(value),
			]

		if source:
			self.item_right = ui.click(lambda: self.on_clicked_source(self.source))[
				ui.spacer(min=1),
				ui.text(source, css=css.label_secondary)
			]

		if not self.variable.has_children:
			return [
				ui.div(height=css.row_height)[
					ui.align()[
						ui.spacer(3),
						value_item,
						self.item_right,
					],
				],
			]


		variable_label = ui.div(height=css.row_height)[
			ui.align()[
				ui.click(self.toggle_expand)[
					ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close)
				],
				value_item,
				self.item_right,
			]
		]

		if not is_expanded:
			return [
				variable_label
			]

		variable_children: list[ui.div] = []
		
		if self.error:
			variable_children.append(
				ui.div(height=css.row_height)[
					ui.text(str(self.error), css=css.label_redish_secondary)
				]
			)
		elif self.variable_children is None:
			variable_children.append(
				ui.div(height=css.row_height)[
					ui.text('◌', css=css.label_secondary)
				]
			)
		else:
			count = self.state.number_expanded(self.variable)
			for variable in self.variable_children[:count]:
				variable_children.append(VariableComponent(variable, state=self.state))

			more_count = len(self.variable_children) - count
			if more_count > 0:
				variable_children.append(
					ui.div(height=css.row_height)[
						ui.click(self.show_more)[
							ui.text("  {} more items...".format(more_count), css=css.label_secondary)
						]
					]
				)

		return [
			variable_label,
			ui.div(css=css.table_inset)[
				variable_children
			]
		]
