from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from ..import core
from ..import ui
from ..import dap

from . import css

import sublime

if TYPE_CHECKING:
	from ..debugger import Debugger

class VariableViewState:
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


class VariableView (ui.div):
	def __init__(self, debugger: Debugger, variable: dap.Variable, state = VariableViewState(), children_only = False) -> None:
		super().__init__()
		self.variable = variable
		self.debugger = debugger
		self.state = state
		self.children_only = children_only

		self.variable_children: Optional[list[dap.Variable]] = None
		self.error: Optional[core.Error] = None

		self.edit_variable_menu = None

		if self.state.is_expanded(self.variable):
			self.set_expanded()

	@core.run
	async def edit_variable(self) -> None:
		if not self.variable.containerVariablesReference:
			raise core.Error('Not able to set value of this item')

		containerVariablesReference = self.variable.containerVariablesReference
		session = self.variable.session
		info = None
		name = self.variable.name
		expression = self.variable.name
		value = self.variable.value or ''
		evaluateName = self.variable.evaluateName

		if session.capabilities.supportsDataBreakpoints:
			info = await session.data_breakpoint_info(containerVariablesReference, name)

		async def on_edit_variable_async(value: str):
			try:
				response = await session.set_variable(containerVariablesReference, name, value)
				self.variable.value = response.value
				self.variable.variablesReference = response.variablesReference
				self.variable.fetched = None
				self.dirty()
			except core.Error as e:
				core.exception()
				core.display(e)

		def on_edit_variable(value: str):
			core.run(on_edit_variable_async(value))

		@core.run
		async def copy_value():
			session = self.variable.session
			if evaluateName:
				try:
					# Attempt to match vscode behavior
					# If the adapter supports clipboard use it otherwise send the none standard 'variables' context
					context = 'clipboard' if session.capabilities.supportsClipboardContext else 'variables'
					v = await self.variable.session.evaluate_expression(evaluateName, context)
					sublime.set_clipboard(v.result)
					return

				except dap.Error as e:
					core.exception()

			sublime.set_clipboard(value)

		def copy_expr():
			sublime.set_clipboard(expression)

		def add_watch():
			session.watch.add(expression)

		items = [
			ui.InputListItem(
				ui.InputText(
					on_edit_variable,
					'editing a variable',
				),
				'Edit Variable',
			),
			ui.InputListItem(
				copy_expr,
				'Copy Expression',
			),
			ui.InputListItem(
				copy_value,
				'Copy Value\t Click again to select',
			),
			ui.InputListItem(
				add_watch,
				'Add Variable To Watch',
			),
		]

		if self.edit_variable_menu:
			copy_value()
			self.edit_variable_menu.cancel()
			return

		if info and info.dataId:
			types = info.accessTypes or ['']
			labels = {
				'write': 'Break On Value Write',
				'readWrite': 'Break On Value Read or Write',
				'read': 'Break On Value Read',
			}

			def on_add_data_breakpoint(accessType: str):
				session.breakpoints.data.add(info, accessType) #type: ignore

			for acessType in types:
				items.append(ui.InputListItem(
					lambda: on_add_data_breakpoint(acessType),
					labels.get(acessType) or 'Break On Value Change'
				))
		self.edit_variable_menu = core.run(ui.InputList(f'{name} {value}')[
			items
		])
		await self.edit_variable_menu
		self.edit_variable_menu = None

	@core.run
	async def set_expanded(self) -> None:
		self.state.set_expanded(self.variable, True)
		self.error = None

		# Give this a little time to load before marking it as dirty to avoid showing loading indicator in most cases
		timer = core.timer(self.dirty, 0.2)

		try:
			self.variable_children = await self.variable.children()
		except core.Error as error:
			self.error = error

		timer.dispose()
		self.dirty()

	@core.run
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


	def render_header(self, name: str, value: str, is_expandable:bool, is_expanded: bool):
		if name:
			value_item = [
				ui.text(name, css=css.secondary, on_click=self.edit_variable),
				ui.spacer(1),
				ui.code(value),
			]
		else:
			value_item = ui.span(on_click=self.edit_variable)[
				ui.code(value),
			]

		if is_expandable:
			return ui.div(height=css.row_height)[
				ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close, on_click=self.toggle_expand),
				value_item,
			]
		else:
			return ui.div(height=css.row_height)[
				ui.spacer(3),
				value_item,
			]

	def render_children(self):
		if self.error:
			return ui.div(height=css.row_height)[
				ui.text(str(self.error), css=css.redish_secondary)
			]

		if self.variable_children is None:
			return ui.div(height=css.row_height)[
				ui.spacer(3),
				ui.text('…', css=css.secondary)
			]

		if not self.variable_children:
			return ui.div(height=css.row_height)[
				ui.spacer(3),
				ui.text('zero items …', css=css.secondary)
			]

		children: list[ui.div] = []

		count = self.state.number_expanded(self.variable)
		for variable in self.variable_children[:count]:
			children.append(VariableView(self.debugger, variable, state=self.state))

		more_count = len(self.variable_children) - count
		if more_count > 0:
			children.append(
				ui.div(height=css.row_height)[
					ui.spacer(3),
					ui.text('{} more items …'.format(more_count), css=css.secondary, on_click=self.show_more)
				]
			)

		return children

	def render(self):
		name =  self.variable.name
		value = self.variable.value or ''

		is_expandable = self.variable.has_children
		is_expanded = self.state.is_expanded(self.variable)

		header = self.render_header(name, value, is_expandable, is_expanded)

		if not is_expandable or not is_expanded:
			return header

		if self.children_only:
			return self.render_children()

		return [
			header,
			ui.div(css=css.table_inset)[
				self.render_children()
			]
		]
