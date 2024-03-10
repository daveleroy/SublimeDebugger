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
	async def copy_value(self):
		value = self.variable.value or ''
		session = self.variable.session
		evaluateName = self.variable.evaluateName

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

	def copy_expr(self):
		expression = self.variable.name
		sublime.set_clipboard(expression)

	def add_watch(self):
		expression = self.variable.name
		self.variable.session.watch.add(expression)

	@core.run
	async def on_edit_variable(self, value: str):
		try:
			if not self.variable.containerVariablesReference:
				raise core.Error('Not able to set value of this item')

			session = self.variable.session
			containerVariablesReference = self.variable.containerVariablesReference
			name = self.variable.name

			response = await session.set_variable(containerVariablesReference, name, value)
			self.variable.value = response.value
			self.variable.variablesReference = response.variablesReference
			self.variable.fetched = None
			self.dirty()
		except core.Error as e:
			core.exception()
			core.display(e)

	@core.run
	async def edit_variable(self) -> None:
		if not self.variable.containerVariablesReference:
			raise core.Error('Not able to set value of this item')

		containerVariablesReference = self.variable.containerVariablesReference
		session = self.variable.session
		info = None
		name = self.variable.name
		value = self.variable.value or ''

		if session.capabilities.supportsDataBreakpoints:
			info = await session.data_breakpoint_info(containerVariablesReference, name)

		items = [
			ui.InputListItem(
				ui.InputText(
					self.on_edit_variable,
					'editing a variable',
				),
				'Set Value',
			),
			ui.InputListItem(
				self.copy_value,
				'Copy Value\t Click again to select',
			),
			ui.InputListItem(
				self.copy_expr,
				'Copy as Expression',
			),
			ui.InputListItem(
				self.add_watch,
				'Add To Watch',
			),
		]

		if self.edit_variable_menu:
			self.copy_value()
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
		with ui.div(height=css.row_height):
			if is_expandable:
				ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close, on_click=self.toggle_expand)
			else:
				ui.spacer(3)

			if name:
				ui.text(name, css=css.secondary, on_click=self.edit_variable)
				ui.spacer(1)
				ui.code(value, on_click=self.edit_variable)

			else:
				ui.code(value, on_click=self.edit_variable)

	def render_children(self):
		if self.error:
			with ui.div(height=css.row_height):
				ui.text(str(self.error), css=css.redish_secondary)

			return

		if self.variable_children is None:
			with ui.div(height=css.row_height):
				ui.spacer(3)
				ui.text('…', css=css.secondary)

			return


		if not self.variable_children:
			with ui.div(height=css.row_height):
				ui.spacer(3)
				ui.text('zero items …', css=css.secondary)

			return


		count = self.state.number_expanded(self.variable)
		for variable in self.variable_children[:count]:
			VariableView(self.debugger, variable, state=self.state)

		more_count = len(self.variable_children) - count
		if more_count > 0:
			with ui.div(height=css.row_height):
				ui.spacer(3)
				ui.text('{} more items …'.format(more_count), css=css.secondary, on_click=self.show_more)


	def render(self):
		name =  self.variable.name
		value = self.variable.value or ''

		is_expandable = self.variable.has_children
		is_expanded = self.state.is_expanded(self.variable)

		self.render_header(name, value, is_expandable, is_expanded)

		if not is_expandable or not is_expanded:
			return

		if self.children_only:
			self.render_children()
			return

		with ui.div(css=css.table_inset):
			self.render_children()
